"""Which question comes next.

The interview asks one field at a time, in tiers:

    0  the product's name and intended purpose
    1  each function's name and description, if extraction found none
    2  confirm the split into functions
    3  the status gate, for every function: whether it is software, then
       the gate fields in the gate's own order
    4  for every function the gate has not stopped: its kind, then the
       "Despite" questions, then the questions that open a group of rules,
       then the rule questions, highest class first
    5  the regulation 3.9 qualifiers on the product (supplied sterile, a
       measuring function)

Gate early stop. A function the gate has already decided is outside the
rules (not a device, excluded, or exempt clinical decision support) is asked
nothing past the gate: its kind, its Schedule 2 or 2A questions and the
qualifiers are all left alone. When every function has stopped, so does the
interview. profile.relevant() still lists those fields, because profile.py
cannot ask the gate (status.py imports profile.py), so the stop lives here.
The gate needs the exclusion table loaded (status.load_exclusions); without
it no function can be found excluded and nothing stops on an exclusion.

Highest class first. Rule questions are ordered by the highest class the
paragraphs they feed can give, so a Class III paragraph is asked before a
Class IIa one. The early stop that makes that ordering pay, leaving out
questions that can no longer change the class, is piece 4c; until then every
relevant field is still asked.

Definitions settle some fields without a question. settle() records them
with basis DEFAULTED (a legal consequence, not a claim about the device):

- a software function does not go into the body, because an invasive
  device is one that penetrates it (dictionary). Its route is non-invasive,
  and it neither handles substances for administration (clauses 2.2, 2.2A,
  2.3) nor touches injured skin or a mucous membrane (clause 2.4), both of
  which need a physical device.

settle() only fills fields that are still unknown, and it takes its own
defaults back if the function stops being software, so a correction by the
founder never leaves a stale default behind. The caller runs settle() after
extraction and after every answer (apply_answer does, from step 5).
next_question() works on a settled copy and never changes the profile it is
given.
"""

from .extract import Question
from .profile import (
    Answer,
    Basis,
    DeviceProfile,
    FunctionProfile,
    Invasiveness,
    Tri,
    relevant_status_fields,
)
from .questions import render
from .status import status_of

# --------------------------------------------------------------------------
# Definitions
# --------------------------------------------------------------------------

# Fields a software function has by definition, and the value.
SOFTWARE_DEFINITIONS = {
    "invasiveness": Invasiveness.NON_INVASIVE,
    "handles_substances_for_administration": Tri.NO,
    "contacts_injured_skin_or_mucous_membrane": Tri.NO,
}


def _default(value) -> Answer:
    return Answer(value=value, basis=Basis.DEFAULTED)


def settle(profile: DeviceProfile) -> DeviceProfile:
    """Record the answers the definitions give. Changes the profile in place."""
    for function in profile.functions:
        general = function.general
        if general is None:
            continue
        software = function.is_software.resolved and function.is_software.value is Tri.YES
        for name, value in SOFTWARE_DEFINITIONS.items():
            answer = getattr(general, name)
            if software and not answer.resolved:
                setattr(general, name, _default(value))
            elif not software and answer.basis is Basis.DEFAULTED and answer.value == value:
                setattr(general, name, Answer())
    return profile


# --------------------------------------------------------------------------
# Order
# --------------------------------------------------------------------------

# Clauses that open "Despite": they displace the others, so they lead.
GENERAL_DESPITE = ["is_export_only"]                                   # 5.8
IVD_DESPITE = ["is_export_only", "is_quality_control_material",        # 1.8, 1.5
               "is_ivd_instrument", "is_specimen_receptacle",          # 1.6(2)(a), (b)
               "is_culture_medium"]                                    # 1.6(2)(c)

# Questions whose answer opens or closes a group of rules. Asked before the
# rules they open, in this order.
GENERAL_OPENERS = [
    "invasiveness", "duration", "orifice_site", "connected_to_an_active_device",
    "is_active_device", "is_programmed_or_programmable",
    "active_for_therapy", "active_for_diagnosis", "administers_or_removes_substances",
    "diagnoses_or_screens", "monitors_disease_state", "specifies_or_recommends_treatment",
    "provides_therapy_through_information",
    "handles_substances_for_administration", "contacts_injured_skin_or_mucous_membrane",
    "records_images_or_anatomical_model", "administers_by_inhalation",
    "is_substance_through_orifice_or_skin",
]
IVD_OPENERS = ["detects_infectious_agent", "types_blood_or_tissue", "is_self_test"]

III, IIB, IIA = 3, 2, 1

