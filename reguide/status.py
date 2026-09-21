"""Stage 3. The regulatory status gate.

Runs before classification and can stop the pipeline. Three questions, in the
order the TGA's own guidance puts them:

1. Is the function a medical device under s41BD of the Therapeutic Goods Act?
2. If it is, does an item of Schedule 1 of the Therapeutic Goods (Excluded
   Goods) Determination 2018 capture it? Excluded goods are outside the
   regulatory scheme entirely.
3. If it is not excluded, does it meet every criterion of the clinical decision
   support exemption, item 2.15 of Schedule 4, Part 2 of the Therapeutic Goods
   (Medical Devices) Regulations 2002? Exempt software is still a medical
   device. It does not need an ARTG entry, but it carries conditions: the
   essential principles, conformity assessment, adverse event reporting, and
   notifying the TGA within 20 working days of import or supply.

Sources checked: the Act at Compilation No. 89 (5 September 2025), the
Determination at Compilation No. 11 (8 August 2024), the Regulations at
Compilation No. 72 (8 September 2026).

No model calls. Every verdict carries the clause that produced it.

Aggregation across functions is asymmetric, and that asymmetry is the whole
reason functions are first-class in the schema:

- being a device is existential. One regulated function makes the product a
  regulated product.
- exclusion and exemption are universal. Every function has to qualify, because
  a product cannot be half outside the scheme.

An absent source is not a negative finding. If the exclusion table has not been
loaded, the gate says so in missing_sources and returns UNDECIDED rather than
reporting that nothing was excluded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .profile import (
    Answer,
    DeviceProfile,
    FunctionProfile,
    TherapeuticPurpose,
    Tri,
)
from .rules.engine import RuleHit

ACT = "Therapeutic Goods Act 1989"
DETERMINATION = "Therapeutic Goods (Excluded Goods) Determination 2018"
REGULATIONS = "Therapeutic Goods (Medical Devices) Regulations 2002"

EXCLUSION_SOURCE = "data/legislation/excluded_goods_determination_2018.json"

CDSS_ITEM = f"{REGULATIONS} Schedule 4 Part 2 item 2.15"

CDSS_NOTIFICATION = (
    "Exempt CDSS, conditions of item 2.15: notify the TGA on the approved form "
    "within 20 working days of importing or supplying the device; comply with "
    "the essential principles; apply the conformity assessment procedures; "
    "report adverse events within the prescribed periods; and provide "
    "compliance information within 20 working days if the TGA asks."
)

# Where each limb of the definition sits in s41BD(1)(a).
LIMB = {
    TherapeuticPurpose.DISEASE: "(i)",
    TherapeuticPurpose.INJURY: "(ii)",
    TherapeuticPurpose.ANATOMY: "(iii)",
    TherapeuticPurpose.CONCEPTION: "(iv)",
    TherapeuticPurpose.IN_VITRO_SPECIMEN: "(v)",
}


class StatusOutcome(str, Enum):
    """Where a function, or a whole product, lands."""

    REGULATED = "regulated_medical_device"
    NOT_A_DEVICE = "not_a_medical_device"
    EXCLUDED = "excluded_from_regulation"
    EXEMPT_CDSS = "exempt_clinical_decision_support"
    UNDECIDED = "undecided"

    @property
    def terminal(self) -> bool:
        """Does this verdict stop the pipeline for the function that holds it."""
        return self in (
            StatusOutcome.NOT_A_DEVICE,
            StatusOutcome.EXCLUDED,
            StatusOutcome.EXEMPT_CDSS,
        )


@dataclass(frozen=True)
class Exclusion:
    """One item of Schedule 1 or Schedule 2 of the Determination.

    Item numbers repeat across the two Schedules, so the key carries the
    Schedule: S1-14B, S2-7. Schedule 2 goods are excluded only when used or
    presented in the way that item describes.
    """

    key: str          # "S1-14B"
    schedule: int     # 1 or 2
    item: str         # "14B"
    citation: str     # as it should appear in the report
    software: bool    # a software item, 14A to 14O
    summary: str      # paraphrase naming the conditions, not the legal text
    caution: str = ""  # a known trap, from TGA guidance; raised as a flag when used


EXCLUSION_TABLE: dict[str, Exclusion] = {}


def exclusion_key(text: str) -> str:
    """Normalise a user-supplied key: ' s1-14b ' becomes 'S1-14B'."""
    return "".join(text.split()).upper()


def load_exclusions(path: str | Path = EXCLUSION_SOURCE) -> int:
    """Populate the exclusion table from the file scripts/build_exclusions.py writes.

    Returns the number of items loaded so a caller can fail loudly on zero.
    """
    payload = json.loads(Path(path).read_text())
    EXCLUSION_TABLE.clear()
    for entry in payload["items"]:
        exclusion = Exclusion(**entry)
        EXCLUSION_TABLE[exclusion_key(exclusion.key)] = exclusion
    return len(EXCLUSION_TABLE)


class Severity(str, Enum):
    """How loudly the report should raise a flag.

    AMBER: the verdict stands, but a person should look before relying on it.
    RED: the tool could not reach a safe verdict and a person must decide.
    """

    AMBER = "amber"
    RED = "red"


@dataclass(frozen=True)
class Flag:
    """Something the report must show beside the verdict, not bury in it."""

    severity: Severity
    code: str        # stable identifier, for tests and for the report layout
    message: str     # plain words for the founder
    functions: tuple[int, ...] = ()   # indices of the functions it concerns


@dataclass
class FunctionStatus:
    """One function's verdict."""

    index: int
    name: str | None
    outcome: StatusOutcome
    hits: list[RuleHit] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)
    exclusion: str | None = None   # the exclusion key, when the outcome is EXCLUDED


