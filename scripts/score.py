"""Score the classification engine against the fixtures.

Run:  uv run python scripts/score.py
      uv run python scripts/score.py --all

Prints agreement as a fraction of fixtures and of functions, then a markdown
table of every miss, worst kind first. Verified fixtures only unless --all.
Exits non-zero if any verified fixture gets a confidently wrong class.
"""

import argparse

from reguide.scoring import WRONG_CLASS, report, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the engine against the fixtures.")
    parser.add_argument("--all", action="store_true", help="include unverified fixtures")
    args = parser.parse_args(argv)

    score = run(include_unverified=args.all)
    print(report(score), end="")
    verified_wrong = [r for r in score.misses if r.verdict == WRONG_CLASS]
    return 1 if verified_wrong and not args.all else 0


if __name__ == "__main__":
    raise SystemExit(main())
