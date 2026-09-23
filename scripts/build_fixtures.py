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

Every fixture also carries intake cases: descriptions for stage 1 to read,
scored by scripts/score_intake.py against the fixture's own profile. The
"described" case is built from the fixture's name and descriptions, in the
regulatory wording the fixture was written in. A few fixtures add a
"founder" case, the same device described the way a founder would pitch it,
with no Regulations vocabulary; those are the fairer test of extraction. A
founder text must never state anything the fixture contradicts.

"specific" lists the fields a fixture sets on purpose, as opposed to the
defaults the builder fills in (mostly "no" for things the description never
mentions). Intake coverage is measured against these, and only against the
ones extraction is allowed to claim.

Run:  python scripts/build_fixtures.py
"""

import json
from pathlib import Path

from reguide.intake_fields import EXTRACTABLE
from reguide.profile import (
    Answer,
    Basis,
    CoreProfile,
    DecisionMaker,
    DeviceKind,
    DeviceProfile,
    Duration,
    FunctionProfile,
    GeneralDeviceProfile,
    highest_class,
    InformationTherapyHarm,
    Invasiveness,
    MonitoringDanger,
    IvdProfile,
    OrificeSite,
    PublicHealthRisk,
    Severity,
    StatusProfile,
    TherapeuticPurpose,
    TreatmentRisk,
    Tri,
)
from reguide.status import StatusOutcome

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
NOT_IVD = "TGA, Classifying medical devices that are not IVDs"
ACTIVE = "TGA, Classifying active medical devices in Australia"
IVD_GUIDE = "TGA, Classifying IVDs for supply in Australia"
RULE_TEXT = "Reasoned from Schedule 2 rule text, not a worked example"
IMDRF_IVD = ("IMDRF/IVD WG/N64FINAL:2021 (formerly GHTF/SG1/N045:2008), "
             "Principles of IVD medical devices classification, rule 5 examples")
IHR_GUIDE = "TGA, Completing Conformity Assessment for immunohaematology reagents (IHRs)"
THERMOMETERS = ("TGA, Regulation of thermometers and other temperature measuring medical "
                "devices and products for COVID-19")
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
    is_active_device=Tri.NO,
    is_programmed_or_programmable=Tri.NO,
    active_for_therapy=Tri.NO,
    active_for_diagnosis=Tri.NO,
    administers_or_exchanges_energy=Tri.NO,
    delivers_hazardous_energy=Tri.NO,
    controls_hazardous_therapy_device=Tri.NO,
    diagnostic_function_determines_patient_management=Tri.NO,
    supplies_absorbed_energy_for_diagnosis=Tri.NO,
    images_radiopharmaceutical_distribution=Tri.NO,
    diagnoses_or_monitors_vital_processes=Tri.NO,
    monitors_vital_parameters_immediate_danger=Tri.NO,
    emits_ionising_radiation_for_interventional_radiology=Tri.NO,
    controls_interventional_radiology_device=Tri.NO,
    administers_or_removes_substances=Tri.NO,
    substance_administration_potentially_hazardous=Tri.NO,
    diagnoses_or_screens=Tri.NO,
    monitors_disease_state=Tri.NO,
    specifies_or_recommends_treatment=Tri.NO,
    provides_therapy_through_information=Tri.NO,
    incorporates_medicine=Tri.NO,
    contraceptive_or_sti_prevention=Tri.NO,
    disinfects_another_device=Tri.NO,
    human_blood_derivative=Tri.NO,
    is_export_only=Tri.NO,
    cares_for_contact_lenses=Tri.NO,
    records_images_or_anatomical_model=Tri.NO,
    records_patient_images_outside_visible_spectrum=Tri.NO,
    is_anatomical_model_for_diagnosis=Tri.NO,
    generates_virtual_anatomical_model=Tri.NO,
    contains_non_viable_animal_material=Tri.NO,
    contacts_intact_skin_only=Tri.NO,
    is_blood_bag=Tri.NO,
    implantable_accessory_to_active_implantable=Tri.NO,
    controls_active_implantable=Tri.NO,
    is_mammary_implant=Tri.NO,
    administers_by_inhalation=Tri.NO,
    inhalation_mode_of_action_essential=Tri.NO,
    inhalation_treats_life_threatening_condition=Tri.NO,
    is_substance_through_orifice_or_skin=Tri.NO,
    substance_acts_in_nose_mouth_or_on_skin=Tri.NO,
    connected_to_an_active_device=Tri.NO,
    liable_to_be_absorbed_by_mucous_membrane=Tri.NO,
    corrects_heart_or_circulatory_defect_by_contact=Tri.NO,
    direct_contact_heart_circulation_or_nervous_system=Tri.NO,
    reusable_surgical_instrument=Tri.NO,
    delivers_ionising_radiation=Tri.NO,
    has_biological_effect=Tri.NO,
    wholly_or_mostly_absorbed=Tri.NO,
    undergoes_chemical_change=Tri.NO,
    placed_in_teeth=Tri.NO,
    administers_medicine_hazardously_by_delivery_system=Tri.NO,
    administers_medicine=Tri.NO,
    joint_replacement_or_surgical_mesh=Tri.NO,
    spinal_motion_preserving=Tri.NO,
    handles_substances_for_administration=Tri.NO,
    contacts_injured_skin_or_mucous_membrane=Tri.NO,
    channels_or_stores_blood_for_administration=Tri.NO,
    stores_organ_or_tissue_for_introduction=Tri.NO,
    channels_or_stores_liquid_or_gas_for_administration=Tri.NO,
    saline_only_flush_or_patency=Tri.NO,
    modifies_composition_of_blood_or_infusion=Tri.NO,
    treatment_is_filtration_centrifugation_or_exchange=Tri.NO,
    barrier_compression_or_absorption=Tri.NO,
    principally_for_breached_dermis_secondary_intent=Tri.NO,
)

IVD_DEFAULTS = dict(
    is_ivd_instrument=Tri.NO,
    is_specimen_receptacle=Tri.NO,
    is_culture_medium=Tri.NO,
    is_quality_control_material=Tri.NO,
    is_export_only=Tri.NO,
    detects_infectious_agent=Tri.NO,
    types_blood_or_tissue=Tri.NO,
    is_self_test=Tri.NO,
    screens_donations_for_transmissible_agents=Tri.NO,
    agent_serious_with_high_propagation_risk=Tri.NO,
    assesses_transfusion_or_transplant_compatibility=Tri.NO,
    detects_listed_blood_group_marker=Tri.NO,
    detects_sexually_transmitted_agent=Tri.NO,
    detects_limited_propagation_agent_in_csf_or_blood=Tri.NO,
    error_could_cause_death_or_severe_disability=Tri.NO,
    prenatal_immune_status_screening=Tri.NO,
    infective_status_error_life_threatening=Tri.NO,
    manages_life_threatening_infectious_disease=Tri.NO,
    selects_patients_for_therapy=Tri.NO,
    selects_patients_for_disease_staging=Tri.NO,
    selects_patients_in_cancer_diagnosis=Tri.NO,
    is_companion_diagnostic=Tri.NO,
    is_human_genetic_test=Tri.NO,
    monitors_levels_error_life_threatening=Tri.NO,
    screens_foetus_for_congenital_disorders=Tri.NO,
    result_not_determining_serious_condition=Tri.NO,
    preliminary_with_follow_up_testing=Tri.NO,
    is_ancillary_reagent_or_article=Tri.NO,
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
        for key in ("is_active_device", "is_programmed_or_programmable",
                    "human_blood_derivative", "contains_non_viable_animal_material",
                    "is_blood_bag", "administers_by_inhalation",
                    "is_substance_through_orifice_or_skin"):
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


QUALIFIER_CODES = {"supplied_sterile", "measuring_function"}


def _expectation(slug, entry):
    """(class, rule, status, qualifiers) for one function.

    A regulated function has a class; a function the gate stops has none.
    Qualifiers are the regulation 3.9 conditions on a Class I general device.
    """
    expected, rule, *rest = entry
    status = rest[0] if rest else REGULATED
    qualifiers = tuple(rest[1]) if len(rest) > 1 else ()
    if status.terminal:
        assert expected is None, f"{slug}: a function the gate stops has no class"
    else:
        assert expected is not None, f"{slug}: a regulated function needs a class"
    assert set(qualifiers) <= QUALIFIER_CODES, f"{slug}: unknown qualifier"
    assert not qualifiers or expected == "Class I", f"{slug}: qualifiers need Class I"
    return expected, rule, status, qualifiers


def add(slug, expected, rule, source, note, profile, verified=True, status=REGULATED,
        qualifiers=()):
    """A single-function fixture. The expectations apply to function 0."""
    entry = _expectation(slug, (expected, rule, status, qualifiers))
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
           reusable_surgical_instrument=Tri.NO, sterile=Tri.YES))

add("screw_short_term", "Class IIa", "3.3(2)", NOT_IVD,
    "Up to 30 days. Same class as transient, different rule.",
    device("Metal fixation screw, short term",
           "Holds bone together for up to 30 days to support fracture healing.",
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.SHORT_TERM,
           sterile=Tri.YES))

add("screw_long_term", "Class IIb", "3.4(2)", NOT_IVD,
    "Crossing 30 days moves the class. The duration band is load-bearing.",
    device("Metal fixation screw, permanent",
           "Holds bone together for longer than 30 days, permanently implanted.",
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           invasiveness=Invasiveness.IMPLANTABLE, duration=Duration.LONG_TERM,
           is_active_implantable=Tri.NO, sterile=Tri.YES))

add("screw_central_circulation", "Class III", "3.3(4)(b)", NOT_IVD,
    "Location beats duration. TGA case study 2 cites 3.3(4)(a), but a fixation "
    "screw does not diagnose, monitor, control or correct a heart defect; direct "
    "contact with the central circulatory or nervous system is 3.3(4)(b).",
    device("Fixation screw contacting central circulatory system",
           "Direct contact with the central circulatory or central nervous system.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.SHORT_TERM,
           direct_contact_heart_circulation_or_nervous_system=Tri.YES, sterile=Tri.YES))

# -- The dressing family. Intended function decides, not the wound. ---------
add("dressing_mechanical_barrier", "Class I", "2.4(3)", NOT_IVD,
    "Barrier, compression or absorption only. The floor of sub-rule 2.4.",
    device("Absorbent pad",
           "Acts as a barrier to and absorbs exudate from a wound.",
           contacts_injured_skin_or_mucous_membrane=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           barrier_compression_or_absorption=Tri.YES))

add("dressing_microenvironment", "Class IIa", "2.4(2)", NOT_IVD,
    "Same contact as the barrier pad. Only the claim differs. TGA's guidance "
    "numbers this 2.4(1); in the Regulations 2.4(1) sets the scope and the "
    "Class IIa comes from 2.4(2).",
    device("Negative wound therapy dressing bandage",
           "Used together with an active medical device to manage the "
           "microenvironment of a wound.",
           contacts_injured_skin_or_mucous_membrane=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           barrier_compression_or_absorption=Tri.NO))

add("dressing_secondary_intent", "Class IIb", "2.4(4)", NOT_IVD,
    "Breached dermis healing by secondary intent. Top of sub-rule 2.4.",
    device("Dressing for chronic extensive ulceration",
           "For wounds that have breached the dermis and can only heal by "
           "secondary intent.",
           contacts_injured_skin_or_mucous_membrane=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           principally_for_breached_dermis_secondary_intent=Tri.YES, sterile=Tri.YES))

add("dressing_collagen_deep_wound", "Class III", "5.5", NOT_IVD,
    "TGA case study 1 (dressings) gives this exact device as Class III under "
    "5.5, animal origin. 2.4(4) also applies (Class IIb) but regulation 3.3(7) "
    "takes the higher class. The guidance cites 5.5(1)(a) in the pre-July 2024 "
    "wording; in Compilation 72 collagen is a derivative under 5.5(1)(b) and "
    "the class is set by 5.5(3), so the fixture names the whole clause.",
    device("Collagen dressing for deep ulcers",
           "Dressing for deep wounds and ulcers that have breached the dermis, "
           "containing collagen for wound healing.",
           contacts_injured_skin_or_mucous_membrane=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           principally_for_breached_dermis_secondary_intent=Tri.YES,
           contains_non_viable_animal_material=Tri.YES, contacts_intact_skin_only=Tri.NO,
           sterile=Tri.YES))

# -- Substances for administration, sub-rules 2.2 and 2.3. -----------------
add("infusion_pump_syringe", "Class IIa", "2.2(1)(c)", NOT_IVD,
    "TGA lists syringes and tubing for infusion pumps under 2.2(1)(c), Class "
    "IIa: a liquid for administration, and connectable to an active device of "
    "Class IIa or higher.",
    device("Infusion pump syringe",
           "Syringe for use with an infusion pump, holding liquid medicine to be "
           "administered to a patient.",
           handles_substances_for_administration=Tri.YES,
           channels_or_stores_liquid_or_gas_for_administration=Tri.YES,
           connected_to_active_device=Tri.YES))

add("haemodialyser", "Class IIb", "2.3(1)", NOT_IVD,
    "TGA gives haemodialysers, which remove undesirable substances from blood by "
    "exchange of solutes, as 2.3(1) Class IIb. The source places them under (1), "
    "not the filtration or exchange of gas or heat in (2).",
    device("Haemodialyser",
           "Removes undesirable substances from blood by exchange of solutes before "
           "the blood is returned to the patient.",
           handles_substances_for_administration=Tri.YES,
           modifies_composition_of_blood_or_infusion=Tri.YES,
           treatment_is_filtration_centrifugation_or_exchange=Tri.NO))

add("trauma_covering_anaesthetic", "Class III", "5.1(2)", NOT_IVD,
    "A medicine overrides sub-rule 2.4 entirely. Tests special-rule priority.",
    device("Trauma covering with anaesthetic gel",
           "Non-sterile trauma covering to maintain stability of a burn patient "
           "en route to hospital, coated in a gel containing anaesthetic.",
           contacts_injured_skin_or_mucous_membrane=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           barrier_compression_or_absorption=Tri.YES,
           incorporates_medicine=Tri.YES))

add("heparin_coated_catheter", "Class III", "5.1", NOT_IVD,
    "Incorporated medicine lifts an otherwise lower-class catheter.",
    device("Heparin-coated catheter",
           "Catheter incorporating heparin as an ancillary medicinal substance.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.SHORT_TERM,
           incorporates_medicine=Tri.YES, sterile=Tri.YES))

add("condom_with_spermicide", "Class III", "5.1(2)", NOT_IVD,
    "Contraception plus a medicine. 5.2(1) alone gives Class IIb (5.2(2) is "
    "for implantable or long-term invasive devices); the incorporated "
    "spermicide brings 5.1, Class III, which governs under regulation 3.3(7).",
    device("Condom with spermicide",
           "Barrier contraceptive incorporating a spermicidal agent.",
           invasiveness=Invasiveness.BODY_ORIFICE, duration=Duration.TRANSIENT,
           orifice_site=OrificeSite.OTHER_ORIFICE, connected_to_an_active_device=Tri.NO,
           contraceptive_or_sti_prevention=Tri.YES, incorporates_medicine=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.CONCEPTION)))

# -- Orifice route ----------------------------------------------------------
add("orifice_long_term", "Class IIb", "3.1(2)(c)(i)", NOT_IVD,
    "Long-term use through a body orifice.",
    device("Long-term indwelling orifice device",
           "Invasive device used through a body orifice for longer than 30 days.",
           invasiveness=Invasiveness.BODY_ORIFICE, duration=Duration.LONG_TERM,
           orifice_site=OrificeSite.OTHER_ORIFICE, connected_to_an_active_device=Tri.NO))

add("nasal_device_long_term", "Class IIa", "3.1(2)(c)(ii)", RULE_TEXT,
    "Reasoned from the 3.1 text, not a worked example: a long-term nasal device "
    "not liable to be absorbed by the mucous membrane is Class IIa under "
    "3.1(2)(c)(ii); if it were liable to be absorbed it would stay at (c)(i), "
    "Class IIb. Exercises the absorption question, which nothing else reaches.",
    device("Long-term nasal splint",
           "Non-absorbable splint used in a nasal cavity for longer than 30 days.",
           invasiveness=Invasiveness.BODY_ORIFICE, duration=Duration.LONG_TERM,
           orifice_site=OrificeSite.NASAL_CAVITY, connected_to_an_active_device=Tri.NO,
           liable_to_be_absorbed_by_mucous_membrane=Tri.NO),
    verified=False)

# -- Active devices ---------------------------------------------------------
add("diagnostic_ultrasound", "Class IIa", "4.3(2)(a)", ACTIVE,
    "Supplies energy absorbed by the body for diagnosis.",
    device("General purpose diagnostic ultrasound",
           "Supplies ultrasonic energy absorbed by the patient for imaging.",
           is_active_device=Tri.YES, active_for_diagnosis=Tri.YES,
           supplies_absorbed_energy_for_diagnosis=Tri.YES,
           records_images_or_anatomical_model=Tri.YES,
           records_patient_images_outside_visible_spectrum=Tri.YES))

add("mri_equipment", "Class IIa", "4.3(2)(a)", ACTIVE,
    "Same rule as ultrasound. Confirms the rule is not imaging-modality specific.",
    device("Magnetic resonance equipment",
           "Supplies energy absorbed by the patient's body for diagnostic imaging.",
           is_active_device=Tri.YES, active_for_diagnosis=Tri.YES,
           supplies_absorbed_energy_for_diagnosis=Tri.YES,
           records_images_or_anatomical_model=Tri.YES,
           records_patient_images_outside_visible_spectrum=Tri.YES))

add("radiotherapy_afterloading_control", "Class IIb", "4.2(3)", ACTIVE,
    "Class IIb either way. TGA's active device guidance lists radiotherapy "
    "after-loading control systems under 4.3(3)(c), but clause 4.3 applies only "
    "to an active medical device for diagnosis (4.3(1)). The same guidance puts "
    "radioactive sources for after-loading therapy under 4.2(2), so controlling "
    "one is 4.2(3), which is what the text supports.",
    device("Radiotherapy after-loading control system",
           "Controls and monitors the performance of a radioactive source for "
           "after-loading therapy, which delivers radiation in a potentially "
           "hazardous way.",
           is_active_device=Tri.YES, active_for_therapy=Tri.YES,
           controls_hazardous_therapy_device=Tri.YES))

add("tens_device", "Class IIa", "4.2(1)", ACTIVE,
    "TGA lists TENS devices under 4.2(1): an active device for therapy that "
    "administers energy, not in a potentially hazardous way.",
    device("TENS device",
           "Transcutaneous electrical nerve stimulator that administers electrical "
           "energy to a patient for pain relief, not in a potentially hazardous way.",
           is_active_device=Tri.YES, active_for_therapy=Tri.YES,
           administers_or_exchanges_energy=Tri.YES, delivers_hazardous_energy=Tri.NO))

# -- Software. The pairs that matter most. ----------------------------------
add("melanoma_screening_app", "Class III", "4.5(1)(c)(i)", ACTIVE,
    "Device gives the screening decision to a consumer, condition can kill "
    "without urgent treatment.",
    device("Consumer melanoma screening app",
           "Analyses an image of a mole to screen for malignant melanoma, giving "
           "the screening decision to the consumer.",
           software=Tri.YES, active_for_diagnosis=Tri.YES,
           diagnoses_or_screens=Tri.YES,
           decision_maker=DecisionMaker.DEVICE_TO_LAY_USER,
           status=dict(cdss_replaces_clinical_judgement=Tri.YES),
           condition_severity=Severity.DEATH_WITHOUT_URGENT_TREATMENT,
           public_health_risk=PublicHealthRisk.LOW))

add("cbt_app_bipolar", "Class IIa", "4.8(c)", ACTIVE,
    "TGA's 4.8 example: an app providing cognitive behavioural therapy for "
    "bipolar disorder that does not reference an established clinical practice "
    "guideline is Class IIa under 4.8(c), therapy that may cause harm. A tool "
    "based on displayed, established guidelines would not be a medical device.",
    device("Cognitive behavioural therapy app",
           "Provides cognitive behavioural therapy to a patient for treating bipolar "
           "disorder, without referencing an established clinical practice "
           "guideline; the therapy may cause harm.",
           software=Tri.YES,
           status=dict(cdss_replaces_clinical_judgement=Tri.YES),
           provides_therapy_through_information=Tri.YES,
           information_therapy_harm=InformationTherapyHarm.HARM))

add("emphysema_ct_software", "Class IIb", "4.5(1)(d)", ACTIVE,
    "TGA's own example: a device that diagnoses emphysema from CT scans makes "
    "the diagnosis itself, and emphysema is a serious disease, so 4.5(1)(d), "
    "Class IIb. Same rule family as the melanoma app, one level lower.",
    device("Emphysema detection software",
           "Diagnoses emphysema, a serious disease, from computed tomography scans.",
           status=PROCESSES_DEVICE_DATA,
           software=Tri.YES, active_for_diagnosis=Tri.YES,
           diagnoses_or_screens=Tri.YES,
           decision_maker=DecisionMaker.DEVICE_TO_PROFESSIONAL,
           condition_severity=Severity.SERIOUS,
           public_health_risk=PublicHealthRisk.LOW))

add("spect_cardiac_monitoring", "Class IIb", "4.6(a)", ACTIVE,
    "Monitoring where the information could indicate immediate danger.",
    device("SPECT cardiac monitoring software",
           "Analyses gamma camera imagery from a SPECT scan to track progression "
           "of heart disease from cardiac muscle blood flow.",
           status=PROCESSES_DEVICE_DATA,
           software=Tri.YES, active_for_diagnosis=Tri.YES,
           monitors_disease_state=Tri.YES,
           monitoring_danger=MonitoringDanger.IMMEDIATE,
           public_health_risk=PublicHealthRisk.LOW))

add("emg_dystrophy_monitoring", "Class IIa", "4.6(b)", ACTIVE,
    "Paired with the SPECT fixture. Same rule, lower danger, lower class.",
    device("Muscle response monitoring app",
           "Receives electromyography data by Bluetooth to monitor muscle fibre "
           "response in a person with muscular dystrophy.",
           status=PROCESSES_DEVICE_DATA,
           software=Tri.YES, active_for_diagnosis=Tri.YES,
           monitors_disease_state=Tri.YES,
           monitoring_danger=MonitoringDanger.OTHER,
           public_health_risk=PublicHealthRisk.LOW))

# -- Class I with regulation 3.9 qualifiers, and a reusable instrument. -----
add("sterile_barrier_dressing", "Class I", "2.4(3)", NOT_IVD,
    "TGA case study 1 (dressings): a sterile adhesive dressing strip is Class I "
    "(sterile) under 2.4(3)(c). Identical to dressing_mechanical_barrier except "
    "for sterile supply, which leaves the Schedule 2 class at I and adds the "
    "regulation 3.9(2) qualifier.",
    device("Sterile adhesive dressing strip",
           "Adhesive dressing strip that absorbs exudate from a wound, supplied sterile.",
           contacts_injured_skin_or_mucous_membrane=Tri.YES,
           status=dict(therapeutic_purpose=TherapeuticPurpose.INJURY),
           barrier_compression_or_absorption=Tri.YES, sterile=Tri.YES),
    qualifiers=("supplied_sterile",))

add("measuring_thermometer", "Class I", "2.1", THERMOMETERS,
    "TGA: clinical thermometers that are not battery-powered are Class I "
    "(measuring); battery-powered digital thermometers are Class IIa. The source "
    "gives the class, not the rule: 2.1 follows from the Schedule 2 text for a "
    "non-active device on intact skin. Exercises has_measuring_function, which "
    "nothing else in the set touches.",
    device("Non-powered clinical thermometer",
           "Clinical thermometer, not battery-powered, that measures body temperature "
           "by contact with intact skin.", measuring=Tri.YES),
    qualifiers=("measuring_function",))

add("reusable_surgical_instrument", "Class I", "3.2(4)", NOT_IVD,
    "TGA lists scissors among the reusable surgical instruments that are Class I "
    "under 3.2(4), despite surgical invasiveness.",
    device("Reusable surgical scissors",
           "Reusable surgical instrument for transient use during surgery.",
           invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=Duration.TRANSIENT,
           reusable_surgical_instrument=Tri.YES))

# -- IVDs, Schedule 2A ------------------------------------------------------
add("culture_media", "Class 1 IVD", "1.6(2)(c)", IVD_GUIDE,
    "Named exception. Cannot be reasoned to, only looked up.",
    ivd("Microbiological culture medium",
        "Prepared culture medium for microbiological laboratory use.",
        is_culture_medium=Tri.YES))

add("prothrombin_meter", "Class 1 IVD", "1.6(2)(a)", IVD_GUIDE,
    "The meter is Class 1 while its own test strips are Class 3. Pairs with "
    "prothrombin_self_test to test that the pack is split, not merged.",
    ivd("Portable prothrombin time meter",
        "Instrument that reads prothrombin time test strips.",
        is_ivd_instrument=Tri.YES))

add("quality_control_material", "Class 2 IVD", "1.5", IVD_GUIDE,
    "Non-assay-specific control material. Another named exception.",
    ivd("Non-assay-specific control plasma",
        "Quality control material for coagulation studies, not assay specific.",
        is_quality_control_material=Tri.YES))

add("prothrombin_self_test", "Class 3 IVD", "1.4", IVD_GUIDE,
    "Self-testing lifts the class of the strips above their own meter.",
    ivd("Prothrombin time self-test strips",
        "Test strips for prothrombin time self-testing by a lay person at home.",
        is_self_test=Tri.YES))

add("hiv_donor_screening", "Class 4 IVD", "1.1(a)", IVD_GUIDE,
    "The IVD ceiling. Donor screening for a high public health risk agent.",
    ivd("HIV blood donor screening assay",
        "Screens donated blood for HIV before transfusion.",
        detects_infectious_agent=Tri.YES, screens_donations_for_transmissible_agents=Tri.YES,
        agent_serious_with_high_propagation_risk=Tri.YES))

add("chlamydia_test", "Class 3 IVD", "1.3(a)", IVD_GUIDE,
    "Transmissible agent at moderate rather than high public health risk.",
    ivd("Chlamydia trachomatis assay",
        "Detects Chlamydia trachomatis in a clinical specimen for diagnosis.",
        detects_infectious_agent=Tri.YES, detects_sexually_transmitted_agent=Tri.YES))

add("pregnancy_self_test", "Class 2 IVD", "1.7", IVD_GUIDE,
    "TGA: pregnancy and fertility self-testing kits are Class 2 IVDs, because "
    "the result does not determine a serious condition. That is exception "
    "(a) to clause 1.4, so no clause of Schedule 2A mentions the device and "
    "1.7 gives Class 2. Exercises the fallback.",
    ivd("Pregnancy self-test",
        "Self-test for pregnancy used by a lay person at home; the result does "
        "not determine a serious condition.",
        is_self_test=Tri.YES, result_not_determining_serious_condition=Tri.YES))

add("wash_solution", "Class 1 IVD", "1.6(1)", IMDRF_IVD,
    "The international model the Schedule 2A rules come from gives wash "
    "solutions as an example of its rule 5, which clause 1.6(1) follows: an "
    "ancillary reagent used in a specific examination. Not an Australian "
    "source, so unverified.",
    ivd("Assay wash solution",
        "Wash solution with specific characteristics for use in a specific "
        "immunoassay examination; an ancillary reagent, not the test itself.",
        is_ancillary_reagent_or_article=Tri.YES),
    verified=False)

add("abo_reagent_red_cells", "Class 4 IVD", "1.2(2)", IHR_GUIDE,
    "TGA's worked example: reagent red cells for ABO reverse grouping are Class 4 "
    "under 1.2(2). Used in pretransfusion testing, so 1.2(1) is met too, but its "
    "paragraph (b) excludes a device mentioned in 1.2(2).",
    ivd("Reagent red blood cells for ABO reverse grouping",
        "Kit of red blood cells for performing ABO reverse groups in pretransfusion "
        "testing.",
        types_blood_or_tissue=Tri.YES,
        assesses_transfusion_or_transplant_compatibility=Tri.YES,
        detects_listed_blood_group_marker=Tri.YES))


add("infusion_pump", "Class IIb", "4.4(2)", ACTIVE,
    "TGA's active device guidance lists infusion pumps under 4.4(2), Class IIb: "
    "administration that is potentially hazardous lifts it above the 4.4(1) "
    "baseline.",
    device("Volumetric infusion pump",
           "Administers medicines to a patient at a controlled rate, where the "
           "manner of administration is potentially hazardous.",
           is_active_device=Tri.YES, active_for_therapy=Tri.YES,
           administers_or_removes_substances=Tri.YES,
           substance_administration_potentially_hazardous=Tri.YES))


# -- Schedule 2 Part 5, clauses no other fixture reaches. -----------------
add("nebuliser", "Class IIb", "5.10(a)", NOT_IVD,
    "TGA gives a nebuliser as its 5.10(a) example: the device's mode of action "
    "has an essential impact on the efficacy and safety of the inhaled medicine.",
    device("Nebuliser",
           "Aerosolises a liquid medicine for the patient to inhale; failure to "
           "aerosolise the medicine would affect its efficacy.",
           is_active_device=Tri.YES, active_for_therapy=Tri.YES,
           administers_or_removes_substances=Tri.YES,
           handles_substances_for_administration=Tri.YES,
           channels_or_stores_liquid_or_gas_for_administration=Tri.YES,
           connected_to_active_device=Tri.NO,
           administers_by_inhalation=Tri.YES,
           inhalation_mode_of_action_essential=Tri.YES,
           inhalation_treats_life_threatening_condition=Tri.NO))

add("saline_nasal_spray", "Class IIa", "5.11(c)", NOT_IVD,
    "TGA lists isotonic saline nasal sprays under 5.11; its decision tree puts a "
    "substance introduced into the nasal cavity that achieves its purpose there "
    "at Class IIa. Saline is not a medicine, so 5.1 does not apply.",
    device("Isotonic saline nasal spray",
           "Isotonic saline solution sprayed into the nasal cavity, where it achieves "
           "its intended purpose.",
           invasiveness=Invasiveness.BODY_ORIFICE, duration=Duration.TRANSIENT,
           orifice_site=OrificeSite.NASAL_CAVITY, connected_to_an_active_device=Tri.NO,
           is_substance_through_orifice_or_skin=Tri.YES,
           substance_acts_in_nose_mouth_or_on_skin=Tri.YES))

add("virtual_anatomical_model_software", "Class IIa", "5.4(3)", NOT_IVD,
    "TGA's 5.4(3) example: software that generates a 3D anatomical virtual model "
    "from patient scans for a health professional diagnosing a stress fracture. "
    "5.4(3) is the only rule the source names; the software's own Part 4 "
    "questions are answered no.",
    device("Virtual anatomical model software",
           "Generates a 3D anatomical virtual model from patient scans for a health "
           "professional diagnosing a stress fracture.",
           status=PROCESSES_DEVICE_DATA,
           software=Tri.YES, active_for_diagnosis=Tri.YES,
           records_images_or_anatomical_model=Tri.YES,
           generates_virtual_anatomical_model=Tri.YES))


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
                   is_ivd_instrument=Tri.YES),
            ivd_fn("Prothrombin time test strips",
                   "Test strips for prothrombin time self-testing by a lay person.",
                   is_self_test=Tri.YES),
            fn("Lancet",
               "Single-use lancet for obtaining a capillary blood specimen.",
               invasiveness=Invasiveness.SURGICALLY_INVASIVE,
               duration=Duration.TRANSIENT,
               reusable_surgical_instrument=Tri.NO),
        ],
        sterile=Tri.YES,
    ),
    [("Class 1 IVD", "1.6(2)(a)"), ("Class 3 IVD", "1.4"), ("Class IIa", "3.2")],
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
               status=IMAGE_STORAGE, software=Tri.YES),
            fn("Abnormality triage",
               "Flags studies showing suspected abnormality for priority review "
               "by a radiologist.",
               status=PROCESSES_DEVICE_DATA, software=Tri.YES, active_for_diagnosis=Tri.YES,
               diagnoses_or_screens=Tri.YES,
               decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
               condition_severity=Severity.SERIOUS,
               public_health_risk=PublicHealthRisk.MODERATE),
            fn("Follow-up interval suggestion",
               "Analyses the scan images and suggests a follow-up imaging interval "
               "to the reporting radiologist.",
               status=PROCESSES_DEVICE_DATA, software=Tri.YES,
               specifies_or_recommends_treatment=Tri.YES,
               decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
               treatment_risk=TreatmentRisk.OTHER_HARM,
               public_health_risk=PublicHealthRisk.LOW),
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
               status=WELLNESS_TRACKING, software=Tri.YES),
            fn("Symptom checker",
               "Asks a consumer about symptoms and suggests whether to seek "
               "medical care.",
               status=dict(cdss_replaces_clinical_judgement=Tri.YES),
               software=Tri.YES, active_for_diagnosis=Tri.YES,
               diagnoses_or_screens=Tri.YES,
               decision_maker=DecisionMaker.DEVICE_TO_LAY_USER,
               condition_severity=Severity.OTHER,
               public_health_risk=PublicHealthRisk.LOW),
        ],
    ),
    [(None, "S1-14B", EXCLUDED),
     ("Class IIa", "4.5(1)(e)")],
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
           status=WELLNESS_TRACKING, software=Tri.YES),
    verified=False, status=EXCLUDED)

add("anatomy_education_app", None, "no limb of s41BD reached", GATE_TEXT,
    "Teaching software for students. It is used on no patient and reaches no "
    "limb of s41BD, it serves no device, and no exclusion item describes it, "
    "so it is simply not a medical device. The only fixture that exercises the "
    "not-a-device verdict and the accessory question.",
    device("Anatomy teaching app",
           "Interactive 3D anatomy lessons for medical students, used for "
           "study only and never on a patient.",
           status=NO_PURPOSE, software=Tri.YES),
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
           software=Tri.YES,
           specifies_or_recommends_treatment=Tri.YES,
           decision_maker=DecisionMaker.INFORMS_PROFESSIONAL,
           treatment_risk=TreatmentRisk.OTHER_HARM,
           public_health_risk=PublicHealthRisk.LOW),
    verified=False, status=EXEMPT_CDSS)


# -- Intake cases. -------------------------------------------------------------

# The same device, as a founder would describe it. Plain words, no clause
# vocabulary, and nothing the fixture's profile contradicts.
FOUNDER_TEXTS = {
    "melanoma_screening_app": (
        "SpotCheck lets anyone check a worrying mole at home. You point your "
        "phone at the mole and our AI tells you whether it looks like it could "
        "be melanoma, so you know whether you need to see a doctor. The result "
        "goes straight to you; no clinician reviews it."
    ),
    "screw_long_term": (
        "We make titanium bone screws that surgeons put in to hold a broken "
        "bone together. They stay in the patient permanently. Every screw is "
        "packed sterile."
    ),
    "sterile_barrier_dressing": (
        "A plaster for small cuts and grazes. It soaks up fluid from the wound "
        "and keeps dirt out while it heals. Each one comes individually wrapped "
        "and sterile."
    ),
    "pregnancy_self_test": (
        "Our pregnancy test is a stick you pee on at home. Two lines means "
        "pregnant. It is designed for women to use themselves, and it only "
        "tells you whether you are pregnant."
    ),
    "tens_device": (
        "PainAway is a small battery-powered unit with sticky pads. You put the "
        "pads on your lower back and it sends gentle electrical pulses through "
        "the skin to ease back pain. The pulses are low power and are not "
        "dangerous."
    ),
    "cbt_app_bipolar": (
        "MoodPath is an app that delivers cognitive behavioural therapy "
        "sessions to people living with bipolar disorder. We wrote the program "
        "ourselves rather than following a published clinical guideline, and "
        "if it is used wrongly the therapy could cause harm."
    ),
    "chlamydia_test": (
        "A laboratory test kit that picks up chlamydia from a patient swab, so "
        "doctors can diagnose the infection."
    ),
    "imaging_platform": (
        "Our cloud platform stores hospital radiology scans. It also flags "
        "scans that look abnormal so a radiologist reads them first, and it "
        "looks at the images and suggests when the patient should have their "
        "next scan. The radiologist always makes the call."
    ),
    "wellness_sleep_tracker": (
        "Our app tracks your sleep and daily activity to help you feel your "
        "best. It is a lifestyle product for general wellbeing."
    ),
}


def described_text(profile):
    """The fixture's own wording, as one description."""
    core = profile.core
    parts = [f"{core.product_name.value}. {core.intended_purpose.value}"]
    if len(profile.functions) > 1:
        parts += [f"{f.name.value}: {f.description.value}" for f in profile.functions]
    return " ".join(parts)


