"""The founder-facing question for every profile field.

intake_fields.py says what each field means to the extraction model, in the
Regulations' terms. This module says how each field is put to a founder who
has never read them: one plain question per field, the provision it feeds,
and the options, each option naming the value it sets.

Rules for the wording:

- Follow the clause. A question may explain a legal term in plain words, but
  it never widens or narrows what the provision says. Where the clause has a
  carve-out ("other than", "does not include"), the question says it.
- Never lead. A question does not say which answer gives a lower class.
- "Not sure" is always offered. Choosing it records that the founder could
  not answer; the field stays unknown and reaches the report as something
  for a regulatory adviser.
- One option set per field. A question may phrase a field the other way
  round (clause 1.4(a) is asked positively), in which case its options map
  "Yes" and "No" to the field's opposite values. The option says what it
  sets, so apply_answer never has to interpret wording.

A question with free text (the product's name, its intended purpose, a
function's name and description) offers only "Not sure"; the founder's typed
reply is the value.

Each entry names the corpus clause ids it was checked against (sources), so
scripts/review_questions.py can print the clause beside the question and the
planned source update check can tell which questions a changed clause
touches. Fields decided outside the Regulations' Schedules (the Act, the
Excluded Goods Determination, Schedule 4, regulations 1.4 and 3.9) have no
corpus clause and cite the instrument instead.

render(profile, dotted) turns an entry into the Question that next_question
hands to the interface, with the field's dotted path in every option.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from . import intake_fields as F
from .extract import Option, Question
from .profile import DeviceProfile, Tri
from .status import EXCLUSION_SOURCE, Exclusion, exclusion_key

REPO = Path(__file__).resolve().parent.parent

ACT = "Therapeutic Goods Act 1989"
EGD = "Therapeutic Goods (Excluded Goods) Determination 2018"
REGS = "Therapeutic Goods (Medical Devices) Regulations 2002"

UNSURE = Option(id="unsure", label="Not sure", unsure=True)


@dataclass(frozen=True)
class Entry:
    """One field's question.

    choices lists (option id, label, value) in the order shown. Empty means a
    free-text question. value is the field's own value as a string, which is
    parsed into the field's type when the Question is rendered.
    """

    target: str                       # "general.duration"
    text: str
    clause: str                       # the provision, as the report cites it
    sources: tuple[str, ...] = ()     # corpus clause ids, "s2-1.1"
    hint: str = ""
    choices: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)


YES_NO = (("yes", "Yes", "yes"), ("no", "No", "no"))

CATALOGUE: dict[str, Entry] = {}


def _add(entry: Entry) -> None:
    if entry.target in CATALOGUE:
        raise ValueError(f"two questions for {entry.target}")
    CATALOGUE[entry.target] = entry


def yes_no(target, text, clause, sources=(), hint="", choices=YES_NO):
    _add(Entry(target, text, clause, tuple(sources), hint, tuple(choices)))


def choice(target, text, clause, sources, labels, hint=""):
    """An enum field. labels maps each value to its label, in display order."""
    choices = tuple((value, label, value) for value, label in labels.items())
    _add(Entry(target, text, clause, tuple(sources), hint, choices))


def free(target, text, clause, hint=""):
    _add(Entry(target, text, clause, (), hint, ()))


# --------------------------------------------------------------------------
# Product level
# --------------------------------------------------------------------------

free("core.product_name", "What is the product called?", "Product name")
free("core.intended_purpose",
     "In your own words, what is the product for, who is it for, and how is it used?",
     "Intended purpose",
     hint="The wording you would put on the label or in the instructions for use is best. "
          "It is kept word for word.")
yes_no("core.supplied_sterile", "Is the product supplied sterile?",
       f"{REGS} regulation 3.9(2)")
yes_no("core.has_measuring_function",
       "Does the product measure a physiological or anatomical quantity, or a quantity of "
       "energy or substance given to or removed from the body, and show the result in units "
       "of measurement?",
       f"{REGS} regulations 1.4 and 3.9(3)",
       hint="For example, a thermometer that shows a temperature in degrees Celsius.")
yes_no("core.functions_confirmed",
       "Is that the right way to split up what your product does?",
       "Product decomposition",
       hint="Each part is assessed on its own, so the split can change the result.",
       choices=(("yes", "Yes, that is right", "yes"),
                ("no", "No, it should be split differently", "no")))

# --------------------------------------------------------------------------
# Each function's basics
# --------------------------------------------------------------------------

free("function.name", "What would you call this part of the product?", "Function name")
free("function.description", "In a sentence, what does this part of the product do?",
     "Function description")
choice("function.kind",
       "Is it used to examine specimens taken from the human body, such as blood, urine, "
       "saliva, tissue or a swab, outside the body?",
       f"{REGS} regulation 3.2 and the dictionary definition of an IVD medical device",
       (),
       {"ivd": "Yes, it examines specimens outside the body",
        "general_device": "No"},
       hint="This includes a test, reagent, instrument, specimen container or software used "
            "for that examination.")
yes_no("function.is_software",
       "Is it software or an app, rather than a physical object?",
       f"{REGS} Schedule 2 Part 4", ("s2-4.5",))

# --------------------------------------------------------------------------
# The status gate
# --------------------------------------------------------------------------

choice("status.therapeutic_purpose",
       "Which of these is it intended for?",
       f"{ACT} s41BD(1)(a)", (),
       {"diagnosis_prevention_monitoring_prediction_treatment_of_disease":
            "Diagnosing, preventing, monitoring, predicting, giving a prognosis for, treating "
            "or alleviating a disease",
        "diagnosis_monitoring_treatment_or_compensation_for_injury":
            "Diagnosing, monitoring, treating, alleviating or compensating for an injury or "
            "disability",
        "investigation_or_modification_of_anatomy_or_physiological_process":
            "Investigating, replacing or modifying the anatomy, or a physiological or "
            "pathological process or state",
        "control_or_support_of_conception": "Controlling or supporting conception",
        "in_vitro_examination_of_specimen_for_medical_purpose":
            "Examining a specimen from the human body outside the body, for a medical purpose",
        "no_therapeutic_purpose": "None of these"},
       hint="Choose the one that best matches what it is intended to do.")
yes_no("status.principal_action_pharmacological",
       "Is its main intended action on the body achieved by pharmacological, immunological "
       "or metabolic means, the way a medicine works?",
       f"{ACT} s41BD(1)(a), closing words",
       hint="A device can be helped along by such means and still be a device. The question "
            "is what does the main work.")
yes_no("status.is_accessory_to_device",
       "Is it made specifically to be used together with a medical device, so that the "
       "device can be used as intended or to assist its medical function?",
       f"{ACT} s41BD(1)(b)")
_add(Entry("status.excluded_item",
           "Does one of these descriptions fit this part of the product exactly?",
           f"{EGD}, Schedules 1 and 2",
           hint="Goods these items describe are outside the medical device rules. Each has "
                "conditions, which the next question checks one item at a time."))
yes_no("status.exclusion_conditions_met",
       "Does every condition in that description hold for it?",
       f"{EGD}, Schedules 1 and 2",
       hint="If any part of the description does not fit, answer No.")
yes_no("status.cdss_sole_purpose_recommendation",
       "Is its only purpose to give a health professional a recommendation, or to support "
       "one, about preventing, diagnosing, curing or alleviating a disease, ailment, defect "
       "or injury?",
       f"{REGS} Schedule 4 Part 2 item 2.15")
yes_no("status.cdss_processes_device_signal_or_image",
       "Does it process or analyse a medical image, or a signal from another medical device, "
       "such as an ECG trace, a scan or a pulse oximeter reading?",
       f"{REGS} Schedule 4 Part 2 item 2.15")
yes_no("status.cdss_replaces_clinical_judgement",
       "Is it intended to replace a health professional's clinical judgement, so that its "
       "output is acted on without the professional independently reviewing the basis "
       "for it?",
       f"{REGS} Schedule 4 Part 2 item 2.15")

# --------------------------------------------------------------------------
# Schedule 2: route and duration
# --------------------------------------------------------------------------

S2 = f"{REGS} Schedule 2"

choice("general.invasiveness",
       "Does it go into the body, and if so, how?",
       f"{S2} Parts 2 and 3, and the dictionary", ("s2-2.1", "s2-3.1"),
       {"non_invasive": "It does not go into the body",
        "invasive_body_orifice":
            "Through a natural opening, such as the mouth, nose, ear canal, anus, vagina or "
            "urethra, or through a stoma",
        "surgically_invasive":
            "Through the skin or another body surface, by or during surgery, including "
            "needles and cannulas",
        "implantable":
            "It is placed in the body, or replaces a body surface, to stay there after "
            "the procedure"},
       hint="Answer for the device itself, not for anything it delivers: a mist a patient "
            "breathes in, or a liquid it pumps into a vein, does not make the device itself "
            "go into the body.")
choice("general.duration",
       "How long is it intended to be used continuously?",
       f"{S2} clause 1.1", ("s2-1.1",),
       {"transient": "Less than 60 minutes",
        "short_term": "From 60 minutes up to 30 days",
        "long_term": "More than 30 days"},
       hint="Short breaks, such as taking it out to clean it, do not count as stopping.")
choice("general.orifice_site",
       "Which opening does it go into?",
       f"{S2} clause 3.1(2)", ("s2-3.1",),
       {"oral_cavity_as_far_as_pharynx": "The mouth, no further than the throat (pharynx)",
        "ear_canal_up_to_eardrum": "The ear canal, no further than the eardrum",
        "nasal_cavity": "The nasal cavity",
        "other_body_orifice": "Another natural opening",
        "stoma": "A stoma"})

# --------------------------------------------------------------------------
# Schedule 2 Part 2: non-invasive devices
# --------------------------------------------------------------------------

yes_no("general.handles_substances_for_administration",
       "Does it handle blood, other body liquids, organs or tissue, or any liquid or gas that "
       "is to be given to a patient, for example by channelling, storing, flushing or "
       "treating it?",
       f"{S2} clauses 2.2, 2.2A and 2.3", ("s2-2.2", "s2-2.2A", "s2-2.3"))
yes_no("general.channels_or_stores_blood_for_administration",
       "Is it used to channel or store blood or other body liquids that are to be infused, "
       "administered or introduced into a patient?",
       f"{S2} clause 2.2(1)(a)", ("s2-2.2",))
yes_no("general.stores_organ_or_tissue_for_introduction",
       "Is it used to store an organ, part of an organ or body tissue that is later to be "
       "introduced into a patient?",
       f"{S2} clause 2.2(1)(b)", ("s2-2.2",))
yes_no("general.channels_or_stores_liquid_or_gas_for_administration",
       "Is it used to channel or store any other liquid or gas that is to be infused, "
       "administered or introduced into a patient?",
       f"{S2} clause 2.2(1)(c)(i)", ("s2-2.2",))
yes_no("general.connected_to_active_device",
       "May it be connected to a powered (active) medical device that is Class IIa or higher, "
       "such as an infusion pump or a ventilator?",
       f"{S2} clauses 2.2(1)(c)(ii) and 3.1(3)", ("s2-2.2", "s2-3.1"),
       hint="If you do not know the class of the device it connects to, answer Not sure.")
yes_no("general.saline_only_flush_or_patency",
       "Is it for keeping another medical device open, or for flushing the inside of another "
       "medical device, and does it contain only saline for that purpose?",
       f"{S2} clause 2.2A", ("s2-2.2A",))
yes_no("general.modifies_composition_of_blood_or_infusion",
       "Is it used to change the biological or chemical composition of blood, other body "
       "liquids, or liquids to be infused into a patient?",
       f"{S2} clause 2.3(1)", ("s2-2.3",))
yes_no("general.treatment_is_filtration_centrifugation_or_exchange",
       "Does that treatment consist of filtration, centrifugation, or exchange of gas or of "
       "heat?",
       f"{S2} clause 2.3(2)", ("s2-2.3",),
       hint="Exchange of other substances, as in dialysis, is none of these.")
yes_no("general.contacts_injured_skin_or_mucous_membrane",
       "Is it used in contact with injured skin or a mucous membrane, such as the moist "
       "lining of the mouth or nose?",
       f"{S2} clause 2.4(1)", ("s2-2.4",),
       hint="A device mainly for managing the micro-environment of a wound counts.")
yes_no("general.barrier_compression_or_absorption",
       "Is it used as a mechanical barrier, for compression, or to absorb fluid from a "
       "wound (exudate)?",
       f"{S2} clause 2.4(3)", ("s2-2.4",))
yes_no("general.principally_for_breached_dermis_secondary_intent",
       "Is it mainly for wounds that have gone through the dermis (the deeper layer of the "
       "skin) and can only heal by secondary intent, that is, from the base up because the "
       "edges cannot be closed?",
       f"{S2} clause 2.4(4)", ("s2-2.4",))

# --------------------------------------------------------------------------
# Schedule 2 Part 3: invasive devices
# --------------------------------------------------------------------------

yes_no("general.connected_to_an_active_device",
       "Is it intended to be connected to a powered (active) medical device of any kind?",
       f"{S2} clause 3.1(2) and (3)", ("s2-3.1",),
       hint="An active device relies on a source of energy other than the body or gravity, "
            "such as a battery or mains power.")
yes_no("general.liable_to_be_absorbed_by_mucous_membrane",
       "Is it liable to be absorbed by the skin or the mucous membrane?",
       f"{S2} clause 3.1(2)(c)(ii)", ("s2-3.1",))
yes_no("general.corrects_heart_or_circulatory_defect_by_contact",
       "Is it specifically intended to diagnose, monitor, control or correct a defect of the "
       "heart or of the central circulatory system, through direct contact with those parts "
       "of the body?",
       f"{S2} clauses 3.2(3) and 3.3(4)(a)", ("s2-3.2", "s2-3.3"))
yes_no("general.direct_contact_heart_circulation_or_nervous_system",
       "Is it specifically intended to be used in direct contact with the heart, the central "
       "circulatory system or the central nervous system?",
       f"{S2} clauses 3.2(3A), 3.3(4)(b) and 3.4(4)(a)", ("s2-3.2", "s2-3.3", "s2-3.4"))
yes_no("general.reusable_surgical_instrument",
       "Is it a reusable surgical instrument, one made to be cleaned and sterilised and used "
       "again?",
       f"{S2} clauses 3.2(3A) and 3.2(4)", ("s2-3.2",))
yes_no("general.delivers_ionising_radiation",
       "Is it used to supply energy in the form of ionising radiation, such as X-rays, gamma "
       "rays or a radioactive source?",
       f"{S2} clauses 3.2(5)(a) and 3.3(3)(a)", ("s2-3.2", "s2-3.3"))
yes_no("general.has_biological_effect",
       "Is it intended to have a biological effect on the body?",
       f"{S2} clauses 3.2(5)(b), 3.3(4)(c) and 3.4(4)(b)", ("s2-3.2", "s2-3.3", "s2-3.4"))
yes_no("general.wholly_or_mostly_absorbed",
       "Is it intended to be wholly, or mostly, absorbed by the patient's body?",
       f"{S2} clauses 3.2(5)(c), 3.3(4)(d) and 3.4(4)(c)", ("s2-3.2", "s2-3.3", "s2-3.4"))
yes_no("general.undergoes_chemical_change",
       "Is it intended to undergo a chemical change in the patient's body?",
       f"{S2} clauses 3.3(3)(b) and 3.4(4)(d)", ("s2-3.3", "s2-3.4"))
yes_no("general.placed_in_teeth",
       "Is it intended to be placed in the teeth?",
       f"{S2} clauses 3.3(3)(b), 3.3(5), 3.4(3) and 3.4(5)", ("s2-3.3", "s2-3.4"),
       hint="Going into a tooth counts. Going through a tooth into the gum or bone beyond "
            "it does not.")
yes_no("general.administers_medicine_hazardously_by_delivery_system",
       "Is it used to give a medicine to a patient through a delivery system, in a way that "
       "is potentially hazardous to the patient because of the characteristics of the "
       "device?",
       f"{S2} clause 3.2(5)(d)", ("s2-3.2",))
yes_no("general.administers_medicine",
       "Is it intended to give a medicine to the patient?",
       f"{S2} clauses 3.3(3)(c) and 3.4(4)(e)", ("s2-3.3", "s2-3.4"))
yes_no("general.joint_replacement_or_surgical_mesh",
       "Is it a joint replacement device, or surgical mesh?",
       f"{S2} clause 3.4(4A)", ("s2-3.4",))
yes_no("general.spinal_motion_preserving",
       "Is it a motion-preserving device for the spine, such as a spinal disc replacement?",
       f"{S2} clause 3.4(4B)", ("s2-3.4",))

# --------------------------------------------------------------------------
# Schedule 2 Part 4: active devices and software
# --------------------------------------------------------------------------

yes_no("general.is_active_device",
       "Does it rely on a source of energy other than the human body or gravity, such as a "
       "battery, mains power or compressed gas?",
       f"{S2} clause 4.1 and the dictionary", ("s2-4.1",))
yes_no("general.is_programmed_or_programmable",
       "Does it run software or firmware, or can it be programmed?",
       f"{S2} clauses 4.5 to 4.8", ("s2-4.5", "s2-4.6", "s2-4.7", "s2-4.8"))
yes_no("general.is_active_implantable",
       "Is it a powered (active) device intended to be put wholly or partly into the body, "
       "and to stay there after the procedure, such as a pacemaker?",
       f"{S2} clause 5.7(1) and the dictionary", ("s2-5.7",))
yes_no("general.active_for_therapy",
       "Is it a powered (active) device used to support, change, replace or restore "
       "biological functions or structures, to treat or relieve an illness, injury or "
       "disability?",
       f"{S2} clause 4.2 and the dictionary", ("s2-4.2",))
yes_no("general.administers_or_exchanges_energy",
       "Is it used to give energy to the patient, or to exchange energy to or from the "
       "patient, for example heat, electrical current, light, sound or movement?",
       f"{S2} clause 4.2(1)", ("s2-4.2",))
yes_no("general.delivers_hazardous_energy",
       "Is that energy given or exchanged in a potentially hazardous way, given the nature, "
       "density and site of application of the energy?",
       f"{S2} clause 4.2(2)", ("s2-4.2",))
yes_no("general.controls_hazardous_therapy_device",
       "Is it used to control or monitor, or directly influence, the performance of a powered "
       "therapy device that gives energy in a potentially hazardous way?",
       f"{S2} clause 4.2(3)", ("s2-4.2",))
yes_no("general.diagnostic_function_determines_patient_management",
       "Does it include a diagnostic function whose purpose is to significantly determine how "
       "the device itself manages the patient, as an automated external defibrillator "
       "decides whether to shock?",
       f"{S2} clause 4.2(4)", ("s2-4.2",))
yes_no("general.active_for_diagnosis",
       "Is it a powered (active) device that supplies information for detecting, diagnosing "
       "or monitoring physiological conditions, states of health, illnesses or congenital "
       "deformities, or for treating them?",
       f"{S2} clause 4.3 and the dictionary", ("s2-4.3",))
yes_no("general.supplies_absorbed_energy_for_diagnosis",
       "Is it used to supply energy that will be absorbed by the patient's body?",
       f"{S2} clause 4.3(2)(a)", ("s2-4.3",),
       hint="A device that only lights up the body with visible light does not count.")
yes_no("general.images_radiopharmaceutical_distribution",
       "Is it used to image how a radiopharmaceutical is distributed inside the patient's "
       "body?",
       f"{S2} clause 4.3(2)(b)", ("s2-4.3",))
yes_no("general.diagnoses_or_monitors_vital_processes",
       "Is it used to allow direct diagnosis or monitoring of the patient's vital "
       "physiological processes?",
       f"{S2} clause 4.3(2)(c)", ("s2-4.3",))
yes_no("general.monitors_vital_parameters_immediate_danger",
       "Is it specifically for monitoring vital physiological parameters, where the kind of "
       "change it monitors could put the patient in immediate danger, such as changes in "
       "heart performance, breathing or central nervous system activity?",
       f"{S2} clause 4.3(3)(a)", ("s2-4.3",))
yes_no("general.emits_ionising_radiation_for_interventional_radiology",
       "Is it intended to emit ionising radiation and to be used for diagnostic or "
       "therapeutic interventional radiology?",
       f"{S2} clause 4.3(3)(b)", ("s2-4.3",))
yes_no("general.controls_interventional_radiology_device",
       "Is it used to control or monitor, or directly influence, the performance of a device "
       "that emits ionising radiation for interventional radiology?",
       f"{S2} clause 4.3(3)(c)", ("s2-4.3",))
yes_no("general.administers_or_removes_substances",
       "Is it used to give medicines, body liquids or other substances to a patient, or to "
       "remove them from a patient?",
       f"{S2} clause 4.4(1)", ("s2-4.4",))
yes_no("general.substance_administration_potentially_hazardous",
       "Is giving or removing them potentially hazardous to the patient, given the substances "
       "involved, the part of the body concerned and the characteristics of the device?",
       f"{S2} clause 4.4(2)", ("s2-4.4",))
yes_no("general.diagnoses_or_screens",
       "Is it used to diagnose or screen for a disease or condition, or to give a health "
       "professional information for making a diagnosis?",
       f"{S2} clause 4.5", ("s2-4.5",))
yes_no("general.monitors_disease_state",
       "Does it provide information used for monitoring the state or progression of a "
       "disease or condition, or a person's parameters, such as heart rate?",
       f"{S2} clause 4.6", ("s2-4.6",))
yes_no("general.specifies_or_recommends_treatment",
       "Is it used to specify or recommend a treatment or intervention?",
       f"{S2} clause 4.7", ("s2-4.7",))
yes_no("general.provides_therapy_through_information",
       "Does it provide therapy to a person through information given to that person, as a "
       "guided therapy app does?",
       f"{S2} clause 4.8", ("s2-4.8",))
choice("general.decision_maker",
       "Who acts on what it produces?",
       f"{S2} clauses 4.5 and 4.7", ("s2-4.5", "s2-4.7"),
       {"device_gives_the_decision_to_a_lay_user":
            "A patient or member of the public receives the result or recommendation and "
            "acts on it",
        "device_gives_the_decision_to_a_health_professional":
            "It gives a health professional the diagnosis, or the treatment, to carry out as "
            "given",
        "informs_a_health_professional_who_decides":
            "It gives a health professional information or a recommendation, and the "
            "professional makes the decision"})
choice("general.condition_severity",
       "How serious is the disease or condition it diagnoses or screens for?",
       f"{S2} clause 4.5", ("s2-4.5",),
       {"death_or_severe_deterioration_without_urgent_treatment":
            "Without urgent treatment it may lead to death, or a severe deterioration in "
            "the person's health",
        "serious_disease_or_condition": "It is serious, but not as serious as that",
        "any_other_case": "Neither of these"},
       hint="Answer for the intended use as you describe it. Nothing is assumed from the "
            "condition's name.")
choice("general.public_health_risk",
       "Could the disease or condition it deals with, or the treatment it recommends, pose a "
       "risk to public health, that is, to people beyond the patient?",
       f"{S2} clauses 4.5, 4.6 and 4.7", ("s2-4.5", "s2-4.6", "s2-4.7"),
       {"high": "A high risk to public health",
        "moderate": "A moderate risk to public health",
        "low": "A low risk to public health",
        "none": "No risk to public health"},
       hint="This is a regulatory judgement. If you are not sure, say so and an adviser will "
            "settle it.")
choice("general.monitoring_danger",
       "What could the information it provides indicate about the person, or about another "
       "person?",
       f"{S2} clause 4.6", ("s2-4.6",),
       {"immediate_danger": "That they may be in immediate danger",
        "other_danger": "That they may be in danger, but not immediate danger",
        "any_other_case": "Neither of these"})
choice("general.treatment_risk",
       "If the treatment or intervention it specifies or recommends is given, or is not "
       "given, what could that do to the person?",
       f"{S2} clause 4.7", ("s2-4.7",),
       {"death_or_severe_deterioration":
            "It may lead to death, or a severe deterioration in their health",
        "otherwise_harmful": "It may otherwise harm them",
        "any_other_case": "Neither of these"})
choice("general.information_therapy_harm",
       "What could the therapy it provides do to the person receiving it?",
       f"{S2} clause 4.8", ("s2-4.8",),
       {"death_or_severe_deterioration":
            "It may result in death, or a severe deterioration in their health",
        "serious_harm": "It may cause serious harm",
        "harm": "It may cause harm",
        "any_other_case": "None of these"})

# --------------------------------------------------------------------------
# Schedule 2 Part 5: particular kinds of devices
# --------------------------------------------------------------------------

yes_no("general.is_export_only",
       "Is it intended for export only, and not for supply in Australia?",
       f"{S2} clause 5.8", ("s2-5.8",))
yes_no("general.incorporates_medicine",
       "Does it include, as an integral part, a substance that would be a medicine if used "
       "on its own, and that is liable to act on the body in support of the device's own "
       "action?",
       f"{S2} clause 5.1(1)", ("s2-5.1",),
       hint="Saline alone is not a medicine for this question.")
yes_no("general.human_blood_derivative",
       "Does it include, as an integral part, a stable derivative of human blood or human "
       "plasma?",
       f"{S2} clause 5.1(3)", ("s2-5.1",))
yes_no("general.contraceptive_or_sti_prevention",
       "Is it for contraception, or for preventing sexually transmitted diseases?",
       f"{S2} clause 5.2", ("s2-5.2",))
yes_no("general.cares_for_contact_lenses",
       "Is it specifically for disinfecting, cleaning, rinsing or hydrating contact lenses?",
       f"{S2} clause 5.3(1)", ("s2-5.3",))
yes_no("general.disinfects_another_device",
       "Is it specifically for disinfecting another medical device?",
       f"{S2} clause 5.3(2) and (3)", ("s2-5.3",),
       hint="A device used only to clean another device by physical action, such as "
            "brushing, does not count.")
yes_no("general.records_images_or_anatomical_model",
       "Does it capture images of patients, or is it, or does it produce, an anatomical "
       "model, physical or virtual?",
       f"{S2} clause 5.4", ("s2-5.4",),
       hint="Storing, showing or sending images that something else captured does not count.")
yes_no("general.records_patient_images_outside_visible_spectrum",
       "Does it record patient images, for diagnosing or monitoring a disease, injury or "
       "disability or for investigating the anatomy or a physiological process, using energy "
       "outside the visible spectrum, such as X-rays, infrared or ultraviolet?",
       f"{S2} clause 5.4(1)", ("s2-5.4",))
yes_no("general.is_anatomical_model_for_diagnosis",
       "Is it an anatomical model, physical or virtual, for diagnosing or monitoring a "
       "disease, injury or disability, or for investigating the anatomy or a physiological "
       "process?",
       f"{S2} clause 5.4(2)", ("s2-5.4",))
yes_no("general.generates_virtual_anatomical_model",
       "Does it generate a virtual anatomical model for diagnosing or monitoring a disease, "
       "injury or disability, or for investigating the anatomy or a physiological process?",
       f"{S2} clause 5.4(3)", ("s2-5.4",))
yes_no("general.contains_non_viable_animal_material",
       "Does it contain non-viable (not living) tissue or cells of animal origin, or anything "
       "derived from them?",
       f"{S2} clause 5.5(1)", ("s2-5.5",),
       hint="Tissue or cells from hair or wool do not count, and neither do sintered "
            "hydroxyapatite or tallow derivatives.")
yes_no("general.contacts_intact_skin_only",
       "Is it intended to come into contact with intact (unbroken) skin only?",
       f"{S2} clause 5.5(2)", ("s2-5.5",))
yes_no("general.is_blood_bag", "Is it a blood bag?", f"{S2} clause 5.6", ("s2-5.6",))
yes_no("general.implantable_accessory_to_active_implantable",
       "Is it an implantable accessory to an active implantable medical device, such as a "
       "pacemaker?",
       f"{S2} clause 5.7(2)", ("s2-5.7",))
yes_no("general.controls_active_implantable",
       "Is it used to control or monitor, or directly influence, the performance of an "
       "active implantable medical device, such as a pacemaker or a cochlear implant?",
       f"{S2} clause 5.7(3)", ("s2-5.7",))
yes_no("general.is_mammary_implant", "Is it a breast (mammary) implant?",
       f"{S2} clause 5.9", ("s2-5.9",))
yes_no("general.administers_by_inhalation",
       "Is it used to give medicines or biologicals by inhalation?",
       f"{S2} clause 5.10", ("s2-5.10",))
yes_no("general.inhalation_mode_of_action_essential",
       "Does the way the device works have an essential impact on how effective and safe "
       "the inhaled medicines or biologicals are?",
       f"{S2} clause 5.10(a)", ("s2-5.10",))
yes_no("general.inhalation_treats_life_threatening_condition",
       "Is the device intended to treat a life-threatening condition?",
       f"{S2} clause 5.10(b)", ("s2-5.10",))
yes_no("general.is_substance_through_orifice_or_skin",
       "Is it made up of a substance, or a combination of substances, that is put into the "
       "body through a natural opening, or applied to the skin and absorbed by it?",
       f"{S2} clause 5.11", ("s2-5.11",))
yes_no("general.substance_acts_in_nose_mouth_or_on_skin",
       "Is it put into the nose or mouth no further than the throat (pharynx), or applied to "
       "and absorbed by the skin, and does it do its job there, in that cavity or on the "
       "skin?",
       f"{S2} clause 5.11(c)", ("s2-5.11",))

# --------------------------------------------------------------------------
# Schedule 2A: IVD medical devices
# --------------------------------------------------------------------------

S2A = f"{REGS} Schedule 2A"

yes_no("ivd.is_ivd_instrument",
       "Is it an instrument, such as an analyser or reader, intended specifically for in "
       "vitro diagnostic procedures, rather than a reagent or a test?",
       f"{S2A} clause 1.6(2)(a)", ("s2a-1.6",))
yes_no("ivd.is_specimen_receptacle",
       "Is it a specimen receptacle: a container, vacuum-type or not, made specifically to "
       "hold and preserve a specimen from the human body for in vitro diagnostic "
       "examination?",
       f"{S2A} clause 1.6(2)(b) and (3)", ("s2a-1.6",))
yes_no("ivd.is_culture_medium", "Is it a microbiological culture medium?",
       f"{S2A} clause 1.6(2)(c)", ("s2a-1.6",))
yes_no("ivd.is_quality_control_material",
       "Is it quality control material that is not specific to one assay?",
       f"{S2A} clause 1.5", ("s2a-1.5",))
yes_no("ivd.is_export_only",
       "Is it intended for export only, and not for supply in Australia?",
       f"{S2A} clause 1.8", ("s2a-1.8",))
yes_no("ivd.detects_infectious_agent",
       "Does it detect the presence of, or exposure to, an infectious or transmissible agent, "
       "such as a virus or a bacterium?",
       f"{S2A} clauses 1.1 and 1.3", ("s2a-1.1", "s2a-1.3"))
yes_no("ivd.types_blood_or_tissue",
       "Is it used for blood grouping or tissue typing, that is, detecting markers that show "
       "whether blood, cells, tissues or organs are compatible for transfusion or "
       "transplantation?",
       f"{S2A} clause 1.2", ("s2a-1.2",))
yes_no("ivd.is_self_test",
       "Is it intended for self-testing, by a person who is not a health professional, for "
       "example at home?",
       f"{S2A} clauses 1.4 and 1.6(2)(b)", ("s2a-1.4", "s2a-1.6"))
yes_no("ivd.screens_donations_for_transmissible_agents",
       "Is it used to detect transmissible agents in blood, blood components, blood products, "
       "cells, tissues or organs, or their derivatives, of human or animal origin, to assess "
       "whether they are suitable for transfusion or transplantation?",
       f"{S2A} clause 1.1(a)", ("s2a-1.1",))
yes_no("ivd.agent_serious_with_high_propagation_risk",
       "Does it detect the presence of, or exposure to, a transmissible agent that causes a "
       "serious disease with a high risk of propagation (spread) in Australia?",
       f"{S2A} clause 1.1(b)", ("s2a-1.1",),
       hint="This is a regulatory judgement. If you are not sure, say so and an adviser will "
            "settle it.")
yes_no("ivd.assesses_transfusion_or_transplant_compatibility",
       "Is it used to detect biological markers to assess the immunological compatibility of "
       "blood, blood components, blood products, cells, tissues or organs intended for "
       "transfusion or transplantation?",
       f"{S2A} clause 1.2(1)", ("s2a-1.2",))
yes_no("ivd.detects_listed_blood_group_marker",
       "Does it detect any of these blood group markers: ABO (A, B, AB); Rhesus (D, C, E, c, "
       "e); Kell (K); Kidd (Jka, Jkb); Duffy (Fya, Fyb)?",
       f"{S2A} clause 1.2(2)", ("s2a-1.2",))
yes_no("ivd.detects_sexually_transmitted_agent",
       "Does it detect the presence of, or exposure to, a sexually transmitted agent?",
       f"{S2A} clause 1.3(a)", ("s2a-1.3",))
yes_no("ivd.detects_limited_propagation_agent_in_csf_or_blood",
       "Does it detect, in cerebrospinal fluid or blood, an infectious agent with a risk of "
       "limited propagation (spread)?",
       f"{S2A} clause 1.3(b)", ("s2a-1.3",))
yes_no("ivd.error_could_cause_death_or_severe_disability",
       "Does it detect an infectious agent where there is a significant risk that a wrong "
       "result would cause death or severe disability to the person or foetus being tested?",
       f"{S2A} clause 1.3(c)", ("s2a-1.3",))
yes_no("ivd.prenatal_immune_status_screening",
       "Is it for pre-natal screening of women to find their immune status towards "
       "transmissible agents?",
       f"{S2A} clause 1.3(d)", ("s2a-1.3",))
yes_no("ivd.infective_status_error_life_threatening",
       "Does it determine infective disease status or immune status, where there is a risk "
       "that a wrong result will lead to a patient management decision resulting in an "
       "imminent life-threatening situation for the patient?",
       f"{S2A} clause 1.3(e)", ("s2a-1.3",))
yes_no("ivd.manages_life_threatening_infectious_disease",
       "Is it used in managing patients who have a life-threatening infectious disease?",
       f"{S2A} clause 1.3(i)", ("s2a-1.3",))
yes_no("ivd.selects_patients_for_therapy",
       "Is it used to select patients for selective therapy and management?",
       f"{S2A} clause 1.3(f)(i)", ("s2a-1.3",))
yes_no("ivd.selects_patients_for_disease_staging",
       "Is it used to select patients for disease staging?",
       f"{S2A} clause 1.3(f)(ii)", ("s2a-1.3",))
yes_no("ivd.selects_patients_in_cancer_diagnosis",
       "Is it used to select patients in the diagnosis of cancer?",
       f"{S2A} clause 1.3(f)(iii)", ("s2a-1.3",))
yes_no("ivd.is_companion_diagnostic",
       "Is it an IVD companion diagnostic, a test that gives information needed for the safe "
       "and effective use of a particular medicine or biological?",
       f"{S2A} clause 1.3(fa)", ("s2a-1.3",))
yes_no("ivd.is_human_genetic_test", "Is it for human genetic testing?",
       f"{S2A} clause 1.3(g)", ("s2a-1.3",))
yes_no("ivd.monitors_levels_error_life_threatening",
       "Does it monitor levels of medicines, substances or biological components, where there "
       "is a risk that a wrong result will lead to a patient management decision resulting in "
       "an immediate life-threatening situation for the patient?",
       f"{S2A} clause 1.3(h)", ("s2a-1.3",))
yes_no("ivd.screens_foetus_for_congenital_disorders",
       "Is it for screening a foetus for congenital disorders?",
       f"{S2A} clause 1.3(j)", ("s2a-1.3",))
yes_no("ivd.result_not_determining_serious_condition",
       "Is the result of the self-test used to determine a serious condition, ailment or "
       "defect?",
       f"{S2A} clause 1.4(a)", ("s2a-1.4",),
       # Asked the positive way round. "Yes" sets the field, which is worded as
       # the clause's exception, to no.
       choices=(("yes", "Yes", "no"), ("no", "No", "yes")))
yes_no("ivd.preliminary_with_follow_up_testing",
       "Is the self-test's examination preliminary, with follow-up testing required?",
       f"{S2A} clause 1.4(b)", ("s2a-1.4",))
yes_no("ivd.is_ancillary_reagent_or_article",
       "Is it a reagent or other article used as part of a specific examination, such as a "
       "buffer, a wash solution or a general reagent, rather than the test itself?",
       f"{S2A} clause 1.6(1)", ("s2a-1.6",))


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def target_of(dotted: str) -> tuple[str, int | None]:
    """'functions.1.general.duration' -> ('general.duration', 1); core -> (..., None)."""
    parts = dotted.split(".")
    if parts[0] == "functions":
        index = int(parts[1])
        rest = parts[2:]
        section = "function" if len(rest) == 1 else rest[0]
        name = rest[-1]
        return f"{section}.{name}", index
    return dotted, None


def parse_value(target: str, raw: str):
    """A catalogue value string in the field's own type."""
    kind = F.value_type(target)
    if isinstance(kind, type) and issubclass(kind, Enum):
        return kind(raw)
    return raw