@dataclass
class StatusResult:
    """The product's verdict, and the per-function verdicts behind it.

    Deliberately not a Classification. result on a Classification means a
    device class, and excluded is not a device class.
    """

    outcome: StatusOutcome = StatusOutcome.UNDECIDED
    functions: list[FunctionStatus] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)

    @property
    def proceeds(self) -> bool:
        """Whether classification should run at all."""
        return self.outcome is StatusOutcome.REGULATED

    @property
    def hits(self) -> list[RuleHit]:
        """Every clause that fired, across functions. The explanation."""
        return [hit for function in self.functions for hit in function.hits]

    @property
    def classifiable(self) -> list[int]:
        """Indices of the functions that still need a class.

        A product can proceed on two of its three functions. Stage 4 should
        classify these and leave the rest alone.
        """
        return [f.index for f in self.functions if f.outcome is StatusOutcome.REGULATED]


def _value(answer: Answer):
    """The value, or None if the answer is not resolved."""
    return answer.value if answer.resolved else None


def _quote(answer: Answer) -> str:
    return answer.evidence or "no supporting phrase recorded"


def status_of(function: FunctionProfile, index: int = 0) -> FunctionStatus:
    """Evaluate one function. Every branch either cites a clause or reports a gap."""
    status = function.status
    unresolved = [
        name for name in function.missing() if name.startswith("status.")
    ]
    verdict = FunctionStatus(
        index=index,
        name=_value(function.name),
        outcome=StatusOutcome.UNDECIDED,
        unresolved=unresolved,
    )

    purpose = _value(status.therapeutic_purpose)
    if purpose is None:
        return verdict

    # 1. Is it a device
    if purpose is TherapeuticPurpose.NONE:
        accessory = _value(status.is_accessory_to_device)
        if accessory in (None, Tri.UNKNOWN):
            return verdict
        if accessory is Tri.NO:
            verdict.outcome = StatusOutcome.NOT_A_DEVICE
            verdict.hits.append(
                RuleHit(
                    rule_id="s41BD",
                    citation=f"{ACT} s41BD(1)(a) and (b)",
                    result=StatusOutcome.NOT_A_DEVICE.value,
                    because=(
                        "no limb of the definition is reached and the function is "
                        f"not an accessory: {_quote(status.therapeutic_purpose)}"
                    ),
                )
            )
            return verdict
        origin = RuleHit(
            rule_id="s41BD-accessory",
            citation=f"{ACT} s41BD(1)(b)",
            result="medical device",
            because=f"accessory to a medical device: {_quote(status.is_accessory_to_device)}",
        )
    else:
        pharmacological = _value(status.principal_action_pharmacological)
        if pharmacological in (None, Tri.UNKNOWN):
            return verdict
        if pharmacological is Tri.YES:
            verdict.outcome = StatusOutcome.NOT_A_DEVICE
            verdict.hits.append(
                RuleHit(
                    rule_id="s41BD-principal-action",
                    citation=f"{ACT} s41BD(1)(a), closing words",
                    result=StatusOutcome.NOT_A_DEVICE.value,
                    because=(
                        "principal intended action is achieved by pharmacological, "
                        "immunological or metabolic means, which points at the "
                        f"medicines pathway: {_quote(status.principal_action_pharmacological)}"
                    ),
                )
            )
            return verdict
        origin = RuleHit(
            rule_id="s41BD",
            citation=f"{ACT} s41BD(1)(a){LIMB[purpose]}",
            result="medical device",
            because=f"{purpose.value}: {_quote(status.therapeutic_purpose)}",
        )

    verdict.hits.append(origin)

    # 2. Is it excluded
    if not EXCLUSION_TABLE:
        verdict.missing_sources.append(EXCLUSION_SOURCE)
        return verdict

    item = _value(status.excluded_item)
    if item is None:
        return verdict
    if item.strip().lower() not in ("", "none"):
        key = exclusion_key(item)
        exclusion = EXCLUSION_TABLE.get(key)
        if exclusion is None:
            verdict.unresolved.append(f"status.excluded_item (no item {key} in table)")
            return verdict
        conditions = _value(status.exclusion_conditions_met)
        if conditions in (None, Tri.UNKNOWN):
            return verdict
        if conditions is Tri.YES:
            verdict.outcome = StatusOutcome.EXCLUDED
            verdict.exclusion = key
            verdict.hits.append(
                RuleHit(
                    rule_id=f"egd-{key}",
                    citation=exclusion.citation,
                    result=StatusOutcome.EXCLUDED.value,
                    because=(
                        f"{exclusion.summary}, every condition met: "
                        f"{_quote(status.exclusion_conditions_met)}"
                    ),
                )
            )
            return verdict

    # 3. Is it exempt CDSS
    if _value(function.is_software) is Tri.YES:
        sole = _value(status.cdss_sole_purpose_recommendation)
        processes = _value(status.cdss_processes_device_signal_or_image)
        replaces = _value(status.cdss_replaces_clinical_judgement)
        if Tri.UNKNOWN in (sole, processes, replaces) or None in (sole, processes, replaces):
            return verdict
        if sole is Tri.YES and processes is Tri.NO and replaces is Tri.NO:
            verdict.outcome = StatusOutcome.EXEMPT_CDSS
            verdict.hits.append(
                RuleHit(
                    rule_id="mdr-sch4-pt2-2.15",
                    citation=CDSS_ITEM,
                    result=StatusOutcome.EXEMPT_CDSS.value,
                    because=(
                        "sole purpose is providing or supporting a recommendation to a "
                        "health professional, it does not process or analyse a signal or "
                        "image from another medical device, and it does not replace "
                        f"clinical judgement: {_quote(status.cdss_sole_purpose_recommendation)}"
                    ),
                )
            )
            return verdict

    verdict.outcome = StatusOutcome.REGULATED
    return verdict


