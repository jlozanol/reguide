"""Score intake against the fixtures, from the recorded cassettes.

No model call. For each case: whether its cassette exists and is current,
whether the function split matches, fields agreed, contradictions (against a
specific fact, or against a builder default), extras, coverage of the
fixture's specific facts, untraceable evidence, dropped claims and how many
questions remain.

    uv run python scripts/score_intake.py
    uv run python scripts/score_intake.py --details
    uv run python scripts/score_intake.py --only founder

Exits non-zero when any recorded case has a contradiction or untraceable
evidence, or a cassette is stale.
"""

import argparse
import sys
from collections import Counter

from reguide.intake_scoring import Cassette, Kind, score_all


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", metavar="TEXT", help="only cases whose name contains TEXT")
    parser.add_argument("--details", action="store_true",
                        help="list extras and dropped claims, not just contradictions")
    args = parser.parse_args(argv)

    scores = [s for s in score_all() if not args.only or args.only in s.case.name]
    header = (f"{'case':46} {'split':>5} {'agree':>5} {'contra':>6} {'extra':>5} "
              f"{'cover':>6} {'drop':>4} {'ask':>4}")
    print(header)
    print("-" * len(header))
    for s in scores:
        if s.cassette is not Cassette.OK:
            print(f"{s.case.name:46} {s.cassette.value.upper()}")
            continue
        split = "ok" if s.split_matches else f"{s.extracted_functions}/{s.expected_functions}"
        contra = len(s.contradictions)
        cover = f"{len(s.covered)}/{len(s.specific)}"
        mark = "  <-- untraceable" if s.untraceable else ""
        print(f"{s.case.name:46} {split:>5} {len(s.of(Kind.AGREED)):>5} "
              f"{contra if contra else '.':>6} {len(s.of(Kind.EXTRA)):>5} {cover:>6} "
              f"{len(s.rejections):>4} {s.askable:>4}{mark}")

    recorded = [s for s in scores if s.cassette is Cassette.OK]
    print(f"\nRecorded {len(recorded)} of {len(scores)} cases "
          f"({sum(s.cassette is Cassette.MISSING for s in scores)} missing, "
          f"{sum(s.cassette is Cassette.STALE for s in scores)} stale)")
    if recorded:
        specific = sum(len(s.specific) for s in recorded)
        covered = sum(len(s.covered) for s in recorded)
        print(f"Coverage of specific facts: {covered}/{specific}"
              f" ({100 * covered / specific:.0f}%)" if specific else "")
        print(f"Split matches: {sum(s.split_matches for s in recorded)}/{len(recorded)}")
        drops = Counter(r.reason.value for s in recorded for r in s.rejections)
        print("Dropped claims by reason: " +
              (", ".join(f"{k} {v}" for k, v in drops.most_common()) or "none"))

    contradictions = [(s, f) for s in recorded for f in s.contradictions]
    if contradictions:
        print(f"\nContradictions ({len(contradictions)}):")
        for s, f in contradictions:
            label = "specific" if f.kind is Kind.CONTRADICTS_SPECIFIC else "default "
            print(f"  [{label}] {s.case.name}  {f.field}: extracted {f.extracted!r}, "
                  f"fixture {f.expected!r}")
            print(f"             evidence: {f.evidence!r}")
    untraceable = [(s, name) for s in recorded for name in s.untraceable]
    for s, name in untraceable:
        print(f"  [untraceable] {s.case.name}  {name}")

    if args.details:
        for s in recorded:
            extras = s.of(Kind.EXTRA)
            missed = [n for n in s.specific if n not in set(s.covered)]
            if not extras and not s.rejections and not missed:
                continue
            print(f"\n{s.case.name}")
            for f in extras:
                print(f"  extra    {f.field} = {f.extracted!r}  evidence: {f.evidence!r}")
            for r in s.rejections:
                print(f"  dropped  {r.target} = {r.value!r}  ({r.reason.value})"
                      f"  evidence: {r.evidence!r}")
            if missed:
                print(f"  not recovered: {', '.join(missed)}")

    stale = any(s.cassette is Cassette.STALE for s in scores)
    return 1 if contradictions or untraceable or stale else 0


if __name__ == "__main__":
    sys.exit(main())