SECTION_DEFAULTS = {"status": STATUS_DEFAULTS, "general": GENERAL_DEFAULTS,
                    "ivd": IVD_DEFAULTS}


def _plain(value):
    return getattr(value, "value", value)


def specific_fields(profile):
    """Dotted names of the facts this fixture sets on purpose.

    Kind and therapeutic purpose always count. Otherwise a field counts when
    its value differs from the builder default, or is a yes on the product.
    Fields extraction may never claim are left out.
    """
    names = []
    for field in ("supplied_sterile", "has_measuring_function"):
        if getattr(profile.core, field).value is Tri.YES:
            names.append(f"core.{field}")
    for index, function in enumerate(profile.functions):
        names.append(f"functions.{index}.kind")
        if function.is_software.value is Tri.YES:
            names.append(f"functions.{index}.is_software")
        for section, defaults in SECTION_DEFAULTS.items():
            part = getattr(function, section)
            if part is None:
                continue
            for name in type(part).model_fields:
                answer = getattr(part, name)
                if not answer.resolved or f"{section}.{name}" not in EXTRACTABLE:
                    continue
                if name not in defaults or _plain(defaults[name]) != _plain(answer.value):
                    names.append(f"functions.{index}.{section}.{name}")
    return names


def intake_cases(slug, profile):
    cases = {"described": described_text(profile)}
    if slug in FOUNDER_TEXTS:
        cases["founder"] = FOUNDER_TEXTS[slug]
    return cases


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
                "expected_qualifiers": list(qualifiers),
            }
            for function, (expected, rule, function_status, qualifiers)
            in zip(profile.functions, expectations, strict=True)
        ]
        payload = {
            "expected_status": status.value,
            "expected_classes": highest_class(e for e, *_ in expectations),
            "functions": functions,
            "source": source,
            "verified": verified,
            "note": note,
            "profile": profile.model_dump(mode="json"),
            "intake": {
                "cases": intake_cases(slug, profile),
                "specific": specific_fields(profile),
            },
        }
        (OUT / f"{slug}.json").write_text(json.dumps(payload, indent=2) + "\n")
        flag = "  " if verified else " ?"
        count = f"{len(functions)} fn" if len(functions) > 1 else "     "
        summary = ", ".join(sorted(payload["expected_classes"].values())) or "no class"
        extras = sorted({q for *_, qs in expectations for q in qs})
        if extras:
            summary = f"{summary} + {', '.join(extras)}"
        if status is not REGULATED:
            summary = f"{summary} [{status.value}]"
        warn = f"  MISSING: {missing}" if missing else ""
        print(f"{flag} {slug:34} {count} {summary}{warn}")

    unknown = set(FOUNDER_TEXTS) - {slug for slug, *_ in F}
    assert not unknown, f"founder texts for fixtures that do not exist: {unknown}"

    verified_count = sum(1 for f in F if f[4])
    multi = sum(1 for f in F if len(f[5]) > 1)
    print(f"\n{len(F)} fixtures, {verified_count} verified, {multi} multi-function, "
          f"{gaps} unresolved fields")


if __name__ == "__main__":
    main()
