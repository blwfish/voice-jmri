# voice-jmri

Restricted-vocabulary voice control for JMRI. Speaks a small fixed grammar
(throw/close turnouts, select routes) derived from a JMRI panel XML file,
runs offline via [Vosk](https://alphacephei.com/vosk/), and dispatches each
recognized command to a handler (currently just `print` — swap for real JMRI
calls later).

## Pieces

- **`jmri_extract.py`** — parses a JMRI panel XML, emits `vocab.json`
  with turnouts and routes plus a speakable token list for each name.
  Handles hyphenated names, spells out short ALL-CAPS abbreviations
  (e.g. `VAL` → `V A L`), and converts trailing digits to number words.
- **`lexicon_check.py`** — checks every vocab token against the Vosk
  model's lexicon, resolves hand-maintained aliases (see below), and
  flags anything still out-of-vocabulary.
- **`voice_daemon.py`** — builds the Vosk grammar from `vocab.json` +
  `aliases.json`, listens on the default mic, dispatches each final
  recognition to a handler.

## OOV handling (aliases)

Vosk's small model ships a pre-compiled HCLG graph and cannot emit words
outside its lexicon at runtime. For a Vocabulary like "Gordonsville" — a
proper noun no general-English model knows — the workaround is to map it
to a sequence of in-lexicon words that sound close. Example `aliases.json`:

```json
{
  "gordonsville": ["gordon", "ville"],
  "louisa":       ["louise"]
}
```

`lexicon_check.py` writes stub entries for any unresolved token so you
just fill in replacements and re-run.

Future options if the alias layer gets tedious:

- Swap to the larger [`vosk-model-en-us-0.22`](https://alphacephei.com/vosk/models)
  (~1.8 GB) which covers far more proper nouns.
- Drop the grammar constraint and fuzzy-match Vosk's free-form output
  against the phrase set.

## Usage

```
pip install -r requirements.txt

# one-time: download the Vosk model
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip && mv vosk-model-small-en-us-0.15 model

# whenever the JMRI panel file changes:
python3 jmri_extract.py /path/to/panel.xml
python3 lexicon_check.py        # edit aliases.json if it reports OOVs

# run the daemon:
python3 voice_daemon.py --verbose
```

`voice_daemon.py --list-devices` shows available input devices; pass
`--device <index-or-substring>` to pick one.

## Grammar shape

For each turnout, two phrases are generated: `throw <tokens>` and
`close <tokens>`. For each route: `select <tokens>`. So 23 turnouts +
5 routes in the sample JMRI file gives ~51 grammar phrases — small
enough that Vosk is very accurate on them.

## Status

Sketch-quality. Actions are `print` statements. Audio comes from the
default microphone but `sounddevice.RawInputStream` can be pointed at
any PCM source in production.