def gate(profile: DeviceProfile) -> StatusResult:
    """Evaluate the product. Classification runs only if this returns REGULATED."""
    result = StatusResult()
    if not profile.functions:
        result.unresolved.append("functions (none recorded)")
        return result

    result.functions = [
        status_of(function, index) for index, function in enumerate(profile.functions)
    ]
    outcomes = [f.outcome for f in result.functions]
    result.unresolved = [name for f in result.functions for name in f.unresolved]
    result.missing_sources = sorted(
        {source for f in result.functions for source in f.missing_sources}
    )
    result.flags = _caution_flags(result.functions)

    # Existential: one regulated function regulates the product, whatever the
    # rest are. Unresolved fields elsewhere still block classification, which is
    # stage 4's refusal to make, not this one's.
    if StatusOutcome.REGULATED in outcomes:
        result.outcome = StatusOutcome.REGULATED
        return result

    if StatusOutcome.UNDECIDED in outcomes:
        result.outcome = StatusOutcome.UNDECIDED
        return result

    # Universal: from here every function is terminal.
    if all(o is StatusOutcome.NOT_A_DEVICE for o in outcomes):
        result.outcome = StatusOutcome.NOT_A_DEVICE
    elif StatusOutcome.EXEMPT_CDSS in outcomes:
        # The exempt function is still a medical device with duties, so the
        # product is supplied as exempt. If another function is excluded, the
        # verdict is defensible but unusual, and the report says so out loud.
        result.outcome = StatusOutcome.EXEMPT_CDSS
        result.obligations.append(CDSS_NOTIFICATION)
        if StatusOutcome.EXCLUDED in outcomes:
            result.flags.append(_mixed_flag(result.functions))
    else:
        result.outcome = StatusOutcome.EXCLUDED
    return result


def _name(function: FunctionStatus) -> str:
    return function.name or f"function {function.index + 1}"


def _mixed_flag(functions: list[FunctionStatus]) -> Flag:
    exempt = [f for f in functions if f.outcome is StatusOutcome.EXEMPT_CDSS]
    excluded = [f for f in functions if f.outcome is StatusOutcome.EXCLUDED]
    return Flag(
        severity=Severity.AMBER,
        code="mixed_exempt_and_excluded",
        message=(
            f"This product mixes an exempt function ({', '.join(map(_name, exempt))}) "
            f"with an excluded one ({', '.join(map(_name, excluded))}). It is treated "
            "as exempt, so the exemption's conditions apply to the whole product, "
            "including notifying the TGA. The excluded function adds no obligations "
            "of its own. Confirm this split with the TGA or a regulatory adviser "
            "before relying on it."
        ),
        functions=tuple(f.index for f in exempt + excluded),
    )


def _caution_flags(functions: list[FunctionStatus]) -> list[Flag]:
    """One flag per excluded function whose exclusion item carries a caution."""
    flags = []
    for function in functions:
        exclusion = EXCLUSION_TABLE.get(function.exclusion or "")
        if exclusion is not None and exclusion.caution:
            flags.append(
                Flag(
                    severity=Severity.AMBER,
                    code=f"exclusion_caution_{exclusion.key}",
                    message=f"{_name(function)}: {exclusion.caution}",
                    functions=(function.index,),
                )
            )
    return flags
