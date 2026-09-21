"""Schedule 2A, classification rules for IVD medical devices.

One function per rule. Each takes the function's IvdProfile and returns a
RuleHit, a Pending or None. The docstring holds the clause text verbatim from
Compilation 72, below a first line naming the clause, so the citation and the
code sit next to each other and drift is visible in review.
tests/test_schedule2a.py checks every docstring against the clause files.

Written so far: the lookups. Clauses 1.5, 1.6(2) and 1.8 each open "Despite
clauses ...", so each displaces the clauses it names even though it gives a
lower class (see engine.py). 1.8 is here with them because it displaces every
other clause: while it is unwritten, no result could ever be confident.

Not written yet, each returning a Pending that blocks the result unless a
lookup displaces it: 1.1 to 1.4, and the fallback step, 1.6(1) with 1.7.
The fallback only applies when no other clause does. 1.6(1) gives Class 1
and has no "despite", so under regulation 3.3(7) it can only decide the
class where 1.7 would otherwise give Class 2.

Classes are reported as "Class N IVD". Every clause here also names the
in-house equivalent (except 1.8, which names Class 1 IVD only). The profile
has no in-house field yet.
"""

from ..profile import IVD_ORDER, IvdProfile, Tri
from .engine import REGULATIONS, Classification, Pending, RuleHit, clauses, known, resolve

PREFIX = "s2a"


def cite(reference: str) -> str:
    return f"{REGULATIONS} Schedule 2A clause {reference}"


def _because(ivd: IvdProfile, *names: str) -> str:
    parts = []
    for name in names:
        answer = getattr(ivd, name)
        parts.append(f'{name} is {answer.value.value} ({answer.basis.value}: "{answer.evidence}")'
                     if answer.evidence else f"{name} is {answer.value.value} "
                     f"({answer.basis.value})")
    return "; ".join(parts)


def _lookup(ivd: IvdProfile, name: str, rule_id: str, reference: str) -> Tri | Pending:
    value = known(getattr(ivd, name))
    if value is None:
        return Pending(rule_id, cite(reference), f"{name} is unresolved", (f"ivd.{name}",))
    return value


def _not_written(number: str) -> Pending:
    return Pending(f"{PREFIX}-{number}", cite(number), "not implemented")


# --------------------------------------------------------------------------
# Not written yet
# --------------------------------------------------------------------------


def rule_1_1(ivd: IvdProfile):
    """Schedule 2A clause 1.1. Not implemented."""
    return _not_written("1.1")


def rule_1_2(ivd: IvdProfile):
    """Schedule 2A clause 1.2. Not implemented."""
    return _not_written("1.2")


def rule_1_3(ivd: IvdProfile):
    """Schedule 2A clause 1.3. Not implemented."""
    return _not_written("1.3")


def rule_1_4(ivd: IvdProfile):
    """Schedule 2A clause 1.4. Not implemented."""
    return _not_written("1.4")


# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------


def rule_1_5(ivd: IvdProfile):
    """Schedule 2A clause 1.5.

    Despite clauses 1.1 to 1.4, an IVD medical device that is intended to be
    used as non assay-specific quality control material is classified as a
    Class 2 IVD medical device or a Class 2 in-house IVD medical device.
    """
    rule_id = f"{PREFIX}-1.5"
    value = _lookup(ivd, "is_quality_control_material", rule_id, "1.5")
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    return RuleHit(
        rule_id=rule_id,
        citation=cite("1.5"),
        result="Class 2 IVD",
        because=_because(ivd, "is_quality_control_material"),
        displaces=clauses(PREFIX, "1.1", "1.2", "1.3", "1.4"),
    )


DESPITE_1_6_2 = clauses(PREFIX, "1.1", "1.2", "1.3", "1.4", "1.5")


