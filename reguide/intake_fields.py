"""What extraction is allowed to claim, and the shape the model returns.

Every profile field is either EXTRACTABLE (the model may claim it, with a
verbatim quote) or ASK_ONLY (only the founder's answer can set it). A test
checks that the two lists together cover the whole schema, so a field added
to profile.py cannot slip through without someone deciding which it is.

A claim names its field as "<section>.<field>":

    core.*      product-level, function_index -1
    funding.*   product-level, function_index -1
    function.*  the function's own name-free fields (kind, is_software)
    status.*    StatusProfile, the regulatory status gate
    general.*   GeneralDeviceProfile, Schedule 2
    ivd.*       IvdProfile, Schedule 2A

The guide text is written for the model, not the founder. It says what the
field means in the Regulations' terms, closely enough that the model can tell
when a phrase in the description supports it. The founder-facing wording is a
separate job (next_question, step 4).
"""

from enum import Enum

from .profile import (
    CoreProfile,
    FunctionProfile,
    FundingProfile,
    GeneralDeviceProfile,
    IvdProfile,
    StatusProfile,
)

PRODUCT_SECTIONS = ("core", "funding")
FUNCTION_SECTIONS = ("function", "status", "general", "ivd")

SECTION_MODELS = {
    "core": CoreProfile,
    "funding": FundingProfile,
    "function": FunctionProfile,
    "status": StatusProfile,
    "general": GeneralDeviceProfile,
    "ivd": IvdProfile,
}

# Function fields that are not Answers of their own, or that extraction sets
# through the functions list rather than through a claim.
FUNCTION_STRUCTURE = {"status", "general", "ivd", "name", "description"}


# Fields only the founder can settle. Each reason is why a quote is not
# enough: the field is a legal judgement, a lookup, or a confirmation.
ASK_ONLY: dict[str, str] = {
    "core.functions_confirmed":
        "the split into functions is proposed by intake and must be confirmed",
    "status.principal_action_pharmacological":
        "whether the principal action is pharmacological is a legal judgement",
    "status.is_accessory_to_device":
        "being an accessory is a legal status under s41BD(1)(b), not a description",
    "status.excluded_item":
        "an Excluded Goods Determination item is a lookup the founder confirms",
    "status.exclusion_conditions_met":
        "every condition of an exclusion item has to be confirmed one by one",
    "general.public_health_risk":
        "the public health risk grade is a regulatory judgement",
    "ivd.agent_serious_with_high_propagation_risk":
        "a high risk of propagation in Australia is a regulatory judgement",
    "funding.is_first_in_class":
        "first in class is a market judgement the founder makes",
    "funding.privately_insured_patients":
        "who pays is asked when stage 5 needs it",
}


