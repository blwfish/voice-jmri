"""Check vocab.json tokens against a Vosk model lexicon; flag OOV words.

Vosk's pre-compiled HCLG graph can only emit words already in its lexicon —
custom pronunciations require rebuilding the graph, which is out of scope here.
So for OOV tokens the workflow is: edit aliases.json to map each OOV word to
a sequence of in-lexicon tokens that *sound* close enough. The daemon applies
those substitutions when building its grammar.
"""

import argparse
import json
import os
from pathlib import Path


def load_lexicon(model_dir: Path) -> set[str]:
    candidates = list(model_dir.rglob("words.txt"))
    if not candidates:
        raise FileNotFoundError(f"no words.txt under {model_dir}")
    lex: set[str] = set()
    for line in candidates[0].read_text().splitlines():
        if not line:
            continue
        word = line.split()[0]
        if word.startswith(("<", "#", "!", "[")):
            continue
        lex.add(word.lower())
    return lex


def collect_tokens(vocab: dict) -> set[str]:
    return {tok for kind in ("turnouts", "routes")
            for item in vocab[kind] for tok in item["tokens"]}


def resolve(tok: str, aliases: dict, lex: set[str]) -> list[str] | None:
    """Return the in-lexicon token sequence for tok, or None if unresolved."""
    if tok.lower() in lex:
        return [tok]
    sub = aliases.get(tok) or aliases.get(tok.lower())
    if not sub:
        return None
    if all(s.lower() in lex for s in sub):
        return sub
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vocab", type=Path, default=Path("vocab.json"))
    parser.add_argument("--aliases", type=Path, default=Path("aliases.json"))
    parser.add_argument("--model", type=Path,
                        default=Path(os.environ.get("VOSK_MODEL", "./model")),
                        help="Vosk model dir (env VOSK_MODEL or ./model)")
    args = parser.parse_args()

    vocab = json.loads(args.vocab.read_text())
    lex = load_lexicon(args.model)
    aliases = json.loads(args.aliases.read_text()) if args.aliases.exists() else {}

    tokens = sorted(collect_tokens(vocab))
    in_lex, resolved, oov = [], [], []
    for tok in tokens:
        r = resolve(tok, aliases, lex)
        if r == [tok]:
            in_lex.append(tok)
        elif r is not None:
            resolved.append((tok, r))
        else:
            oov.append(tok)

    print(f"lexicon: {len(lex)} words loaded from {args.model}")
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
