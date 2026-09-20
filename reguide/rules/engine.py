"""Rule evaluation and result types.

Every applicable rule is evaluated. Where more than one applies, the highest
resulting classification governs, but the full set is retained because the set
is the explanation shown to the user.
"""

from dataclasses import dataclass, field

from ..profile import DeviceProfile


@dataclass(frozen=True)
class RuleHit:
    rule_id: str          # e.g. "s2-5.2" or "s2a-1.3"
    citation: str         # clause reference as it should appear in the report
    result: str           # "Class IIa", "Class 3", and so on
    because: str          # which profile fields satisfied the rule


@dataclass
class Classification:
    result: str | None = None
    hits: list[RuleHit] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    @property
    def confident(self) -> bool:
        return self.result is not None and not self.unresolved


def classify(profile: DeviceProfile) -> Classification:
    """Route to Schedule 2 or Schedule 2A and evaluate.

    Refuses to return a result while any field the applicable rules depend on
    is unresolved. A partial answer here is worse than no answer.
    """
    raise NotImplementedError
