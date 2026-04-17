"""Extract speakable turnout + route vocabulary from a JMRI panel XML file."""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

NUMBER_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
    "10": "ten", "11": "eleven", "12": "twelve", "13": "thirteen",
    "14": "fourteen", "15": "fifteen", "16": "sixteen", "17": "seventeen",
    "18": "eighteen", "19": "nineteen", "20": "twenty",
}


def tokenize(name: str) -> list[str]:
    """Split a JMRI user-name into speakable tokens.

    Rules:
      - split on '-', whitespace, and underscore
      - ALL-CAPS segments up to 5 letters become spelled-out letters (VAL -> V A L)
      - pure digits become number words (3 -> three)
      - everything else is lowercased
    """
    tokens: list[str] = []
    for segment in re.split(r"[-\s_]+", name.strip()):
        if not segment:
            continue
        if segment.isdigit():
            tokens.append(NUMBER_WORDS.get(segment, segment))
        elif segment.isalpha() and segment.isupper() and len(segment) <= 5:
            tokens.extend(list(segment))
        else:
            tokens.append(segment.lower())
    return tokens


def extract(xml_path: Path) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    turnouts = []
    for turnouts_block in root.iter("turnouts"):
        for t in turnouts_block.findall("turnout"):
            user = t.findtext("userName")
            system = t.findtext("systemName")
            if user:
                turnouts.append({
                    "user_name": user,
                    "system_name": system,
                    "tokens": tokenize(user),
                })

    routes = []
    for routes_block in root.iter("routes"):
        for r in routes_block.findall("route"):
            user = r.get("userName") or r.findtext("userName")
            system = r.findtext("systemName")
            if user:
                routes.append({
                    "user_name": user,
                    "system_name": system,
                    "tokens": tokenize(user),
                })

    return {"turnouts": turnouts, "routes": routes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml", type=Path, help="path to JMRI panel XML")
    parser.add_argument(
        "-o", "--out", type=Path, default=Path("vocab.json"),
        help="output JSON path (default: vocab.json)",
    )
    args = parser.parse_args()

    vocab = extract(args.xml)
    args.out.write_text(json.dumps(vocab, indent=2))

    unique_tokens = sorted({tok for kind in ("turnouts", "routes")
                            for item in vocab[kind] for tok in item["tokens"]})
    print(f"wrote {args.out}: "
          f"{len(vocab['turnouts'])} turnouts, {len(vocab['routes'])} routes, "
          f"{len(unique_tokens)} unique tokens")
    print("tokens:", " ".join(unique_tokens))


if __name__ == "__main__":
    main()
