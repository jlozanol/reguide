"""Build the fixture set.

Fixtures marked verified=true come from a TGA worked example, so the expected
class arrives with the rule that produces it. Fixtures marked verified=false
are reasoned from rule text rather than quoted from an example, or sit on a
point where sources disagree. The scoring harness counts only verified ones.
Promote a fixture to verified after checking it against the primary document.

Every fixture also records the regulatory status gate's expected verdict, for
the product and for each function. It is written by hand, never derived from
status.py, so the gate can be scored against it. A function the gate stops
(not a device, excluded, exempt CDSS) carries no expected class, because
classification never runs for it.

The therapeutic purpose limb recorded on each function is for the citation
only. The gate does not branch on which limb, only on whether one is reached.

Run:  python scripts/build_fixtures.py
"""

import json
from pathlib import Path

from reguide.profile import (
    ActiveType,
    Answer,
    Basis,
    BodyContact,
    ClinicalFunction,
    CoreProfile,
    DecisionMaker,
    DeviceKind,
    DeviceProfile,
    Duration,
    FluidHandling,
    FunctionProfile,
    GeneralDeviceProfile,
    highest_class,
    Invasiveness,
    IvdProfile,
    IvdPurpose,
    OrificeSite,
    PublicHealthRisk,
    Severity,
    StatusProfile,
    TherapeuticPurpose,
    Tri,
    WoundFunction,
)
from reguide.status import StatusOutcome

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
NOT_IVD = "TGA, Classifying medical devices that are not IVDs"
ACTIVE = "TGA, Classifying active medical devices in Australia"
IVD_GUIDE = "TGA, Classifying IVDs for supply in Australia"
RULE_TEXT = "Reasoned from Schedule 2 rule text, not a worked example"
GATE_TEXT = ("Reasoned from s41BD of the Act and Schedule 4 Part 2 of the "
             "Regulations, not a worked example")

REGULATED = StatusOutcome.REGULATED
NOT_A_DEVICE = StatusOutcome.NOT_A_DEVICE
EXCLUDED = StatusOutcome.EXCLUDED
EXEMPT_CDSS = StatusOutcome.EXEMPT_CDSS


def a(value, evidence):
    return Answer(value=value, basis=Basis.STATED, evidence=evidence)


GENERAL_DEFAULTS = dict(
    invasiveness=Invasiveness.NON_INVASIVE,
    active_type=ActiveType.NOT_ACTIVE,
    incorporates_medicine=Tri.NO,
    contraceptive_or_sti_prevention=Tri.NO,
    disinfects_another_device=Tri.NO,
    animal_or_microbial_origin=Tri.NO,
    human_blood_derivative=Tri.NO,
    contacts_injured_skin=Tri.NO,
    fluid_handling=FluidHandling.NONE,
)

IVD_DEFAULTS = dict(
    is_instrument_or_receptacle=Tri.NO,
    is_quality_control_material=Tri.NO,
    is_export_only=Tri.NO,
    purpose=IvdPurpose.OTHER,
    is_self_test=Tri.NO,
    is_near_patient_test=Tri.NO,
    detects_transmissible_agent=Tri.NO,
    transmission_risk_to_population=Tri.NO,
    disease_is_life_threatening=Tri.NO,
    result_drives_critical_decision=Tri.NO,
    sample_type="not stated",
)


# Answers to the gate's questions. Anything the gating does not ask for this
# function is cleared by prune() in product(), so a hardware device keeps no
# CDSS answers and a device keeps no accessory answer.
STATUS_DEFAULTS = dict(
    principal_action_pharmacological=Tri.NO,
    is_accessory_to_device=Tri.NO,
    excluded_item="none",
    # Software fixtures are regulated unless one says otherwise. Failing the
    # sole-purpose criterion is enough to keep a function out of the exemption.
    cdss_sole_purpose_recommendation=Tri.NO,
    cdss_processes_device_signal_or_image=Tri.NO,
    cdss_replaces_clinical_judgement=Tri.NO,
)

# Clinician-facing software that analyses images or signals from another
# device. Recommends to a professional without replacing judgement, but fails
# the exemption because of what it processes.
PROCESSES_DEVICE_DATA = dict(
    cdss_sole_purpose_recommendation=Tri.YES,
    cdss_processes_device_signal_or_image=Tri.YES,
    cdss_replaces_clinical_judgement=Tri.NO,
)