def exclusions(path: Path | None = None) -> list[Exclusion]:
    """The Determination's items, read from the committed table.

    Read here rather than through status.load_exclusions, which fills the
    gate's own table: rendering a question must not change what the gate
    sees.
    """
    payload = json.loads((path or REPO / EXCLUSION_SOURCE).read_text(encoding="utf-8"))
    return [Exclusion(**entry) for entry in payload["items"]]


def _function_label(profile: DeviceProfile, index: int) -> str:
    name = profile.functions[index].name
    if name.resolved and name.value:
        return str(name.value)
    return f"part {index + 1}"


def _exclusion_options(dotted: str, software: bool) -> list[Option]:
    """Every item, the ones matching the function's kind first."""
    items = exclusions()
    items.sort(key=lambda item: item.software is not software)
    options = [Option(id=item.key, label=f"{item.summary} ({item.key})",
                      sets={dotted: item.key}) for item in items]
    options.append(Option(id="none", label="None of these", sets={dotted: "none"}))
    return options


def _chosen_exclusion(profile: DeviceProfile, index: int) -> Exclusion | None:
    item = profile.functions[index].status.excluded_item
    if not item.resolved or not item.value:
        return None
    key = exclusion_key(str(item.value))
    return next((e for e in exclusions() if exclusion_key(e.key) == key), None)


