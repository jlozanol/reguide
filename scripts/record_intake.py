"""Record the model's reply for every intake case, one live call each.

The only thing in the project, besides try_intake.py, that calls OpenAI.
Needs OPENAI_API_KEY in .env. Saves one cassette per case in
tests/intake_cassettes/<fixture>__<variant>.json.

A case whose cassette already matches the current instructions, schema, model
and text is skipped, so re-running only records what is missing or stale.

    uv run python scripts/record_intake.py --dry-run
    uv run python scripts/record_intake.py
    uv run python scripts/record_intake.py --only melanoma
    uv run python scripts/record_intake.py --only melanoma --force
"""

import argparse
import sys

from reguide.intake_scoring import Cassette, cassette_state, load_cases
from reguide.llm import CASSETTE_DIR, CassetteClient, IntakeError, OpenAIIntake, configured_model


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", metavar="TEXT",
                        help="only cases whose name contains TEXT")
    parser.add_argument("--force", action="store_true",
                        help="record again even when the cassette is current")
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would be recorded, call nothing")
    args = parser.parse_args(argv)

    model = configured_model()
    cases = [c for c in load_cases() if not args.only or args.only in c.name]
    todo = []
    for case in cases:
        state, _ = cassette_state(case, CASSETTE_DIR, model)
        if args.force or state is not Cassette.OK:
            todo.append((case, state))

    print(f"{len(cases)} cases, {len(todo)} to record with {model}")
    if args.dry_run or not todo:
        for case, state in todo:
            print(f"  {case.name:48} {state.value}")
        return 0

    client = OpenAIIntake(model=model)
    cassettes = CassetteClient(CASSETTE_DIR, model=model)
    failed = []
    for number, (case, state) in enumerate(todo, 1):
        print(f"[{number}/{len(todo)}] {case.name} ({state.value}) ...", end=" ", flush=True)
        try:
            output = client.complete(case.text)
        except IntakeError as error:
            print(f"FAILED: {error}")
            failed.append(case.name)
            continue
        cassettes.record(case.name, case.text, output)
        print(f"{len(output.get('claims', []))} claims")

    names = {case.name for case in load_cases()}
    orphans = sorted(p.name for p in CASSETTE_DIR.glob("*.json") if p.stem not in names)
    if orphans:
        print(f"\nCassettes with no matching case (safe to delete): {', '.join(orphans)}")
    if failed:
        print(f"\n{len(failed)} failed: {', '.join(failed)}. Re-run to retry them.")
        return 1
    print("\nDone. Next: uv run python scripts/score_intake.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
