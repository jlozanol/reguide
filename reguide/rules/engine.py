"""Rule evaluation and result types.

Every applicable rule is evaluated and every rule that fires is kept, because
the set is the explanation shown to the user. Which of them decides the class
follows the Regulations:

- Regulation 3.3(7): if two or more rules apply, the device takes the highest
  class among them.
- A clause that opens "Despite clauses ..." sets those clauses aside. Schedule
  2A clauses 1.5, 1.6(2) and 1.8 work this way, and all three give a lower
  class than the clauses they displace, so "highest wins" alone would get
  them wrong. A hit records the clauses it displaces; displaced hits stay in
  the explanation but do not compete for the result.

A rule whose inputs are unresolved, or that is not written yet, returns a
Pending. A Pending blocks the result unless a hit displaces its clause,
because a rule nobody could evaluate might have applied. A partial answer here
is worse than no answer.

Rule functions never call a model and never read free text. They read
resolved profile fields and nothing else.
"""

import re
from dataclasses import dataclass, field

from ..profile import DeviceKind, DeviceProfile, FunctionProfile, Tri

REGULATIONS = "Therapeutic Goods (Medical Devices) Regulations 2002"
RULE_ID = re.compile(r"^(s2a?)-(\d+\.\d+[A-Z]?)")


@dataclass(frozen=True)
class RuleHit:
    rule_id: str          # e.g. "s2-5.2" or "s2a-1.6(2)(c)"
    citation: str         # clause reference as it should appear in the report
    result: str           # "Class IIa", "Class 3 IVD", and so on
    because: str          # which profile fields satisfied the rule
    displaces: tuple[str, ...] = ()   # clause ids set aside, e.g. ("s2a-1.1",)


@dataclass(frozen=True)
class Pending:
    """A rule that could not be evaluated. Never a negative finding."""

    rule_id: str
    citation: str
    reason: str                       # plain words for the report
    fields: tuple[str, ...] = ()      # unresolved inputs, e.g. "ivd.is_self_test"


@dataclass
class Classification:
    result: str | None = None
    hits: list[RuleHit] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    displaced: list[str] = field(default_factory=list)   # rule ids set aside

    @property
    def confident(self) -> bool:
        return self.result is not None and not self.unresolved

    @property
    def governing(self) -> list[RuleHit]:
        """The hits that produce the result, in rule order."""
        return [h for h in self.hits
                if h.result == self.result and h.rule_id not in self.displaced]


Outcome = RuleHit | Pending | None


def clause_of(rule_id: str) -> str:
    """'s2a-1.6(2)(a)' -> 's2a-1.6'. Displacement works on whole clauses."""
    m = RULE_ID.match(rule_id)
    if not m:
        raise ValueError(f"not a rule id: {rule_id!r}")
    return f"{m.group(1)}-{m.group(2)}"


def clauses(prefix: str, *numbers: str) -> tuple[str, ...]:
    return tuple(f"{prefix}-{n}" for n in numbers)


def known(answer) -> Tri | None:
    """YES or NO when resolved, else None. A stated UNKNOWN is still unknown."""
    if answer.resolved and answer.value in (Tri.YES, Tri.NO):
        return answer.value
    return None


def resolve(outcomes: list[Outcome], order: list[str]) -> Classification:
    """Combine rule outcomes into one Classification.

    order is the class ladder for the family, lowest first (IVD_ORDER or
    GENERAL_ORDER from profile.py).
    """
    hits = [o for o in outcomes if isinstance(o, RuleHit)]
    pending = [o for o in outcomes if isinstance(o, Pending)]

    set_aside = {c for h in hits for c in h.displaces}
    live = [h for h in hits if clause_of(h.rule_id) not in set_aside]
    blocking = [p for p in pending if clause_of(p.rule_id) not in set_aside]

    unresolved = []
    for p in blocking:
        entries = list(p.fields) or [f"{p.rule_id} ({p.reason})"]
        unresolved += [e for e in entries if e not in unresolved]

    result = None
    if live and not blocking:
        result = max((h.result for h in live), key=order.index)

    return Classification(
        result=result,
        hits=hits,
        unresolved=unresolved,
        displaced=[h.rule_id for h in hits if h not in live],
    )


def classify_function(function: FunctionProfile) -> Classification:
    """Classify one function the status gate marked regulated.

    Schedule 2A for an IVD, Schedule 2 for anything else (regulation 3.2).
    The caller decides which functions reach this point; nothing here
    re-checks regulatory status.
    """
    kind = function.branch()
    if kind is DeviceKind.IVD:
        from . import schedule2a
        if function.ivd is None:
            return Classification(unresolved=["ivd"])
        return schedule2a.evaluate(function.ivd)
    if kind is DeviceKind.GENERAL:
        return Classification(unresolved=["s2 (Schedule 2 rules not implemented)"])
    return Classification(unresolved=["kind"])


def classify(profile: DeviceProfile) -> Classification:
    """Route every regulated function and aggregate per family.

    Wired up with the scoring harness, which is where the gate's verdict
    decides which functions are classified.
    """
    raise NotImplementedError