# The highest class each remaining field's paragraphs can give. Where one
# field feeds several paragraphs, or a paragraph that another in the same
# clause is "subject to", the clause's highest class is used.
GENERAL_RANK = {
    # Part 2
    "channels_or_stores_blood_for_administration": IIA,                # 2.2(1)(a)
    "stores_organ_or_tissue_for_introduction": IIA,                    # 2.2(1)(b)
    "channels_or_stores_liquid_or_gas_for_administration": IIA,        # 2.2(1)(c)(i)
    "connected_to_active_device": IIA,                                 # 2.2(1)(c)(ii), 3.1(3)
    "saline_only_flush_or_patency": IIA,                               # 2.2A
    "modifies_composition_of_blood_or_infusion": IIB,                  # 2.3(1)
    "treatment_is_filtration_centrifugation_or_exchange": IIB,         # 2.3(2)
    "barrier_compression_or_absorption": IIB,                          # 2.4(3)
    "principally_for_breached_dermis_secondary_intent": IIB,           # 2.4(4)
    # Part 3
    "liable_to_be_absorbed_by_mucous_membrane": IIB,                   # 3.1(2)(c)
    "corrects_heart_or_circulatory_defect_by_contact": III,            # 3.2(3), 3.3(4)(a)
    "direct_contact_heart_circulation_or_nervous_system": III,         # 3.2(3A) to 3.4(4)(a)
    "reusable_surgical_instrument": III,                               # 3.2(3A), (4)
    "delivers_ionising_radiation": IIB,                                # 3.2(5)(a), 3.3(3)(a)
    "has_biological_effect": III,                                      # 3.3(4)(c), 3.4(4)(b)
    "wholly_or_mostly_absorbed": III,                                  # 3.3(4)(d), 3.4(4)(c)
    "undergoes_chemical_change": III,                                  # 3.4(4)(d)
    "placed_in_teeth": III,                                            # 3.4(3), (4)(d)
    "administers_medicine_hazardously_by_delivery_system": IIB,        # 3.2(5)(d)
    "administers_medicine": III,                                       # 3.4(4)(e)
    "joint_replacement_or_surgical_mesh": III,                         # 3.4(4A)
    "spinal_motion_preserving": III,                                   # 3.4(4B)
    # Part 4
    "administers_or_exchanges_energy": IIB,                            # 4.2(1), (2)
    "delivers_hazardous_energy": IIB,                                  # 4.2(2)
    "controls_hazardous_therapy_device": IIB,                          # 4.2(3)
    "diagnostic_function_determines_patient_management": III,          # 4.2(4)
    "supplies_absorbed_energy_for_diagnosis": IIA,                     # 4.3(2)(a)
    "images_radiopharmaceutical_distribution": IIA,                    # 4.3(2)(b)
    "diagnoses_or_monitors_vital_processes": IIA,                      # 4.3(2)(c)
    "monitors_vital_parameters_immediate_danger": IIB,                 # 4.3(3)(a)
    "emits_ionising_radiation_for_interventional_radiology": IIB,      # 4.3(3)(b)
    "controls_interventional_radiology_device": IIB,                   # 4.3(3)(c)
    "substance_administration_potentially_hazardous": IIB,             # 4.4(2)
    "decision_maker": III,                                             # 4.5, 4.7
    "condition_severity": III,                                         # 4.5
    "public_health_risk": III,                                         # 4.5 to 4.7
    "monitoring_danger": IIB,                                          # 4.6
    "treatment_risk": III,                                             # 4.7
    "information_therapy_harm": III,                                   # 4.8
    # Part 5
    "incorporates_medicine": III,                                      # 5.1
    "human_blood_derivative": III,                                     # 5.1(3)
    "contraceptive_or_sti_prevention": III,                            # 5.2
    "cares_for_contact_lenses": IIB,                                   # 5.3(1)
    "disinfects_another_device": IIB,                                  # 5.3(2)
    "records_patient_images_outside_visible_spectrum": IIA,            # 5.4(1)
    "is_anatomical_model_for_diagnosis": IIA,                          # 5.4(2)
    "generates_virtual_anatomical_model": IIA,                         # 5.4(3)
    "contains_non_viable_animal_material": III,                        # 5.5
    "contacts_intact_skin_only": III,                                  # 5.5(2)
    "is_blood_bag": IIB,                                               # 5.6
    "is_active_implantable": III,                                      # 5.7(1)
    "implantable_accessory_to_active_implantable": III,                # 5.7(2)
    "controls_active_implantable": III,                                # 5.7(3)
    "is_mammary_implant": III,                                         # 5.9
    "inhalation_mode_of_action_essential": IIB,                        # 5.10(a)
    "inhalation_treats_life_threatening_condition": IIB,               # 5.10(b)
    "substance_acts_in_nose_mouth_or_on_skin": IIB,                    # 5.11
}