def rule_1_6_2_a(ivd: IvdProfile):
    """Schedule 2A clause 1.6(2)(a).

    (2) Despite clauses 1.1 to 1.5, the following IVD medical devices are
    classified as Class 1 IVD medical devices or Class 1 in-house IVD medical
    devices:

    (a) an instrument, intended by the manufacturer, to be specifically used
    for in vitro diagnostic procedures;
    """
    rule_id = f"{PREFIX}-1.6(2)(a)"
    value = _lookup(ivd, "is_ivd_instrument", rule_id, "1.6(2)(a)")
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    return RuleHit(rule_id, cite("1.6(2)(a)"), "Class 1 IVD",
                   _because(ivd, "is_ivd_instrument"), DESPITE_1_6_2)


def rule_1_6_2_b(ivd: IvdProfile):
    """Schedule 2A clause 1.6(2)(b).

    (2) Despite clauses 1.1 to 1.5, the following IVD medical devices are
    classified as Class 1 IVD medical devices or Class 1 in-house IVD medical
    devices:

    (b) a specimen receptacle, other than a specimen receptacle that is
    intended for use in self-testing;
    """
    rule_id = f"{PREFIX}-1.6(2)(b)"
    value = _lookup(ivd, "is_specimen_receptacle", rule_id, "1.6(2)(b)")
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    self_test = _lookup(ivd, "is_self_test", rule_id, "1.6(2)(b)")
    if self_test is not Tri.NO:
        # A self-test receptacle is outside (b) and falls to the other rules.
        return self_test if isinstance(self_test, Pending) else None
    return RuleHit(rule_id, cite("1.6(2)(b)"), "Class 1 IVD",
                   _because(ivd, "is_specimen_receptacle", "is_self_test"), DESPITE_1_6_2)


def rule_1_6_2_c(ivd: IvdProfile):
    """Schedule 2A clause 1.6(2)(c).

    (2) Despite clauses 1.1 to 1.5, the following IVD medical devices are
    classified as Class 1 IVD medical devices or Class 1 in-house IVD medical
    devices:

    (c) a microbiological culture medium.
    """
    rule_id = f"{PREFIX}-1.6(2)(c)"
    value = _lookup(ivd, "is_culture_medium", rule_id, "1.6(2)(c)")
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    return RuleHit(rule_id, cite("1.6(2)(c)"), "Class 1 IVD",
                   _because(ivd, "is_culture_medium"), DESPITE_1_6_2)


def rule_1_8(ivd: IvdProfile):
    """Schedule 2A clause 1.8.

    Despite clauses 1.1 to 1.7, an IVD medical device is classified as a
    Class 1 IVD medical device if it is intended by the manufacturer for
    export only.
    """
    rule_id = f"{PREFIX}-1.8"
    value = _lookup(ivd, "is_export_only", rule_id, "1.8")
    if value is not Tri.YES:
        return value if isinstance(value, Pending) else None
    return RuleHit(rule_id, cite("1.8"), "Class 1 IVD", _because(ivd, "is_export_only"),
                   clauses(PREFIX, "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7"))


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------

ALL_RULES = [
    rule_1_1,
    rule_1_2,
    rule_1_3,
    rule_1_4,
    rule_1_5,
    rule_1_6_2_a,
    rule_1_6_2_b,
    rule_1_6_2_c,
    rule_1_8,
]


def fallback(ivd: IvdProfile):
    """Clauses 1.6(1) and 1.7, which apply only when no other clause does.

    Not implemented. Whether 1.6(1) catches the assay itself or only general
    purpose reagents used in one is a judgement still to make.
    """
    return Pending(f"{PREFIX}-1.7", cite("1.6(1) and 1.7"), "not implemented")


def evaluate(ivd: IvdProfile) -> Classification:
    outcomes = [rule(ivd) for rule in ALL_RULES]
    result = resolve(outcomes, IVD_ORDER)
    if result.result is None and not any(
        h.rule_id not in result.displaced for h in result.hits
    ):
        outcomes.append(fallback(ivd))
        result = resolve(outcomes, IVD_ORDER)
    return result