def render(profile: DeviceProfile, dotted: str) -> Question:
    """The Question for one field of this profile.

    The text names the function it is about when the product has more than
    one, so a founder answering for "Abnormality triage" knows which part is
    meant.
    """
    target, index = target_of(dotted)
    entry = CATALOGUE[target]
    text = entry.text

    if target == "core.functions_confirmed":
        names = [_function_label(profile, i) for i in range(len(profile.functions))]
        if len(names) == 1:
            listing = f"We read your product as doing one thing: {names[0]}."
        else:
            listing = (f"We read your product as doing {len(names)} separate things: "
                       + "; ".join(f"{n + 1}. {name}" for n, name in enumerate(names)) + ".")
        text = f"{listing} {text}"

    if target == "status.exclusion_conditions_met" and index is not None:
        chosen = _chosen_exclusion(profile, index)
        if chosen is not None:
            summary = chosen.summary.rstrip(".")
            text = f'Item {chosen.key} covers: "{summary}." {text}'

    if index is not None and len(profile.functions) > 1:
        text = f'About "{_function_label(profile, index)}": {text}'

    if target == "status.excluded_item":
        software = (index is not None
                    and profile.functions[index].is_software.resolved
                    and profile.functions[index].is_software.value is Tri.YES)
        options = _exclusion_options(dotted, software)
    else:
        options = [Option(id=option_id, label=label, sets={dotted: parse_value(target, raw)})
                   for option_id, label, raw in entry.choices]
    options.append(UNSURE)

    return Question(id=dotted, text=text, fields=[dotted], options=options,
                    clause=entry.clause, hint=entry.hint)