EXTRACTABLE: dict[str, str] = {
    # ---------------------------------------------------------------- core
    "core.product_name":
        "The product's name as the founder writes it. The value must be copied "
        "from inside the evidence.",
    "core.intended_purpose":
        "The statement of what the product is for, who it is for and how it is "
        "used, copied word for word. The value must be exactly the evidence. Use "
        "the founder's own sentence; never summarise or combine sentences.",
    "core.supplied_sterile":
        "The product is supplied sterile.",
    "core.has_measuring_function":
        "The product measures a physiological or anatomical quantity, or a "
        "quantity of energy or substance delivered to or removed from the body, "
        "and shows the result in legal units (regulation 1.4).",

    # ------------------------------------------------------------- function
    "function.kind":
        "general_device, or ivd when the function examines a specimen taken "
        "from the human body (blood, urine, saliva, tissue, a swab) outside the "
        "body, as a reagent, kit, calibrator, control, instrument, specimen "
        "container or software.",
    "function.is_software":
        "The function is software or an app, rather than a physical object.",

    # --------------------------------------------------------------- status
    "status.therapeutic_purpose":
        "Which purpose the text states for this function: diagnosis, prevention, "
        "monitoring, prediction, prognosis, treatment or alleviation of a disease "
        "(diagnosis_prevention_monitoring_prediction_treatment_of_disease); "
        "diagnosis, monitoring, treatment or compensation of an injury "
        "(diagnosis_monitoring_treatment_or_compensation_for_injury); "
        "investigation, replacement or modification of anatomy or of a "
        "physiological process (investigation_or_modification_of_anatomy_or_"
        "physiological_process); control or support of conception "
        "(control_or_support_of_conception); in vitro examination of a specimen "
        "from the human body for a medical purpose (in_vitro_examination_of_"
        "specimen_for_medical_purpose). Never claim no_therapeutic_purpose.",
    "status.cdss_sole_purpose_recommendation":
        "The function's only purpose is to give a health professional a "
        "recommendation about preventing, diagnosing, curing or alleviating a "
        "disease or condition.",
    "status.cdss_processes_device_signal_or_image":
        "The function processes or analyses a medical image, or a signal from "
        "another medical device (an ECG trace, a CT scan, a pulse oximeter "
        "reading).",
    "status.cdss_replaces_clinical_judgement":
        "The function is intended to replace a health professional's clinical "
        "judgement, so its output is acted on without the professional "
        "independently reviewing the basis for it.",

    # ---------------------------------------------- general: route and contact
    "general.invasiveness":
        "How the device itself enters the body: non_invasive (does not enter it); "
        "invasive_body_orifice (through a natural opening such as the mouth, "
        "nose, ear canal, anus, vagina or urethra, or through a stoma); "
        "surgically_invasive (through the skin or a body surface, by or during "
        "surgery, including needles and cannulas); implantable (placed in the "
        "body, or replacing a surface of it, to stay there after the procedure). "
        "Judge where the device goes, not where a substance it delivers goes: a "
        "mist the patient inhales or a liquid it infuses does not make the "
        "device invasive.",
    "general.duration":
        "How long it is in continuous use: transient (under 60 minutes), "
        "short_term (60 minutes to 30 days), long_term (over 30 days). Convert a "
        "stated time into the band; the evidence is the stated time.",
    "general.orifice_site":
        "Which orifice: oral_cavity_as_far_as_pharynx, ear_canal_up_to_eardrum, "
        "nasal_cavity, other_body_orifice, or stoma.",

    # ------------------------------------ general: Part 2, non-invasive devices
    "general.handles_substances_for_administration":
        "It channels, stores or handles blood, body liquids, organs, tissues, "
        "or other liquids or gases that will later be infused, administered or "
        "introduced into the body.",
    "general.channels_or_stores_blood_for_administration":
        "It channels or stores blood for later administration into the body "
        "(clause 2.2(1)(a)).",
    "general.stores_organ_or_tissue_for_introduction":
        "It stores organs, parts of organs or body tissues for later "
        "introduction into a body (clause 2.2(1)(b)).",
    "general.channels_or_stores_liquid_or_gas_for_administration":
        "It channels or stores liquids or gases, other than blood, for later "
        "infusion, administration or introduction into the body (clause "
        "2.2(1)(c)).",
    "general.connected_to_active_device":
        "It may be connected to an active medical device of Class IIa or higher.",
    "general.saline_only_flush_or_patency":
        "It contains only saline and is for flushing, or for keeping a line or "
        "catheter open (clause 2.2A).",
    "general.modifies_composition_of_blood_or_infusion":
        "It changes the biological or chemical composition of blood, other body "
        "liquids, or liquids for infusion into the body (clause 2.3).",
    "general.treatment_is_filtration_centrifugation_or_exchange":
        "That change is made only by filtration, centrifugation, or exchange of "
        "gas or of heat (clause 2.3(2)). Exchange of solutes or of any other "
        "substance, as in dialysis, is none of these.",
    "general.contacts_injured_skin_or_mucous_membrane":
        "It comes into contact with injured skin or a mucous membrane (clause "
        "2.4).",
    "general.barrier_compression_or_absorption":
        "It is used only as a mechanical barrier, for compression, or to absorb "
        "exudate (clause 2.4(3)).",
    "general.principally_for_breached_dermis_secondary_intent":
        "It is principally for wounds that have breached the dermis and can "
        "heal only by secondary intent (clause 2.4(4)).",

    # ------------------------------------------ general: Part 3, invasive devices
    "general.connected_to_an_active_device":
        "It is intended to be connected to any active medical device (clause "
        "3.1).",
    "general.liable_to_be_absorbed_by_mucous_membrane":
        "It is liable to be absorbed by the mucous membrane (clause 3.1(2)).",
    "general.corrects_heart_or_circulatory_defect_by_contact":
        "It is specifically for diagnosing, monitoring or correcting a defect of "
        "the heart or of the central circulatory system through direct contact "
        "with those parts of the body.",
    "general.direct_contact_heart_circulation_or_nervous_system":
        "It is used in direct contact with the heart, the central circulatory "
        "system or the central nervous system.",
    "general.reusable_surgical_instrument":
        "It is a reusable surgical instrument.",
    "general.delivers_ionising_radiation":
        "It supplies energy in the form of ionising radiation (X-rays, gamma "
        "rays, a radioactive source).",
    "general.has_biological_effect":
        "It is intended to have a biological effect on the body.",
    "general.wholly_or_mostly_absorbed":
        "It is wholly or mainly absorbed by the body.",
    "general.undergoes_chemical_change":
        "It is intended to undergo chemical change in the body.",
    "general.placed_in_teeth":
        "It is intended to be placed in the teeth.",
    "general.administers_medicine_hazardously_by_delivery_system":
        "It administers a medicine through a delivery system in a way that is "
        "potentially hazardous.",
    "general.administers_medicine":
        "It is intended to administer a medicine.",
    "general.joint_replacement_or_surgical_mesh":
        "It is a total or partial joint replacement, or a surgical mesh.",
    "general.spinal_motion_preserving":
        "It is a spinal implant that preserves motion of the spine, such as a "
        "disc replacement.",

    # ------------------------------ general: Part 4, active devices and software
    "general.is_active_device":
        "It depends on a source of energy other than the human body or gravity: "
        "a battery, mains power, compressed gas.",
    "general.is_programmed_or_programmable":
        "The hardware runs firmware or software, or can be programmed. Claim it "
        "only when the text mentions software, firmware, a processor or "
        "programming; controlled or automatic behaviour alone is not enough.",
    "general.is_active_implantable":
        "It is an active device intended to be implanted.",
    "general.active_for_therapy":
        "It is an active device that supports, modifies, replaces or restores "
        "biological functions or structures to treat or relieve an illness, "
        "injury or disability.",
    "general.administers_or_exchanges_energy":
        "It gives energy to the body or exchanges energy with it (heat, "
        "electrical current, light, sound, mechanical energy).",
    "general.delivers_hazardous_energy":
        "It does so in a potentially hazardous way, given the kind, density and "
        "site of the energy.",
    "general.controls_hazardous_therapy_device":
        "It controls or monitors, or directly influences the performance of, an "
        "active therapy device that delivers energy in a hazardous way.",
    "general.diagnostic_function_determines_patient_management":
        "It includes a diagnostic function that significantly determines how "
        "the patient is managed.",
    "general.active_for_diagnosis":
        "It is an active device that supplies information for detecting, "
        "diagnosing, monitoring or treating a physiological condition, state of "
        "health, illness or congenital deformity.",
    "general.supplies_absorbed_energy_for_diagnosis":
        "It supplies energy that the body absorbs, other than visible light, to "
        "diagnose.",
    "general.images_radiopharmaceutical_distribution":
        "It images how a radiopharmaceutical is distributed in the body.",
    "general.diagnoses_or_monitors_vital_processes":
        "It directly diagnoses or monitors vital physiological processes.",
    "general.monitors_vital_parameters_immediate_danger":
        "It monitors vital physiological parameters (heart function, breathing, "
        "central nervous system activity) whose variation could put the patient "
        "in immediate danger.",
    "general.emits_ionising_radiation_for_interventional_radiology":
        "It emits ionising radiation for diagnostic or interventional radiology.",
    "general.controls_interventional_radiology_device":
        "It controls or monitors, or directly influences the performance of, a "
        "device that emits ionising radiation for radiology.",
    "general.administers_or_removes_substances":
        "It is an active device that gives medicines, body liquids or other "
        "substances to the body, or removes them from it.",
    "general.substance_administration_potentially_hazardous":
        "It does so in a potentially hazardous way.",
    "general.diagnoses_or_screens":
        "It provides information used to diagnose, or screen for, a disease or "
        "condition.",
    "general.monitors_disease_state":
        "It monitors the state or progression of a disease or condition, or a "
        "person's physiological parameters.",
    "general.specifies_or_recommends_treatment":
        "It specifies or recommends a treatment or intervention.",
    "general.provides_therapy_through_information":
        "It gives therapy to a person by providing information, as a "
        "psychological therapy app does.",
    "general.decision_maker":
        "Who acts on the output: device_gives_the_decision_to_a_lay_user (a "
        "patient or consumer receives the result or recommendation and acts on "
        "it); device_gives_the_decision_to_a_health_professional (the device "
        "itself specifies the result or treatment, and the professional carries "
        "it out as given); informs_a_health_professional_who_decides (the device "
        "suggests or recommends something to a professional, who then makes the "
        "decision, clause 4.7(2)).",
    "general.condition_severity":
        "How serious the disease or condition is, only when the text itself "
        "says so: death_or_severe_deterioration_without_urgent_treatment, "
        "serious_disease_or_condition, or any_other_case. Never use medical "
        "knowledge about the named disease.",
    "general.monitoring_danger":
        "What the monitored information could indicate, only when the text says "
        "so: immediate_danger, other_danger, or any_other_case.",
    "general.treatment_risk":
        "What the recommended treatment, or failing to give it, could cause, "
        "only when the text says so: death_or_severe_deterioration, "
        "otherwise_harmful, or any_other_case.",
    "general.information_therapy_harm":
        "What the therapy given through information could cause, only when the "
        "text says so: death_or_severe_deterioration, serious_harm, harm, or "
        "any_other_case.",

    # ------------------------------- general: Part 5, particular kinds of devices
    "general.is_export_only":
        "It is intended for export only, not for supply in Australia.",
    "general.incorporates_medicine":
        "It incorporates, as an integral part, a substance that would be a "
        "medicine if used on its own, acting in support of the device.",
    "general.human_blood_derivative":
        "The incorporated substance is a derivative of human blood or plasma.",
    "general.contraceptive_or_sti_prevention":
        "It is for contraception or for preventing sexually transmitted "
        "infections.",
    "general.cares_for_contact_lenses":
        "It is for disinfecting, cleaning, rinsing or hydrating contact lenses.",
    "general.disinfects_another_device":
        "It is for disinfecting another medical device.",
    "general.records_images_or_anatomical_model":
        "It captures images of a patient, or is or produces an anatomical model. "
        "Storing, displaying or transmitting images that something else captured "
        "does not count.",
    "general.records_patient_images_outside_visible_spectrum":
        "It records patient images using radiation outside the visible spectrum "
        "(X-ray, infrared, ultraviolet).",
    "general.is_anatomical_model_for_diagnosis":
        "It is an anatomical model used for diagnosis.",
    "general.generates_virtual_anatomical_model":
        "It is software that generates a virtual anatomical model of a patient.",
    "general.contains_non_viable_animal_material":
        "It contains non-viable animal tissue, cells or derivatives, other than "
        "hair, wool, sintered hydroxyapatite or tallow derivatives.",
    "general.contacts_intact_skin_only":
        "It comes into contact only with intact skin.",
    "general.is_blood_bag":
        "It is a blood bag.",
    "general.implantable_accessory_to_active_implantable":
        "It is an implantable accessory to an active implantable device.",
    "general.controls_active_implantable":
        "It controls, monitors or directly influences an active implantable "
        "device.",
    "general.is_mammary_implant":
        "It is a breast implant.",
    "general.administers_by_inhalation":
        "It administers medicines or biologicals by inhalation.",
    "general.inhalation_mode_of_action_essential":
        "Its mode of action has an essential effect on the medicine's efficacy "
        "and safety.",
    "general.inhalation_treats_life_threatening_condition":
        "The inhaled medicine treats a life-threatening condition.",
    "general.is_substance_through_orifice_or_skin":
        "It is made of substances introduced into the body through an orifice, "
        "or applied to the skin and absorbed.",
    "general.substance_acts_in_nose_mouth_or_on_skin":
        "Those substances act only in the nose or mouth, or on the skin.",

    # ------------------------------------------------------ ivd: Schedule 2A
    "ivd.is_ivd_instrument":
        "It is an instrument or analyser for in vitro diagnostic use, rather "
        "than a reagent or test kit (clause 1.6(2)(a)).",
    "ivd.is_specimen_receptacle":
        "It is a container for holding specimens (clause 1.6(2)(b)).",
    "ivd.is_culture_medium":
        "It is a microbiological culture medium (clause 1.6(2)(c)).",
    "ivd.is_quality_control_material":
        "It is a quality control material not assigned to a specific assay "
        "(clause 1.5).",
    "ivd.is_export_only":
        "It is intended for export only (clause 1.8).",
    "ivd.detects_infectious_agent":
        "It detects the presence of, or exposure to, an infectious or "
        "transmissible agent.",
    "ivd.types_blood_or_tissue":
        "It is used for blood grouping or tissue typing.",
    "ivd.is_self_test":
        "It is intended for a lay person to use, for example at home.",
    "ivd.screens_donations_for_transmissible_agents":
        "It screens donated blood, blood components, cells, tissues or organs "
        "for transmissible agents (clause 1.1(a)).",
    "ivd.assesses_transfusion_or_transplant_compatibility":
        "It assesses compatibility for transfusion or transplantation (clause "
        "1.2(1)).",
    "ivd.detects_listed_blood_group_marker":
        "It detects a blood group marker in the ABO, Rh, Kell, Kidd or Duffy "
        "systems (clause 1.2(2)).",
    "ivd.detects_sexually_transmitted_agent":
        "It detects a sexually transmitted agent (clause 1.3(a)).",
    "ivd.detects_limited_propagation_agent_in_csf_or_blood":
        "It detects an infectious agent in cerebrospinal fluid or blood, where "
        "the agent has a limited risk of propagation (clause 1.3(b)).",
    "ivd.error_could_cause_death_or_severe_disability":
        "An incorrect result could cause death or severe disability to the "
        "patient or to the patient's offspring (clause 1.3(c)).",
    "ivd.prenatal_immune_status_screening":
        "It screens pregnant women for immune status to an infectious agent "
        "(clause 1.3(d)).",
    "ivd.infective_status_error_life_threatening":
        "It determines infective disease or immune status where an error could "
        "lead to a life-threatening patient management decision (clause 1.3(e)).",
    "ivd.manages_life_threatening_infectious_disease":
        "It is used to manage a patient with a life-threatening infectious "
        "disease (clause 1.3(i)).",
    "ivd.selects_patients_for_therapy":
        "It selects patients for a particular therapy (clause 1.3(f)(i)).",
    "ivd.selects_patients_for_disease_staging":
        "It is used for disease staging (clause 1.3(f)(ii)).",
    "ivd.selects_patients_in_cancer_diagnosis":
        "It is used in the diagnosis of cancer (clause 1.3(f)(iii)).",
    "ivd.is_companion_diagnostic":
        "It is a companion diagnostic for a specific medicine (clause 1.3(fa)).",
    "ivd.is_human_genetic_test":
        "It is a human genetic test (clause 1.3(g)).",
    "ivd.monitors_levels_error_life_threatening":
        "It monitors levels of medicines, substances or biological components "
        "where an error could lead to a life-threatening decision (clause "
        "1.3(h)).",
    "ivd.screens_foetus_for_congenital_disorders":
        "It screens an embryo or foetus for congenital disorders (clause "
        "1.3(j)).",
    "ivd.result_not_determining_serious_condition":
        "It is a self-test whose result does not determine a medically serious "
        "condition (clause 1.4(a)).",
    "ivd.preliminary_with_follow_up_testing":
        "It is a self-test giving a preliminary result that needs follow-up "
        "laboratory testing (clause 1.4(b)).",
    "ivd.is_ancillary_reagent_or_article":
        "It is an ancillary reagent or article used in a specific examination, "
        "such as a buffer, a wash solution or a general reagent, rather than "
        "the test itself (clause 1.6(1)).",

    # -------------------------------------------------------------- funding
    "funding.care_setting":
        "Where it is used: public_hospital, private_hospital, specialist_rooms, "
        "primary_care, pathology_lab, or home_or_self_use.",
    "funding.operator":
        "Who operates it: medical_specialist, general_practitioner, "
        "nurse_or_allied_health, laboratory_scientist, or patient_or_carer.",
    "funding.replaces_existing_service":
        "The existing test, procedure or service it replaces, as the text names "
        "it. The value must be copied from inside the evidence.",
}