CLASS_4, CLASS_3, CLASS_1 = 4, 3, 1

IVD_RANK = {
    "screens_donations_for_transmissible_agents": CLASS_4,             # 1.1(a)
    "agent_serious_with_high_propagation_risk": CLASS_4,               # 1.1(b)
    "detects_listed_blood_group_marker": CLASS_4,                      # 1.2(2)
    "assesses_transfusion_or_transplant_compatibility": CLASS_3,       # 1.2(1)
    "detects_sexually_transmitted_agent": CLASS_3,                     # 1.3(a)
    "detects_limited_propagation_agent_in_csf_or_blood": CLASS_3,      # 1.3(b)
    "error_could_cause_death_or_severe_disability": CLASS_3,           # 1.3(c)
    "prenatal_immune_status_screening": CLASS_3,                       # 1.3(d)
    "infective_status_error_life_threatening": CLASS_3,                # 1.3(e)
    "selects_patients_for_therapy": CLASS_3,                           # 1.3(f)(i)
    "selects_patients_for_disease_staging": CLASS_3,                   # 1.3(f)(ii)
    "selects_patients_in_cancer_diagnosis": CLASS_3,                   # 1.3(f)(iii)
    "is_companion_diagnostic": CLASS_3,                                # 1.3(fa)
    "is_human_genetic_test": CLASS_3,                                  # 1.3(g)
    "monitors_levels_error_life_threatening": CLASS_3,                 # 1.3(h)
    "manages_life_threatening_infectious_disease": CLASS_3,            # 1.3(i)
    "screens_foetus_for_congenital_disorders": CLASS_3,                # 1.3(j)
    "result_not_determining_serious_condition": CLASS_3,               # 1.4(a)
    "preliminary_with_follow_up_testing": CLASS_3,                     # 1.4(b)
    "is_ancillary_reagent_or_article": CLASS_1,                        # 1.6(1)
}

BRANCH_ORDER = {
    "general": (GENERAL_DESPITE, GENERAL_OPENERS, GENERAL_RANK),
    "ivd": (IVD_DESPITE, IVD_OPENERS, IVD_RANK),
}

CORE_FIRST = ["core.product_name", "core.intended_purpose"]
CORE_LAST = ["core.supplied_sterile", "core.has_measuring_function"]


def stopped(function: FunctionProfile, index: int) -> bool:
    """Has the gate already decided this function is outside the rules."""
    return status_of(function, index).outcome.terminal


def _function_key(profile: DeviceProfile, index: int, rest: str, position: int):
    """The sort key for one of a function's fields, or None to leave it out."""
    function = profile.functions[index]
    if rest in ("name", "description"):
        return (1, index, 0 if rest == "name" else 1)
    if rest == "is_software":
        return (3, index, 0, 0)
    if rest.startswith("status."):
        order = relevant_status_fields(function)
        name = rest.split(".", 1)[1]
        return (3, index, 1, order.index(name) if name in order else len(order))
    if stopped(function, index):
        return None
    if rest == "kind":
        return (4, index, 0, 0, 0)
    section, name = rest.split(".", 1)
    despite, openers, rank = BRANCH_ORDER[section]
    if name in despite:
        return (4, index, 1, despite.index(name), 0)
    if name in openers:
        return (4, index, 2, openers.index(name), 0)
    return (4, index, 3, -rank.get(name, 0), position)


def plan(profile: DeviceProfile) -> list[str]:
    """The askable fields, in the order they will be asked.

    Works on the profile as given; next_question settles a copy first.
    """
    askable = profile.askable()
    all_stopped = bool(profile.functions) and all(
        stopped(f, i) for i, f in enumerate(profile.functions))
    keyed = []
    for position, dotted in enumerate(askable):
        if dotted in CORE_FIRST:
            key = (0, CORE_FIRST.index(dotted))
        elif dotted == "core.functions_confirmed":
            key = (2,)
        elif dotted in CORE_LAST:
            if all_stopped:
                continue
            key = (5, CORE_LAST.index(dotted))
        else:
            _, index, rest = dotted.split(".", 2)
            key = _function_key(profile, int(index), rest, position)
            if key is None:
                continue
        keyed.append((key, dotted))
    return [dotted for _, dotted in sorted(keyed)]


def next_question(profile: DeviceProfile) -> Question | None:
    """The next question for this profile, or None when nothing is left to ask."""
    settled = settle(profile.model_copy(deep=True))
    order = plan(settled)
    return render(settled, order[0]) if order else None