def entry_for(dotted: str) -> Entry:
    return CATALOGUE[target_of(dotted)[0]]


# --------------------------------------------------------------------------
# Checklists: several fields on one screen
# --------------------------------------------------------------------------
#
# A checklist puts every still-open field of one group on one screen as
# "tick every one that applies" (decision C, 24 Sep 2026):
#
# - a ticked item sets its field to yes;
# - an unticked item sets its field to no, unless the founder chose
#   "I'm not sure about some of these", in which case unticked items are
#   left open and come back later as single questions;
# - "None of these apply" must be chosen to submit nothing ticked, so an
#   empty checklist is never an accident; it sets every field to no.
#
# The reply records the ticked and the unticked items by label
# (checklist_reply), so each field's evidence is its own label in the
# founder's reply. A checklist is shown once per function; after that, any
# field it left open is asked on its own.

CHECKLIST_NONE = "none"
CHECKLIST_PARTIAL = "not_sure_some"


@dataclass(frozen=True)
class Checklist:
    id: str
    section: str                      # "general" or "ivd"
    text: str
    clause: str
    fields: tuple[str, ...]           # field names inside the section
    hint: str = ""


# Each item as a statement the founder ticks. Carve-outs from the clause stay
# in the item, as they do in the single question.
ITEM_LABELS: dict[str, str] = {
    # Schedule 2A clause 1.3
    "ivd.detects_sexually_transmitted_agent":
        "It detects the presence of, or exposure to, a sexually transmitted agent",
    "ivd.detects_limited_propagation_agent_in_csf_or_blood":
        "It detects, in cerebrospinal fluid or blood, an infectious agent with a risk of "
        "limited propagation (spread)",
    "ivd.error_could_cause_death_or_severe_disability":
        "It detects an infectious agent where there is a significant risk that a wrong result "
        "would cause death or severe disability to the person or foetus being tested",
    "ivd.prenatal_immune_status_screening":
        "It is for pre-natal screening of women to find their immune status towards "
        "transmissible agents",
    "ivd.infective_status_error_life_threatening":
        "It determines infective disease status or immune status, where there is a risk that a "
        "wrong result will lead to a patient management decision resulting in an imminent "
        "life-threatening situation for the patient",
    "ivd.manages_life_threatening_infectious_disease":
        "It is used in managing patients who have a life-threatening infectious disease",
    "ivd.selects_patients_for_therapy":
        "It is used to select patients for selective therapy and management",
    "ivd.selects_patients_for_disease_staging": "It is used to select patients for disease staging",
    "ivd.selects_patients_in_cancer_diagnosis":
        "It is used to select patients in the diagnosis of cancer",
    "ivd.is_companion_diagnostic":
        "It is an IVD companion diagnostic, a test that gives information needed for the safe "
        "and effective use of a particular medicine or biological",
    "ivd.is_human_genetic_test": "It is for human genetic testing",
    "ivd.monitors_levels_error_life_threatening":
        "It monitors levels of medicines, substances or biological components, where there is a "
        "risk that a wrong result will lead to a patient management decision resulting in an "
        "immediate life-threatening situation for the patient",
    "ivd.screens_foetus_for_congenital_disorders":
        "It is for screening a foetus for congenital disorders",
    # Schedule 2 clauses 4.5 to 4.8
    "general.diagnoses_or_screens":
        "It diagnoses or screens for a disease or condition, or gives a health professional "
        "information for making a diagnosis",
    "general.monitors_disease_state":
        "It provides information used for monitoring the state or progression of a disease or "
        "condition, or a person's parameters, such as heart rate",
    "general.specifies_or_recommends_treatment":
        "It specifies or recommends a treatment or intervention",
    "general.provides_therapy_through_information":
        "It provides therapy to a person through information given to that person, as a guided "
        "therapy app does",
    # Schedule 2 clause 4.3
    "general.supplies_absorbed_energy_for_diagnosis":
        "It supplies energy that will be absorbed by the patient's body (only lighting up the "
        "body with visible light does not count)",
    "general.images_radiopharmaceutical_distribution":
        "It images how a radiopharmaceutical is distributed inside the patient's body",
    "general.diagnoses_or_monitors_vital_processes":
        "It allows direct diagnosis or monitoring of the patient's vital physiological processes",
    "general.monitors_vital_parameters_immediate_danger":
        "It is specifically for monitoring vital physiological parameters, where the kind of "
        "change it monitors could put the patient in immediate danger, such as changes in heart "
        "performance, breathing or central nervous system activity",
    "general.emits_ionising_radiation_for_interventional_radiology":
        "It emits ionising radiation and is used for diagnostic or therapeutic interventional "
        "radiology",
    "general.controls_interventional_radiology_device":
        "It controls or monitors, or directly influences, the performance of a device that "
        "emits ionising radiation for interventional radiology",
    # Schedule 2 Parts 3 and 5: particular kinds of device
    "general.corrects_heart_or_circulatory_defect_by_contact":
        "It is specifically for diagnosing, monitoring, controlling or correcting a defect of "
        "the heart or of the central circulatory system, through direct contact with those parts "
        "of the body",
    "general.direct_contact_heart_circulation_or_nervous_system":
        "It is specifically for use in direct contact with the heart, the central circulatory "
        "system or the central nervous system",
    "general.reusable_surgical_instrument":
        "It is a reusable surgical instrument, made to be cleaned and sterilised and used again",
    "general.delivers_ionising_radiation":
        "It supplies energy in the form of ionising radiation, such as X-rays, gamma rays or a "
        "radioactive source",
    "general.has_biological_effect": "It is intended to have a biological effect on the body",
    "general.wholly_or_mostly_absorbed":
        "It is intended to be wholly, or mostly, absorbed by the patient's body",
    "general.undergoes_chemical_change":
        "It is intended to undergo a chemical change in the patient's body",
    "general.placed_in_teeth":
        "It is intended to be placed in the teeth (going into a tooth counts; going through a "
        "tooth into the gum or bone beyond it does not)",
    "general.administers_medicine_hazardously_by_delivery_system":
        "It gives a medicine through a delivery system, in a way that is potentially hazardous "
        "to the patient because of the characteristics of the device",
    "general.administers_medicine": "It is intended to give a medicine to the patient",
    "general.joint_replacement_or_surgical_mesh":
        "It is a joint replacement device, or surgical mesh",
    "general.spinal_motion_preserving":
        "It is a motion-preserving device for the spine, such as a spinal disc replacement",
    "general.incorporates_medicine":
        "It includes, as an integral part, a substance that would be a medicine if used on its "
        "own and that is liable to act on the body in support of the device's own action "
        "(saline alone is not a medicine here)",
    "general.human_blood_derivative":
        "It includes, as an integral part, a stable derivative of human blood or human plasma",
    "general.contraceptive_or_sti_prevention":
        "It is for contraception, or for preventing sexually transmitted diseases",
    "general.cares_for_contact_lenses":
        "It is specifically for disinfecting, cleaning, rinsing or hydrating contact lenses",
    "general.disinfects_another_device":
        "It is specifically for disinfecting another medical device (cleaning another device "
        "only by physical action, such as brushing, does not count)",
    "general.records_images_or_anatomical_model":
        "It captures images of patients, or is, or produces, an anatomical model (storing, "
        "showing or sending images that something else captured does not count)",
    "general.contains_non_viable_animal_material":
        "It contains non-viable (not living) tissue or cells of animal origin, or anything "
        "derived from them (tissue or cells from hair or wool, sintered hydroxyapatite and "
        "tallow derivatives do not count)",
    "general.is_blood_bag": "It is a blood bag",
    "general.is_active_implantable":
        "It is a powered (active) device intended to be put wholly or partly into the body and "
        "to stay there after the procedure, such as a pacemaker",
    "general.implantable_accessory_to_active_implantable":
        "It is an implantable accessory to an active implantable medical device, such as a "
        "pacemaker",
    "general.controls_active_implantable":
        "It controls or monitors, or directly influences, the performance of an active "
        "implantable medical device, such as a pacemaker or a cochlear implant",
    "general.is_mammary_implant": "It is a breast (mammary) implant",
    "general.administers_by_inhalation":
        "It is used to give medicines or biologicals by inhalation",
    "general.is_substance_through_orifice_or_skin":
        "It is made up of a substance, or a combination of substances, that is put into the body "
        "through a natural opening, or applied to the skin and absorbed by it",
}

