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

Part 5, the rules for particular kinds of devices, is written in full. Its
rules take the whole FunctionProfile, because several turn on whether the
function is software, and read only fields relevant_general_fields asks: a
clause about materials is silent for software, a clause about implants is
silent for any other route. Clause 5.8 opens "Despite any other
classification in this Schedule", so an export-only device displaces every
other clause and is Class I. Clause 5.5(2) is read literally: a device that
touches no patient is not "intended to come into contact with intact skin
only", so the exception does not reach it, and an amber flag asks a person
to confirm.

The clause text keeps its own words and punctuation, except that its em
dashes are written as spaced en dashes; the docstring test treats the two as
the same character.

Part 3, the invasive clauses, is written in full. Within each clause the
default subclause ("Subject to ...") fires only when none of the subclauses
it names applies, and when several of those apply the highest class governs
with every hit recorded. Clause 3.1(1) excludes a device covered by 5.10 or
5.11, so a nasal spray is decided by 5.11 alone. Clause 3.1 has a gap: (2)
needs a device not connected to any active device and (3) one connected to
an active device of Class IIa or higher, so a device connected only to a
Class I active device fits neither. It is given the (2) rules, as if
unconnected, with an amber flag.

Part 4, active devices and software, is written in full, which completes
Schedule 2. Software is always an active device and always programmed
(dictionary), so 4.1 to 4.4 reach it as well as 4.5 to 4.8. 4.1 is the
floor for every active device. The graded software rules take the level
their paragraph names: 4.5 the disease and public health risk, 4.6 the
danger the information could indicate, 4.7 the harm of the treatment or its
absence, 4.8 the harm of the therapy. Where a paragraph splits into (i) and
(ii), each is its own rule, so the citation names the limb that applies. A
decision_maker that informs a relevant health professional selects 4.5(2)
and 4.7(2); anything else selects (1).