# A function with no therapeutic purpose of its own and no device it serves.
NO_PURPOSE = dict(therapeutic_purpose=TherapeuticPurpose.NONE,
                  is_accessory_to_device=Tri.NO)

# Consumer wellness tracking. Monitoring sleep or activity arguably reaches
# limb (iii), a physiological state, which is why item 14B exists to take it
# back out. Every condition of 14B holds: consumer use, general wellness,
# non-invasive, not for clinical practice, nothing about a serious condition.
WELLNESS_TRACKING = dict(therapeutic_purpose=TherapeuticPurpose.ANATOMY,
                         excluded_item="S1-14B",
                         exclusion_conditions_met=Tri.YES)

# Storage and transmission of patient images only. Storing images that serve
# diagnosis arguably reaches limb (i), which is why item 14H exists to take it
# back out. The fixture is worded as store and transmit ONLY on purpose: TGA
# guidance says 14H does not cover software that also displays images for
# diagnosis or screening, and such software is likely a regulated device. The
# class of an image display function is a stage 4 question; add a display
# fixture once the Schedule 2 rules exist.
IMAGE_STORAGE = dict(therapeutic_purpose=TherapeuticPurpose.DISEASE,
                     excluded_item="S1-14H",
                     exclusion_conditions_met=Tri.YES)


def status_for(text, purpose, overrides):
    fields = dict(STATUS_DEFAULTS, therapeutic_purpose=purpose)
    fields.update(overrides or {})
    return StatusProfile(**{k: a(v, text) for k, v in fields.items()})


def fn(name, text, **given):
    """One general-device function."""
    software = given.pop("software", Tri.NO)
    status = status_for(text, TherapeuticPurpose.DISEASE, given.pop("status", None))
    fields = dict(GENERAL_DEFAULTS)
    fields.update(given)
    if software is Tri.YES:
        for key in ("animal_or_microbial_origin", "human_blood_derivative"):
            fields.pop(key, None)
    return FunctionProfile(
        name=a(name, name),
        description=a(text, text),
        kind=a(DeviceKind.GENERAL, text),
        is_software=a(software, text),
        status=status,
        general=GeneralDeviceProfile(**{k: a(v, text) for k, v in fields.items()}),
    )


def ivd_fn(name, text, **given):
    """One IVD function."""
    software = given.pop("software", Tri.NO)
    status = status_for(text, TherapeuticPurpose.IN_VITRO_SPECIMEN,
                        given.pop("status", None))
    fields = dict(IVD_DEFAULTS)
    fields.update(given)
    return FunctionProfile(
        name=a(name, name),
        description=a(text, text),
        kind=a(DeviceKind.IVD, text),
        is_software=a(software, text),
        status=status,
        ivd=IvdProfile(**{k: a(v, text) for k, v in fields.items()}),
    )


def product(name, text, functions, sterile=Tri.NO, measuring=Tri.NO):
    """Assemble a product and prune each function to what gating asks for.

    source_text is everything the founder would have written, so every piece
    of evidence in the fixture really is a phrase from the source.
    """
    confirmation = "fixture decomposition is fixed by hand"
    parts = [name, text] + [
        f"{f.name.value} {f.description.value}" for f in functions
    ] + [confirmation]
    source_text = " ".join(parts)

    core = CoreProfile(
        product_name=a(name, name),
        intended_purpose=a(text, text),
        supplied_sterile=a(sterile, text),
        has_measuring_function=a(measuring, text),
        functions_confirmed=a(Tri.YES, confirmation),
    )
    return DeviceProfile(
        core=core,
        functions=[f.prune() for f in functions],
        source_text=source_text,
    )


def device(name, text, **given):
    """A single-function general device product. The common case."""
    sterile = given.pop("sterile", Tri.NO)
    measuring = given.pop("measuring", Tri.NO)
    return product(name, text, [fn(name, text, **given)],
                   sterile=sterile, measuring=measuring)


def ivd(name, text, **given):
    """A single-function IVD product."""
    return product(name, text, [ivd_fn(name, text, **given)])


