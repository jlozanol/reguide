"""Count the screens the interview takes, answering from the fixtures.

No model call. Two starts:

- blank: the fixture's number of functions and nothing else, the worst case;
- extracted: each intake case's recorded extraction, closer to a real
  interview.

    uv run python scripts/count_questions.py
    uv run python scripts/count_questions.py --only imaging
    uv run python scripts/count_questions.py --details

Each run ends by scoring the finished profile. "ok" means it reaches the
fixture's verdict; otherwise the per-function verdicts are shown. From an
extraction, a field the fixture leaves unanswered is answered "not sure", so
a reviewed extraction that adds questions can end without a result.
Exits non-zero when a blank run does not reach the fixture's verdict.
"""

import argparse
import statistics
import sys

from reguide import status as S
from reguide.interview_oracle import run_blank, run_extracted
from reguide.scoring import EXCLUSIONS

TYPICAL, COMPLEX = 20, 35


def _table(title: str, runs, details: bool) -> None:
    print(f"{title}")
    print(f"  {'run':50} {'screens':>7} {'unsure':>6}  result")
    for run in sorted(runs, key=lambda r: (r.questions, r.start, r.slug)):
        name = run.slug if run.start == "blank" else run.start
        result = "ok" if run.agrees else ", ".join(run.verdicts)
        print(f"  {name:50} {run.questions:7} {len(run.unsure):6}  {result}")
        if details:
            for dotted in run.asked:
                mark = " (not sure)" if dotted in run.unsure else ""
                print(f"      {dotted}{mark}")
    counts = [r.questions for r in runs]
    if counts:
        print(f"  median {statistics.median(counts)}, max {max(counts)}, "
              f"under {TYPICAL}: {sum(c < TYPICAL for c in counts)} of {len(counts)}, "
              f"under {COMPLEX}: {sum(c < COMPLEX for c in counts)} of {len(counts)}")
    print()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", metavar="TEXT", help="only runs whose name contains TEXT")
    parser.add_argument("--details", action="store_true", help="list every field asked")
    args = parser.parse_args(argv)
    if S.load_exclusions(EXCLUSIONS) == 0:
        print(f"exclusion table is empty: {EXCLUSIONS}", file=sys.stderr)
        return 2

    def keep(run) -> bool:
        return not args.only or args.only in run.slug or args.only in run.start

    blank = [r for r in run_blank() if keep(r)]
    extracted = [r for r in run_extracted() if keep(r)]
    _table("Blank start", blank, args.details)
    _table("From the recorded extraction", extracted, args.details)
    failed = [r.slug for r in blank if not r.agrees]
    if failed:
        print(f"Blank runs that miss the fixture's verdict: {', '.join(failed)}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