TICK = "Tick every one that applies."

CHECKLISTS: list[Checklist] = [
    Checklist(
        "ivd_1_3", "ivd", f"Which of these does it do? {TICK}", f"{S2A} clause 1.3",
        ("detects_sexually_transmitted_agent",
         "detects_limited_propagation_agent_in_csf_or_blood",
         "error_could_cause_death_or_severe_disability", "prenatal_immune_status_screening",
         "infective_status_error_life_threatening",
         "manages_life_threatening_infectious_disease", "selects_patients_for_therapy",
         "selects_patients_for_disease_staging", "selects_patients_in_cancer_diagnosis",
         "is_companion_diagnostic", "is_human_genetic_test",
         "monitors_levels_error_life_threatening", "screens_foetus_for_congenital_disorders")),
    Checklist(
        "software_purposes", "general", f"Which of these does it do? {TICK}",
        f"{S2} clauses 4.5 to 4.8",
        ("diagnoses_or_screens", "monitors_disease_state", "specifies_or_recommends_treatment",
         "provides_therapy_through_information")),
    Checklist(
        "active_diagnosis_4_3", "general", f"Which of these does it do? {TICK}",
        f"{S2} clause 4.3",
        ("supplies_absorbed_energy_for_diagnosis", "images_radiopharmaceutical_distribution",
         "diagnoses_or_monitors_vital_processes", "monitors_vital_parameters_immediate_danger",
         "emits_ionising_radiation_for_interventional_radiology",
         "controls_interventional_radiology_device")),
    Checklist(
        "particular_kinds", "general", f"Do any of these describe it? {TICK}",
        f"{S2} Parts 3 and 5",
        ("corrects_heart_or_circulatory_defect_by_contact",
         "direct_contact_heart_circulation_or_nervous_system", "reusable_surgical_instrument",
         "delivers_ionising_radiation", "has_biological_effect", "wholly_or_mostly_absorbed",
         "undergoes_chemical_change", "placed_in_teeth",
         "administers_medicine_hazardously_by_delivery_system", "administers_medicine",
         "joint_replacement_or_surgical_mesh", "spinal_motion_preserving",
         "incorporates_medicine", "human_blood_derivative", "contraceptive_or_sti_prevention",
         "cares_for_contact_lenses", "disinfects_another_device",
         "records_images_or_anatomical_model", "contains_non_viable_animal_material",
         "is_blood_bag", "is_active_implantable", "implantable_accessory_to_active_implantable",
         "controls_active_implantable", "is_mammary_implant", "administers_by_inhalation",
         "is_substance_through_orifice_or_skin"),
        hint="Most products tick none of these."),
]

