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

Not written yet: Parts 3 and 4. Each returns a Pending that blocks the
result where the Part could apply, so a class is never given while a higher
clause might still be waiting:

- Part 3 applies only to invasive devices, so it blocks only when the route
  is invasive or unknown.
- Part 4 applies to active devices (4.1 to 4.4) and to programmed or
  programmable devices and software (4.5 to 4.8), so it blocks only when the
  device is active or software, or either is unknown.
"""

from ..flags import Flag, Severity
from ..profile import (
    GENERAL_ORDER,
    ActiveType,
    Duration,
    FunctionProfile,
    GeneralDeviceProfile,
    Invasiveness,
    Tri,
)
from .engine import REGULATIONS, Classification, Pending, RuleHit, clauses, known, resolve

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
    active = function.general.active_type
    software = known(function.is_software)
    if active.resolved and active.value in (ActiveType.THERAPEUTIC, ActiveType.DIAGNOSTIC):
        return True
    if software is Tri.YES:
        return True
    missing = []
    if not active.resolved or active.value is None:
        missing.append("general.active_type")
    if software is None:
        missing.append("is_software")
    if missing:
        return Pending(rule_id, cite(reference), "applicability is unresolved", tuple(missing))
    return None


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
    if (
        f"{PREFIX}-5.5(3)" in live
        and general.invasiveness.value is Invasiveness.NON_INVASIVE
        and known(general.contacts_injured_skin_or_mucous_membrane) is Tri.NO
    ):
        return [NO_PATIENT_CONTACT]
    return []


def evaluate(function: FunctionProfile) -> Classification:
    general = function.general
    outcomes = [rule(general) for rule in PART_2]
    outcomes += [rule(function) for rule in PART_5]
    outcomes += [part_3(function), part_4(function)]
    result = resolve(outcomes, GENERAL_ORDER)
    result.flags = _flags(function, result)
    return result