F = []


def _expectation(slug, entry):
    """(class, rule) for a regulated function, (None, reason, status) otherwise."""
    expected, rule, *rest = entry
    status = rest[0] if rest else REGULATED
    if status.terminal:
        assert expected is None, f"{slug}: a function the gate stops has no class"
    else:
        assert expected is not None, f"{slug}: a regulated function needs a class"
    return expected, rule, status


def add(slug, expected, rule, source, note, profile, verified=True, status=REGULATED):
    """A single-function fixture. The expectations apply to function 0."""
    entry = _expectation(slug, (expected, rule, status))
    F.append((slug, source, note, profile, verified, [entry], status))


def add_multi(slug, source, note, profile, expectations, verified=False,
              status=REGULATED):
    """A multi-function fixture. One expectation per function, in order.

    The product class is derived, not asserted: the highest class per family.
    The product status is asserted by hand, because deriving it would mean
    copying the gate's aggregation into the answer key.
    """
    assert len(expectations) == len(profile.functions), slug
    entries = [_expectation(slug, e) for e in expectations]
    F.append((slug, source, note, profile, verified, entries, status))


# -- The screw family. One device, three classes. ---------------------------
add("screw_transient", "Class IIa", "3.2(2)", NOT_IVD,
    "Transient use during surgery.",
    device("Metal fixation screw, intraoperative",
           "Holds bone together temporarily during surgery.",
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.TRANSIENT,
           body_contact=BodyContact.BREACHED_SKIN, absorbed_or_chemically_changed=Tri.NO,
           reusable_surgical_instrument=Tri.NO, sterile=Tri.YES))

add("screw_short_term", "Class IIa", "3.3(2)", NOT_IVD,
    "Up to 30 days. Same class as transient, different rule.",
    device("Metal fixation screw, short term",
           "Holds bone together for up to 30 days to support fracture healing.",
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.SHORT_TERM,
           body_contact=BodyContact.BREACHED_SKIN, absorbed_or_chemically_changed=Tri.NO,
           sterile=Tri.YES))

add("screw_long_term", "Class IIb", "3.4(2)", NOT_IVD,
    "Crossing 30 days moves the class. The duration band is load-bearing.",
    device("Metal fixation screw, permanent",
           "Holds bone together for longer than 30 days, permanently implanted.",
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           invasiveness=Invasiveness.IMPLANTABLE, duration=Duration.LONG_TERM,
           body_contact=BodyContact.BREACHED_SKIN, absorbed_or_chemically_changed=Tri.NO,
           is_active_implantable=Tri.NO, sterile=Tri.YES))

add("screw_central_circulation", "Class III", "3.3(4)(a)", NOT_IVD,
    "Location beats duration. Tests that body_contact is read first.",
    device("Fixation screw contacting central circulatory system",
           "Direct contact with the central circulatory or central nervous system.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.SHORT_TERM,
           body_contact=BodyContact.CENTRAL_CIRCULATION,
           absorbed_or_chemically_changed=Tri.NO, sterile=Tri.YES))

# -- The dressing family. Intended function decides, not the wound. ---------
add("dressing_mechanical_barrier", "Class I", "2.4(3)", NOT_IVD,
    "Barrier, compression or absorption only. The floor of sub-rule 2.4.",
    device("Absorbent pad",
           "Acts as a barrier to and absorbs exudate from a wound.",
           contacts_injured_skin=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           wound_function=WoundFunction.MECHANICAL_BARRIER))

add("dressing_microenvironment", "Class IIa", "2.4(1)", NOT_IVD,
    "Same contact as the barrier pad. Only the claim differs.",
    device("Negative wound therapy dressing bandage",
           "Used together with an active medical device to manage the "
           "microenvironment of a wound.",
           contacts_injured_skin=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           wound_function=WoundFunction.MICROENVIRONMENT,
           connected_to_active_device=Tri.YES))

add("dressing_secondary_intent", "Class IIb", "2.4(4)", NOT_IVD,
    "Breached dermis healing by secondary intent. Top of sub-rule 2.4.",
    device("Dressing for chronic extensive ulceration",
           "For wounds that have breached the dermis and can only heal by "
           "secondary intent.",
           contacts_injured_skin=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           wound_function=WoundFunction.SECONDARY_INTENT,
           breaches_dermis=Tri.YES, sterile=Tri.YES))