Every paragraph except 5.8 has a ceiling in CEILINGS, the class it gives, so
an unanswered paragraph stops blocking once a live hit is already at or above
it (regulation 3.3(7): the highest class wins, and only 5.8 can lower one).
"""

from ..flags import Flag, Severity
from ..profile import (
    GENERAL_ORDER,
    DecisionMaker,
    Duration,
    FunctionProfile,
    GeneralDeviceProfile,
    InformationTherapyHarm,
    Invasiveness,
    MonitoringDanger,
    OrificeSite,
    PublicHealthRisk,
    TreatmentRisk,
    Tri,
    invasive_band,
)
from ..profile import Severity as ConditionSeverity
from .engine import (
    REGULATIONS,
    Classification,
    Pending,
    RuleHit,
    apply_ceilings,
    clauses,
    known,
    resolve,
)

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


# --------------------------------------------------------------------------
# Part 3, invasive devices
# --------------------------------------------------------------------------


def _orifice_scope(function: FunctionProfile, rule_id: str, reference: str):
    """3.1(1): through a body orifice, not surgically invasive, not 5.10 or 5.11."""
    route = _route_is(function, (Invasiveness.BODY_ORIFICE,), rule_id, reference)
    if route is not True:
        return route
    if _physical(function, rule_id, reference) is True:
        for name in ("administers_by_inhalation", "is_substance_through_orifice_or_skin"):
            covered = _yes(function, name, rule_id, reference)
            if isinstance(covered, Pending):
                return covered
            if covered is Tri.YES:
                return None
    elif isinstance(_physical(function, rule_id, reference), Pending):
        return _physical(function, rule_id, reference)
    return True


def _connection(function: FunctionProfile, rule_id: str, reference: str):
    """'none', 'class I only' or 'IIa or higher', or a Pending."""
    any_active = _yes(function, "connected_to_an_active_device", rule_id, reference)
    if isinstance(any_active, Pending):
        return any_active
    if any_active is Tri.NO:
        return "none"
    high = _yes(function, "connected_to_active_device", rule_id, reference)
    if isinstance(high, Pending):
        return high
    return "IIa or higher" if high is Tri.YES else "class I only"


def _orifice(function: FunctionProfile, reference: str, result: str, durations,
             sites=None, absorbed=None):
    """One paragraph of 3.1(2): unconnected (or Class I only), by duration and site."""
    rule_id = f"{PREFIX}-{reference}"
    scope = _orifice_scope(function, rule_id, reference)
    if scope is not True:
        return scope
    connection = _connection(function, rule_id, reference)
    if isinstance(connection, Pending):
        return connection
    if connection == "IIa or higher":
        return None
    general = function.general
    names = ["invasiveness", "connected_to_an_active_device", "duration"]
    if connection == "class I only":
        names.insert(2, "connected_to_active_device")
    duration = general.duration
    if not duration.resolved or duration.value is None:
        return Pending(rule_id, cite(reference), "duration is unresolved", ("general.duration",))
    if duration.value not in durations:
        return None
    if sites is not None:
        site = general.orifice_site
        if not site.resolved or site.value is None:
            return Pending(rule_id, cite(reference), "orifice_site is unresolved",
                           ("general.orifice_site",))
        wanted, in_set = sites
        if (site.value in wanted) is not in_set:
            return None
        names.append("orifice_site")
    if absorbed is not None:
        value = _yes(function, "liable_to_be_absorbed_by_mucous_membrane", rule_id, reference)
        if isinstance(value, Pending):
            return value
        if value is not absorbed:
            return None
        names.append("liable_to_be_absorbed_by_mucous_membrane")
    return RuleHit(rule_id, cite(reference), result, _because(general, *names))


SHALLOW = {OrificeSite.ORAL_TO_PHARYNX, OrificeSite.EAR_TO_EARDRUM, OrificeSite.NASAL_CAVITY}
MOUTH_OR_EAR = {OrificeSite.ORAL_TO_PHARYNX, OrificeSite.EAR_TO_EARDRUM}
NASAL = {OrificeSite.NASAL_CAVITY}


def rule_3_1_2_a(function: FunctionProfile):
    """Schedule 2 clause 3.1(2)(a).

    (2) If the device is not intended to be connected to an active medical
    device, the following rules apply:

    (a) if the device is intended for transient use, the device is classified
    as Class I;
    """
    return _orifice(function, "3.1(2)(a)", "Class I", {Duration.TRANSIENT})


def rule_3_1_2_b_i(function: FunctionProfile):
    """Schedule 2 clause 3.1(2)(b)(i).

    (2) If the device is not intended to be connected to an active medical
    device, the following rules apply:

    (b) if the device is intended for short-term use:

    (i) the device is classified as Class IIa; or
    """
    return _orifice(function, "3.1(2)(b)(i)", "Class IIa", {Duration.SHORT_TERM},
                    sites=(SHALLOW, False))


def rule_3_1_2_b_ii(function: FunctionProfile):
    """Schedule 2 clause 3.1(2)(b)(ii).

    (2) If the device is not intended to be connected to an active medical
    device, the following rules apply:

    (b) if the device is intended for short-term use:

    (ii) if the device is intended to be used in the oral cavity as far as the
    pharynx, in an ear canal up to the ear drum, or in a nasal cavity – the
    device is classified as Class I;
    """
    return _orifice(function, "3.1(2)(b)(ii)", "Class I", {Duration.SHORT_TERM},
                    sites=(SHALLOW, True))


def rule_3_1_2_c_i(function: FunctionProfile):
    """Schedule 2 clause 3.1(2)(c)(i).

    (2) If the device is not intended to be connected to an active medical
    device, the following rules apply:

    (c) if the device is intended for long-term use:

    (i) the device is classified as Class IIb; or
    """
    other = _orifice(function, "3.1(2)(c)(i)", "Class IIb", {Duration.LONG_TERM},
                     sites=(SHALLOW, False))
    if other is not None:
        return other
    # A nasal device liable to be absorbed is outside (ii) and stays at (i).
    return _orifice(function, "3.1(2)(c)(i)", "Class IIb", {Duration.LONG_TERM},
                    sites=(NASAL, True), absorbed=Tri.YES)


def rule_3_1_2_c_ii(function: FunctionProfile):
    """Schedule 2 clause 3.1(2)(c)(ii).

    (2) If the device is not intended to be connected to an active medical
    device, the following rules apply:

    (c) if the device is intended for long-term use:

    (ii) if the device is intended to be used in the oral cavity as far as the
    pharynx or in an ear canal up to the ear drum, or the device is intended
    to be used in a nasal cavity and the device is not liable to be absorbed
    by the skin or mucous membrane – the device is classified as Class IIa.
    """
    mouth_or_ear = _orifice(function, "3.1(2)(c)(ii)", "Class IIa", {Duration.LONG_TERM},
                            sites=(MOUTH_OR_EAR, True))
    if mouth_or_ear is not None:
        return mouth_or_ear
    return _orifice(function, "3.1(2)(c)(ii)", "Class IIa", {Duration.LONG_TERM},
                    sites=(NASAL, True), absorbed=Tri.NO)


def rule_3_1_3(function: FunctionProfile):
    """Schedule 2 clause 3.1(3).

    (3) If the device is intended to be connected to an active medical device
    that is classified as Class IIa or higher, the device is classified as
    Class IIa.
    """
    rule_id, reference = f"{PREFIX}-3.1(3)", "3.1(3)"
    scope = _orifice_scope(function, rule_id, reference)
    if scope is not True:
        return scope
    connection = _connection(function, rule_id, reference)
    if connection != "IIa or higher":
        return connection if isinstance(connection, Pending) else None
    return RuleHit(rule_id, cite(reference), "Class IIa",
                   _because(function.general, "invasiveness", "connected_to_an_active_device",
                            "connected_to_active_device"))


def _band(function: FunctionProfile, band: str, rule_id: str, reference: str):
    """True when the device is in clause 3.2, 3.3 or 3.4, None if not, else Pending."""
    general = function.general
    route = general.invasiveness
    if not route.resolved or route.value is None:
        return Pending(rule_id, cite(reference), "invasiveness is unresolved",
                       ("general.invasiveness",))
    if route.value not in (Invasiveness.SURGICALLY_INVASIVE, Invasiveness.IMPLANTABLE):
        return None
    found = invasive_band(general)
    if found is None:
        return Pending(rule_id, cite(reference), "duration is unresolved", ("general.duration",))
    return True if found == band else None


def _surgical(function: FunctionProfile, band: str, reference: str, result: str,
              yes=(), no=()):
    rule_id = f"{PREFIX}-{reference}"
    inside = _band(function, band, rule_id, reference)
    if inside is not True:
        return inside
    hit = _chain(function, rule_id, reference, result, (), yes=yes, no=no)
    if isinstance(hit, RuleHit):
        return RuleHit(hit.rule_id, hit.citation, hit.result,
                       _because(function.general, "invasiveness", "duration", *yes, *no))
    return hit


HEART_DEFECT = "corrects_heart_or_circulatory_defect_by_contact"
CONTACT = "direct_contact_heart_circulation_or_nervous_system"
REUSABLE = "reusable_surgical_instrument"
IONISING = "delivers_ionising_radiation"
BIOLOGICAL = "has_biological_effect"
ABSORBED = "wholly_or_mostly_absorbed"
CHEMICAL = "undergoes_chemical_change"
TEETH = "placed_in_teeth"
MEDICINE = "administers_medicine"
HAZARDOUS_DELIVERY = "administers_medicine_hazardously_by_delivery_system"


def rule_3_2_2(function: FunctionProfile):
    """Schedule 2 clause 3.2(2).

    (1) This clause applies to a surgically invasive medical device that is
    intended for transient use.

    (2) Subject to subclauses (3) to (5), the device is classified as Class
    IIa.
    """
    return _surgical(function, "3.2", "3.2(2)", "Class IIa",
                     no=(HEART_DEFECT, CONTACT, REUSABLE, IONISING, BIOLOGICAL, ABSORBED,
                         HAZARDOUS_DELIVERY))


def rule_3_2_3(function: FunctionProfile):
    """Schedule 2 clause 3.2(3).

    (3) If the device is intended by the manufacturer specifically to be used
    to diagnose, monitor, control or correct a defect of the heart, or the
    central circulatory system, of a patient through direct contact with
    these parts of the body, the device is classified as Class III.
    """
    return _surgical(function, "3.2", "3.2(3)", "Class III", yes=(HEART_DEFECT,))


def rule_3_2_3A(function: FunctionProfile):
    """Schedule 2 clause 3.2(3A).

    (3A) If the device is not a reusable surgical instrument and the device is
    intended by the manufacturer specifically to be used in direct contact
    with the heart, the central circulatory system or the central nervous
    system of a patient, the device is classified as Class III.
    """
    return _surgical(function, "3.2", "3.2(3A)", "Class III", yes=(CONTACT,), no=(REUSABLE,))


def rule_3_2_4(function: FunctionProfile):
    """Schedule 2 clause 3.2(4).

    (4) If the device is a reusable surgical instrument, the device is
    classified as Class I.
    """
    return _surgical(function, "3.2", "3.2(4)", "Class I", yes=(REUSABLE,))


def rule_3_2_5_a(function: FunctionProfile):
    """Schedule 2 clause 3.2(5)(a).

    (5) If:

    (a) the device is intended by the manufacturer to be used to supply
    energy in the form of ionising radiation; or

    the device is classified as Class IIb.
    """
    return _surgical(function, "3.2", "3.2(5)(a)", "Class IIb", yes=(IONISING,))


def rule_3_2_5_b(function: FunctionProfile):
    """Schedule 2 clause 3.2(5)(b).

    (5) If:

    (b) the device is intended by the manufacturer to have a biological
    effect; or

    the device is classified as Class IIb.
    """
    return _surgical(function, "3.2", "3.2(5)(b)", "Class IIb", yes=(BIOLOGICAL,))


def rule_3_2_5_c(function: FunctionProfile):
    """Schedule 2 clause 3.2(5)(c).

    (5) If:

    (c) the device is intended by the manufacturer to be wholly, or mostly,
    absorbed by the patient’s body; or

    the device is classified as Class IIb.
    """
    return _surgical(function, "3.2", "3.2(5)(c)", "Class IIb", yes=(ABSORBED,))


def rule_3_2_5_d(function: FunctionProfile):
    """Schedule 2 clause 3.2(5)(d).

    (5) If:

    (d) the device is intended by the manufacturer to be used to administer
    medicine to a patient by means of a delivery system, and the
    administration is potentially hazardous to the patient having regard to
    the characteristics of the device;

    the device is classified as Class IIb.
    """
    return _surgical(function, "3.2", "3.2(5)(d)", "Class IIb", yes=(HAZARDOUS_DELIVERY,))


def rule_3_3_2(function: FunctionProfile):
    """Schedule 2 clause 3.3(2).

    (1) This clause applies to a surgically invasive medical device that is
    intended for short-term use.

    (2) Subject to subclauses (3) and (4), the device is classified as Class
    IIa.
    """
    hit = _surgical(function, "3.3", "3.3(2)", "Class IIa",
                    no=(IONISING, MEDICINE, HEART_DEFECT, CONTACT, BIOLOGICAL, ABSORBED))
    if not isinstance(hit, RuleHit):
        return hit
    # Chemical change is (3)(b) only outside the teeth; in the teeth it stays here.
    chemical = _yes(function, CHEMICAL, hit.rule_id, "3.3(2)")
    if isinstance(chemical, Pending):
        return chemical
    if chemical is Tri.YES:
        teeth = _yes(function, TEETH, hit.rule_id, "3.3(2)")
        if teeth is not Tri.YES:
            return teeth if isinstance(teeth, Pending) else None
    return hit


def rule_3_3_3_a(function: FunctionProfile):
    """Schedule 2 clause 3.3(3)(a).

    (3) If:

    (a) the device is intended by the manufacturer to be used to supply
    energy in the form of ionising radiation; or

    the device is classified as Class IIb.
    """
    return _surgical(function, "3.3", "3.3(3)(a)", "Class IIb", yes=(IONISING,))


def rule_3_3_3_b(function: FunctionProfile):
    """Schedule 2 clause 3.3(3)(b).

    (3) If:

    (b) the device is intended by the manufacturer to undergo a chemical
    change in a patient’s body (other than a device that is intended by the
    manufacturer to be placed in the teeth); or

    the device is classified as Class IIb.
    """
    return _surgical(function, "3.3", "3.3(3)(b)", "Class IIb", yes=(CHEMICAL,), no=(TEETH,))


def rule_3_3_3_c(function: FunctionProfile):
    """Schedule 2 clause 3.3(3)(c).

    (3) If:

    (c) the device is intended by the manufacturer to administer medicine;

    the device is classified as Class IIb.
    """
    return _surgical(function, "3.3", "3.3(3)(c)", "Class IIb", yes=(MEDICINE,))


def rule_3_3_4_a(function: FunctionProfile):
    """Schedule 2 clause 3.3(4)(a).

    (4) If the device is intended by the manufacturer:

    (a) specifically to be used to diagnose, monitor, control or correct a
    defect of the heart, or the central circulatory system, of a patient
    through direct contact with these parts of the body; or

    the device is classified as Class III.
    """
    return _surgical(function, "3.3", "3.3(4)(a)", "Class III", yes=(HEART_DEFECT,))


def rule_3_3_4_b(function: FunctionProfile):
    """Schedule 2 clause 3.3(4)(b).

    (4) If the device is intended by the manufacturer:

    (b) specifically to be used in direct contact with the heart, the central
    circulatory system or the central nervous system of a patient; or

    the device is classified as Class III.
    """
    return _surgical(function, "3.3", "3.3(4)(b)", "Class III", yes=(CONTACT,))


def rule_3_3_4_c(function: FunctionProfile):
    """Schedule 2 clause 3.3(4)(c).

    (4) If the device is intended by the manufacturer:

    (c) to have a biological effect; or

    the device is classified as Class III.
    """
    return _surgical(function, "3.3", "3.3(4)(c)", "Class III", yes=(BIOLOGICAL,))


def rule_3_3_4_d(function: FunctionProfile):
    """Schedule 2 clause 3.3(4)(d).

    (4) If the device is intended by the manufacturer:

    (d) to be wholly, or mostly, absorbed by a patient’s body;

    the device is classified as Class III.
    """
    return _surgical(function, "3.3", "3.3(4)(d)", "Class III", yes=(ABSORBED,))


def rule_3_4_2(function: FunctionProfile):
    """Schedule 2 clause 3.4(2).

    (1) This clause applies to:

    (a) a surgically invasive medical device that is intended for long-term
    use; and

    (b) an implantable medical device.

    (2) Subject to subclauses (3), (4), (4A) and (4B), the device is
    classified as Class IIb.
    """
    return _surgical(function, "3.4", "3.4(2)", "Class IIb",
                     no=(TEETH, CONTACT, BIOLOGICAL, ABSORBED, CHEMICAL, MEDICINE,
                         "joint_replacement_or_surgical_mesh", "spinal_motion_preserving"))


def rule_3_4_3(function: FunctionProfile):
    """Schedule 2 clause 3.4(3).

    (3) If the device is intended by the manufacturer to be placed in the
    teeth of a patient, the device is classified as Class IIa.
    """
    return _surgical(function, "3.4", "3.4(3)", "Class IIa", yes=(TEETH,))


def rule_3_4_4_a(function: FunctionProfile):
    """Schedule 2 clause 3.4(4)(a).

    (4) If the device is intended by the manufacturer:

    (a) to be used in direct contact with the heart, the central circulatory
    system or the central nervous system of a patient; or

    the device is classified as Class III.
    """
    return _surgical(function, "3.4", "3.4(4)(a)", "Class III", yes=(CONTACT,))


def rule_3_4_4_b(function: FunctionProfile):
    """Schedule 2 clause 3.4(4)(b).

    (4) If the device is intended by the manufacturer:

    (b) to have a biological effect; or

    the device is classified as Class III.
    """
    return _surgical(function, "3.4", "3.4(4)(b)", "Class III", yes=(BIOLOGICAL,))


def rule_3_4_4_c(function: FunctionProfile):
    """Schedule 2 clause 3.4(4)(c).

    (4) If the device is intended by the manufacturer:

    (c) to be wholly, or mostly, absorbed by a patient’s body; or

    the device is classified as Class III.
    """
    return _surgical(function, "3.4", "3.4(4)(c)", "Class III", yes=(ABSORBED,))


def rule_3_4_4_d(function: FunctionProfile):
    """Schedule 2 clause 3.4(4)(d).

    (4) If the device is intended by the manufacturer:

    (d) to undergo a chemical change in a patient’s body (other than a device
    that is intended by the manufacturer to be placed in the teeth); or

    the device is classified as Class III.
    """
    return _surgical(function, "3.4", "3.4(4)(d)", "Class III", yes=(CHEMICAL,), no=(TEETH,))


def rule_3_4_4_e(function: FunctionProfile):
    """Schedule 2 clause 3.4(4)(e).

    (4) If the device is intended by the manufacturer:

    (e) to be used to administer medicine;

    the device is classified as Class III.
    """
    return _surgical(function, "3.4", "3.4(4)(e)", "Class III", yes=(MEDICINE,))


def rule_3_4_4A(function: FunctionProfile):
    """Schedule 2 clause 3.4(4A).

    (4A) The device is classified as Class III if it is:

    (a) a joint replacement medical device; or

    (b) surgical mesh.
    """
    return _surgical(function, "3.4", "3.4(4A)", "Class III",
                     yes=("joint_replacement_or_surgical_mesh",))


def rule_3_4_4B(function: FunctionProfile):
    """Schedule 2 clause 3.4(4B).

    (4B) If the device is intended by the manufacturer to be a
    motion-preserving device for the spine (such as a spinal disc
    replacement), the device is classified as Class III.
    """
    return _surgical(function, "3.4", "3.4(4B)", "Class III", yes=("spinal_motion_preserving",))


PART_3 = [
    rule_3_1_2_a, rule_3_1_2_b_i, rule_3_1_2_b_ii, rule_3_1_2_c_i, rule_3_1_2_c_ii,
    rule_3_1_3,
    rule_3_2_2, rule_3_2_3, rule_3_2_3A, rule_3_2_4,
    rule_3_2_5_a, rule_3_2_5_b, rule_3_2_5_c, rule_3_2_5_d,
    rule_3_3_2, rule_3_3_3_a, rule_3_3_3_b, rule_3_3_3_c,
    rule_3_3_4_a, rule_3_3_4_b, rule_3_3_4_c, rule_3_3_4_d,
    rule_3_4_2, rule_3_4_3, rule_3_4_4_a, rule_3_4_4_b, rule_3_4_4_c, rule_3_4_4_d,
    rule_3_4_4_e, rule_3_4_4A, rule_3_4_4B,
]


CLASS_I_ACTIVE_CONNECTION = Flag(
    severity=Severity.AMBER,
    code="s2_3_1_class_i_active_connection",
    message=(
        "Schedule 2 clause 3.1(2) covers orifice devices not connected to any "
        "active device, and 3.1(3) those connected to an active device of Class "
        "IIa or higher. This device connects only to a Class I active device, "
        "which neither subclause names. It has been classified under 3.1(2) as "
        "if unconnected. Confirm that reading before relying on the class."
    ),
)


# --------------------------------------------------------------------------
# Part 4, active devices and software
# --------------------------------------------------------------------------


def _active(function: FunctionProfile, rule_id: str, reference: str):
    """True for an active device. Software always is (dictionary)."""
    software = known(function.is_software)
    if software is Tri.YES:
        return True
    if software is None:
        return Pending(rule_id, cite(reference), "is_software is unresolved", ("is_software",))
    value = _yes(function, "is_active_device", rule_id, reference)
    if isinstance(value, Pending):
        return value
    return True if value is Tri.YES else None


def _programmable(function: FunctionProfile, rule_id: str, reference: str):
    """True for software or a programmed or programmable active device (4.5 to 4.8)."""
    active = _active(function, rule_id, reference)
    if active is not True:
        return active
    if known(function.is_software) is Tri.YES:
        return True
    value = _yes(function, "is_programmed_or_programmable", rule_id, reference)
    if isinstance(value, Pending):
        return value
    return True if value is Tri.YES else None


def _enum(function: FunctionProfile, name: str, rule_id: str, reference: str):
    answer = getattr(function.general, name)
    if not answer.resolved or answer.value is None:
        return Pending(rule_id, cite(reference), f"{name} is unresolved", (f"general.{name}",))
    return answer.value


def _active_chain(function, reference, result, scope, yes=(), no=()):
    rule_id = f"{PREFIX}-{reference}"
    inside = scope(function, rule_id, reference)
    if inside is not True:
        return inside
    return _chain(function, rule_id, reference, result, (), yes=yes, no=no)


THERAPY = "active_for_therapy"
DIAGNOSIS = "active_for_diagnosis"


def rule_4_1(function: FunctionProfile):
    """Schedule 2 clause 4.1.

    An active medical device is classified as Class I, unless the device is
    classified at a higher level under another clause in this Part or in Part
    2, 3 or 5.
    """
    rule_id = f"{PREFIX}-4.1"
    active = _active(function, rule_id, "4.1")
    if active is not True:
        return active
    return RuleHit(rule_id, cite("4.1"), "Class I", "an active medical device (dictionary)")


def rule_4_2_1(function: FunctionProfile):
    """Schedule 2 clause 4.2(1).

    (1) Subject to subclause (2), an active medical device for therapy that is
    intended by the manufacturer to be used to administer energy to a patient,
    or exchange energy to or from a patient, is classified as Class IIa.
    """
    return _active_chain(function, "4.2(1)", "Class IIa", _active,
                         yes=(THERAPY, "administers_or_exchanges_energy"),
                         no=("delivers_hazardous_energy",))


def rule_4_2_2(function: FunctionProfile):
    """Schedule 2 clause 4.2(2).

    (2) If the device is of a kind such that the administration or exchange of
    energy occurs in a potentially hazardous way, having regard to the nature,
    density and site of application of the energy, the device is classified as
    Class IIb.
    """
    return _active_chain(function, "4.2(2)", "Class IIb", _active,
                         yes=(THERAPY, "administers_or_exchanges_energy",
                              "delivers_hazardous_energy"))


def rule_4_2_3(function: FunctionProfile):
    """Schedule 2 clause 4.2(3).

    (3) An active medical device that is intended by the manufacturer to be
    used to control or monitor, or directly influence, the performance of an
    active medical device for therapy of the kind mentioned in subclause (2)
    is classified as Class IIb.
    """
    return _active_chain(function, "4.2(3)", "Class IIb", _active,
                         yes=(THERAPY, "controls_hazardous_therapy_device"))


def rule_4_2_4(function: FunctionProfile):
    """Schedule 2 clause 4.2(4).

    (4) An active medical device for therapy that includes a diagnostic
    function the purpose of which is to significantly determine patient
    management by the device is classified as Class III.
    """
    return _active_chain(function, "4.2(4)", "Class III", _active,
                         yes=(THERAPY, "diagnostic_function_determines_patient_management"))


def rule_4_3_2_a(function: FunctionProfile):
    """Schedule 2 clause 4.3(2)(a).

    (1) This clause applies to an active medical device for diagnosis.

    (2) If:

    (a) the device is intended by the manufacturer to be used to supply
    energy that will be absorbed by a patient’s body (other than a device that
    is intended only to illuminate the patient’s body in the visible
    spectrum); or

    the device is classified as Class IIa.
    """
    return _active_chain(function, "4.3(2)(a)", "Class IIa", _active,
                         yes=(DIAGNOSIS, "supplies_absorbed_energy_for_diagnosis"))


def rule_4_3_2_b(function: FunctionProfile):
    """Schedule 2 clause 4.3(2)(b).

    (1) This clause applies to an active medical device for diagnosis.

    (2) If:

    (b) the device is intended by the manufacturer to be used to image in
    vivo distribution of radiopharmaceuticals in a patient; or

    the device is classified as Class IIa.
    """
    return _active_chain(function, "4.3(2)(b)", "Class IIa", _active,
                         yes=(DIAGNOSIS, "images_radiopharmaceutical_distribution"))


def rule_4_3_2_c(function: FunctionProfile):
    """Schedule 2 clause 4.3(2)(c).

    (1) This clause applies to an active medical device for diagnosis.

    (2) If:

    (c) the device is intended by the manufacturer to be used to allow direct
    diagnosis or monitoring of vital physiological processes of a patient
    (other than a device of a kind mentioned in paragraph (3)(a));

    the device is classified as Class IIa.
    """
    return _active_chain(function, "4.3(2)(c)", "Class IIa", _active,
                         yes=(DIAGNOSIS, "diagnoses_or_monitors_vital_processes"),
                         no=("monitors_vital_parameters_immediate_danger",))


def rule_4_3_3_a(function: FunctionProfile):
    """Schedule 2 clause 4.3(3)(a).

    (1) This clause applies to an active medical device for diagnosis.

    (3) If:

    (a) the device is intended by the manufacturer specifically to be used to
    monitor vital physiological parameters of a patient, and the nature of the
    variations monitored is of a kind that could result in immediate danger to
    the patient (for example, variations in cardiac performance, respiration,
    activity of the central nervous system); or

    the device is classified as Class IIb.
    """
    return _active_chain(function, "4.3(3)(a)", "Class IIb", _active,
                         yes=(DIAGNOSIS, "monitors_vital_parameters_immediate_danger"))


def rule_4_3_3_b(function: FunctionProfile):
    """Schedule 2 clause 4.3(3)(b).

    (1) This clause applies to an active medical device for diagnosis.

    (3) If:

    (b) the device is intended by the manufacturer to emit ionising radiation
    and to be used for diagnostic or therapeutic interventional radiology; or

    the device is classified as Class IIb.
    """
    return _active_chain(function, "4.3(3)(b)", "Class IIb", _active,
                         yes=(DIAGNOSIS, "emits_ionising_radiation_for_interventional_radiology"))


def rule_4_3_3_c(function: FunctionProfile):
    """Schedule 2 clause 4.3(3)(c).

    (1) This clause applies to an active medical device for diagnosis.

    (3) If:

    (c) the device is intended by the manufacturer to be used to control or
    monitor, or directly influence, the performance of a device of the kind
    mentioned in paragraph (b);

    the device is classified as Class IIb.
    """
    return _active_chain(function, "4.3(3)(c)", "Class IIb", _active,
                         yes=(DIAGNOSIS, "controls_interventional_radiology_device"))


def rule_4_4_1(function: FunctionProfile):
    """Schedule 2 clause 4.4(1).

    (1) Subject to subclause (2), an active medical device that is intended by
    the manufacturer to be used to administer medicine, body liquids or other
    substances to a patient, or to remove medicine, body liquids or other
    substances from a patient, is classified as Class IIa.
    """
    return _active_chain(function, "4.4(1)", "Class IIa", _active,
                         yes=("administers_or_removes_substances",),
                         no=("substance_administration_potentially_hazardous",))


def rule_4_4_2(function: FunctionProfile):
    """Schedule 2 clause 4.4(2).

    (2) If the device is of a kind such that the administration or removal of
    the medicine, body liquids or other substances is potentially hazardous to
    the patient, having regard to the nature of the substances involved, the
    part of the patient’s body concerned, and the characteristics of the
    device, the device is classified as Class IIb.
    """
    return _active_chain(function, "4.4(2)", "Class IIb", _active,
                         yes=("administers_or_removes_substances",
                              "substance_administration_potentially_hazardous"))


# The software rules grade by a level. Each helper returns the level a
# function reaches, or a Pending, and each paragraph rule fires on its level.

HIGH_RISK = PublicHealthRisk.HIGH
MODERATE_RISK = PublicHealthRisk.MODERATE


def _software_rule(function, reference, result, gate, want):
    """A 4.5 to 4.8 paragraph: programmable, gate yes, then want(level) true."""
    rule_id = f"{PREFIX}-{reference}"
    inside = _programmable(function, rule_id, reference)
    if inside is not True:
        return inside
    opened = _yes(function, gate, rule_id, reference)
    if opened is not Tri.YES:
        return opened if isinstance(opened, Pending) else None
    outcome = want(function, rule_id, reference)
    if outcome is not True:
        return outcome if isinstance(outcome, Pending) else None
    return RuleHit(rule_id, cite(reference), result, _because(function.general, gate))


def _level(function, rule_id, reference, names):
    values = {}
    for name in names:
        value = _enum(function, name, rule_id, reference)
        if isinstance(value, Pending):
            return value
        values[name] = value
    return values


def _to_professional(function, rule_id, reference):
    value = _enum(function, "decision_maker", rule_id, reference)
    if isinstance(value, Pending):
        return value
    return value is DecisionMaker.INFORMS_PROFESSIONAL


def _diagnosis_level(professional: bool, which: str):
    """want() for 4.5: professional selects (1) or (2); which is the level."""
    def want(function, rule_id, reference):
        to_pro = _to_professional(function, rule_id, reference)
        if isinstance(to_pro, Pending):
            return to_pro
        if to_pro is not professional:
            return None
        v = _level(function, rule_id, reference, ("condition_severity", "public_health_risk"))
        if isinstance(v, Pending):
            return v
        death = v["condition_severity"] is ConditionSeverity.DEATH_WITHOUT_URGENT_TREATMENT
        high = v["public_health_risk"] is HIGH_RISK
        serious = (v["condition_severity"] is ConditionSeverity.SERIOUS
                   or v["public_health_risk"] is MODERATE_RISK)
        return {"death": death, "high": high, "serious": serious and not (death or high),
                "other": not (death or high or serious)}[which]
    return want


def _monitoring_level(which: str):
    def want(function, rule_id, reference):
        v = _level(function, rule_id, reference, ("monitoring_danger", "public_health_risk"))
        if isinstance(v, Pending):
            return v
        top = (v["monitoring_danger"] is MonitoringDanger.IMMEDIATE
               or v["public_health_risk"] is HIGH_RISK)
        mid = (v["monitoring_danger"] is MonitoringDanger.OTHER
               or v["public_health_risk"] is MODERATE_RISK)
        return {"a": top, "b": mid and not top, "c": not (top or mid)}[which]
    return want


def _treatment_level(professional: bool, which: str):
    def want(function, rule_id, reference):
        to_pro = _to_professional(function, rule_id, reference)
        if isinstance(to_pro, Pending):
            return to_pro
        if to_pro is not professional:
            return None
        v = _level(function, rule_id, reference, ("treatment_risk", "public_health_risk"))
        if isinstance(v, Pending):
            return v
        death = v["treatment_risk"] is TreatmentRisk.DEATH_OR_SEVERE_DETERIORATION
        high = v["public_health_risk"] is HIGH_RISK
        harm = v["treatment_risk"] is TreatmentRisk.OTHER_HARM
        moderate = v["public_health_risk"] is MODERATE_RISK
        top = death or high
        return {"a(i)": death, "a(ii)": high, "b(i)": harm and not top,
                "b(ii)": moderate and not top,
                "c": not (top or harm or moderate)}[which]
    return want


def _information_level(level):
    def want(function, rule_id, reference):
        value = _enum(function, "information_therapy_harm", rule_id, reference)
        if isinstance(value, Pending):
            return value
        return value is level
    return want


DIAGNOSES = "diagnoses_or_screens"
MONITORS = "monitors_disease_state"
TREATS = "specifies_or_recommends_treatment"
INFORMS = "provides_therapy_through_information"


def rule_4_5_1_c_i(function: FunctionProfile):
    """Schedule 2 clause 4.5(1)(c)(i).

    (1) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to:

    (a) provide a diagnosis of a disease or condition; or

    (b) screen for a disease or condition;

    is classified as:

    (c) in the case of a disease or condition that:

    (i) may lead to the death of a person, or a severe deterioration in the
    state of a person’s health, without urgent treatment; or

    Class III; or
    """
    return _software_rule(function, "4.5(1)(c)(i)", "Class III", DIAGNOSES,
                          _diagnosis_level(False, "death"))


def rule_4_5_1_c_ii(function: FunctionProfile):
    """Schedule 2 clause 4.5(1)(c)(ii).

    (1) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to:

    (c) in the case of a disease or condition that:

    (ii) may pose a high risk to public health;

    Class III; or
    """
    return _software_rule(function, "4.5(1)(c)(ii)", "Class III", DIAGNOSES,
                          _diagnosis_level(False, "high"))


def rule_4_5_1_d(function: FunctionProfile):
    """Schedule 2 clause 4.5(1)(d).

    (1) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to:

    (d) in the case of a serious disease or serious condition or a disease or
    condition that may pose a moderate risk to public health, and where
    paragraph (c) does not apply – Class IIb; or
    """
    return _software_rule(function, "4.5(1)(d)", "Class IIb", DIAGNOSES,
                          _diagnosis_level(False, "serious"))


def rule_4_5_1_e(function: FunctionProfile):
    """Schedule 2 clause 4.5(1)(e).

    (1) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to:

    (e) in any other case – Class IIa.
    """
    return _software_rule(function, "4.5(1)(e)", "Class IIa", DIAGNOSES,
                          _diagnosis_level(False, "other"))


def rule_4_5_2_a_i(function: FunctionProfile):
    """Schedule 2 clause 4.5(2)(a)(i).

    (2) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to provide
    information to a relevant health professional for the purposes of the
    health professional making a diagnosis of a disease or condition:

    (a) in the case of a disease or condition that:

    (i) may lead to the death of a person, or a severe deterioration in the
    state of a person’s health, without urgent treatment; or

    is classified as Class IIb; or
    """
    return _software_rule(function, "4.5(2)(a)(i)", "Class IIb", DIAGNOSES,
                          _diagnosis_level(True, "death"))


def rule_4_5_2_a_ii(function: FunctionProfile):
    """Schedule 2 clause 4.5(2)(a)(ii).

    (2) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to provide
    information to a relevant health professional for the purposes of the
    health professional making a diagnosis of a disease or condition:

    (ii) may pose a high risk to public health;

    is classified as Class IIb; or
    """
    return _software_rule(function, "4.5(2)(a)(ii)", "Class IIb", DIAGNOSES,
                          _diagnosis_level(True, "high"))


def rule_4_5_2_b(function: FunctionProfile):
    """Schedule 2 clause 4.5(2)(b).

    (2) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to provide
    information to a relevant health professional for the purposes of the
    health professional making a diagnosis of a disease or condition:

    (b) in the case of a serious disease or serious condition or a disease or
    condition that may pose a moderate risk to public health, and where
    paragraph (a) does not apply – is classified as Class IIa; or
    """
    return _software_rule(function, "4.5(2)(b)", "Class IIa", DIAGNOSES,
                          _diagnosis_level(True, "serious"))


def rule_4_5_2_c(function: FunctionProfile):
    """Schedule 2 clause 4.5(2)(c).

    (2) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to provide
    information to a relevant health professional for the purposes of the
    health professional making a diagnosis of a disease or condition:

    (c) in any other case – is classified as Class I.
    """
    return _software_rule(function, "4.5(2)(c)", "Class I", DIAGNOSES,
                          _diagnosis_level(True, "other"))


def rule_4_6_a(function: FunctionProfile):
    """Schedule 2 clause 4.6(a).

    A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to provide
    information that is to be used for monitoring the state or progression of
    a disease or condition of a person or the parameters in relation to a
    person:

    (a) in the case where the information to be provided could indicate that
    the person or another person may be in immediate danger or that there may
    be a high risk to public health – is classified as Class IIb; or
    """
    return _software_rule(function, "4.6(a)", "Class IIb", MONITORS, _monitoring_level("a"))


def rule_4_6_b(function: FunctionProfile):
    """Schedule 2 clause 4.6(b).

    A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to provide
    information that is to be used for monitoring the state or progression of
    a disease or condition of a person or the parameters in relation to a
    person:

    (b) in the case where the information to be provided could indicate that
    the person or another person may be in other danger or that there may be
    a moderate risk to public health – is classified as Class IIa; or
    """
    return _software_rule(function, "4.6(b)", "Class IIa", MONITORS, _monitoring_level("b"))


def rule_4_6_c(function: FunctionProfile):
    """Schedule 2 clause 4.6(c).

    A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to provide
    information that is to be used for monitoring the state or progression of
    a disease or condition of a person or the parameters in relation to a
    person:

    (c) in any other case – is classified as Class I.
    """
    return _software_rule(function, "4.6(c)", "Class I", MONITORS, _monitoring_level("c"))


def rule_4_7_1_a_i(function: FunctionProfile):
    """Schedule 2 clause 4.7(1)(a)(i).

    (1) Subject to subclause (2), a programmed or programmable medical
    device, or software that is a medical device, that is intended by the
    manufacturer to be used to specify or recommend a treatment or
    intervention:

    (a) in the case where the absence of the treatment or intervention or
    where the treatment or intervention itself:

    (i) may lead to the death of a person or a severe deterioration in the
    state of a person’s health; or

    is classified as Class III; or
    """
    return _software_rule(function, "4.7(1)(a)(i)", "Class III", TREATS,
                          _treatment_level(False, "a(i)"))


def rule_4_7_1_a_ii(function: FunctionProfile):
    """Schedule 2 clause 4.7(1)(a)(ii).

    (1) Subject to subclause (2), a programmed or programmable medical
    device, or software that is a medical device, that is intended by the
    manufacturer to be used to specify or recommend a treatment or
    intervention:

    (ii) may pose a high risk to public health;

    is classified as Class III; or
    """
    return _software_rule(function, "4.7(1)(a)(ii)", "Class III", TREATS,
                          _treatment_level(False, "a(ii)"))


def rule_4_7_1_b_i(function: FunctionProfile):
    """Schedule 2 clause 4.7(1)(b)(i).

    (1) Subject to subclause (2), a programmed or programmable medical
    device, or software that is a medical device, that is intended by the
    manufacturer to be used to specify or recommend a treatment or
    intervention:

    (b) in the case where the absence of the treatment or intervention or
    where the treatment or intervention itself:

    (i) may otherwise be harmful to a person; or

    is classified as Class IIb; or
    """
    return _software_rule(function, "4.7(1)(b)(i)", "Class IIb", TREATS,
                          _treatment_level(False, "b(i)"))


def rule_4_7_1_b_ii(function: FunctionProfile):
    """Schedule 2 clause 4.7(1)(b)(ii).

    (1) Subject to subclause (2), a programmed or programmable medical
    device, or software that is a medical device, that is intended by the
    manufacturer to be used to specify or recommend a treatment or
    intervention:

    (ii) may pose a moderate risk to public health;

    is classified as Class IIb; or
    """
    return _software_rule(function, "4.7(1)(b)(ii)", "Class IIb", TREATS,
                          _treatment_level(False, "b(ii)"))


def rule_4_7_1_c(function: FunctionProfile):
    """Schedule 2 clause 4.7(1)(c).

    (1) Subject to subclause (2), a programmed or programmable medical
    device, or software that is a medical device, that is intended by the
    manufacturer to be used to specify or recommend a treatment or
    intervention:

    (c) in any other case – is classified as Class IIa.
    """
    return _software_rule(function, "4.7(1)(c)", "Class IIa", TREATS,
                          _treatment_level(False, "c"))


def rule_4_7_2_a_i(function: FunctionProfile):
    """Schedule 2 clause 4.7(2)(a)(i).

    (2) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to
    recommend a treatment or intervention (the recommended treatment or
    intervention) to a relevant health professional for the purposes of the
    health professional making a decision about the treatment or
    intervention:

    (a) in the case where the absence of the recommended treatment or
    intervention or where the recommended treatment or intervention itself:

    (i) may lead to the death of a person or a severe deterioration in the
    state of a person’s health; or

    is classified as Class IIb; or
    """
    return _software_rule(function, "4.7(2)(a)(i)", "Class IIb", TREATS,
                          _treatment_level(True, "a(i)"))


def rule_4_7_2_a_ii(function: FunctionProfile):
    """Schedule 2 clause 4.7(2)(a)(ii).

    (2) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to
    recommend a treatment or intervention (the recommended treatment or
    intervention) to a relevant health professional for the purposes of the
    health professional making a decision about the treatment or
    intervention:

    (ii) may pose a high risk to public health;

    is classified as Class IIb; or
    """
    return _software_rule(function, "4.7(2)(a)(ii)", "Class IIb", TREATS,
                          _treatment_level(True, "a(ii)"))


def rule_4_7_2_b_i(function: FunctionProfile):
    """Schedule 2 clause 4.7(2)(b)(i).

    (2) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to
    recommend a treatment or intervention (the recommended treatment or
    intervention) to a relevant health professional for the purposes of the
    health professional making a decision about the treatment or
    intervention:

    (b) in the case where the absence of the recommended treatment or
    intervention or where the recommended treatment or intervention itself:

    (i) may otherwise be harmful to a person; or

    is classified as Class IIa; or
    """
    return _software_rule(function, "4.7(2)(b)(i)", "Class IIa", TREATS,
                          _treatment_level(True, "b(i)"))


def rule_4_7_2_b_ii(function: FunctionProfile):
    """Schedule 2 clause 4.7(2)(b)(ii).

    (2) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to
    recommend a treatment or intervention (the recommended treatment or
    intervention) to a relevant health professional for the purposes of the
    health professional making a decision about the treatment or
    intervention:

    (ii) may pose a moderate risk to public health;

    is classified as Class IIa; or
    """
    return _software_rule(function, "4.7(2)(b)(ii)", "Class IIa", TREATS,
                          _treatment_level(True, "b(ii)"))


def rule_4_7_2_c(function: FunctionProfile):
    """Schedule 2 clause 4.7(2)(c).

    (2) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to
    recommend a treatment or intervention (the recommended treatment or
    intervention) to a relevant health professional for the purposes of the
    health professional making a decision about the treatment or
    intervention:

    (c) in any other case – is classified as Class I.
    """
    return _software_rule(function, "4.7(2)(c)", "Class I", TREATS,
                          _treatment_level(True, "c"))


def rule_4_8_a(function: FunctionProfile):
    """Schedule 2 clause 4.8(a).

    A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to provide therapy to
    a person through the provision of information to the person:

    (a) in the case of therapy that may result in the death of the person or a
    severe deterioration in the state of the person’s health – is classified
    as Class III; or
    """
    return _software_rule(function, "4.8(a)", "Class III", INFORMS,
                          _information_level(InformationTherapyHarm.DEATH_OR_SEVERE_DETERIORATION))


def rule_4_8_b(function: FunctionProfile):
    """Schedule 2 clause 4.8(b).

    A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to provide therapy to
    a person through the provision of information to the person:

    (b) in the case of therapy that may cause serious harm to the person and
    where paragraph (a) does not apply – is classified as Class IIb; or
    """
    return _software_rule(function, "4.8(b)", "Class IIb", INFORMS,
                          _information_level(InformationTherapyHarm.SERIOUS_HARM))


def rule_4_8_c(function: FunctionProfile):
    """Schedule 2 clause 4.8(c).

    A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to provide therapy to
    a person through the provision of information to the person:

    (c) in the case of therapy that may cause harm to the person and where
    neither paragraph (a) nor (b) applies – is classified as Class IIa; or
    """
    return _software_rule(function, "4.8(c)", "Class IIa", INFORMS,
                          _information_level(InformationTherapyHarm.HARM))


def rule_4_8_d(function: FunctionProfile):
    """Schedule 2 clause 4.8(d).

    A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to provide therapy to
    a person through the provision of information to the person:

    (d) in any other case – is classified as Class I.
    """
    return _software_rule(function, "4.8(d)", "Class I", INFORMS,
                          _information_level(InformationTherapyHarm.NONE))


PART_4 = [
    rule_4_1,
    rule_4_2_1, rule_4_2_2, rule_4_2_3, rule_4_2_4,
    rule_4_3_2_a, rule_4_3_2_b, rule_4_3_2_c, rule_4_3_3_a, rule_4_3_3_b, rule_4_3_3_c,
    rule_4_4_1, rule_4_4_2,
    rule_4_5_1_c_i, rule_4_5_1_c_ii, rule_4_5_1_d, rule_4_5_1_e,
    rule_4_5_2_a_i, rule_4_5_2_a_ii, rule_4_5_2_b, rule_4_5_2_c,
    rule_4_6_a, rule_4_6_b, rule_4_6_c,
    rule_4_7_1_a_i, rule_4_7_1_a_ii, rule_4_7_1_b_i, rule_4_7_1_b_ii, rule_4_7_1_c,
    rule_4_7_2_a_i, rule_4_7_2_a_ii, rule_4_7_2_b_i, rule_4_7_2_b_ii, rule_4_7_2_c,
    rule_4_8_a, rule_4_8_b, rule_4_8_c, rule_4_8_d,
]


# --------------------------------------------------------------------------
# Part 5, particular kinds of devices
# --------------------------------------------------------------------------


def _yes(function: FunctionProfile, name: str, rule_id: str, reference: str):
    """YES, NO or a Pending for one general field."""
    return _lookup(function.general, name, rule_id, reference)


def _physical(function: FunctionProfile, rule_id: str, reference: str):
    """True for a device that is not software alone; the material clauses."""
    software = known(function.is_software)
    if software is None:
        return Pending(rule_id, cite(reference), "is_software is unresolved", ("is_software",))
    return True if software is Tri.NO else None


def _route_is(function: FunctionProfile, routes, rule_id: str, reference: str):
    route = function.general.invasiveness
    if not route.resolved or route.value is None:
        return Pending(rule_id, cite(reference), "invasiveness is unresolved",
                       ("general.invasiveness",))
    return True if route.value in routes else None


def _active_or_software(function: FunctionProfile, rule_id: str, reference: str):
    """5.7(3) needs an active medical device; software always is one."""
    return _active(function, rule_id, reference)


def _chain(function: FunctionProfile, rule_id: str, reference: str, result: str,
           checks, yes=(), no=(), displaces=()):
    """Run applicability checks, then fields that must be yes and fields that must be no."""
    for check in checks:
        outcome = check(function, rule_id, reference)
        if outcome is not True:
            return outcome
    for name in yes:
        value = _yes(function, name, rule_id, reference)
        if value is not Tri.YES:
            return value if isinstance(value, Pending) else None
    for name in no:
        value = _yes(function, name, rule_id, reference)
        if value is not Tri.NO:
            return value if isinstance(value, Pending) else None
    return RuleHit(rule_id, cite(reference), result,
                   _because(function.general, *yes, *no), displaces)


def _physical_check(function, rule_id, reference):
    return _physical(function, rule_id, reference)


def _implantable(function, rule_id, reference):
    return _route_is(function, (Invasiveness.IMPLANTABLE,), rule_id, reference)


def _software_only(function, rule_id, reference):
    software = known(function.is_software)
    if software is None:
        return Pending(rule_id, cite(reference), "is_software is unresolved", ("is_software",))
    return True if software is Tri.YES else None


IMAGING = "records_images_or_anatomical_model"
INHALATION = "administers_by_inhalation"
SUBSTANCE = "is_substance_through_orifice_or_skin"


def rule_5_1(function: FunctionProfile):
    """Schedule 2 clause 5.1(2).

    (1) This clause applies to a medical device of any kind that incorporates,
    or is intended to incorporate, as an integral part, a substance that:

    (a) if used separately, would be a medicine; and

    (b) is liable to act on a patient’s body with action ancillary to that of
    the device.

    (2) The device is classified as Class III.

    (3) For the purposes of this clause, any stable derivative of human blood
    or human plasma is considered to be a medicine.
    """
    rule_id, reference = f"{PREFIX}-5.1(2)", "5.1(2)"
    medicine = _yes(function, "incorporates_medicine", rule_id, reference)
    if medicine is Tri.YES:
        return RuleHit(rule_id, cite(reference), "Class III",
                       _because(function.general, "incorporates_medicine"))
    blood = None
    if _physical(function, rule_id, reference) is True:
        blood = _yes(function, "human_blood_derivative", rule_id, reference)
        if blood is Tri.YES:
            return RuleHit(rule_id, cite(reference), "Class III",
                           _because(function.general, "human_blood_derivative"))
    for value in (medicine, blood, _physical(function, rule_id, reference)):
        if isinstance(value, Pending):
            return value
    return None


def _long_term_invasive(function: FunctionProfile, rule_id: str, reference: str):
    """5.2(2): implantable, or invasive and intended for long-term use."""
    route = _route_is(function, (Invasiveness.IMPLANTABLE,), rule_id, reference)
    if isinstance(route, Pending) or route is True:
        return route
    if function.general.invasiveness.value is Invasiveness.NON_INVASIVE:
        return None
    duration = function.general.duration
    if not duration.resolved or duration.value is None:
        return Pending(rule_id, cite(reference), "duration is unresolved", ("general.duration",))
    return True if duration.value is Duration.LONG_TERM else None


def rule_5_2_1(function: FunctionProfile):
    """Schedule 2 clause 5.2(1).

    (1) Subject to subclause (2), a medical device that is intended by the
    manufacturer to be used for contraception, or the prevention of sexually
    transmitted diseases, is classified as Class IIb.
    """
    rule_id, reference = f"{PREFIX}-5.2(1)", "5.2(1)"
    hit = _chain(function, rule_id, reference, "Class IIb", (),
                 yes=("contraceptive_or_sti_prevention",))
    if not isinstance(hit, RuleHit):
        return hit
    long_term = _long_term_invasive(function, rule_id, reference)
    if long_term is True:
        return None          # subclause (2) gives Class III instead
    return long_term if isinstance(long_term, Pending) else hit


def rule_5_2_2(function: FunctionProfile):
    """Schedule 2 clause 5.2(2).

    (2) If the device is an implantable medical device or an invasive medical
    device that is intended for long-term use, the device is classified as
    Class III.
    """
    rule_id, reference = f"{PREFIX}-5.2(2)", "5.2(2)"
    hit = _chain(function, rule_id, reference, "Class III", (),
                 yes=("contraceptive_or_sti_prevention",))
    if not isinstance(hit, RuleHit):
        return hit
    long_term = _long_term_invasive(function, rule_id, reference)
    if long_term is not True:
        return long_term
    return hit


def rule_5_3_1(function: FunctionProfile):
    """Schedule 2 clause 5.3(1).

    (1) A medical device that is intended by the manufacturer specifically to
    be used for disinfecting, cleaning, rinsing or hydrating contact lenses is
    classified as Class IIb.
    """
    return _chain(function, f"{PREFIX}-5.3(1)", "5.3(1)", "Class IIb", (),
                  yes=("cares_for_contact_lenses",))


def rule_5_3_2(function: FunctionProfile):
    """Schedule 2 clause 5.3(2).

    (2) A medical device that is intended by the manufacturer specifically to
    be used for disinfecting another medical device is classified as Class
    IIb.
    """
    return _chain(function, f"{PREFIX}-5.3(2)", "5.3(2)", "Class IIb", (),
                  yes=("disinfects_another_device",))


def rule_5_4_1(function: FunctionProfile):
    """Schedule 2 clause 5.4(1).

    (1) If:

    (a) a medical device is intended by the manufacturer to be used to record
    patient images that are to be used for either or both of the following:

    (i) the diagnosis or monitoring of a disease, injury or disability;

    (ii) the investigation of the anatomy or of a physiological process; and

    (b) the images are to be acquired through a method that relies on energy
    outside the visible spectrum;

    the device is classified as Class IIa.
    """
    return _chain(function, f"{PREFIX}-5.4(1)", "5.4(1)", "Class IIa", (),
                  yes=(IMAGING, "records_patient_images_outside_visible_spectrum"))


def rule_5_4_2(function: FunctionProfile):
    """Schedule 2 clause 5.4(2).

    (2) A medical device that is an anatomical model (whether physical or
    virtual) that is intended by the manufacturer to be used for either or
    both of the following:

    (a) the diagnosis or monitoring of a disease, injury or disability;

    (b) the investigation of the anatomy or of a physiological process;

    is classified as Class IIa.
    """
    return _chain(function, f"{PREFIX}-5.4(2)", "5.4(2)", "Class IIa", (),
                  yes=(IMAGING, "is_anatomical_model_for_diagnosis"))


def rule_5_4_3(function: FunctionProfile):
    """Schedule 2 clause 5.4(3).

    (3) A programmed or programmable medical device, or software that is a
    medical device, that is intended by the manufacturer to be used to
    generate a virtual anatomical model that is to be used for either or both
    of the following:

    (a) the diagnosis or monitoring of a disease, injury or disability;

    (b) the investigation of the anatomy or of a physiological process;

    is classified as Class IIa.
    """
    return _chain(function, f"{PREFIX}-5.4(3)", "5.4(3)", "Class IIa", (_software_only,),
                  yes=(IMAGING, "generates_virtual_anatomical_model"))


def rule_5_5(function: FunctionProfile):
    """Schedule 2 clause 5.5(3).

    (1) Subject to subclause (2), this clause applies to a medical device if
    the device contains any of the following:

    (a) non-viable tissues, or cells, of animal origin (other than tissues or
    cells from hair or wool);

    (b) derivatives of tissues or cells covered by paragraph (a) (other than
    sintered hydroxyapatite or tallow derivatives).

    (2) This clause does not apply to a medical device if the device is
    intended by the manufacturer to come into contact with intact skin only.

    (3) A device to which this clause applies is classified as Class III.
    """
    return _chain(function, f"{PREFIX}-5.5(3)", "5.5(3)", "Class III", (_physical_check,),
                  yes=("contains_non_viable_animal_material",),
                  no=("contacts_intact_skin_only",))


def rule_5_6(function: FunctionProfile):
    """Schedule 2 clause 5.6.

    A medical device that is a blood bag is classified as Class IIb.
    """
    return _chain(function, f"{PREFIX}-5.6", "5.6", "Class IIb", (_physical_check,),
                  yes=("is_blood_bag",))


def rule_5_7_1(function: FunctionProfile):
    """Schedule 2 clause 5.7(1).

    (1) An active implantable medical device is classified as Class III.
    """
    return _chain(function, f"{PREFIX}-5.7(1)", "5.7(1)", "Class III", (_implantable,),
                  yes=("is_active_implantable",))


def rule_5_7_2(function: FunctionProfile):
    """Schedule 2 clause 5.7(2).

    (2) An implantable accessory to an active implantable medical device is
    classified as Class III.
    """
    return _chain(function, f"{PREFIX}-5.7(2)", "5.7(2)", "Class III", (_implantable,),
                  yes=("implantable_accessory_to_active_implantable",))


def rule_5_7_3(function: FunctionProfile):
    """Schedule 2 clause 5.7(3).

    (3) An active medical device that is intended by the manufacturer to be
    used to control or monitor, or directly influence, the performance of an
    active implantable medical device is classified as Class III.
    """
    return _chain(function, f"{PREFIX}-5.7(3)", "5.7(3)", "Class III", (_active_or_software,),
                  yes=("controls_active_implantable",))


EVERY_OTHER_CLAUSE = clauses(
    PREFIX, "2.1", "2.2", "2.2A", "2.3", "2.4", "3.1", "3.2", "3.3", "3.4",
    "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8",
    "5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "5.9", "5.10", "5.11",
)


def rule_5_8(function: FunctionProfile):
    """Schedule 2 clause 5.8.

    Despite any other classification in this Schedule, a medical device that
    is intended by the manufacturer to be for export only is classified as
    Class I.
    """
    return _chain(function, f"{PREFIX}-5.8", "5.8", "Class I", (), yes=("is_export_only",),
                  displaces=EVERY_OTHER_CLAUSE)


def rule_5_9(function: FunctionProfile):
    """Schedule 2 clause 5.9.

    A medical device that is a mammary implant is classified as Class III.
    """
    return _chain(function, f"{PREFIX}-5.9", "5.9", "Class III", (_implantable,),
                  yes=("is_mammary_implant",))


def rule_5_10_a(function: FunctionProfile):
    """Schedule 2 clause 5.10(a).

    If a medical device is intended to be used to administer medicines or
    biologicals by inhalation:

    (a) if the mode of action of the device has an essential impact on the
    efficacy and safety of the medicines or biologicals – the device is
    classified as Class IIb; or
    """
    return _chain(function, f"{PREFIX}-5.10(a)", "5.10(a)", "Class IIb", (_physical_check,),
                  yes=(INHALATION, "inhalation_mode_of_action_essential"))


def rule_5_10_b(function: FunctionProfile):
    """Schedule 2 clause 5.10(b).

    If a medical device is intended to be used to administer medicines or
    biologicals by inhalation:

    (b) if the device is intended to treat a life-threatening condition – the
    device is classified as Class IIb; or
    """
    return _chain(function, f"{PREFIX}-5.10(b)", "5.10(b)", "Class IIb", (_physical_check,),
                  yes=(INHALATION, "inhalation_treats_life_threatening_condition"))


def rule_5_10_c(function: FunctionProfile):
    """Schedule 2 clause 5.10(c).

    If a medical device is intended to be used to administer medicines or
    biologicals by inhalation:

    (c) if paragraphs (a) and (b) do not apply – the device is classified as
    Class IIa.
    """
    return _chain(function, f"{PREFIX}-5.10(c)", "5.10(c)", "Class IIa", (_physical_check,),
                  yes=(INHALATION,),
                  no=("inhalation_mode_of_action_essential",
                      "inhalation_treats_life_threatening_condition"))


def rule_5_11_c(function: FunctionProfile):
    """Schedule 2 clause 5.11(c).

    If a medical device is composed of substances, or combinations of
    substances, that are intended to be:

    (a) introduced into the human body through a body orifice; or

    (b) applied to and absorbed by the skin;

    the device is classified as follows:

    (c) if the device is introduced into the nasal or oral cavity as far as
    the pharynx, or is applied to and absorbed by the skin, and achieves its
    intended purpose in that cavity or on the skin – Class IIa;
    """
    return _chain(function, f"{PREFIX}-5.11(c)", "5.11(c)", "Class IIa", (_physical_check,),
                  yes=(SUBSTANCE, "substance_acts_in_nose_mouth_or_on_skin"))


def rule_5_11_d(function: FunctionProfile):
    """Schedule 2 clause 5.11(d).

    If a medical device is composed of substances, or combinations of
    substances, that are intended to be:

    (a) introduced into the human body through a body orifice; or

    (b) applied to and absorbed by the skin;

    the device is classified as follows:

    (d) in any other case – Class IIb.
    """
    return _chain(function, f"{PREFIX}-5.11(d)", "5.11(d)", "Class IIb", (_physical_check,),
                  yes=(SUBSTANCE,), no=("substance_acts_in_nose_mouth_or_on_skin",))


PART_5 = [
    rule_5_1,
    rule_5_2_1,
    rule_5_2_2,
    rule_5_3_1,
    rule_5_3_2,
    rule_5_4_1,
    rule_5_4_2,
    rule_5_4_3,
    rule_5_5,
    rule_5_6,
    rule_5_7_1,
    rule_5_7_2,
    rule_5_7_3,
    rule_5_8,
    rule_5_9,
    rule_5_10_a,
    rule_5_10_b,
    rule_5_10_c,
    rule_5_11_c,
    rule_5_11_d,
]


NO_PATIENT_CONTACT = Flag(
    severity=Severity.AMBER,
    code="s2_5_5_no_patient_contact",
    message=(
        "Classified Class III under Schedule 2 clause 5.5 for animal-derived "
        "material, on a device that appears to touch no patient. Subclause (2) "
        "excludes devices intended to contact intact skin only; it has been read "
        "as not reaching a device with no patient contact. Confirm that reading "
        "before relying on Class III."
    ),
)


def _flags(function: FunctionProfile, result: Classification) -> list[Flag]:
    live = {h.rule_id for h in result.hits if h.rule_id not in result.displaced}
    general = function.general
    flags = []
    if (
        f"{PREFIX}-5.5(3)" in live
        and general.invasiveness.value is Invasiveness.NON_INVASIVE
        and known(general.contacts_injured_skin_or_mucous_membrane) is Tri.NO
    ):
        flags.append(NO_PATIENT_CONTACT)
    if (
        any(rule_id.startswith(f"{PREFIX}-3.1(2)") for rule_id in live)
        and known(general.connected_to_an_active_device) is Tri.YES
    ):
        flags.append(CLASS_I_ACTIVE_CONNECTION)
    return flags


# The class each paragraph gives, which is the most an unresolved one could
# give. Clause 5.8 opens "Despite" and is left out: it can displace a higher
# class, so an unresolved 5.8 always blocks.
DESPITE = frozenset({f"{PREFIX}-5.8"})

CEILINGS = {f"{PREFIX}-{reference}": result for reference, result in {
    "2.1": "Class I",
    "2.2(1)(a)": "Class IIa", "2.2(1)(b)": "Class IIa", "2.2(1)(c)": "Class IIa",
    "2.2A": "Class IIa",
    "2.3(1)": "Class IIb", "2.3(2)": "Class IIa",
    "2.4(2)": "Class IIa", "2.4(3)": "Class I", "2.4(4)": "Class IIb",
    "3.1(2)(a)": "Class I", "3.1(2)(b)(i)": "Class IIa", "3.1(2)(b)(ii)": "Class I",
    "3.1(2)(c)(i)": "Class IIb", "3.1(2)(c)(ii)": "Class IIa", "3.1(3)": "Class IIa",
    "3.2(2)": "Class IIa", "3.2(3)": "Class III", "3.2(3A)": "Class III",
    "3.2(4)": "Class I",
    "3.2(5)(a)": "Class IIb", "3.2(5)(b)": "Class IIb", "3.2(5)(c)": "Class IIb",
    "3.2(5)(d)": "Class IIb",
    "3.3(2)": "Class IIa",
    "3.3(3)(a)": "Class IIb", "3.3(3)(b)": "Class IIb", "3.3(3)(c)": "Class IIb",
    "3.3(4)(a)": "Class III", "3.3(4)(b)": "Class III", "3.3(4)(c)": "Class III",
    "3.3(4)(d)": "Class III",
    "3.4(2)": "Class IIb", "3.4(3)": "Class IIa",
    "3.4(4)(a)": "Class III", "3.4(4)(b)": "Class III", "3.4(4)(c)": "Class III",
    "3.4(4)(d)": "Class III", "3.4(4)(e)": "Class III",
    "3.4(4A)": "Class III", "3.4(4B)": "Class III",
    "4.1": "Class I",
    "4.2(1)": "Class IIa", "4.2(2)": "Class IIb", "4.2(3)": "Class IIb",
    "4.2(4)": "Class III",
    "4.3(2)(a)": "Class IIa", "4.3(2)(b)": "Class IIa", "4.3(2)(c)": "Class IIa",
    "4.3(3)(a)": "Class IIb", "4.3(3)(b)": "Class IIb", "4.3(3)(c)": "Class IIb",
    "4.4(1)": "Class IIa", "4.4(2)": "Class IIb",
    "4.5(1)(c)(i)": "Class III", "4.5(1)(c)(ii)": "Class III",
    "4.5(1)(d)": "Class IIb", "4.5(1)(e)": "Class IIa",
    "4.5(2)(a)(i)": "Class IIb", "4.5(2)(a)(ii)": "Class IIb",
    "4.5(2)(b)": "Class IIa", "4.5(2)(c)": "Class I",
    "4.6(a)": "Class IIb", "4.6(b)": "Class IIa", "4.6(c)": "Class I",
    "4.7(1)(a)(i)": "Class III", "4.7(1)(a)(ii)": "Class III",
    "4.7(1)(b)(i)": "Class IIb", "4.7(1)(b)(ii)": "Class IIb", "4.7(1)(c)": "Class IIa",
    "4.7(2)(a)(i)": "Class IIb", "4.7(2)(a)(ii)": "Class IIb",
    "4.7(2)(b)(i)": "Class IIa", "4.7(2)(b)(ii)": "Class IIa", "4.7(2)(c)": "Class I",
    "4.8(a)": "Class III", "4.8(b)": "Class IIb", "4.8(c)": "Class IIa",
    "4.8(d)": "Class I",
    "5.1(2)": "Class III",
    "5.2(1)": "Class IIb", "5.2(2)": "Class III",
    "5.3(1)": "Class IIb", "5.3(2)": "Class IIb",
    "5.4(1)": "Class IIa", "5.4(2)": "Class IIa", "5.4(3)": "Class IIa",
    "5.5(3)": "Class III",
    "5.6": "Class IIb",
    "5.7(1)": "Class III", "5.7(2)": "Class III", "5.7(3)": "Class III",
    "5.9": "Class III",
    "5.10(a)": "Class IIb", "5.10(b)": "Class IIb", "5.10(c)": "Class IIa",
    "5.11(c)": "Class IIa", "5.11(d)": "Class IIb",
}.items()}


def evaluate(function: FunctionProfile) -> Classification:
    general = function.general
    outcomes = [rule(general) for rule in PART_2]
    outcomes += [rule(function) for rule in PART_3]
    outcomes += [rule(function) for rule in PART_4]
    outcomes += [rule(function) for rule in PART_5]
    outcomes = apply_ceilings(outcomes, CEILINGS, DESPITE)
    result = resolve(outcomes, GENERAL_ORDER)
    result.flags = _flags(function, result)
    return result
