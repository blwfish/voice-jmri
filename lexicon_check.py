"""Check vocab.json tokens against the Vosk model lexicon; flag OOV words.

Uses `Model.find_word()` which returns -1 for words not in the lexicon.
(The small Vosk model doesn't ship a readable words.txt, so the C-API
lookup is the only reliable check.)

Vosk's pre-compiled HCLG graph can only emit words already in its lexicon —
custom pronunciations require rebuilding the graph, which is out of scope
here. So for OOV tokens the workflow is: edit aliases.json to map each
OOV word to a sequence of in-lexicon tokens that *sound* close enough.
The daemon applies those substitutions when building its grammar.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from vosk import Model, SetLogLevel


def collect_tokens(vocab: dict) -> set[str]:
    return {tok for kind in ("turnouts", "routes")
            for item in vocab[kind] for tok in item["tokens"]}


def in_lexicon(model: Model, token: str) -> bool:
    return model.find_word(token.lower()) != -1


def resolve(tok: str, aliases: dict, model: Model) -> list[str] | None:
    if in_lexicon(model, tok):
        return [tok]
    sub = aliases.get(tok) or aliases.get(tok.lower())
    if not sub:
        return None
    if all(in_lexicon(model, s) for s in sub):
        return sub
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vocab", type=Path, default=Path("vocab.json"))
    parser.add_argument("--aliases", type=Path, default=Path("aliases.json"))
    parser.add_argument("--model", type=Path,
                        default=Path(os.environ.get("VOSK_MODEL", "./model")))
    args = parser.parse_args()

    SetLogLevel(-1)
    vocab = json.loads(args.vocab.read_text())
    aliases = json.loads(args.aliases.read_text()) if args.aliases.exists() else {}
    model = Model(str(args.model))

    # Sanity-check the API: if a common word comes back missing, find_word isn't
    # working against this model and the rest of the report would be meaningless.
    if model.find_word("hello") == -1:
        print("ERROR: Model.find_word('hello') returned -1. The API is not "
              "functioning against this model; cannot perform lexicon check.",
              file=sys.stderr)
        raise SystemExit(2)

    tokens = sorted(collect_tokens(vocab))
    in_lex, resolved, oov = [], [], []
    for tok in tokens:
        r = resolve(tok, aliases, model)
        if r == [tok]:
            in_lex.append(tok)
        elif r is not None:
            resolved.append((tok, r))
        else:
            oov.append(tok)

    print(f"model:   {args.model}")
    print(f"vocab:   {len(tokens)} unique tokens")
    print(f"  in-lexicon:  {len(in_lex)}")
    print(f"  via alias:   {len(resolved)}")
    print(f"  unresolved:  {len(oov)}")
    if resolved:
        print("\naliased:")
        for tok, sub in resolved:
            print(f"  {tok!r} -> {' '.join(sub)}")
    if oov:
        print("\nUNRESOLVED (add entries to aliases.json):")
        for tok in oov:
            print(f"  {tok!r}")
        stub = {**aliases, **{tok: [] for tok in oov if tok not in aliases}}
        args.aliases.write_text(json.dumps(stub, indent=2, sort_keys=True))
        print(f"\nwrote stub entries to {args.aliases}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