add("dressing_collagen_deep_wound", "Class IIb", "2.4(4)", NOT_IVD,
    "SOURCES CONFLICT. A TGA case study puts a collagen dressing for breached "
    "dermis at 2.4(4) Class IIb, while collagen dressings also appear in a "
    "Class III list under the animal origin rule. Resolve from the primary "
    "document before trusting either value.",
    device("Collagen dressing for deep ulcers",
           "Dressing for deep wounds and ulcers that have breached the dermis, "
           "containing collagen for wound healing.",
           contacts_injured_skin=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           wound_function=WoundFunction.SECONDARY_INTENT,
           breaches_dermis=Tri.YES, animal_or_microbial_origin=Tri.YES,
           sterile=Tri.YES),
    verified=False)

add("trauma_covering_anaesthetic", "Class III", "5.1(2)", NOT_IVD,
    "A medicine overrides sub-rule 2.4 entirely. Tests special-rule priority.",
    device("Trauma covering with anaesthetic gel",
           "Non-sterile trauma covering to maintain stability of a burn patient "
           "en route to hospital, coated in a gel containing anaesthetic.",
           contacts_injured_skin=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           wound_function=WoundFunction.MECHANICAL_BARRIER,
           incorporates_medicine=Tri.YES))

add("heparin_coated_catheter", "Class III", "5.1", NOT_IVD,
    "Incorporated medicine lifts an otherwise lower-class catheter.",
    device("Heparin-coated catheter",
           "Catheter incorporating heparin as an ancillary medicinal substance.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.SHORT_TERM,
           body_contact=BodyContact.CENTRAL_CIRCULATION,
           absorbed_or_chemically_changed=Tri.NO,
           incorporates_medicine=Tri.YES, sterile=Tri.YES))

add("condom_with_spermicide", "Class III", "5.2", NOT_IVD,
    "Contraception plus a medicine. A plain condom sits lower.",
    device("Condom with spermicide",
           "Barrier contraceptive incorporating a spermicidal agent.",
           invasiveness=Invasiveness.BODY_ORIFICE, duration=Duration.TRANSIENT,
           orifice_site=OrificeSite.OTHER_ORIFICE, connected_to_active_device=Tri.NO,
           contraceptive_or_sti_prevention=Tri.YES, incorporates_medicine=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.CONCEPTION)))

# -- Orifice route ----------------------------------------------------------
add("orifice_long_term", "Class IIb", "3.1(2)(c)(i)", NOT_IVD,
    "Long-term use through a body orifice.",
    device("Long-term indwelling orifice device",
           "Invasive device used through a body orifice for longer than 30 days.",
           invasiveness=Invasiveness.BODY_ORIFICE, duration=Duration.LONG_TERM,
           orifice_site=OrificeSite.OTHER_ORIFICE, connected_to_active_device=Tri.NO))

# -- Active devices ---------------------------------------------------------
add("diagnostic_ultrasound", "Class IIa", "4.3(2)(a)", ACTIVE,
    "Supplies energy absorbed by the body for diagnosis.",
    device("General purpose diagnostic ultrasound",
           "Supplies ultrasonic energy absorbed by the patient for imaging.",
           active_type=ActiveType.DIAGNOSTIC, clinical_function=ClinicalFunction.SUPPLY_ENERGY,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.YES, body_contact=BodyContact.INTACT_SKIN))

add("mri_equipment", "Class IIa", "4.3(2)(a)", ACTIVE,
    "Same rule as ultrasound. Confirms the rule is not imaging-modality specific.",
    device("Magnetic resonance equipment",
           "Supplies energy absorbed by the patient's body for diagnostic imaging.",
           active_type=ActiveType.DIAGNOSTIC, clinical_function=ClinicalFunction.SUPPLY_ENERGY,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.YES, body_contact=BodyContact.NONE))

add("radiotherapy_afterloading_control", "Class IIb", "4.3(3)(c)", ACTIVE,
    "Controls a device that emits ionising radiation. Control inherits the risk.",
    device("Radiotherapy after-loading control system",
           "Controls and monitors the performance of a device emitting ionising "
           "radiation for therapeutic interventional radiology.",
           active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.CONTROL_ANOTHER_DEVICE,
           delivers_hazardous_energy=Tri.YES, delivers_ionising_radiation=Tri.YES,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE))