CHECKLIST_OF: dict[str, Checklist] = {
    f"{c.section}.{name}": c for c in CHECKLISTS for name in c.fields
}


def checklist_id(index: int, checklist: Checklist) -> str:
    return f"functions.{index}.checklist.{checklist.id}"


def render_checklist(profile: DeviceProfile, index: int, checklist: Checklist,
                     fields: list[str]) -> Question:
    """One screen for the open fields of a checklist, in checklist order."""
    order = {f"functions.{index}.{checklist.section}.{name}": n
             for n, name in enumerate(checklist.fields)}
    fields = sorted(fields, key=order.__getitem__)
    options = [Option(id=target_of(d)[0].split(".", 1)[1], label=ITEM_LABELS[target_of(d)[0]],
                      sets={d: Tri.YES}) for d in fields]
    options.append(Option(id=CHECKLIST_NONE, label="None of these apply",
                          sets={d: Tri.NO for d in fields}))
    options.append(Option(id=CHECKLIST_PARTIAL, label="I'm not sure about some of these"))
    text = checklist.text
    if len(profile.functions) > 1:
        text = f'About "{_function_label(profile, index)}": {text}'
    return Question(id=checklist_id(index, checklist), text=text, fields=fields,
                    options=options, multi=True, clause=checklist.clause, hint=checklist.hint)


