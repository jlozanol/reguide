"""Schedule 2, classification rules for medical devices other than IVDs.

One function per rule. Each paragraph rule takes the function's
GeneralDeviceProfile and returns a RuleHit, a Pending or None. The docstring
holds the clause text verbatim from Compilation 72, below a first line naming
the clause, and tests/test_schedule2.py checks every docstring against the
clause files.

Written so far: Part 2, the non-invasive clauses. 2.1 is a floor that fires
for every non-invasive device, because "unless the device is classified at a
higher level under another clause" is exactly what regulation 3.3(7) does
with the other hits. Within clause 2.4, subclause (2) is "subject to" (3) and
(4): it fires only when neither does. When (3) and (4) both apply, both hits
are kept and (4) governs as the higher class, the reading TGA's examples
support (dressings for chronic ulcerated wounds are Class IIb although they
absorb exudate).

Not written yet: Parts 3, 4 and 5. Each returns a Pending that blocks the
result where the Part could apply, so a class is never given while a higher
clause might still be waiting:

- Part 3 applies only to invasive devices, so it blocks only when the route
  is invasive or unknown.
- Part 4 applies to active devices (4.1 to 4.4) and to programmed or
  programmable devices and software (4.5 to 4.8), so it blocks only when the
  device is active or software, or either is unknown.
- Part 5 can apply to any device, so it blocks every result until written.
"""

from ..profile import (
    GENERAL_ORDER,
    ActiveType,
    FunctionProfile,
    GeneralDeviceProfile,
    Invasiveness,
    Tri,
)
from .engine import REGULATIONS, Classification, Pending, RuleHit, known, resolve

PREFIX = "s2"


def cite(reference: str) -> str:
    return f"{REGULATIONS} Schedule 2 clause {reference}"


def _because(general: GeneralDeviceProfile, *names: str) -> str:
    parts = []
    for name in names:
        answer = getattr(general, name)
        value = answer.value.value
        quote = f' ("{answer.evidence}")' if answer.evidence else ""
        parts.append(f"{name} is {value} ({answer.basis.value}){quote}")
    return "; ".join(parts)


def _lookup(general: GeneralDeviceProfile, name: str, rule_id: str, reference: str):
    value = known(getattr(general, name))
    if value is None:
        return Pending(rule_id, cite(reference), f"{name} is unresolved", (f"general.{name}",))
    return value


def _non_invasive(general: GeneralDeviceProfile, rule_id: str, reference: str):
    """True for a non-invasive device, None for any other, Pending if unknown."""
    route = general.invasiveness
    if not route.resolved or route.value is None:
        return Pending(rule_id, cite(reference), "invasiveness is unresolved",
                       ("general.invasiveness",))
    return True if route.value is Invasiveness.NON_INVASIVE else None


def _paragraph(general: GeneralDeviceProfile, reference: str, result: str,
               gate: str | None, *conditions: str, unless: tuple[str, ...] = ()):
    """A paragraph of Part 2: non-invasive, behind an optional gate.

    It applies when every condition is yes and every field in unless is no.
    """
    rule_id = f"{PREFIX}-{reference}"
    route = _non_invasive(general, rule_id, reference)
    if route is not True:
        return route
    for name in ((gate,) if gate else ()) + conditions:
        value = _lookup(general, name, rule_id, reference)
        if value is not Tri.YES:
            return value if isinstance(value, Pending) else None
    for name in unless:
        value = _lookup(general, name, rule_id, reference)
        if value is not Tri.NO:
            return value if isinstance(value, Pending) else None
    names = ["invasiveness", *(g for g in (gate,) if g), *conditions, *unless]
    return RuleHit(rule_id, cite(reference), result, _because(general, *names))


SUBSTANCES = "handles_substances_for_administration"
WOUND = "contacts_injured_skin_or_mucous_membrane"


# --------------------------------------------------------------------------
# Part 2, non-invasive medical devices
# --------------------------------------------------------------------------


def rule_2_1(general: GeneralDeviceProfile):
    """Schedule 2 clause 2.1.

    A non-invasive medical device is classified as Class I, unless the device
    is classified at a higher level under another clause in this Part or in
    Part 4 or 5 of this Schedule.
    """
    return _paragraph(general, "2.1", "Class I", None)


def rule_2_2_1_a(general: GeneralDeviceProfile):
    """Schedule 2 clause 2.2(1)(a).

    (1) This clause applies to:

    (a) a non-invasive medical device that is intended by the manufacturer to
    be used to channel or store blood or body liquids that are to be infused,
    administered or introduced into a patient; and

    (2) The device is classified as Class IIa.
    """
    return _paragraph(general, "2.2(1)(a)", "Class IIa", SUBSTANCES,
                      "channels_or_stores_blood_for_administration")


def rule_2_2_1_b(general: GeneralDeviceProfile):
    """Schedule 2 clause 2.2(1)(b).

    (1) This clause applies to:

    (b) a non-invasive medical device that is intended by the manufacturer to
    be used to store an organ, part of an organ or body tissue that is to be
    later introduced into a patient; and

    (2) The device is classified as Class IIa.
    """
    return _paragraph(general, "2.2(1)(b)", "Class IIa", SUBSTANCES,
                      "stores_organ_or_tissue_for_introduction")


def rule_2_2_1_c(general: GeneralDeviceProfile):
    """Schedule 2 clause 2.2(1)(c).

    (1) This clause applies to:

    (c) a non-invasive medical device that:

    (i) is intended by the manufacturer to be used to channel or store a
    liquid or gas that is to be infused, administered or introduced into a
    patient; and

    (ii) may be connected to an active medical device classified as Class IIa
    or higher.

    (2) The device is classified as Class IIa.
    """
    return _paragraph(general, "2.2(1)(c)", "Class IIa", SUBSTANCES,
                      "channels_or_stores_liquid_or_gas_for_administration",
                      "connected_to_active_device")


