"""Voice-controlled JMRI command daemon.

Reads vocab.json (from jmri_extract.py) and aliases.json, builds a Vosk
grammar covering `throw <turnout>`, `close <turnout>`, `select <route>`,
listens on the default microphone, and dispatches each final recognition
to a handler. Actions currently just print; swap in real JMRI calls later.
"""

import argparse
import json
import os
import queue
import sys
from pathlib import Path

import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel

VERBS_TURNOUT = ("throw", "close")
VERBS_ROUTE = ("select",)
SAMPLE_RATE = 16000


def substitute(tokens: list[str], aliases: dict) -> list[str]:
    out = []
    for t in tokens:
        sub = aliases.get(t) or aliases.get(t.lower())
        out.extend(sub if sub else [t])
    return out


def build_grammar(vocab: dict, aliases: dict) -> tuple[list[str], dict]:
    """Return (grammar phrases, reverse-lookup map phrase -> (verb, item))."""
    phrases: list[str] = []
    lookup: dict[str, tuple[str, dict]] = {}

    for t in vocab["turnouts"]:
        spoken = " ".join(substitute(t["tokens"], aliases)).lower()
        for verb in VERBS_TURNOUT:
            phrase = f"{verb} {spoken}"
            phrases.append(phrase)
            lookup[phrase] = (verb, t)

    for r in vocab["routes"]:
        spoken = " ".join(substitute(r["tokens"], aliases)).lower()
        for verb in VERBS_ROUTE:
            phrase = f"{verb} {spoken}"
            phrases.append(phrase)
            lookup[phrase] = (verb, r)

    return phrases, lookup


def dispatch(verb: str, item: dict) -> None:
    kind = "turnout" if "system_name" in item and verb in VERBS_TURNOUT else "route"
    print(f"[ACTION] {verb} {kind} "
          f"user={item['user_name']!r} system={item.get('system_name')!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vocab", type=Path, default=Path("vocab.json"))
    parser.add_argument("--aliases", type=Path, default=Path("aliases.json"))
    parser.add_argument("--model", type=Path,
                        default=Path(os.environ.get("VOSK_MODEL", "./model")))
    parser.add_argument("--device", default=None,
                        help="input device index or substring (see --list-devices)")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    vocab = json.loads(args.vocab.read_text())
    aliases = json.loads(args.aliases.read_text()) if args.aliases.exists() else {}
    phrases, lookup = build_grammar(vocab, aliases)

    if args.verbose:
        print(f"{len(phrases)} grammar phrases:")
        for p in phrases:
            print(f"  {p}")

    SetLogLevel(-1)
    model = Model(str(args.model))
    # Grammar as JSON list; "[unk]" lets the recognizer reject non-matches.
    grammar = json.dumps(phrases + ["[unk]"])
    rec = KaldiRecognizer(model, SAMPLE_RATE, grammar)

    audio_q: queue.Queue = queue.Queue()

    def cb(indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        audio_q.put(bytes(indata))

    device = args.device
    if device is not None and not device.isdigit():
        # allow substring match
        for idx, d in enumerate(sd.query_devices()):
            if device.lower() in d["name"].lower() and d["max_input_channels"] > 0:
                device = idx
                break
    elif device is not None:
        device = int(device)

    print(f"listening on {sd.query_devices(device, 'input')['name']!r}; Ctrl-C to quit")

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype="int16",
                           channels=1, device=device, callback=cb):
        try:
            while True:
                data = audio_q.get()
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip()
                    if not text or text == "[unk]":
                        continue
                    match = lookup.get(text)
                    if match:
                        dispatch(*match)
                    else:
                        print(f"[heard] {text!r} (no match)")
                elif args.verbose:
                    partial = json.loads(rec.PartialResult()).get("partial", "")
                    if partial:
                        print(f"  ...{partial}", end="\r", file=sys.stderr)
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