def checklist_reply(question: Question, chosen: list[str]) -> str:
    """The reply recorded for a checklist: what was ticked and what was not.

    Every item's label appears in it, so each field's evidence is its own
    label. With "I'm not sure about some of these" the unticked items are
    named as not sure rather than not ticked.
    """
    items = [o for o in question.options if o.id not in (CHECKLIST_NONE, CHECKLIST_PARTIAL)]
    ticked = [o.label for o in items if o.id in chosen]
    rest = [o.label for o in items if o.id not in chosen]
    if CHECKLIST_NONE in chosen:
        return "None of these apply. Not ticked: " + "; ".join(rest) + "."
    parts = []
    if ticked:
        parts.append("Ticked: " + "; ".join(ticked) + ".")
    if rest:
        label = "Not sure about" if CHECKLIST_PARTIAL in chosen else "Not ticked"
        parts.append(f"{label}: " + "; ".join(rest) + ".")
    return " ".join(parts)


# --------------------------------------------------------------------------
# "Same as an earlier part?" for multi-function products
# --------------------------------------------------------------------------
#
# Parts of one product often share their basic facts. Before asking a later
# function's gate questions, and again before its Schedule 2 or 2A
# questions, the founder can confirm on one screen that a set of facts is the
# same as an earlier function's. The screen shows every value it would copy,
# so nothing is copied unseen. The founder ticks the facts that are the
# same; each unticked fact is asked on its own later. Only facts about what
# the part is are offered, never its purpose-specific rule answers. The
# branch screen comes after the part's kind is answered and only lends facts
# from an earlier part of the same kind; a specific exclusion item is never
# lent, only "none of these".

SAME_AS_NONE = "none_same"

# Paths relative to a function, with a short name for the fact.
SAME_AS_GATE: dict[str, str] = {
    "is_software": "Software or an app",
    "status.therapeutic_purpose": "What it is intended for",
    "status.principal_action_pharmacological": "Main action achieved the way a medicine works",
    "status.is_accessory_to_device": "Made to be used with a medical device",
    "status.excluded_item": "Excluded goods item",
}
SAME_AS_BRANCH: dict[str, str] = {
    "general.is_export_only": "For export only",
    "general.invasiveness": "How it goes into the body",
    "general.duration": "How long it is used continuously",
    "general.orifice_site": "Which opening it goes into",
    "general.connected_to_an_active_device": "Connected to a powered medical device",
    "general.is_active_device": "Relies on a power source",
    "general.is_programmed_or_programmable": "Runs software or firmware",
    "general.is_active_implantable": "Powered and stays in the body",
    "general.incorporates_medicine": "Includes a medicine as an integral part",
    "general.human_blood_derivative": "Includes a human blood or plasma derivative",
    "general.contains_non_viable_animal_material": "Contains animal tissue or cells",
    "general.contacts_intact_skin_only": "Touches intact skin only",
    "ivd.is_export_only": "For export only",
    "ivd.is_self_test": "For self-testing",
}
SAME_AS_GROUPS = {"gate": SAME_AS_GATE, "branch": SAME_AS_BRANCH}


