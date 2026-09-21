"""Agreement between the engine and the fixtures.

The fraction of verified fixtures the engine gets right is the project's
quality measure, so the harness is strict about what counts:

- The status gate runs first, on every function, against the real exclusion
  table. A function the gate does not mark regulated is never classified.
- A regulated function agrees only when the engine returns a confident class
  equal to the fixture's, and the fixture's rule is among the governing hits.
  A rule reference agrees with its own paragraphs: "3.2" accepts
  "s2-3.2(2)", but "1.1" never accepts "s2a-1.10".
- A function the fixture expects to be outside regulation agrees when the
  gate reaches the same verdict.
- A fixture agrees only when every one of its functions does.

A miss is one of four kinds, worst first:

- wrong class: a confident class that differs from the fixture. This is the
  only failure that could mislead a founder, so the test suite forbids it
  outright on verified fixtures.
- wrong rule: the right class for a reason the fixture does not record.
- gate: the status gate disagrees with the fixture, so the class question
  never arose or arose wrongly.
- no result: the engine refused, with the unresolved inputs or unwritten
  rules that stopped it. Expected while rules are still being written.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import status as S
from .profile import DeviceKind, DeviceProfile
from .rules.engine import Classification, classify

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "tests" / "fixtures"
EXCLUSIONS = ROOT / "data" / "legislation" / "excluded_goods_determination_2018.json"

REGULATED = S.StatusOutcome.REGULATED.value

AGREE = "agree"
WRONG_CLASS = "wrong class"
WRONG_RULE = "wrong rule"
GATE = "gate"
NO_RESULT = "no result"

RULE_REFERENCE = re.compile(r"^\d+\.\d+[A-Z]?(?:\([0-9a-zA-Z]+\))*")
FAMILY_PREFIX = {DeviceKind.IVD: "s2a", DeviceKind.GENERAL: "s2"}


@dataclass
class Row:
    fixture: str
    index: int
    function: str
    expected_status: str
    gate_status: str
    expected_class: str | None
    expected_rule: str
    got_class: str | None = None
    got_rules: list[str] = field(default_factory=list)
    verdict: str = AGREE
    detail: str = ""


@dataclass
class Score:
    rows: list[Row]

    @property
    def fixtures(self) -> list[str]:
        return list(dict.fromkeys(r.fixture for r in self.rows))

    @property
    def agreeing_fixtures(self) -> list[str]:
        return [f for f in self.fixtures
                if all(r.verdict == AGREE for r in self.rows if r.fixture == f)]

    @property
    def agreeing_functions(self) -> int:
        return sum(1 for r in self.rows if r.verdict == AGREE)

    @property
    def misses(self) -> list[Row]:
        order = [WRONG_CLASS, WRONG_RULE, GATE, NO_RESULT]
        return sorted((r for r in self.rows if r.verdict != AGREE),
                      key=lambda r: (order.index(r.verdict), r.fixture, r.index))


def expected_rule_id(kind: DeviceKind | None, reference: str) -> str | None:
    """'1.6(2)(a)' on an IVD -> 's2a-1.6(2)(a)'. Trailing prose is dropped.

    None when the reference is not a clause, such as 'S1-14B' on an
    excluded function.
    """
    m = RULE_REFERENCE.match(reference.strip())
    if not m or kind not in FAMILY_PREFIX:
        return None
    return f"{FAMILY_PREFIX[kind]}-{m.group(0)}"


def rule_matches(expected: str, got: str) -> bool:
    return got == expected or got.startswith(expected + "(")


def score_fixture(slug: str, data: dict) -> list[Row]:
    profile = DeviceProfile.model_validate(data["profile"])
    verdict = S.gate(profile)
    classifiable = verdict.classifiable
    classes = classify(profile, classifiable) if classifiable else {}

    rows = []
    for index, (function, expected) in enumerate(zip(profile.functions, data["functions"],
                                                     strict=True)):
        gate_status = verdict.functions[index].outcome.value
        row = Row(
            fixture=slug,
            index=index,
            function=expected["name"],
            expected_status=expected["expected_status"],
            gate_status=gate_status,
            expected_class=expected["expected_class"],
            expected_rule=expected["expected_rule"],
        )
        rows.append(row)

        if gate_status != row.expected_status:
            row.verdict = GATE
            row.detail = f"gate {gate_status}, fixture {row.expected_status}"
            continue
        if row.expected_status != REGULATED:
            continue

        outcome: Classification = classes[index]
        row.got_class = outcome.result
        row.got_rules = [h.rule_id for h in outcome.governing]
        if not outcome.confident:
            row.verdict = NO_RESULT
            row.detail = ", ".join(outcome.unresolved)
            continue
        if outcome.result != row.expected_class:
            row.verdict = WRONG_CLASS
            row.detail = f"cited {', '.join(row.got_rules)}"
            continue
        wanted = expected_rule_id(function.branch(), row.expected_rule)
        if wanted is None or not any(rule_matches(wanted, got) for got in row.got_rules):
            row.verdict = WRONG_RULE
            row.detail = f"fixture cites {row.expected_rule}"
    return rows


def run(fixture_dir: Path = FIXTURE_DIR, include_unverified: bool = False) -> Score:
    if S.load_exclusions(EXCLUSIONS) == 0:
        raise RuntimeError(f"exclusion table is empty: {EXCLUSIONS}")
    rows = []
    for path in sorted(Path(fixture_dir).glob("*.json")):
        data = json.loads(path.read_text())
        if data["verified"] or include_unverified:
            rows += score_fixture(path.stem, data)
    return Score(rows)


def _cell(text: str | None) -> str:
    return (text or "none").replace("|", "\\|")


def report(score: Score) -> str:
    fixtures = len(score.fixtures)
    agreeing = len(score.agreeing_fixtures)
    percent = f"{100 * agreeing / fixtures:.0f}%" if fixtures else "n/a"
    lines = [
        f"Agreement: {agreeing}/{fixtures} fixtures ({percent}), "
        f"{score.agreeing_functions}/{len(score.rows)} functions",
    ]
    counts = {}
    for row in score.misses:
        counts[row.verdict] = counts.get(row.verdict, 0) + 1
    if counts:
        lines.append("Misses: " + ", ".join(f"{n} {kind}" for kind, n in counts.items()))
    if score.agreeing_fixtures:
        lines.append("Agreeing: " + ", ".join(score.agreeing_fixtures))
    if not score.misses:
        return "\n".join(lines) + "\n"

    lines += [
        "",
        "| fixture | function | expected | got | miss | detail |",
        "|---|---|---|---|---|---|",
    ]
    for row in score.misses:
        expected = row.expected_class or row.expected_status
        expected = f"{expected} ({row.expected_rule})"
        got = row.got_class or (row.gate_status if row.verdict == GATE else None)
        if row.got_rules:
            got = f"{got} ({', '.join(row.got_rules)})"
        lines.append(
            f"| {row.fixture} | {_cell(row.function)} | {_cell(expected)} | {_cell(got)} "
            f"| {row.verdict} | {_cell(row.detail)} |"
        )
    return "\n".join(lines) + "\n"
