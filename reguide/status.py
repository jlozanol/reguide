"""Stage 3. The regulatory status gate.

Runs before classification and can stop the pipeline. Three questions, in the
order the TGA's own guidance puts them:

1. Is the function a medical device under s41BD of the Therapeutic Goods Act?
2. If it is, does an item of Schedule 1 of the Therapeutic Goods (Excluded
   Goods) Determination 2018 capture it? Excluded goods are outside the
   regulatory scheme entirely.
3. If it is not excluded, does it meet every criterion of the clinical decision
   support exemption in Schedule 4, Part 2 of the Therapeutic Goods (Medical
   Devices) Regulations 2002? Exempt software is still a medical device. It
   does not need an ARTG entry, but the sponsor must notify the TGA within 30
   working days of supply and the essential principles still apply.

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

CDSS_NOTIFICATION = (
    "Exempt CDSS: notify the TGA using the Clinical Decision Support Software "
    "Exemption notification form within 30 working days of supply. The "
    "essential principles, advertising requirements and adverse event "
    "reporting continue to apply."
)


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
    """One item of Schedule 1 of the Determination."""

    item: str        # "14E"
    citation: str    # as it should appear in the report
    summary: str     # short description of what the item covers


EXCLUSION_TABLE: dict[str, Exclusion] = {}


def load_exclusions(path: str | Path = EXCLUSION_SOURCE) -> int:
    """Populate the exclusion table from the Determination.

    Expects a list of objects with item, citation and summary. Returns the
    number of items loaded so a caller can fail loudly on zero.
    """
    entries = json.loads(Path(path).read_text())
    EXCLUSION_TABLE.clear()
    for entry in entries:
        exclusion = Exclusion(**entry)
        EXCLUSION_TABLE[exclusion.item.upper()] = exclusion
    return len(EXCLUSION_TABLE)


@dataclass
class FunctionStatus:
    """One function's verdict."""

    index: int
    name: str | None
    outcome: StatusOutcome
    hits: list[RuleHit] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    missing_sources: list[str] = field(default_factory=list)


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
                    citation=f"{ACT} s41BD(1)",
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
            citation=f"{ACT} s41BD(3)",
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
                    citation=f"{ACT} s41BD(1)(b)",
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
            citation=f"{ACT} s41BD(1)",
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
        key = item.strip().upper()
        exclusion = EXCLUSION_TABLE.get(key)
        if exclusion is None:
            verdict.unresolved.append(f"status.excluded_item (no item {key} in table)")
            return verdict
        conditions = _value(status.exclusion_conditions_met)
        if conditions in (None, Tri.UNKNOWN):
            return verdict
        if conditions is Tri.YES:
            verdict.outcome = StatusOutcome.EXCLUDED
            verdict.hits.append(
                RuleHit(
                    rule_id=f"egd-{key}",
                    citation=f"{DETERMINATION} Schedule 1 item {key}",
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
                    rule_id="mdr-sch4-pt2-cdss",
                    citation=f"{REGULATIONS} Schedule 4 Part 2",
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
        # A product with an exempt function and an excluded one is supplied as
        # exempt: the notification obligation is the binding one.
        result.outcome = StatusOutcome.EXEMPT_CDSS
        result.obligations.append(CDSS_NOTIFICATION)
    else:
        result.outcome = StatusOutcome.EXCLUDED
    return result