def same_as_id(index: int, group: str) -> str:
    return f"functions.{index}.same_as.{group}"


def _value_label(target: str, value) -> str:
    if target == "status.excluded_item":
        return "None of these" if str(value) == "none" else str(value)
    raw = getattr(value, "value", value)
    for _, label, choice_value in CATALOGUE[target].choices:
        if choice_value == raw:
            return label
    return str(raw)


def same_as_lines(copies: dict[str, object]) -> list[str]:
    """'Fact: value' for each dotted field to copy, in group order."""
    lines = []
    for dotted, value in copies.items():
        target, _ = target_of(dotted)
        rest = dotted.split(".", 2)[2]
        name = SAME_AS_GATE.get(rest) or SAME_AS_BRANCH[rest]
        lines.append(f"{name}: {_value_label(target, value)}")
    return lines


def render_same_as(profile: DeviceProfile, index: int, source: int, group: str,
                   copies: dict[str, object]) -> Question:
    """One screen offering to copy these values from function source to index.

    A "tick the ones that are the same" list: each ticked fact is copied,
    each unticked one is asked on its own later. "None of these are the
    same" must be chosen to submit nothing ticked.
    """
    here, there = _function_label(profile, index), _function_label(profile, source)
    text = (f'Which of these are the same for "{here}" as for "{there}"? '
            "Tick every one that is the same.")
    lines = same_as_lines(copies)
    options = [Option(id=dotted.split(".", 2)[2], label=line, sets={dotted: value})
               for (dotted, value), line in zip(copies.items(), lines, strict=True)]
    options.append(Option(id=SAME_AS_NONE, label="None of these are the same"))
    return Question(id=same_as_id(index, group), text=text, fields=list(copies),
                    options=options, multi=True, clause="Product decomposition",
                    hint="Each part of a product is assessed on its own, so only tick a line "
                         "that is true of this part too. Anything left unticked is asked on "
                         "its own.")


def same_as_reply(question: Question, chosen: list[str]) -> str:
    """The reply recorded: the facts ticked as the same, and the rest."""
    items = [o for o in question.options if o.id != SAME_AS_NONE]
    same = [o.label for o in items if o.id in chosen]
    rest = [o.label for o in items if o.id not in chosen]
    parts = []
    if same:
        parts.append("The same: " + "; ".join(same) + ".")
    if rest:
        parts.append("Not the same, or not sure: " + "; ".join(rest) + ".")
    return " ".join(parts)

# --------------------------------------------------------------------------
# The review document
# --------------------------------------------------------------------------

def _clause_order(clause_id: str) -> tuple:
    """'s2-2.2A' sorts after 's2-2.2' and before 's2-2.3'; Schedule 2 before 2A."""
    schedule, number = clause_id.split("-", 1)
    parts = []
    for piece in number.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append((int(digits) if digits else 0, piece[len(digits):]))
    return (schedule != "s2", tuple(parts))


def _plain_legislation(text: str) -> str:
    """Legislation em dashes as spaced en dashes, the project's convention."""
    return text.replace("\u2014", " \u2013 ")


def _options_line(entry: Entry) -> str:
    if entry.target == "status.excluded_item":
        return ("every item of the Determination, the items matching the function's kind "
                "(software or not) first, then None of these, then Not sure")
    if not entry.choices:
        return "a typed reply, or Not sure"
    shown = []
    for _, label, value in entry.choices:
        shown.append(label if label.lower() == value else f"{label} [{value}]")
    return "; ".join(shown + ["Not sure"])


def review_markdown(clauses: dict | None) -> str:
    """docs/QUESTIONS.md: every question beside the clause it was checked against.

    clauses is legislation.load(), or None when the corpus is not built, in
    which case the clause text is left out and the document says so.
    """
    groups: dict[str, list[Entry]] = {}
    for entry in CATALOGUE.values():
        if entry.sources:
            key = entry.sources[0]
        elif entry.target.startswith("status."):
            key = "status"
        else:
            key = "product"
        groups.setdefault(key, []).append(entry)

    compilation = ""
    if clauses:
        any_clause = next(iter(clauses.values()))
        compilation = (f" and the clause files (Compilation {any_clause.compilation}, "
                       f"{any_clause.compilation_date})")
    lines = [
        "# Intake questions for review",
        "",
        f"Generated by `scripts/review_questions.py` from `reguide/questions.py`{compilation}. "
        "Do not edit by hand: change the catalogue and regenerate.",
        "",
        "For each question, check three things: it asks what the clause asks, no wider and "
        "no narrower; it does not hint at which answer gives a lower class; and a founder "
        "could answer it without reading the Regulations. Square brackets show the value an "
        "option sets where its label does not say it.",
        "",
    ]
    if not clauses:
        lines += ["Clause text is not shown: the clause files were not built when this was "
                  "generated.", ""]

    def section(title: str, entries: list[Entry], clause_text: str = "") -> None:
        lines.extend([f"## {title}", ""])
        if clause_text:
            lines.extend(["<details><summary>Clause text</summary>", ""])
            lines.extend(f"> {line}".rstrip() for line in clause_text.splitlines())
            lines.extend(["", "</details>", ""])
        for entry in entries:
            lines.extend([f"### `{entry.target}`", "", f"**Asked:** {entry.text}", ""])
            if entry.hint:
                lines.extend([f"**Hint:** {entry.hint}", ""])
            lines.extend([f"**Options:** {_options_line(entry)}", "",
                          f"**Feeds:** {entry.clause}", ""])
            if len(entry.sources) > 1:
                others = ", ".join(entry.sources[1:])
                lines.extend([f"**Also checked against:** {others}", ""])

    section("Product and functions", groups.pop("product", []))
    section("Status gate (the Act, the Excluded Goods Determination, Schedule 4)",
            groups.pop("status", []))
    for clause_id in sorted(groups, key=_clause_order):
        clause = (clauses or {}).get(clause_id)
        if clause is None:
            section(clause_id, groups[clause_id])
            continue
        body = clause.text.split("\n", 1)[1].strip() if clause.text.startswith("#") \
            else clause.text
        title = clause.citation.removeprefix(f"{REGS} ")
        section(_plain_legislation(f"{title}: {clause.heading}"), groups[clause_id],
                _plain_legislation(body))
    lines.extend(["## Checklists", "",
                  "Each checklist puts the open fields of its group on one screen. A ticked "
                  "item sets its field to yes; an unticked one sets it to no, unless the "
                  "founder chose \"I'm not sure about some of these\", which leaves the "
                  "unticked items to come back as single questions. \"None of these apply\" "
                  "must be chosen to submit nothing ticked. Only the items still open for the "
                  "function are shown. Check each item says what its single question says.",
                  ""])
    for checklist in CHECKLISTS:
        lines.extend([f"### Checklist `{checklist.id}`", "", f"**Asked:** {checklist.text}", ""])
        if checklist.hint:
            lines.extend([f"**Hint:** {checklist.hint}", ""])
        lines.extend([f"**Feeds:** {checklist.clause}", "", "**Items:**", ""])
        for name in checklist.fields:
            target = f"{checklist.section}.{name}"
            lines.append(f"- {ITEM_LABELS[target]} [`{target}`]")
        lines.extend(["", "**Also offered:** None of these apply; I'm not sure about some "
                      "of these", ""])
    lines.extend(["## Same as an earlier part", "",
                  "On a later part of a multi-part product, the gate and the Schedule 2 or 2A "
                  "questions each open with one screen listing an earlier part's answers to "
                  "these facts, as \"Fact: answer\". The founder ticks the ones that are the "
                  "same for this part; each unticked fact is asked on its own. \"None of these "
                  "are the same\" must be chosen to submit nothing ticked. The branch screen "
                  "comes after the part's kind is answered and lends only from a part of the "
                  "same kind; an exclusion item is lent only when it is \"none\".", ""])
    for group, facts in SAME_AS_GROUPS.items():
        lines.extend([f"### Same-as facts: {group}", ""])
        lines.extend(f"- {name} [`{path}`]" for path, name in facts.items())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