# The fields whose value is the founder's own text rather than a choice.
VERBATIM_VALUE = {"core.intended_purpose"}
VALUE_INSIDE_EVIDENCE = {"core.product_name", "funding.replaces_existing_service"}

# A "no" is a claim, and silence is not one. These fields may be claimed as
# "no" only when the evidence itself contains a negation. The exception is
# whether a function is software: "an adhesive dressing strip" positively
# describes a physical object.
NEGATION_EXEMPT = {"function.is_software"}


def target_section(target: str) -> str:
    return target.split(".", 1)[0]


def target_field(target: str) -> str:
    return target.split(".", 1)[1]


def value_type(target: str):
    """The T in the field's Answer[T]."""
    model = SECTION_MODELS[target_section(target)]
    annotation = model.model_fields[target_field(target)].annotation
    return annotation.__pydantic_generic_metadata__["args"][0]


def allowed_values(target: str) -> list[str] | None:
    """The values a claim may give, or None for free text."""
    kind = value_type(target)
    if isinstance(kind, type) and issubclass(kind, Enum):
        return [m.value for m in kind if m.value not in ("unknown", "no_therapeutic_purpose")]
    return None


def schema() -> dict:
    """The strict JSON schema the model's output has to match.

    Strict mode needs every property listed as required and no extra
    properties, so optional things are expressed as empty lists, not as
    missing keys. The target enum keeps the model from naming a field that
    does not exist or one it may not claim.
    """
    function = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "name_evidence", "description"],
        "properties": {
            "name": {"type": "string",
                     "description": "A short label for the function, a few words."},
            "name_evidence": {"type": "string",
                              "description": "The phrase of the text the label comes from, "
                                             "copied exactly."},
            "description": {"type": "string",
                            "description": "The text's own sentence or phrase describing "
                                           "this function, copied exactly."},
        },
    }
    claim = {
        "type": "object",
        "additionalProperties": False,
        "required": ["function_index", "target", "value", "evidence"],
        "properties": {
            "function_index": {"type": "integer",
                               "description": "Index into functions, or -1 for core.* "
                                              "and funding.* targets."},
            "target": {"type": "string", "enum": sorted(EXTRACTABLE)},
            "value": {"type": "string"},
            "evidence": {"type": "string",
                         "description": "The shortest phrase of the text that fully "
                                        "supports the value, copied exactly."},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["functions", "claims"],
        "properties": {
            "functions": {"type": "array", "items": function},
            "claims": {"type": "array", "items": claim},
        },
    }


def field_catalogue() -> str:
    """The field list as it appears in the instructions."""
    lines = []
    for target in sorted(EXTRACTABLE):
        values = allowed_values(target)
        if values is None:
            shape = "text"
        elif values == ["yes", "no"]:
            shape = "yes | no"
        else:
            shape = " | ".join(values)
        lines.append(f"- {target} [{shape}]: {EXTRACTABLE[target]}")
    return "\n".join(lines)


INSTRUCTIONS = f"""\
You read a founder's description of a health product and record only the \
facts the description states, for a classification under Australia's \
Therapeutic Goods (Medical Devices) Regulations 2002. You do not classify. \
Anything you leave out will be asked of the founder, so leaving a fact out \
costs one question, while recording a fact the text does not state can \
produce a wrong legal result.

Rules:
1. Record a claim only when a phrase of the text states it. Never use what \
is typical for this kind of product, your knowledge of the disease, the \
technology or the market, or what the founder probably means.
2. Silence is not "no". Claim "no" only when the text itself says no: \
"non-sterile", "does not store images", "used on intact skin only".
3. Evidence is copied from the text exactly, character for character, as \
the shortest phrase that fully supports the value. Never paraphrase, correct, \
shorten with ellipses or join separate phrases.
4. core.intended_purpose is the founder's own statement of what the product \
is for, copied exactly; its value and its evidence are the same text. If the \
text has no such statement, leave it out.
5. Split the product into functions only where the text describes distinct \
things it does, such as storing images and also flagging abnormal ones. Most \
products have one function. Each function's description is copied exactly \
from the text.
6. core.* and funding.* claims use function_index -1. Every other claim \
names the index of the function it is about.
7. general.* claims apply to a general device function and ivd.* claims to \
an IVD function; also record that function's function.kind.
8. Values are exactly one of the listed options. For yes/no fields use "yes" \
or "no". If none fits, leave the claim out.
9. Record each fact once. If the text is ambiguous or contradicts itself on \
a field, leave it out.

Fields you may claim:
{field_catalogue()}
"""