def rule_2_2A(general: GeneralDeviceProfile):
    """Schedule 2 clause 2.2A.

    A medical device is classified as Class IIa if the device:

    (a) is a non-invasive medical device; and

    (b) is intended by the manufacturer to be used for the purpose of:

    (i) maintaining the patency of another medical device; or

    (ii) flushing the lumen of another medical device; and

    (c) only contains saline to be used for a purpose mentioned in paragraph
    (b).
    """
    return _paragraph(general, "2.2A", "Class IIa", SUBSTANCES, "saline_only_flush_or_patency")


def rule_2_3_1(general: GeneralDeviceProfile):
    """Schedule 2 clause 2.3(1).

    (1) Subject to subclause (2), a non-invasive medical device that is
    intended by the manufacturer to be used to modify the biological or
    chemical composition of blood, other body liquids, or other liquids
    intended to be infused into a patient, is classified as Class IIb.
    """
    return _paragraph(general, "2.3(1)", "Class IIb", SUBSTANCES,
                      "modifies_composition_of_blood_or_infusion",
                      unless=("treatment_is_filtration_centrifugation_or_exchange",))


def rule_2_3_2(general: GeneralDeviceProfile):
    """Schedule 2 clause 2.3(2).

    (2) If the treatment for which the device is designed consists of
    filtration, centrifugation or exchanges of gas or heat, the device is
    classified as Class IIa.
    """
    return _paragraph(general, "2.3(2)", "Class IIa", SUBSTANCES,
                      "modifies_composition_of_blood_or_infusion",
                      "treatment_is_filtration_centrifugation_or_exchange")


def rule_2_4_2(general: GeneralDeviceProfile):
    """Schedule 2 clause 2.4(2).

    (1) This clause applies to a non-invasive medical device that is intended
    by the manufacturer to be used in contact with injured skin or a mucous
    membrane (including a device the principal intention of which is to
    manage the micro-environment of a wound).

    (2) Subject to subclauses (3) and (4), the device is classified as Class
    IIa.
    """
    return _paragraph(general, "2.4(2)", "Class IIa", WOUND,
                      unless=("barrier_compression_or_absorption",
                              "principally_for_breached_dermis_secondary_intent"))


def rule_2_4_3(general: GeneralDeviceProfile):
    """Schedule 2 clause 2.4(3).

    (3) If the device is intended to be used:

    (a) as a mechanical barrier; or

    (b) for compression; or

    (c) for the absorption of exudates;

    the device is classified as Class I.
    """
    return _paragraph(general, "2.4(3)", "Class I", WOUND, "barrier_compression_or_absorption")


def rule_2_4_4(general: GeneralDeviceProfile):
    """Schedule 2 clause 2.4(4).

    (4) If the device is intended to be used principally for wounds that have
    breached the dermis and the wounds can only heal by secondary intent, the
    device is classified as Class IIb.
    """
    return _paragraph(general, "2.4(4)", "Class IIb", WOUND,
                      "principally_for_breached_dermis_secondary_intent")


PART_2 = [
    rule_2_1,
    rule_2_2_1_a,
    rule_2_2_1_b,
    rule_2_2_1_c,
    rule_2_2A,
    rule_2_3_1,
    rule_2_3_2,
    rule_2_4_2,
    rule_2_4_3,
    rule_2_4_4,
]


# --------------------------------------------------------------------------
# Parts not written yet
# --------------------------------------------------------------------------


def part_3(function: FunctionProfile):
    """Part 3, invasive devices. Blocks only an invasive or unknown route."""
    route = function.general.invasiveness
    if not route.resolved or route.value is None:
        return Pending(f"{PREFIX}-3.1", cite("3.1"), "invasiveness is unresolved",
                       ("general.invasiveness",))
    if route.value is Invasiveness.NON_INVASIVE:
        return None
    return Pending(f"{PREFIX}-3.1", cite("3.1"), "not implemented: Part 3, clauses 3.1 to 3.4")


def part_4(function: FunctionProfile):
    """Part 4, active devices and software. Blocks only where it could apply."""
    active = function.general.active_type
    software = known(function.is_software)
    if active.resolved and active.value in (ActiveType.THERAPEUTIC, ActiveType.DIAGNOSTIC):
        return Pending(f"{PREFIX}-4.1", cite("4.1"), "not implemented: Part 4, clauses 4.1 to 4.8")
    if software is Tri.YES:
        return Pending(f"{PREFIX}-4.1", cite("4.1"), "not implemented: Part 4, clauses 4.1 to 4.8")
    unknown = []
    if not active.resolved or active.value is None:
        unknown.append("general.active_type")
    if software is None:
        unknown.append("is_software")
    if unknown:
        return Pending(f"{PREFIX}-4.1", cite("4.1"), "Part 4 applicability is unresolved",
                       tuple(unknown))
    return None


def part_5(function: FunctionProfile):
    """Part 5, particular kinds of devices. Can apply to any device."""
    return Pending(f"{PREFIX}-5.1", cite("5.1"), "not implemented: Part 5, clauses 5.1 to 5.11")


def evaluate(function: FunctionProfile) -> Classification:
    general = function.general
    outcomes = [rule(general) for rule in PART_2]
    outcomes += [part_3(function), part_4(function), part_5(function)]
    return resolve(outcomes, GENERAL_ORDER)
