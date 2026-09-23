"""Device profile schema.

The structured object produced by intake and consumed by the rule engines.
Every field records where its value came from, so the report can cite the
founder's own words and the clarification loop knows what is still missing.

Version 0.3 moves the unit of analysis from a device to a product made of one
or more functions. A product is a list of FunctionProfile objects, each with
its own route through the rules. Results aggregate two different ways:
classification takes the highest class across functions, while exclusion and
the CDSS exemption require every function to qualify. That asymmetry is the
reason functions have to be first-class rather than a flag.

Version 0.4 adds the inputs the regulatory status gate needs. Nothing here
decides status; these are the facts the gate in status.py reads. They sit on
the function rather than the product because a single product can hold one
function that is a regulated device and another that is excluded.

Version 0.5 splits the one Schedule 2A field is_instrument_or_receptacle
into the three things clause 1.6(2) actually names: an instrument (a), a
specimen receptacle (b) and a microbiological culture medium (c). Each
paragraph is cited on its own, and (b) excludes a receptacle intended for
self-testing, which a combined field could not express.

Version 0.6 gives Schedule 2A clauses 1.1 to 1.4 one field per paragraph.
The paragraphs are intended uses, not combinations of shared attributes, and
several can apply to one device, so a single purpose field could neither
cite the paragraph nor record the overlap. Three gate questions keep the
interview short: an infectious or transmissible agent opens 1.1 and the
agent paragraphs of 1.3; blood group or tissue typing opens 1.2;
self-testing opens the two exceptions in 1.4. The coarse fields they replace
(purpose, transmission risk, life-threatening disease, critical decision,
near-patient testing, sample type) are gone: no rule read them, and
near-patient testing has no clause in Schedule 2A at all.

Whether an agent poses "a high risk of propagation in Australia" is a
regulatory judgement. It is asked, with evidence, never inferred.

Version 0.7 does the same for Schedule 2 Part 2, the non-invasive clauses.
One field per paragraph of 2.2, 2.2A, 2.3 and 2.4 behind two gates: a device
that handles substances for administration, and a device in contact with
injured skin or a mucous membrane. The single-choice fluid_handling and
wound_function fields could not record a device meeting two paragraphs, and
had nothing for organ storage (2.2(1)(b)) or saline flushes (2.2A).
contacts_injured_skin missed the mucous membranes 2.4(1) names, and
breaches_dermis split the one condition in 2.4(4) across two fields.

Version 0.8 covers Schedule 2 Part 5, the rules for particular kinds of
devices, one field per paragraph gated by facts already held: software is
never asked about materials, only implantable devices about implants, only
active devices or software about controlling an active implantable device.
animal_or_microbial_origin becomes contains_non_viable_animal_material,
because since July 2024 clause 5.5 covers animal material only.

Version 0.9 covers Schedule 2 Part 3, the invasive clauses. body_contact
conflated two conditions (a purpose to correct a heart defect, and plain
direct contact with the heart, circulation or nerves), and
absorbed_or_chemically_changed merged two paragraphs that give different
classes in 3.3 (absorbed is Class III, chemical change Class IIb). Both are
replaced by one field per condition, asked only in the duration band where
the text uses it. Orifice devices get a gate for connection to any active
device, because 3.1(2) and 3.1(3) turn on different connections.

Version 0.10 covers Schedule 2 Part 4, active devices and software, and
completes the Schedule 2 inputs. The single-choice active_type and
clinical_function could not hold a device that is both for therapy and for
diagnosis, or one that both monitors vital signs (4.3) and tracks a disease
(4.6). They are replaced by two yes/no questions, "active device for
therapy" and "for diagnosis" (dictionary terms; a device can be both), with
one field per paragraph behind each, and four gates for the software rules
4.5 to 4.8. Those rules reach "a programmed or programmable medical device,
or software", so active hardware is asked whether it is programmable;
software always is, and is always active (dictionary). 4.6, 4.7 and 4.8
each grade on their own scale, so each has its own level question;
condition_severity keeps the 4.5 scale only and loses its "moderate" value,
which no clause uses.

Version 0.11 adds the Schedule 2A fallback question for clause 1.6(1):
whether the IVD is an ancillary reagent or article used in a specific
examination (a buffer, a wash solution, a general reagent) rather than the
test itself. Read literally, 1.6(1) would catch almost every test kit and
leave clause 1.7 nearly empty; it is read the way the international model
the rules came from reads it (IMDRF/GHTF rule 5: wash solutions, general
culture media, plain urine cups).

Version 0.12 is the first intake schema. The profile carries a transcript of
every question put to the founder and the reply, word for word. An ANSWERED
field's evidence has to be a phrase from the reply to a question that covered
that field, the same way a STATED field's evidence has to be a phrase from
source_text; before the transcript there was nowhere to check it against.
A reply can also be "not sure": the field stays unknown, the turn records
that it was asked, and askable() stops offering it, so an interview cannot
loop on a question the founder cannot answer. The engine's Pending for that
field then reaches the report as something for a regulatory adviser.

The two regulation 3.9 qualifiers are asked only where the engine can read
them: both only for a product with a general device function (regulation
1.4(2) and 3.9A keep IVDs out), and sterile supply never for a product whose
general functions are all software, which cannot be supplied sterile. A
product whose functions are not yet known is asked both.
"""

from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class Basis(str, Enum):
    """How a field got its value."""

    STATED = "stated"        # present in the founder's description
    ANSWERED = "answered"    # supplied in response to a clarifying question
    DEFAULTED = "defaulted"  # a legal default, not a claim about this device
    UNKNOWN = "unknown"      # not yet established