# -- Software. The pairs that matter most. ----------------------------------
add("melanoma_screening_app", "Class III", "4.5(1)(c)(i)", ACTIVE,
    "Device gives the screening decision to a consumer, condition can kill "
    "without urgent treatment.",
    device("Consumer melanoma screening app",
           "Analyses an image of a mole to screen for malignant melanoma, giving "
           "the screening decision to the consumer.",
           software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.DIAGNOSE_OR_SCREEN,
           decision_maker=DecisionMaker.DEVICE_TO_LAY_USER,
           status=dict(cdss_replaces_clinical_judgement=Tri.YES),
           condition_severity=Severity.DEATH_WITHOUT_URGENT_TREATMENT,
           public_health_risk=PublicHealthRisk.LOW,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE))

add("emphysema_ct_software", "Class IIa", "4.5(2)(b)", ACTIVE,
    "Same rule family as the melanoma app. A clinician decides, so it drops.",
    device("Emphysema detection software",
           "Diagnoses emphysema from CT scans, providing information to a health "
           "professional to support diagnostic decision making.",
           status=PROCESSES_DEVICE_DATA,
           software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.DIAGNOSE_OR_SCREEN,
           decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
           condition_severity=Severity.SERIOUS,
           public_health_risk=PublicHealthRisk.MODERATE,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE))

add("spect_cardiac_monitoring", "Class IIb", "4.6(a)", ACTIVE,
    "Monitoring where the information could indicate immediate danger.",
    device("SPECT cardiac monitoring software",
           "Analyses gamma camera imagery from a SPECT scan to track progression "
           "of heart disease from cardiac muscle blood flow.",
           status=PROCESSES_DEVICE_DATA,
           software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.MONITOR,
           decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
           condition_severity=Severity.DEATH_WITHOUT_URGENT_TREATMENT,
           public_health_risk=PublicHealthRisk.LOW,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE))

add("emg_dystrophy_monitoring", "Class IIa", "4.6(b)", ACTIVE,
    "Paired with the SPECT fixture. Same rule, lower danger, lower class.",
    device("Muscle response monitoring app",
           "Receives electromyography data by Bluetooth to monitor muscle fibre "
           "response in a person with muscular dystrophy.",
           status=PROCESSES_DEVICE_DATA,
           software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.MONITOR,
           decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
           condition_severity=Severity.MODERATE,
           public_health_risk=PublicHealthRisk.LOW,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE))

# -- Class I sub-classes. Not quoted from a worked example. -----------------
add("sterile_barrier_dressing", "Class Is", "2.4(3) with sterile supply", RULE_TEXT,
    "Identical to dressing_mechanical_barrier except for sterile supply.",
    device("Sterile absorbent pad",
           "Acts as a barrier to and absorbs exudate from a wound, supplied sterile.",
           contacts_injured_skin=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           wound_function=WoundFunction.MECHANICAL_BARRIER, sterile=Tri.YES),
    verified=False)

add("measuring_thermometer", "Class Im", "2.1 with measuring function", RULE_TEXT,
    "Exercises has_measuring_function, which nothing else in the set touches.",
    device("Non-invasive clinical thermometer",
           "Measures body temperature by contact with intact skin.",
           body_contact=BodyContact.INTACT_SKIN, measuring=Tri.YES),
    verified=False)

add("reusable_surgical_instrument", "Class I", "3.2(3)", RULE_TEXT,
    "A reusable instrument drops to Class I despite surgical invasiveness.",
    device("Reusable surgical scissors",
           "Reusable surgical instrument for transient use during surgery.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.TRANSIENT,
           body_contact=BodyContact.BREACHED_SKIN, absorbed_or_chemically_changed=Tri.NO,
           reusable_surgical_instrument=Tri.YES),
    verified=False)

# -- IVDs, Schedule 2A ------------------------------------------------------
add("culture_media", "Class 1 IVD", "1.6", IVD_GUIDE,
    "Named exception. Cannot be reasoned to, only looked up.",
    ivd("Microbiological culture medium",
        "Prepared culture medium for microbiological laboratory use.",
        is_instrument_or_receptacle=Tri.YES))

