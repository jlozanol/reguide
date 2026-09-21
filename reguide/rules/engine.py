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
from dataclasses import dataclass, field, replace

from ..flags import Flag
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


@dataclass(frozen=True)
class Qualifier:
    """A conformity assessment condition attached to a class, not a class.

    Regulation 3.9 adds procedures for a Class I medical device that is
    supplied sterile (3.9(2)) or has a measuring function (1.4, 3.9(3)).
    """

    code: str             # "supplied_sterile" or "measuring_function"
    label: str            # plain words for the report
    citation: str
    because: str


@dataclass
class Classification:
    result: str | None = None
    hits: list[RuleHit] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    displaced: list[str] = field(default_factory=list)   # rule ids set aside
    flags: list[Flag] = field(default_factory=list)      # shown beside the class
    qualifiers: list[Qualifier] = field(default_factory=list)

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


QUALIFIERS = [
    ("supplied_sterile", "supplied_sterile", "supplied sterile",
     f"{REGULATIONS} regulation 3.9(2)"),
    ("has_measuring_function", "measuring_function", "has a measuring function",
     f"{REGULATIONS} regulations 1.4 and 3.9(3)"),
]


def qualify(profile: DeviceProfile, function: FunctionProfile,
            outcome: Classification) -> Classification:
    """Attach the regulation 3.9 qualifiers to a confident Class I result.

    Only general devices: regulation 1.4(2) excludes IVDs from the measuring
    function, and Class 1 IVDs have their own procedures (regulation 3.9A).
    The inputs sit on the product (CoreProfile), so every function of a
    product shares them. An unanswered input leaves the result standing but
    not confident, because the conformity route of a Class I device is not
    known until both are answered.
    """
    if function.branch() is not DeviceKind.GENERAL or outcome.result != "Class I":
        return outcome
    if not outcome.confident:
        return outcome
    for field_name, code, label, citation in QUALIFIERS:
        answer = getattr(profile.core, field_name)
        value = known(answer)
        if value is None:
            outcome.unresolved.append(f"core.{field_name}")
        elif value is Tri.YES:
            quote = f' ("{answer.evidence}")' if answer.evidence else ""
            outcome.qualifiers.append(Qualifier(
                code, label, citation,
                f"{field_name} is yes ({answer.basis.value}){quote}"))
    return outcome


def classify(profile: DeviceProfile, indices: list[int]) -> dict[int, Classification]:
    """Classify the functions at indices, keyed by index.

    indices is the status gate's classifiable list (StatusResult.classifiable).
    It is a required argument so that no caller can classify a function the
    gate has not marked regulated by forgetting to ask. Results are per
    function; the class per family for the product is highest_class() over
    the confident ones, and only when every regulated function is confident.
    Flags raised by a rule are stamped with the function's index here, and a
    Class I general device gets its regulation 3.9 qualifiers.
    """
    results = {}
    for i in indices:
        function = profile.functions[i]
        outcome = qualify(profile, function, classify_function(function))
        outcome.flags = [replace(f, functions=(i,)) for f in outcome.flags]
        results[i] = outcome
    return results