class Answer(BaseModel, Generic[T]):
    """A field value plus its provenance."""

    value: T | None = None
    basis: Basis = Basis.UNKNOWN
    evidence: str | None = Field(
        default=None,
        description="Verbatim phrase from the source text that supports the value.",
    )

    @model_validator(mode="after")
    def _claims_need_evidence(self):
        """A claim about this device has to point at where it came from.

        DEFAULTED is exempt: a legal default is not a claim about the device
        and has no phrase behind it.
        """
        if self.basis in (Basis.STATED, Basis.ANSWERED) and not self.evidence:
            raise ValueError(f"basis {self.basis.value} requires evidence")
        return self

    @property
    def resolved(self) -> bool:
        return self.basis in (Basis.STATED, Basis.ANSWERED, Basis.DEFAULTED)


class Tri(str, Enum):
    """Never use a bare bool. Unknown must be distinguishable from no."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------
# Enumerations, worded to follow the regulations rather than marketing copy
# --------------------------------------------------------------------------


class DeviceKind(str, Enum):
    GENERAL = "general_device"
    IVD = "ivd"
    UNKNOWN = "unknown"


class TherapeuticPurpose(str, Enum):
    """The limbs of the medical device definition, s41BD(1)(a)(i) to (v).

    A function qualifies through one of these or through none. NONE is a
    finding, not a gap: it means the founder's own description of what the
    function is for does not reach any limb, which is what makes the thing not
    a device unless it is an accessory under s41BD(1)(b).

    Checked against the Act at Compilation No. 89 (5 September 2025).
    """

    DISEASE = "diagnosis_prevention_monitoring_prediction_treatment_of_disease"  # (i)
    INJURY = "diagnosis_monitoring_treatment_or_compensation_for_injury"          # (ii)
    ANATOMY = "investigation_or_modification_of_anatomy_or_physiological_process"  # (iii)
    CONCEPTION = "control_or_support_of_conception"                               # (iv)
    IN_VITRO_SPECIMEN = "in_vitro_examination_of_specimen_for_medical_purpose"    # (v)
    NONE = "no_therapeutic_purpose"


class Invasiveness(str, Enum):
    NON_INVASIVE = "non_invasive"
    BODY_ORIFICE = "invasive_body_orifice"
    SURGICALLY_INVASIVE = "surgically_invasive"
    IMPLANTABLE = "implantable"


class Duration(str, Enum):
    """The legal bands, not free-form minutes."""

    TRANSIENT = "transient"      # continuous use under 60 minutes
    SHORT_TERM = "short_term"    # 60 minutes to 30 days
    LONG_TERM = "long_term"      # over 30 days


class OrificeSite(str, Enum):
    """Sub-rule 3.1 treats the shallow orifices differently from the rest."""

    ORAL_TO_PHARYNX = "oral_cavity_as_far_as_pharynx"
    EAR_TO_EARDRUM = "ear_canal_up_to_eardrum"
    NASAL_CAVITY = "nasal_cavity"
    OTHER_ORIFICE = "other_body_orifice"
    STOMA = "stoma"


class DecisionMaker(str, Enum):
    """Who acts on the output. The single biggest lever on software class."""

    DEVICE_TO_LAY_USER = "device_gives_the_decision_to_a_lay_user"
    DEVICE_TO_PROFESSIONAL = "device_gives_the_decision_to_a_health_professional"
    INFORMS_PROFESSIONAL = "informs_a_health_professional_who_decides"


class Severity(str, Enum):
    """The disease or condition, as clause 4.5 grades it."""

    DEATH_WITHOUT_URGENT_TREATMENT = "death_or_severe_deterioration_without_urgent_treatment"
    SERIOUS = "serious_disease_or_condition"
    OTHER = "any_other_case"


class MonitoringDanger(str, Enum):
    """What the monitoring information could indicate, as clause 4.6 grades it."""

    IMMEDIATE = "immediate_danger"
    OTHER = "other_danger"
    NONE = "any_other_case"


class TreatmentRisk(str, Enum):
    """The treatment or its absence, as clause 4.7 grades it."""

    DEATH_OR_SEVERE_DETERIORATION = "death_or_severe_deterioration"
    OTHER_HARM = "otherwise_harmful"
    NONE = "any_other_case"


class InformationTherapyHarm(str, Enum):
    """The therapy given through information, as clause 4.8 grades it."""

    DEATH_OR_SEVERE_DETERIORATION = "death_or_severe_deterioration"
    SERIOUS_HARM = "serious_harm"
    HARM = "harm"
    NONE = "any_other_case"


class PublicHealthRisk(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


class CareSetting(str, Enum):
    PUBLIC_HOSPITAL = "public_hospital"
    PRIVATE_HOSPITAL = "private_hospital"
    SPECIALIST_ROOMS = "specialist_rooms"
    PRIMARY_CARE = "primary_care"
    PATHOLOGY_LAB = "pathology_lab"
    HOME = "home_or_self_use"


class Operator(str, Enum):
    SPECIALIST = "medical_specialist"
    GENERAL_PRACTITIONER = "general_practitioner"
    NURSE_OR_ALLIED = "nurse_or_allied_health"
    LABORATORY_SCIENTIST = "laboratory_scientist"
    PATIENT = "patient_or_carer"


# --------------------------------------------------------------------------
# Sub-profiles
# --------------------------------------------------------------------------


class CoreProfile(BaseModel):
    """Product-level facts. True of the thing as supplied, not of one function."""

    product_name: Answer[str] = Answer()
    intended_purpose: Answer[str] = Answer()
    # Not classification inputs. On a Class I device they add conformity
    # assessment procedures (regulation 3.9(2) and (3)), reported as qualifiers
    # beside the class. Often shortened to "Class Is" and "Class Im".
    supplied_sterile: Answer[Tri] = Answer()
    has_measuring_function: Answer[Tri] = Answer()    # regulation 1.4
    functions_confirmed: Answer[Tri] = Answer(
        # The founder describes a product; the decomposition into functions is
        # proposed by intake and has to be confirmed, because the boundary
        # between one function and three changes the regulatory outcome.
    )


class GeneralDeviceProfile(BaseModel):
    """Inputs to the Schedule 2 rules.

    Wider than any one device needs. Relevance gating decides which are
    actually asked, so a software product is never questioned about animal
    tissue and a bandage is never questioned about ionising radiation.
    """

    # Route and contact
    invasiveness: Answer[Invasiveness] = Answer()
    duration: Answer[Duration] = Answer()
    orifice_site: Answer[OrificeSite] = Answer()

    # Schedule 2 Part 2, non-invasive devices. Each comment names its paragraph.
    # Gate: substances for administration opens 2.2, 2.2A and 2.3.
    handles_substances_for_administration: Answer[Tri] = Answer()
    channels_or_stores_blood_for_administration: Answer[Tri] = Answer()     # 2.2(1)(a)
    stores_organ_or_tissue_for_introduction: Answer[Tri] = Answer()         # 2.2(1)(b)
    channels_or_stores_liquid_or_gas_for_administration: Answer[Tri] = Answer()  # 2.2(1)(c)(i)
    # "May be connected to an active medical device classified as Class IIa or
    # higher". Read by 2.2(1)(c)(ii) and by 3.1(3).
    connected_to_active_device: Answer[Tri] = Answer()
    saline_only_flush_or_patency: Answer[Tri] = Answer()                    # 2.2A
    modifies_composition_of_blood_or_infusion: Answer[Tri] = Answer()       # 2.3(1)
    treatment_is_filtration_centrifugation_or_exchange: Answer[Tri] = Answer()  # 2.3(2)
    # Gate: injured skin or a mucous membrane opens 2.4.
    contacts_injured_skin_or_mucous_membrane: Answer[Tri] = Answer()        # 2.4(1)
    barrier_compression_or_absorption: Answer[Tri] = Answer()               # 2.4(3)
    principally_for_breached_dermis_secondary_intent: Answer[Tri] = Answer()  # 2.4(4)

    # Schedule 2 Part 3, invasive devices. Each comment names its paragraphs.
    # Orifice route (3.1). Gate: any active device; "Class IIa or higher" is
    # connected_to_active_device above.
    connected_to_an_active_device: Answer[Tri] = Answer()                   # 3.1(2), (3)
    liable_to_be_absorbed_by_mucous_membrane: Answer[Tri] = Answer()        # 3.1(2)(c)(ii)
    # Surgically invasive and implantable (3.2 to 3.4).
    # 3.2(3), 3.3(4)(a)
    corrects_heart_or_circulatory_defect_by_contact: Answer[Tri] = Answer()
    # 3.2(3A), 3.3(4)(b), 3.4(4)(a)
    direct_contact_heart_circulation_or_nervous_system: Answer[Tri] = Answer()
    reusable_surgical_instrument: Answer[Tri] = Answer()                    # 3.2(4)
    # "Supply energy in the form of ionising radiation"; also read by Part 4.
    delivers_ionising_radiation: Answer[Tri] = Answer()                     # 3.2(5)(a), 3.3(3)(a)
    # 3.2(5)(b), 3.3(4)(c), 3.4(4)(b)
    has_biological_effect: Answer[Tri] = Answer()
    # 3.2(5)(c), 3.3(4)(d), 3.4(4)(c)
    wholly_or_mostly_absorbed: Answer[Tri] = Answer()
    undergoes_chemical_change: Answer[Tri] = Answer()                       # 3.3(3)(b), 3.4(4)(d)
    placed_in_teeth: Answer[Tri] = Answer()                                 # 3.3(3)(b), 3.4(3)
    administers_medicine_hazardously_by_delivery_system: Answer[Tri] = Answer()  # 3.2(5)(d)
    administers_medicine: Answer[Tri] = Answer()                            # 3.3(3)(c), 3.4(4)(e)
    joint_replacement_or_surgical_mesh: Answer[Tri] = Answer()              # 3.4(4A)
    spinal_motion_preserving: Answer[Tri] = Answer()                        # 3.4(4B)

    # Schedule 2 Part 4, active devices and software. Software is always an
    # active device and always programmed, so neither is asked of it.
    is_active_device: Answer[Tri] = Answer()                                # 4.1
    is_programmed_or_programmable: Answer[Tri] = Answer()                   # 4.5 to 4.8
    is_active_implantable: Answer[Tri] = Answer()                           # 5.7(1)
    # Gate: active medical device for therapy (dictionary), opens 4.2.
    active_for_therapy: Answer[Tri] = Answer()
    administers_or_exchanges_energy: Answer[Tri] = Answer()                 # 4.2(1)
    delivers_hazardous_energy: Answer[Tri] = Answer()                       # 4.2(2)
    controls_hazardous_therapy_device: Answer[Tri] = Answer()               # 4.2(3)
    diagnostic_function_determines_patient_management: Answer[Tri] = Answer()  # 4.2(4)
    # Gate: active medical device for diagnosis (dictionary), opens 4.3.
    active_for_diagnosis: Answer[Tri] = Answer()
    supplies_absorbed_energy_for_diagnosis: Answer[Tri] = Answer()          # 4.3(2)(a)
    images_radiopharmaceutical_distribution: Answer[Tri] = Answer()         # 4.3(2)(b)
    diagnoses_or_monitors_vital_processes: Answer[Tri] = Answer()           # 4.3(2)(c)
    monitors_vital_parameters_immediate_danger: Answer[Tri] = Answer()      # 4.3(3)(a)
    emits_ionising_radiation_for_interventional_radiology: Answer[Tri] = Answer()  # 4.3(3)(b)
    controls_interventional_radiology_device: Answer[Tri] = Answer()        # 4.3(3)(c)
    # Any active device.
    administers_or_removes_substances: Answer[Tri] = Answer()               # 4.4(1)
    substance_administration_potentially_hazardous: Answer[Tri] = Answer()  # 4.4(2)
    # Programmed or programmable devices and software, 4.5 to 4.8.
    diagnoses_or_screens: Answer[Tri] = Answer()                            # 4.5
    monitors_disease_state: Answer[Tri] = Answer()                          # 4.6
    specifies_or_recommends_treatment: Answer[Tri] = Answer()               # 4.7
    provides_therapy_through_information: Answer[Tri] = Answer()            # 4.8
    decision_maker: Answer[DecisionMaker] = Answer()                        # 4.5, 4.7
    condition_severity: Answer[Severity] = Answer()                         # 4.5
    public_health_risk: Answer[PublicHealthRisk] = Answer()                 # 4.5 to 4.7
    monitoring_danger: Answer[MonitoringDanger] = Answer()                  # 4.6
    treatment_risk: Answer[TreatmentRisk] = Answer()                        # 4.7
    information_therapy_harm: Answer[InformationTherapyHarm] = Answer()     # 4.8

    # Schedule 2 Part 5, particular kinds of devices. Any can outrank the
    # clauses above; 5.8 displaces all of them. Each comment names its clause.
    is_export_only: Answer[Tri] = Answer()                                  # 5.8
    incorporates_medicine: Answer[Tri] = Answer()                           # 5.1(1)
    human_blood_derivative: Answer[Tri] = Answer()                          # 5.1(3)
    contraceptive_or_sti_prevention: Answer[Tri] = Answer()                 # 5.2
    cares_for_contact_lenses: Answer[Tri] = Answer()                        # 5.3(1)
    disinfects_another_device: Answer[Tri] = Answer()                       # 5.3(2)
    # Gate: records patient images or is an anatomical model, opens 5.4.
    records_images_or_anatomical_model: Answer[Tri] = Answer()
    records_patient_images_outside_visible_spectrum: Answer[Tri] = Answer()  # 5.4(1)
    is_anatomical_model_for_diagnosis: Answer[Tri] = Answer()               # 5.4(2)
    generates_virtual_anatomical_model: Answer[Tri] = Answer()              # 5.4(3), software
    # Non-viable animal tissue, cells or derivatives, other than hair or wool,
    # sintered hydroxyapatite or tallow derivatives.
    contains_non_viable_animal_material: Answer[Tri] = Answer()             # 5.5(1)
    contacts_intact_skin_only: Answer[Tri] = Answer()                       # 5.5(2)
    is_blood_bag: Answer[Tri] = Answer()                                    # 5.6
    implantable_accessory_to_active_implantable: Answer[Tri] = Answer()     # 5.7(2)
    controls_active_implantable: Answer[Tri] = Answer()                     # 5.7(3)
    is_mammary_implant: Answer[Tri] = Answer()                              # 5.9
    # Gate: administers medicines or biologicals by inhalation, opens 5.10.
    administers_by_inhalation: Answer[Tri] = Answer()
    inhalation_mode_of_action_essential: Answer[Tri] = Answer()             # 5.10(a)
    inhalation_treats_life_threatening_condition: Answer[Tri] = Answer()    # 5.10(b)
    # Gate: composed of substances introduced through an orifice or absorbed
    # by the skin, opens 5.11.
    is_substance_through_orifice_or_skin: Answer[Tri] = Answer()
    substance_acts_in_nose_mouth_or_on_skin: Answer[Tri] = Answer()         # 5.11(c)

class IvdProfile(BaseModel):
    """Inputs to the Schedule 2A rules. Each comment names the clause it feeds."""

    # Gates. Each opens a group of paragraphs; none decides a class alone.
    detects_infectious_agent: Answer[Tri] = Answer()          # 1.1, 1.3(a)-(e), (i)
    types_blood_or_tissue: Answer[Tri] = Answer()             # 1.2
    is_self_test: Answer[Tri] = Answer()                      # 1.4, 1.6(2)(b)

    # Clause 1.1, Class 4. Asked when detects_infectious_agent is yes.
    screens_donations_for_transmissible_agents: Answer[Tri] = Answer()   # 1.1(a)
    agent_serious_with_high_propagation_risk: Answer[Tri] = Answer()     # 1.1(b)

    # Clause 1.2. Asked when types_blood_or_tissue is yes.
    assesses_transfusion_or_transplant_compatibility: Answer[Tri] = Answer()  # 1.2(1)
    detects_listed_blood_group_marker: Answer[Tri] = Answer()                 # 1.2(2)

    # Clause 1.3, Class 3. The agent paragraphs, asked when
    # detects_infectious_agent is yes.
    detects_sexually_transmitted_agent: Answer[Tri] = Answer()           # 1.3(a)
    detects_limited_propagation_agent_in_csf_or_blood: Answer[Tri] = Answer()  # 1.3(b)
    error_could_cause_death_or_severe_disability: Answer[Tri] = Answer()  # 1.3(c)
    prenatal_immune_status_screening: Answer[Tri] = Answer()             # 1.3(d)
    infective_status_error_life_threatening: Answer[Tri] = Answer()      # 1.3(e)
    manages_life_threatening_infectious_disease: Answer[Tri] = Answer()  # 1.3(i)

    # Clause 1.3, Class 3. Asked of every IVD that reaches the ordinary rules.
    selects_patients_for_therapy: Answer[Tri] = Answer()                 # 1.3(f)(i)
    selects_patients_for_disease_staging: Answer[Tri] = Answer()         # 1.3(f)(ii)
    selects_patients_in_cancer_diagnosis: Answer[Tri] = Answer()         # 1.3(f)(iii)
    is_companion_diagnostic: Answer[Tri] = Answer()                      # 1.3(fa)
    is_human_genetic_test: Answer[Tri] = Answer()                        # 1.3(g)
    monitors_levels_error_life_threatening: Answer[Tri] = Answer()       # 1.3(h)
    screens_foetus_for_congenital_disorders: Answer[Tri] = Answer()      # 1.3(j)

    # Clause 1.4 exceptions. Asked when is_self_test is yes.
    result_not_determining_serious_condition: Answer[Tri] = Answer()     # 1.4(a)
    preliminary_with_follow_up_testing: Answer[Tri] = Answer()           # 1.4(b)

    # Named exceptions. These cannot be reasoned to, only looked up.
    is_ivd_instrument: Answer[Tri] = Answer()                # clause 1.6(2)(a)
    is_specimen_receptacle: Answer[Tri] = Answer()           # clause 1.6(2)(b)
    is_culture_medium: Answer[Tri] = Answer()                # clause 1.6(2)(c)
    is_quality_control_material: Answer[Tri] = Answer()      # clause 1.5
    is_export_only: Answer[Tri] = Answer()                   # clause 1.8

    # Clause 1.6(1), read narrowly: an ancillary reagent or article used in a
    # specific examination (buffer, wash solution, general reagent), not the
    # test itself. Asked on the ordinary route with the other 1.3 questions.
    is_ancillary_reagent_or_article: Answer[Tri] = Answer()  # clause 1.6(1)


class FundingProfile(BaseModel):
    """Inputs to reimbursement triage. Product level, not per function."""

    care_setting: Answer[CareSetting] = Answer()
    operator: Answer[Operator] = Answer()
    is_first_in_class: Answer[Tri] = Answer()
    replaces_existing_service: Answer[str] = Answer()
    privately_insured_patients: Answer[Tri] = Answer()


class StatusProfile(BaseModel):
    """Inputs to the regulatory status gate. One per function.

    Three separate questions live here and they are not the same question.
    Whether the function is a device at all is decided by the Act. Whether an
    excluded good description captures it is decided by the Excluded Goods
    Determination 2018 and removes it from regulation entirely. Whether it is
    exempt clinical decision support is decided by the Medical Devices
    Regulations, leaves it a medical device, and carries a notification
    obligation rather than an ARTG entry.
    """

    # Is it a device at all, s41BD
    therapeutic_purpose: Answer[TherapeuticPurpose] = Answer()
    principal_action_pharmacological: Answer[Tri] = Answer()
    is_accessory_to_device: Answer[Tri] = Answer()

    # Is it excluded, Excluded Goods Determination 2018, Schedule 1
    excluded_item: Answer[str] = Answer()            # "S1-14B", "S2-7", or "none"
    exclusion_conditions_met: Answer[Tri] = Answer()  # every condition of that item

    # Is it exempt CDSS, Medical Devices Regulations 2002, Schedule 4 Part 2
    # item 2.15.
    # Worded as the criteria are worded, deliberately. decision_maker on the
    # general section is close to the third criterion but is not the same test,
    # so neither is derived from the other.
    cdss_sole_purpose_recommendation: Answer[Tri] = Answer()
    cdss_processes_device_signal_or_image: Answer[Tri] = Answer()
    cdss_replaces_clinical_judgement: Answer[Tri] = Answer()


class FunctionProfile(BaseModel):
    """One function of a product, with its own route through the rules.

    A function is the unit the rules actually operate on. An imaging platform
    that stores studies, flags abnormal ones and suggests a follow-up interval
    is three functions, and they can land in three different places.
    """

    name: Answer[str] = Answer()
    description: Answer[str] = Answer()
    kind: Answer[DeviceKind] = Answer()
    is_software: Answer[Tri] = Answer()

    status: StatusProfile = StatusProfile()
    general: GeneralDeviceProfile | None = None
    ivd: IvdProfile | None = None

    def branch(self) -> DeviceKind | None:
        """The settled kind, or None.

        Goes through _value rather than reading kind.value directly, so an
        unresolved answer cannot route a function into a rule family. UNKNOWN
        is not a branch either.
        """
        kind = _value(self.kind)
        return None if kind is DeviceKind.UNKNOWN else kind

    def relevant(self) -> list[str]:
        """Field names this function requires, unprefixed."""
        names = ["name", "description", "kind", "is_software"]
        names += [f"status.{n}" for n in relevant_status_fields(self)]
        if self.branch() is DeviceKind.IVD and self.ivd is not None:
            names += [f"ivd.{n}" for n in relevant_ivd_fields(self.ivd)]
        elif self.branch() is DeviceKind.GENERAL and self.general is not None:
            names += [f"general.{n}" for n in relevant_general_fields(self)]
        return names

    def missing(self) -> list[str]:
        out = []
        for dotted in self.relevant():
            answer = self
            for part in dotted.split("."):
                answer = getattr(answer, part, None)
                if answer is None:
                    break
            if isinstance(answer, Answer) and not answer.resolved:
                out.append(dotted)
        return out

    def prune(self) -> "FunctionProfile":
        """Clear any section field the gating does not ask for.

        An answer nobody asked for is not evidence, it is a guess that survived.
        Keeping it would also mask a gating gap: a rule could read a field the
        interview never covers and still find it populated in testing.
        """
        asked = {n.split(".", 1)[1] for n in self.relevant() if "." in n}
        for section in (self.status, self.general, self.ivd):
            if section is None:
                continue
            for name in type(section).model_fields:
                if name not in asked:
                    setattr(section, name, Answer())
        return self


# --------------------------------------------------------------------------
# Relevance gating
# --------------------------------------------------------------------------

ALWAYS_GENERAL = [
    "invasiveness",
    "is_export_only",
    "incorporates_medicine",
    "contraceptive_or_sti_prevention",
    "cares_for_contact_lenses",
    "disinfects_another_device",
    "records_images_or_anatomical_model",
]

# Asked only of a physical device, never of software alone.
MATERIAL_FIELDS = [
    "human_blood_derivative",
    "contains_non_viable_animal_material",
    "is_blood_bag",
    "administers_by_inhalation",
    "is_substance_through_orifice_or_skin",
]


def _value(answer: Answer):
    return answer.value if answer.resolved else None


def _dedupe(names: list[str]) -> list[str]:
    seen: set[str] = set()
    return [n for n in names if not (n in seen or seen.add(n))]


def relevant_status_fields(function: "FunctionProfile") -> list[str]:
    """Which gate fields this function needs.

    Asked of every function, whatever its kind, because the gate runs before
    the general and IVD branches open. A function that reaches no limb of the
    definition and is not an accessory needs nothing else: it is out of scope
    and asking it about sterility or sample type would be theatre.
    """
    status = function.status
    fields = ["therapeutic_purpose"]
    purpose = _value(status.therapeutic_purpose)
    if purpose is None:
        return fields

    if purpose is TherapeuticPurpose.NONE:
        fields += ["is_accessory_to_device"]
        if _value(status.is_accessory_to_device) is not Tri.YES:
            return fields
    else:
        fields += ["principal_action_pharmacological"]
        if _value(status.principal_action_pharmacological) is Tri.YES:
            return fields

    fields += ["excluded_item"]
    item = _value(status.excluded_item)
    if item is not None and item.strip().lower() not in ("", "none"):
        fields += ["exclusion_conditions_met"]
        # Excluded goods are outside the Act. Nothing after this matters.
        if _value(status.exclusion_conditions_met) is Tri.YES:
            return _dedupe(fields)
    if _value(function.is_software) is Tri.YES:
        fields += [
            "cdss_sole_purpose_recommendation",
            "cdss_processes_device_signal_or_image",
            "cdss_replaces_clinical_judgement",
        ]
    return _dedupe(fields)


PART_2_SUBSTANCE_FIELDS = [
    "channels_or_stores_blood_for_administration",
    "stores_organ_or_tissue_for_introduction",
    "channels_or_stores_liquid_or_gas_for_administration",
    "saline_only_flush_or_patency",
    "modifies_composition_of_blood_or_infusion",
]
PART_2_WOUND_FIELDS = [
    "barrier_compression_or_absorption",
    "principally_for_breached_dermis_secondary_intent",
]


PART_3_FIELDS = {
    "3.2": ["corrects_heart_or_circulatory_defect_by_contact",
            "direct_contact_heart_circulation_or_nervous_system",
            "reusable_surgical_instrument", "delivers_ionising_radiation",
            "has_biological_effect", "wholly_or_mostly_absorbed",
            "administers_medicine_hazardously_by_delivery_system"],
    "3.3": ["corrects_heart_or_circulatory_defect_by_contact",
            "direct_contact_heart_circulation_or_nervous_system",
            "delivers_ionising_radiation", "undergoes_chemical_change",
            "administers_medicine", "has_biological_effect", "wholly_or_mostly_absorbed"],
    "3.4": ["placed_in_teeth", "direct_contact_heart_circulation_or_nervous_system",
            "has_biological_effect", "wholly_or_mostly_absorbed", "undergoes_chemical_change",
            "administers_medicine", "joint_replacement_or_surgical_mesh",
            "spinal_motion_preserving"],
}


def invasive_band(general: "GeneralDeviceProfile") -> str | None:
    """Which of 3.2, 3.3 or 3.4 a surgically invasive or implantable device is in.

    3.4 covers every implantable device and a surgically invasive device for
    long-term use; 3.2 and 3.3 turn on duration. None until that is known.
    """
    route = _value(general.invasiveness)
    if route is Invasiveness.IMPLANTABLE:
        return "3.4"
    if route is not Invasiveness.SURGICALLY_INVASIVE:
        return None
    return {Duration.TRANSIENT: "3.2", Duration.SHORT_TERM: "3.3",
            Duration.LONG_TERM: "3.4"}.get(_value(general.duration))


def part_4_fields(function: "FunctionProfile") -> list[str]:
    """The Part 4 questions for an active device, gate by gate."""
    general = function.general
    software = _value(function.is_software) is Tri.YES
    fields = ["active_for_therapy", "active_for_diagnosis", "administers_or_removes_substances"]
    if not software:
        fields += ["is_programmed_or_programmable"]
    if _value(general.active_for_therapy) is Tri.YES:
        fields += ["administers_or_exchanges_energy", "controls_hazardous_therapy_device",
                   "diagnostic_function_determines_patient_management"]
        if _value(general.administers_or_exchanges_energy) is Tri.YES:
            fields += ["delivers_hazardous_energy"]
    if _value(general.active_for_diagnosis) is Tri.YES:
        fields += ["supplies_absorbed_energy_for_diagnosis",
                   "images_radiopharmaceutical_distribution",
                   "diagnoses_or_monitors_vital_processes",
                   "monitors_vital_parameters_immediate_danger",
                   "emits_ionising_radiation_for_interventional_radiology",
                   "controls_interventional_radiology_device"]
    if _value(general.administers_or_removes_substances) is Tri.YES:
        fields += ["substance_administration_potentially_hazardous"]
    if software or _value(general.is_programmed_or_programmable) is Tri.YES:
        fields += ["diagnoses_or_screens", "monitors_disease_state",
                   "specifies_or_recommends_treatment", "provides_therapy_through_information"]
        if _value(general.diagnoses_or_screens) is Tri.YES:
            fields += ["decision_maker", "condition_severity", "public_health_risk"]
        if _value(general.monitors_disease_state) is Tri.YES:
            fields += ["monitoring_danger", "public_health_risk"]
        if _value(general.specifies_or_recommends_treatment) is Tri.YES:
            fields += ["decision_maker", "treatment_risk", "public_health_risk"]
        if _value(general.provides_therapy_through_information) is Tri.YES:
            fields += ["information_therapy_harm"]
    return fields


def relevant_general_fields(function: "FunctionProfile") -> list[str]:
    """Which Schedule 2 fields this function actually needs.

    Grows as facts are established. Before invasiveness is known the list is
    short; once it is known the branch opens. This is what stops intake turning
    into a twenty-six question interrogation per function.
    """
    general = function.general
    if general is None:
        return []

    fields = list(ALWAYS_GENERAL)
    software = _value(function.is_software) is Tri.YES
    route = _value(general.invasiveness)
    active = software or _value(general.is_active_device) is Tri.YES

    if not software:
        fields += ["is_active_device"] + MATERIAL_FIELDS
        if _value(general.contains_non_viable_animal_material) is Tri.YES:
            fields += ["contacts_intact_skin_only"]
        if _value(general.administers_by_inhalation) is Tri.YES:
            fields += ["inhalation_mode_of_action_essential",
                       "inhalation_treats_life_threatening_condition"]
        if _value(general.is_substance_through_orifice_or_skin) is Tri.YES:
            fields += ["substance_acts_in_nose_mouth_or_on_skin"]
    if _value(general.records_images_or_anatomical_model) is Tri.YES:
        fields += ["records_patient_images_outside_visible_spectrum",
                   "is_anatomical_model_for_diagnosis"]
        if software:
            fields += ["generates_virtual_anatomical_model"]
    if active:
        fields += ["controls_active_implantable"]

    if route is Invasiveness.NON_INVASIVE:
        fields += ["handles_substances_for_administration",
                   "contacts_injured_skin_or_mucous_membrane"]
        if _value(general.handles_substances_for_administration) is Tri.YES:
            fields += PART_2_SUBSTANCE_FIELDS
            if _value(general.channels_or_stores_liquid_or_gas_for_administration) is Tri.YES:
                fields += ["connected_to_active_device"]
            if _value(general.modifies_composition_of_blood_or_infusion) is Tri.YES:
                fields += ["treatment_is_filtration_centrifugation_or_exchange"]
        if _value(general.contacts_injured_skin_or_mucous_membrane) is Tri.YES:
            fields += PART_2_WOUND_FIELDS

    elif route is Invasiveness.BODY_ORIFICE:
        fields += ["duration", "orifice_site", "connected_to_an_active_device"]
        if _value(general.connected_to_an_active_device) is Tri.YES:
            fields += ["connected_to_active_device"]
        if (_value(general.duration) is Duration.LONG_TERM
                and _value(general.orifice_site) is OrificeSite.NASAL_CAVITY):
            fields += ["liable_to_be_absorbed_by_mucous_membrane"]

    elif route in (Invasiveness.SURGICALLY_INVASIVE, Invasiveness.IMPLANTABLE):
        fields += ["duration"]
        band = invasive_band(general)
        fields += PART_3_FIELDS.get(band, [])
        if band == "3.3" and _value(general.undergoes_chemical_change) is Tri.YES:
            fields += ["placed_in_teeth"]
        if route is Invasiveness.IMPLANTABLE:
            fields += ["is_active_implantable", "implantable_accessory_to_active_implantable",
                       "is_mammary_implant"]

    if active:
        fields += part_4_fields(function)

    return _dedupe(fields)


IVD_AGENT_FIELDS = [
    "screens_donations_for_transmissible_agents",
    "agent_serious_with_high_propagation_risk",
    "detects_sexually_transmitted_agent",
    "detects_limited_propagation_agent_in_csf_or_blood",
    "error_could_cause_death_or_severe_disability",
    "prenatal_immune_status_screening",
    "infective_status_error_life_threatening",
    "manages_life_threatening_infectious_disease",
]
IVD_TYPING_FIELDS = [
    "assesses_transfusion_or_transplant_compatibility",
    "detects_listed_blood_group_marker",
]
IVD_GENERAL_FIELDS = [
    "selects_patients_for_therapy",
    "selects_patients_for_disease_staging",
    "selects_patients_in_cancer_diagnosis",
    "is_companion_diagnostic",
    "is_human_genetic_test",
    "monitors_levels_error_life_threatening",
    "screens_foetus_for_congenital_disorders",
    "is_ancillary_reagent_or_article",
]
IVD_SELF_TEST_FIELDS = [
    "result_not_determining_serious_condition",
    "preliminary_with_follow_up_testing",
]


def relevant_ivd_fields(ivd: IvdProfile) -> list[str]:
    """Which Schedule 2A fields this IVD function needs.

    The named exceptions are checked first. An instrument, a culture medium,
    a non assay-specific quality control material or an export-only device
    is classified by that fact alone, so nothing else is worth asking. A
    specimen receptacle is too, but only when it is not intended for
    self-testing (clause 1.6(2)(b)), so it opens that one question. A
    self-test receptacle falls back to the ordinary rules and is asked
    everything.
    """
    exceptions = [
        "is_ivd_instrument",
        "is_specimen_receptacle",
        "is_culture_medium",
        "is_quality_control_material",
        "is_export_only",
    ]
    receptacle = _value(ivd.is_specimen_receptacle) is Tri.YES
    if receptacle:
        exceptions.append("is_self_test")
    decisive = [
        "is_ivd_instrument",
        "is_culture_medium",
        "is_quality_control_material",
        "is_export_only",
    ]
    if any(_value(getattr(ivd, name)) is Tri.YES for name in decisive):
        return exceptions
    if receptacle and _value(ivd.is_self_test) is not Tri.YES:
        return exceptions

    fields = exceptions + [
        "detects_infectious_agent",
        "types_blood_or_tissue",
        "is_self_test",
    ]
    if _value(ivd.detects_infectious_agent) is Tri.YES:
        fields += IVD_AGENT_FIELDS
    if _value(ivd.types_blood_or_tissue) is Tri.YES:
        fields += IVD_TYPING_FIELDS
    fields += IVD_GENERAL_FIELDS
    if _value(ivd.is_self_test) is Tri.YES:
        fields += IVD_SELF_TEST_FIELDS

    return _dedupe(fields)


# --------------------------------------------------------------------------
# Classification vocabulary and aggregation
# --------------------------------------------------------------------------

# The classes Schedule 2 assigns, lowest first. "Highest" is regulation
# 3.3(7)'s sense when rules conflict, and the per-family maximum when several
# functions classify differently. Sterile supply and a measuring function are
# not classes: they are conformity assessment conditions on a Class I device
# (regulation 3.9) and are reported as qualifiers. There is no AIMD class in
# Compilation 72: Schedule 2 clause 5.7(1) makes an active implantable
# medical device Class III.
GENERAL_ORDER = ["Class I", "Class IIa", "Class IIb", "Class III"]
IVD_ORDER = ["Class 1 IVD", "Class 2 IVD", "Class 3 IVD", "Class 4 IVD"]


def highest_class(classes) -> dict[str, str]:
    """The governing class per family.

    General devices and IVDs are not comparable and do not collapse into one
    answer: a product with both kinds of function needs separate ARTG entries,
    so this returns one result per family rather than a single class.
    """
    # Materialised first: a generator argument would be exhausted by the
    # first family and every later family would silently come back empty.
    classes = list(classes)
    result: dict[str, str] = {}
    for family, order in (("general", GENERAL_ORDER), ("ivd", IVD_ORDER)):
        present = [c for c in classes if c in order]
        if present:
            result[family] = max(present, key=order.index)
    return result


class Turn(BaseModel):
    """One question put to the founder, and the reply.

    fields holds the dotted names the question covers, relative to the
    product ("core.supplied_sterile", "functions.0.general.duration"). One
    question can cover several fields, as a "which of these apply" checklist
    does. reply is kept word for word: it is the evidence for every field the
    turn answered.
    """

    question_id: str
    fields: list[str]
    asked: str
    reply: str
    unsure: bool = False


def relevant_core_fields(functions: list["FunctionProfile"]) -> list[str]:
    """Which product-level fields this product needs.

    The regulation 3.9 qualifiers are read only for a general device function
    (engine.qualify), and sterile supply never for software. A function whose
    kind or software status is still open counts as possibly needing both, so
    nothing is dropped on a guess.
    """
    names = ["product_name", "intended_purpose"]
    general = [f for f in functions if f.branch() is not DeviceKind.IVD]
    if not functions or any(_value(f.is_software) is not Tri.YES for f in general):
        names.append("supplied_sterile")
    if not functions or general:
        names.append("has_measuring_function")
    names.append("functions_confirmed")
    return names


class DeviceProfile(BaseModel):
    """A product, made of one or more functions.

    Named DeviceProfile for continuity, but the unit is the product as
    supplied. Single-function products are the common case and carry one
    entry in functions.
    """

    core: CoreProfile = CoreProfile()
    functions: list[FunctionProfile] = Field(default_factory=list)
    funding: FundingProfile | None = None

    source_text: str = ""
    transcript: list[Turn] = Field(default_factory=list)
    schema_version: Literal["0.12"] = "0.12"

    @property
    def single_function(self) -> bool:
        return len(self.functions) == 1

    def kinds(self) -> set[DeviceKind]:
        """Which rule families this product touches. More than one is legal."""
        return {f.branch() for f in self.functions if f.branch() is not None}

    def relevant(self) -> list[str]:
        """Dotted names of every field this product requires."""
        names = [f"core.{n}" for n in relevant_core_fields(self.functions)]
        for index, function in enumerate(self.functions):
            names += [f"functions.{index}.{n}" for n in function.relevant()]
        return names

    def missing(self) -> list[str]:
        """Relevant fields still unresolved, in the order they should be asked.

        Classification must not run while this is non-empty. A product with
        three functions produces three groups of questions, and a function
        cannot be classified until its own group is answered.
        """
        out = [
            f"core.{name}"
            for name in relevant_core_fields(self.functions)
            if not getattr(self.core, name).resolved
        ]
        for index, function in enumerate(self.functions):
            out += [f"functions.{index}.{n}" for n in function.missing()]
        return out

    def missing_for(self, index: int) -> list[str]:
        """Unresolved fields for one function, so it can be completed alone."""
        return self.functions[index].missing()

    def unsure(self) -> list[str]:
        """Missing fields the founder has already said they cannot answer.

        Only while the field is still unresolved: a later answer, from the
        founder or from an adviser, takes it off this list.
        """
        marked = {name for turn in self.transcript if turn.unsure for name in turn.fields}
        return [name for name in self.missing() if name in marked]

    def askable(self) -> list[str]:
        """Missing fields still worth asking: missing() less unsure()."""
        marked = set(self.unsure())
        return [name for name in self.missing() if name not in marked]

    def answer_at(self, dotted: str) -> "Answer | None":
        """The Answer at a dotted name, or None if the path does not reach one."""
        node = self
        for part in dotted.split("."):
            if part.isdigit():
                index = int(part)
                if not isinstance(node, list) or index >= len(node):
                    return None
                node = node[index]
            else:
                node = getattr(node, part, None)
            if node is None:
                return None
        return node if isinstance(node, Answer) else None

    def untraceable_evidence(self) -> list[str]:
        """Fields whose evidence is not a phrase from where it claims to come from.

        STATED and DEFAULTED evidence has to be a phrase of source_text.
        ANSWERED evidence has to be a phrase of the reply to a question that
        covered that field; a phrase that happens to appear in the original
        description, or in the reply to a different question, does not count.
        Anything listed here is a field where someone else's words went into
        the evidence slot, which is the shape a fabricated fact takes.

        Funding fields are checked too when the funding section exists, even
        though no stage asks them yet.
        """
        names = list(self.relevant())
        if self.funding is not None:
            names += [f"funding.{n}" for n in FundingProfile.model_fields]
        out = []
        for dotted in names:
            answer = self.answer_at(dotted)
            if answer is None or not answer.evidence:
                continue
            if answer.basis is Basis.ANSWERED:
                replies = [t.reply for t in self.transcript if dotted in t.fields]
                traced = any(answer.evidence in reply for reply in replies)
            else:
                traced = answer.evidence in self.source_text
            if not traced:
                out.append(dotted)
        return out

    def unresolved_in(self, section: BaseModel) -> list[str]:
        """Every unresolved field in one section, relevant or not. Diagnostic only."""
        return [
            name
            for name in type(section).model_fields
            if isinstance(getattr(section, name), Answer)
            and not getattr(section, name).resolved
        ]