add("prothrombin_meter", "Class 1 IVD", "1.6", IVD_GUIDE,
    "The meter is Class 1 while its own test strips are Class 3. Pairs with "
    "prothrombin_self_test to test that the pack is split, not merged.",
    ivd("Portable prothrombin time meter",
        "Instrument that reads prothrombin time test strips.",
        is_instrument_or_receptacle=Tri.YES))

add("quality_control_material", "Class 2 IVD", "1.5", IVD_GUIDE,
    "Non-assay-specific control material. Another named exception.",
    ivd("Non-assay-specific control plasma",
        "Quality control material for coagulation studies, not assay specific.",
        is_quality_control_material=Tri.YES))

add("prothrombin_self_test", "Class 3 IVD", "1.4", IVD_GUIDE,
    "Self-testing lifts the class of the strips above their own meter.",
    ivd("Prothrombin time self-test strips",
        "Test strips for prothrombin time self-testing by a lay person at home.",
        purpose=IvdPurpose.MONITORING, is_self_test=Tri.YES,
        result_drives_critical_decision=Tri.YES, sample_type="capillary whole blood"))

add("hiv_donor_screening", "Class 4 IVD", "1.1", IVD_GUIDE,
    "The IVD ceiling. Donor screening for a high public health risk agent.",
    ivd("HIV blood donor screening assay",
        "Screens donated blood for HIV before transfusion.",
        purpose=IvdPurpose.BLOOD_OR_TISSUE_SCREENING, detects_transmissible_agent=Tri.YES,
        transmission_risk_to_population=Tri.YES, disease_is_life_threatening=Tri.YES,
        result_drives_critical_decision=Tri.YES, sample_type="donor whole blood"))

add("chlamydia_test", "Class 3 IVD", "1.3", IVD_GUIDE,
    "Transmissible agent at moderate rather than high public health risk.",
    ivd("Chlamydia trachomatis assay",
        "Detects Chlamydia trachomatis in a clinical specimen for diagnosis.",
        purpose=IvdPurpose.TRANSMISSIBLE_AGENT, detects_transmissible_agent=Tri.YES,
        transmission_risk_to_population=Tri.NO, disease_is_life_threatening=Tri.NO,
        result_drives_critical_decision=Tri.YES, sample_type="urine or swab"))


add("infusion_pump", "Class IIb", "4.4(2)", ACTIVE,
    "Reaches administers_or_removes_medicine, which nothing else touches. "
    "Potentially hazardous administration lifts it above the 4.4 baseline.",
    device("Volumetric infusion pump",
           "Administers medicines to a patient at a controlled rate, where the "
           "manner of administration is potentially hazardous.",
           active_type=ActiveType.THERAPEUTIC,
           clinical_function=ClinicalFunction.ADMINISTER_SUBSTANCE,
           administers_or_removes_medicine=Tri.YES,
           delivers_hazardous_energy=Tri.YES),
    verified=False)


# -- Multi-function products. The reason functions are first-class. ---------
add_multi(
    "prothrombin_self_test_pack",
    IVD_GUIDE,
    "A procedure pack holding three functions in two rule families. The pack "
    "does not take one class: the meter and strips classify separately as "
    "IVDs and the lancet as a general device.",
    product(
        "Prothrombin time self-testing pack",
        "Procedure pack for prothrombin time self-testing at home, containing "
        "a portable meter, test strips and a lancet.",
        [
            ivd_fn("Portable prothrombin time meter",
                   "Instrument that reads prothrombin time test strips.",
                   is_instrument_or_receptacle=Tri.YES),
            ivd_fn("Prothrombin time test strips",
                   "Test strips for prothrombin time self-testing by a lay person.",
                   purpose=IvdPurpose.MONITORING, is_self_test=Tri.YES,
                   result_drives_critical_decision=Tri.YES,
                   sample_type="capillary whole blood"),
            fn("Lancet",
               "Single-use lancet for obtaining a capillary blood specimen.",
               invasiveness=Invasiveness.SURGICALLY_INVASIVE,
               duration=Duration.TRANSIENT, body_contact=BodyContact.BREACHED_SKIN,
               absorbed_or_chemically_changed=Tri.NO,
               reusable_surgical_instrument=Tri.NO),
        ],
        sterile=Tri.YES,
    ),
    [("Class 1 IVD", "1.6"), ("Class 3 IVD", "1.4"), ("Class IIa", "3.2")],
    verified=True,
)

