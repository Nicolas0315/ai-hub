#!/usr/bin/env python3
"""
KS40b-lite Write Gate — verify claims before writing to memory/knowledge.

Usage:
    python write_gate.py "text to verify"
    python write_gate.py --file path/to/file.md
    echo "text" | python write_gate.py --stdin

Returns JSON with:
  - approved: bool (safe to write)
  - claims: list of extracted claims with verification results
  - needs_llm: list of claims that need LLM review
"""

import argparse
import json
import re
import sys
import os

# Add venv site-packages
venv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.venv', 'lib')
for d in os.listdir(venv_path) if os.path.isdir(venv_path) else []:
    sp = os.path.join(venv_path, d, 'site-packages')
    if os.path.isdir(sp) and sp not in sys.path:
        sys.path.insert(0, sp)

from ks40b_lite import KS40bLite


def extract_claims(text: str) -> list[str]:
    """Split text into individual claims (sentences)."""
    # Split on Japanese/English sentence boundaries
    sentences = re.split(r'[。．.！!？?\n]+', text)
    claims = []
    for s in sentences:
        s = s.strip()
        if len(s) > 5:  # Skip very short fragments
            claims.append(s)
    return claims


def verify_text(text: str, evidence: list[str] | None = None) -> dict:
    """Run KS40b-lite verification on text."""
    ks = KS40bLite()
    claims = extract_claims(text)

    results = []
    needs_llm = []
    all_approved = True

    for claim in claims:
        r = ks.verify(claim, evidence, None)
        entry = {
            "claim": claim[:100],
            "pass_rate": round(r.pass_rate, 3),
            "coherence": round(r.coherence_score, 3),
            "layer": r.detected_layer,
            "needs_llm": r.needs_llm_review,
            "solvers": f"{r.solvers_passed}/{r.total_solvers}",
        }
        results.append(entry)

        if r.needs_llm_review:
            needs_llm.append(claim[:100])
        if r.pass_rate < 0.5:
            all_approved = False

    return {
        "approved": all_approved,
        "total_claims": len(claims),
        "failed_claims": sum(1 for r in results if r["pass_rate"] < 0.5),
        "needs_llm_count": len(needs_llm),
        "needs_llm": needs_llm,
        "claims": results,
    }


def main():
    parser = argparse.ArgumentParser(description="KS40b-lite Write Gate")
    parser.add_argument("text", nargs="?", help="Text to verify")
    parser.add_argument("--file", help="Read text from file")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--evidence", nargs="*", help="Evidence strings")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            text = f.read()
    elif args.stdin:
        text = sys.stdin.read()
    elif args.text:
        text = args.text
    else:
        parser.error("Provide text, --file, or --stdin")

    result = verify_text(text, args.evidence)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["approved"] else 1)


if __name__ == "__main__":
    main()
