"""Score extraction against the fixtures, the way scoring.py scores the engine.

Each fixture carries intake cases (a "described" text, sometimes a "founder"
one) and the list of facts it sets on purpose ("specific"). For each case,
the recorded model reply is run through the same checks extract() uses, and
every field the result states is compared with the fixture's profile:

- agreed: the fixture holds the same value.
- contradiction: the fixture holds a different value. This is the failure
  that matters, the analogue of a wrong class. It comes in two kinds. Against
  a specific fact it points at the model or the prompt. Against a builder
  default (a "no" the fixture filled in because the description was silent)
  it may instead mean the fixture's default is wrong for this text; each one
  is triaged by hand, never waved through.
- extra: the fixture has no answer there, usually because gating pruned the
  field. Not wrong, listed for review.

Coverage is how many of the fixture's specific facts extraction recovered.
It is reported, not required: a description does not state everything, and
anything it does not state is asked.

Free text (the product name, the intended purpose, function names and
descriptions) is not compared: the fixture's wording and the case's wording
differ by design.

Functions are matched by position. When extraction splits the product into a
different number of functions, function-level fields are not compared and
the case is marked as a split difference; the founder confirms the split in
the interview anyway.
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from .extract import Rejection, build_profile
from .llm import CASSETTE_DIR, DEFAULT_MODEL, request_key
from .profile import Answer, Basis, DeviceProfile, FundingProfile

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "tests" / "fixtures"

NOT_COMPARED = {"core.product_name", "core.intended_purpose",
                "funding.replaces_existing_service"}


class Cassette(StrEnum):
    OK = "ok"
    MISSING = "missing"
    STALE = "stale"


class Kind(StrEnum):
    AGREED = "agreed"
    CONTRADICTS_SPECIFIC = "contradicts_specific"
    CONTRADICTS_DEFAULT = "contradicts_default"
    EXTRA = "extra"


@dataclass(frozen=True)
class IntakeCase:
    slug: str
    variant: str
    text: str

    @property
    def name(self) -> str:
        """The cassette file stem."""
        return f"{self.slug}__{self.variant}"


@dataclass(frozen=True)
class Finding:
    kind: Kind
    field: str
    extracted: Any
    expected: Any
    evidence: str


@dataclass
class CaseScore:
    case: IntakeCase
    cassette: Cassette
    split_matches: bool = True
    extracted_functions: int = 0
    expected_functions: int = 0
    findings: list[Finding] = field(default_factory=list)
    specific: list[str] = field(default_factory=list)
    untraceable: list[str] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)
    askable: int = 0

    def of(self, *kinds: Kind) -> list[Finding]:
        return [f for f in self.findings if f.kind in kinds]

    @property
    def contradictions(self) -> list[Finding]:
        return self.of(Kind.CONTRADICTS_SPECIFIC, Kind.CONTRADICTS_DEFAULT)

    @property
    def covered(self) -> list[str]:
        agreed = {f.field for f in self.of(Kind.AGREED)}
        return [name for name in self.specific if name in agreed]

    @property
    def clean(self) -> bool:
        return self.cassette is Cassette.OK and not self.contradictions \
            and not self.untraceable


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_fixture(slug: str, directory: Path = FIXTURE_DIR) -> dict[str, Any]:
    return json.loads((directory / f"{slug}.json").read_text())


def load_cases(directory: Path = FIXTURE_DIR) -> list[IntakeCase]:
    cases = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text())
        for variant, text in data["intake"]["cases"].items():
            cases.append(IntakeCase(path.stem, variant, text))
    return cases


def cassette_state(case: IntakeCase, directory: Path = CASSETTE_DIR,
                   model: str = DEFAULT_MODEL) -> tuple[Cassette, dict | None]:
    """Whether a recording exists for this case and matches the current request."""
    path = directory / f"{case.name}.json"
    if not path.exists():
        return Cassette.MISSING, None
    entry = json.loads(path.read_text())
    if entry.get("key") != request_key(model, case.text):
        return Cassette.STALE, None
    return Cassette.OK, entry["output"]


# --------------------------------------------------------------------------
# Comparing
# --------------------------------------------------------------------------

def _plain(value: Any) -> Any:
    return getattr(value, "value", value)


def stated_fields(profile: DeviceProfile) -> list[tuple[str, Answer]]:
    """Every field extraction filled in, by dotted name, free text included."""
    out = []
    for name in type(profile.core).model_fields:
        answer = getattr(profile.core, name)
        if answer.basis is Basis.STATED:
            out.append((f"core.{name}", answer))
    if profile.funding is not None:
        for name in FundingProfile.model_fields:
            answer = getattr(profile.funding, name)
            if answer.basis is Basis.STATED:
                out.append((f"funding.{name}", answer))
    for index, function in enumerate(profile.functions):
        for name in ("kind", "is_software"):
            answer = getattr(function, name)
            if answer.basis is Basis.STATED:
                out.append((f"functions.{index}.{name}", answer))
        for section in ("status", "general", "ivd"):
            part = getattr(function, section)
            if part is None:
                continue
            for name in type(part).model_fields:
                answer = getattr(part, name)
                if answer.basis is Basis.STATED:
                    out.append((f"functions.{index}.{section}.{name}", answer))
    return out


def compare(extracted: DeviceProfile, expected: DeviceProfile,
            specific: set[str]) -> tuple[list[Finding], bool]:
    """Findings for every stated field, and whether the function split matched."""
    split_matches = len(extracted.functions) == len(expected.functions)
    findings = []
    for dotted, answer in stated_fields(extracted):
        if dotted in NOT_COMPARED:
            continue
        if dotted.startswith("functions.") and not split_matches:
            continue
        target = expected.answer_at(dotted)
        got = _plain(answer.value)
        if target is None or not target.resolved:
            findings.append(Finding(Kind.EXTRA, dotted, got, None, answer.evidence or ""))
            continue
        want = _plain(target.value)
        if got == want:
            kind = Kind.AGREED
        elif dotted in specific:
            kind = Kind.CONTRADICTS_SPECIFIC
        else:
            kind = Kind.CONTRADICTS_DEFAULT
        findings.append(Finding(kind, dotted, got, want, answer.evidence or ""))
    return findings, split_matches


def score_case(case: IntakeCase, output: dict[str, Any] | None, cassette: Cassette,
               fixture: dict[str, Any]) -> CaseScore:
    expected = DeviceProfile.model_validate(fixture["profile"])
    specific = list(fixture["intake"]["specific"])
    score = CaseScore(case=case, cassette=cassette, specific=specific,
                      expected_functions=len(expected.functions))
    if cassette is not Cassette.OK or output is None:
        return score
    extracted, rejections = build_profile(output, case.text)
    score.findings, score.split_matches = compare(extracted, expected, set(specific))
    score.extracted_functions = len(extracted.functions)
    score.untraceable = extracted.untraceable_evidence()
    score.rejections = rejections
    score.askable = len(extracted.askable())
    return score


def score_all(fixtures: Path = FIXTURE_DIR, cassettes: Path = CASSETTE_DIR,
              model: str = DEFAULT_MODEL) -> list[CaseScore]:
    scores = []
    for case in load_cases(fixtures):
        state, output = cassette_state(case, cassettes, model)
        scores.append(score_case(case, output, state, load_fixture(case.slug, fixtures)))
    return scores