add_multi(
    "imaging_platform",
    RULE_TEXT,
    "Three software functions of one platform. The archive is excluded under "
    "item 14H, triage flags abnormal studies, and the follow-up suggestion "
    "specifies an intervention. Tests that the highest function governs the "
    "product and that one regulated function pulls the whole platform in. "
    "WARNING: the archive is worded as store and transmit only on purpose. "
    "TGA guidance (March 2026) says 14H does not cover software that also "
    "displays images for diagnosis or screening; such a function is likely a "
    "regulated device, and its class waits on the stage 4 rules. The follow-up "
    "suggestion analyses the scan images, which fails the second CDSS "
    "criterion and keeps it regulated; cdss_followup_from_report_text is the "
    "report-only version, which is exempt.",
    product(
        "Radiology reporting platform",
        "Stores radiology studies, flags abnormal ones for priority review and "
        "suggests a follow-up imaging interval.",
        [
            fn("Study archive",
               "Stores and transmits radiology studies without interpretation.",
               status=IMAGE_STORAGE, software=Tri.YES, active_type=ActiveType.NOT_ACTIVE,
               body_contact=BodyContact.NONE),
            fn("Abnormality triage",
               "Flags studies showing suspected abnormality for priority review "
               "by a radiologist.",
               status=PROCESSES_DEVICE_DATA, software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
               clinical_function=ClinicalFunction.DIAGNOSE_OR_SCREEN,
               decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
               condition_severity=Severity.SERIOUS,
               public_health_risk=PublicHealthRisk.MODERATE,
               delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
               records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE),
            fn("Follow-up interval suggestion",
               "Analyses the scan images and suggests a follow-up imaging interval "
               "to the reporting radiologist.",
               status=PROCESSES_DEVICE_DATA, software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
               clinical_function=ClinicalFunction.SPECIFY_THERAPY,
               decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
               condition_severity=Severity.SERIOUS,
               public_health_risk=PublicHealthRisk.MODERATE,
               delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
               records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE),
        ],
    ),
    [(None, "S1-14H", EXCLUDED),
     ("Class IIa", "4.5(2)(b)"),
     ("Class IIa", "4.7(2)(b)(i)")],
    verified=False,
)

add_multi(
    "wellness_app_with_symptom_checker",
    RULE_TEXT,
    "A consumer app whose tracking function is an excluded good under item "
    "14B. The symptom checker is not excluded, and a product is excluded only "
    "when every function qualifies, so one regulated function pulls the whole "
    "app into regulation. This is the unanimity test.",
    product(
        "Consumer wellbeing app",
        "Tracks sleep and activity for general wellbeing and includes a symptom "
        "checker that suggests whether to seek care.",
        [
            fn("Activity and sleep tracking",
               "Records sleep and activity for general wellbeing.",
               status=WELLNESS_TRACKING, software=Tri.YES, active_type=ActiveType.NOT_ACTIVE,
               body_contact=BodyContact.NONE),
            fn("Symptom checker",
               "Asks a consumer about symptoms and suggests whether to seek "
               "medical care.",
               status=dict(cdss_replaces_clinical_judgement=Tri.YES),
               software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
               clinical_function=ClinicalFunction.DIAGNOSE_OR_SCREEN,
               decision_maker=DecisionMaker.DEVICE_TO_LAY_USER,
               condition_severity=Severity.MODERATE,
               public_health_risk=PublicHealthRisk.LOW,
               delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
               records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE),
        ],
    ),
    [(None, "S1-14B", EXCLUDED),
     ("Class IIa", "4.5(2)")],
    verified=False,
)


