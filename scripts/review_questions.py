"""Write docs/QUESTIONS.md, every intake question beside its clause.

    uv run python scripts/review_questions.py
    uv run python scripts/review_questions.py --check

The clause text comes from the local clause files, so run
scripts/load_legislation.py first. --check writes nothing and exits non-zero
when the document is out of date with the catalogue.
"""

import argparse
import sys
from pathlib import Path

from reguide import legislation
from reguide.questions import review_markdown

OUT = Path(__file__).resolve().parent.parent / "docs" / "QUESTIONS.md"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if docs/QUESTIONS.md is out of date")
    args = parser.parse_args(argv)
    try:
        clauses = legislation.load()
    except legislation.CorpusMissing:
        print("No clause files. Run scripts/load_legislation.py first.", file=sys.stderr)
        return 2
    text = review_markdown(clauses)
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{OUT} is out of date. Run scripts/review_questions.py.", file=sys.stderr)
            return 1
        print(f"{OUT} is up to date.")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT} ({len(text.splitlines())} lines, "
          f"{text.count('### ')} questions).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