# -- The status gate. Products the gate stops before classification. ---------
add("wellness_sleep_tracker", None, "S1-14B", GATE_TEXT,
    "The tracking function of the wellness app, supplied on its own. It is an "
    "excluded good under item 14B, so the gate stops it and classification "
    "never runs. Pairs with the wellness app to show the same function "
    "deciding a product alone and failing to decide it alongside a regulated "
    "function.",
    device("Sleep and activity tracker",
           "Records sleep and activity for general wellbeing.",
           status=WELLNESS_TRACKING, software=Tri.YES,
           active_type=ActiveType.NOT_ACTIVE, body_contact=BodyContact.NONE),
    verified=False, status=EXCLUDED)

add("anatomy_education_app", None, "no limb of s41BD reached", GATE_TEXT,
    "Teaching software for students. It is used on no patient and reaches no "
    "limb of s41BD, it serves no device, and no exclusion item describes it, "
    "so it is simply not a medical device. The only fixture that exercises the "
    "not-a-device verdict and the accessory question.",
    device("Anatomy teaching app",
           "Interactive 3D anatomy lessons for medical students, used for "
           "study only and never on a patient.",
           status=NO_PURPOSE, software=Tri.YES,
           active_type=ActiveType.NOT_ACTIVE, body_contact=BodyContact.NONE),
    verified=False, status=NOT_A_DEVICE)

add("cdss_followup_from_report_text", None, "Schedule 4 Part 2", GATE_TEXT,
    "The follow-up suggestion from the imaging platform, rebuilt to read only "
    "the written report. It recommends to a radiologist, processes no image "
    "or signal from another device, and leaves the decision with the "
    "radiologist, so all three CDSS criteria are met and it is exempt. The "
    "pair with imaging_platform isolates the second criterion.",
    device("Follow-up interval recommender",
           "Reads the written radiology report and recommends a follow-up "
           "imaging interval to the reporting radiologist, who decides.",
           status=dict(cdss_sole_purpose_recommendation=Tri.YES,
                       cdss_processes_device_signal_or_image=Tri.NO,
                       cdss_replaces_clinical_judgement=Tri.NO),
           software=Tri.YES, active_type=ActiveType.DIAGNOSTIC,
           clinical_function=ClinicalFunction.SPECIFY_THERAPY,
           decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
           condition_severity=Severity.SERIOUS,
           public_health_risk=PublicHealthRisk.MODERATE,
           delivers_hazardous_energy=Tri.NO, delivers_ionising_radiation=Tri.NO,
           records_diagnostic_images=Tri.NO, body_contact=BodyContact.NONE),
    verified=False, status=EXEMPT_CDSS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # The directory is rebuilt, not added to. A renamed fixture would otherwise
    # leave its old file behind, and stale fixtures fail against a newer schema
    # in ways that look like schema bugs.
    written = {f"{slug}.json" for slug, *_ in F}
    for stale in OUT.glob("*.json"):
        if stale.name not in written:
            stale.unlink()
            print(f"   removed stale fixture {stale.name}")

    gaps = 0
    for slug, source, note, profile, verified, expectations, status in F:
        missing = profile.missing()
        gaps += len(missing)
        functions = [
            {
                "name": function.name.value,
                "expected_status": function_status.value,
                "expected_class": expected,
                "expected_rule": rule,
            }
            for function, (expected, rule, function_status)
            in zip(profile.functions, expectations)
        ]
        payload = {
            "expected_status": status.value,
            "expected_classes": highest_class(e for e, _, _ in expectations),
            "functions": functions,
            "source": source,
            "verified": verified,
            "note": note,
            "profile": profile.model_dump(mode="json"),
        }
        (OUT / f"{slug}.json").write_text(json.dumps(payload, indent=2) + "\n")
        flag = "  " if verified else " ?"
        count = f"{len(functions)} fn" if len(functions) > 1 else "     "
        summary = ", ".join(sorted(payload["expected_classes"].values())) or "no class"
        if status is not REGULATED:
            summary = f"{summary} [{status.value}]"
        warn = f"  MISSING: {missing}" if missing else ""
        print(f"{flag} {slug:34} {count} {summary}{warn}")

    verified_count = sum(1 for f in F if f[4])
    multi = sum(1 for f in F if len(f[5]) > 1)
    print(f"\n{len(F)} fixtures, {verified_count} verified, {multi} multi-function, "
          f"{gaps} unresolved fields")


if __name__ == "__main__":
    main()
