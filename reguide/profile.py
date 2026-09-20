"""Device profile schema.

The structured object produced by intake and consumed by the rule engines.
Every field records where its value came from, so the report can cite the
founder's own words and the clarification loop knows what is still missing.

Version 0.2 adds the fields the rules turn on that physical description alone
does not supply, chiefly intended function, and adds relevance gating so the
clarification loop asks only what the device's own branch requires.
"""

from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

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


class BodyContact(str, Enum):
    NONE = "none"
    INTACT_SKIN = "intact_skin"
    BREACHED_SKIN = "breached_skin_or_wound"
    MUCOUS_MEMBRANE = "mucous_membrane"
    CENTRAL_CIRCULATION = "central_circulatory_system"
    CENTRAL_NERVOUS = "central_nervous_system"
    TEETH = "teeth"


class WoundFunction(str, Enum):
    """Sub-rule 2.4 turns on this, not on the wound itself.

    The same film dressing is one class as a barrier and another as a
    microenvironment manager. Physical description cannot settle it, so this
    has to be asked, and the answer has to be the manufacturer's own claim.
    """

    MECHANICAL_BARRIER = "mechanical_barrier_compression_or_absorption"
    MICROENVIRONMENT = "manage_microenvironment_of_wound"
    SECONDARY_INTENT = "breached_dermis_healing_by_secondary_intent"
    OTHER = "other"


class OrificeSite(str, Enum):
    """Sub-rule 3.1 treats the shallow orifices differently from the rest."""

    ORAL_TO_PHARYNX = "oral_cavity_as_far_as_pharynx"
    EAR_TO_EARDRUM = "ear_canal_up_to_eardrum"
    NASAL_CAVITY = "nasal_cavity"
    OTHER_ORIFICE = "other_body_orifice"
    STOMA = "stoma"


class FluidHandling(str, Enum):
    """Sub-rules 2.2 and 2.3, non-invasive devices handling body substances."""

    NONE = "none"
    CHANNEL_OR_STORE = "channel_or_store_for_administration"
    MODIFY_COMPOSITION = "modify_biological_or_chemical_composition"
    FILTER_OR_EXCHANGE = "filtration_centrifugation_or_gas_or_heat_exchange"


class ActiveType(str, Enum):
    NOT_ACTIVE = "not_active"
    THERAPEUTIC = "active_therapeutic"
    DIAGNOSTIC = "active_diagnostic"


class ClinicalFunction(str, Enum):
    """Which rule in the 4.x family applies. Software lives or dies here."""

    NONE = "none"
    DIAGNOSE_OR_SCREEN = "diagnose_or_screen_for_a_condition"
    MONITOR = "monitor_a_condition_or_parameter"
    SPECIFY_THERAPY = "specify_treatment_or_intervention"
    SUPPLY_ENERGY = "supply_or_exchange_energy"
    ADMINISTER_SUBSTANCE = "administer_or_remove_medicines_or_fluids"
    CONTROL_ANOTHER_DEVICE = "control_or_monitor_another_active_device"


class DecisionMaker(str, Enum):
    """Who acts on the output. The single biggest lever on software class."""

    DEVICE_TO_LAY_USER = "device_gives_the_decision_to_a_lay_user"
    DEVICE_TO_PROFESSIONAL = "device_gives_the_decision_to_a_health_professional"
    INFORMS_PROFESSIONAL = "informs_a_health_professional_who_decides"


class Severity(str, Enum):
    """The severity ladder the 4.5 to 4.7 rules step through."""

    DEATH_WITHOUT_URGENT_TREATMENT = "death_or_severe_deterioration_without_urgent_treatment"
    SERIOUS = "serious_disease_or_condition"
    MODERATE = "moderate"
    OTHER = "any_other_case"


class PublicHealthRisk(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


class IvdPurpose(str, Enum):
    BLOOD_OR_TISSUE_SCREENING = "blood_or_tissue_donor_screening"
    TRANSMISSIBLE_AGENT = "transmissible_agent_detection"
    BLOOD_GROUP_OR_TISSUE_TYPE = "blood_grouping_or_tissue_typing"
    DISEASE_DIAGNOSIS = "disease_diagnosis"
    MONITORING = "therapy_or_disease_monitoring"
    SCREENING_ASYMPTOMATIC = "population_screening"
    GENETIC_TESTING = "genetic_testing"
    OTHER = "other"


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
    """Asked for every device, whatever branch it takes."""

    device_name: Answer[str] = Answer()
    intended_purpose: Answer[str] = Answer()
    kind: Answer[DeviceKind] = Answer()
    is_software_only: Answer[Tri] = Answer()
    supplied_sterile: Answer[Tri] = Answer()          # drives Class Is
    has_measuring_function: Answer[Tri] = Answer()    # drives Class Im


class GeneralDeviceProfile(BaseModel):
    """Inputs to the Schedule 2 rules.

    Wider than any one device needs. Relevance gating decides which are
    actually asked, so a software product is never questioned about animal
    tissue and a bandage is never questioned about ionising radiation.
    """

    # Route and contact
    invasiveness: Answer[Invasiveness] = Answer()
    duration: Answer[Duration] = Answer()
    body_contact: Answer[BodyContact] = Answer()
    orifice_site: Answer[OrificeSite] = Answer()

    # Injured skin, sub-rule 2.4
    contacts_injured_skin: Answer[Tri] = Answer()
    wound_function: Answer[WoundFunction] = Answer()
    breaches_dermis: Answer[Tri] = Answer()

    # Body substances, sub-rules 2.2 and 2.3
    fluid_handling: Answer[FluidHandling] = Answer()
    connected_to_active_device: Answer[Tri] = Answer()

    # Surgically invasive specifics
    reusable_surgical_instrument: Answer[Tri] = Answer()
    absorbed_or_chemically_changed: Answer[Tri] = Answer()
    delivers_ionising_radiation: Answer[Tri] = Answer()

    # Active devices and software, rules 4.1 to 4.7
    active_type: Answer[ActiveType] = Answer()
    is_active_implantable: Answer[Tri] = Answer()
    clinical_function: Answer[ClinicalFunction] = Answer()
    delivers_hazardous_energy: Answer[Tri] = Answer()
    administers_or_removes_medicine: Answer[Tri] = Answer()
    decision_maker: Answer[DecisionMaker] = Answer()
    condition_severity: Answer[Severity] = Answer()
    public_health_risk: Answer[PublicHealthRisk] = Answer()
    records_diagnostic_images: Answer[Tri] = Answer()

    # Special rules, 5.x. Any of these can override everything above.
    incorporates_medicine: Answer[Tri] = Answer()
    animal_or_microbial_origin: Answer[Tri] = Answer()
    human_blood_derivative: Answer[Tri] = Answer()
    contraceptive_or_sti_prevention: Answer[Tri] = Answer()
    disinfects_another_device: Answer[Tri] = Answer()


class IvdProfile(BaseModel):
    """Inputs to the Schedule 2A rules."""

    purpose: Answer[IvdPurpose] = Answer()
    is_self_test: Answer[Tri] = Answer()
    is_near_patient_test: Answer[Tri] = Answer()
    detects_transmissible_agent: Answer[Tri] = Answer()
    transmission_risk_to_population: Answer[Tri] = Answer()
    disease_is_life_threatening: Answer[Tri] = Answer()
    result_drives_critical_decision: Answer[Tri] = Answer()

    # Named exceptions. These cannot be reasoned to, only looked up.
    is_instrument_or_receptacle: Answer[Tri] = Answer()      # rule 1.6
    is_quality_control_material: Answer[Tri] = Answer()      # rule 1.5
    is_export_only: Answer[Tri] = Answer()                   # rule 1.8

    sample_type: Answer[str] = Answer()


class FundingProfile(BaseModel):
    """Inputs to reimbursement triage. Not used by classification."""

    care_setting: Answer[CareSetting] = Answer()
    operator: Answer[Operator] = Answer()
    is_first_in_class: Answer[Tri] = Answer()
    replaces_existing_service: Answer[str] = Answer()
    privately_insured_patients: Answer[Tri] = Answer()


# --------------------------------------------------------------------------
# Relevance gating
# --------------------------------------------------------------------------

ALWAYS_GENERAL = [
    "invasiveness",
    "active_type",
    "incorporates_medicine",
    "contraceptive_or_sti_prevention",
    "disinfects_another_device",
]

MATERIAL_FIELDS = ["animal_or_microbial_origin", "human_blood_derivative"]


def _value(answer: Answer):
    return answer.value if answer.resolved else None


def _dedupe(names: list[str]) -> list[str]:
    seen: set[str] = set()
    return [n for n in names if not (n in seen or seen.add(n))]


def relevant_general_fields(core: CoreProfile, general: GeneralDeviceProfile) -> list[str]:
    """Which Schedule 2 fields this device actually needs.

    Grows as facts are established. Before invasiveness is known the list is
    short; once it is known the branch opens. This is what stops intake turning
    into a twenty-six question interrogation.
    """
    fields = list(ALWAYS_GENERAL)
    software = _value(core.is_software_only) is Tri.YES
    route = _value(general.invasiveness)
    active = _value(general.active_type)

    if not software:
        fields += MATERIAL_FIELDS

    if route is Invasiveness.NON_INVASIVE:
        fields += ["contacts_injured_skin", "fluid_handling"]
        if _value(general.contacts_injured_skin) is Tri.YES:
            fields += ["wound_function"]
            if _value(general.wound_function) is WoundFunction.SECONDARY_INTENT:
                fields += ["breaches_dermis"]
        if _value(general.fluid_handling) in (
            FluidHandling.CHANNEL_OR_STORE,
            FluidHandling.MODIFY_COMPOSITION,
        ):
            fields += ["connected_to_active_device"]

    elif route is Invasiveness.BODY_ORIFICE:
        fields += ["duration", "orifice_site", "connected_to_active_device"]

    elif route in (Invasiveness.SURGICALLY_INVASIVE, Invasiveness.IMPLANTABLE):
        fields += ["duration", "body_contact", "absorbed_or_chemically_changed"]
        if _value(general.duration) is Duration.TRANSIENT:
            fields += ["reusable_surgical_instrument"]
        if route is Invasiveness.IMPLANTABLE:
            fields += ["is_active_implantable"]

    if active in (ActiveType.THERAPEUTIC, ActiveType.DIAGNOSTIC):
        fields += ["clinical_function", "delivers_hazardous_energy"]
        if active is ActiveType.DIAGNOSTIC:
            fields += ["delivers_ionising_radiation", "records_diagnostic_images"]
        function = _value(general.clinical_function)
        if function in (
            ClinicalFunction.DIAGNOSE_OR_SCREEN,
            ClinicalFunction.MONITOR,
            ClinicalFunction.SPECIFY_THERAPY,
        ):
            fields += ["decision_maker", "condition_severity", "public_health_risk"]
        if function is ClinicalFunction.ADMINISTER_SUBSTANCE:
            fields += ["administers_or_removes_medicine"]

    return _dedupe(fields)


def relevant_ivd_fields(ivd: IvdProfile) -> list[str]:
    """Which Schedule 2A fields this IVD needs.

    The named exceptions are checked first. An IVD that is a specimen
    receptacle or a quality control material is classified by that fact alone,
    so nothing else is worth asking.
    """
    exceptions = [
        "is_instrument_or_receptacle",
        "is_quality_control_material",
        "is_export_only",
    ]
    for name in exceptions:
        if _value(getattr(ivd, name)) is Tri.YES:
            return exceptions

    fields = exceptions + [
        "purpose",
        "is_self_test",
        "detects_transmissible_agent",
        "sample_type",
    ]
    if _value(ivd.detects_transmissible_agent) is Tri.YES:
        fields += ["transmission_risk_to_population", "disease_is_life_threatening"]
    if _value(ivd.is_self_test) is Tri.NO:
        fields += ["is_near_patient_test"]
    fields += ["result_drives_critical_decision"]

    return _dedupe(fields)


# --------------------------------------------------------------------------


class DeviceProfile(BaseModel):
    core: CoreProfile = CoreProfile()
    general: GeneralDeviceProfile | None = None
    ivd: IvdProfile | None = None
    funding: FundingProfile | None = None

    source_text: str = ""
    schema_version: Literal["0.2"] = "0.2"

    def branch(self) -> DeviceKind | None:
        return self.core.kind.value

    def relevant(self) -> list[str]:
        """Dotted names of every field this device's branch requires."""
        names = [f"core.{n}" for n in CoreProfile.model_fields]
        if self.branch() is DeviceKind.IVD and self.ivd is not None:
            names += [f"ivd.{n}" for n in relevant_ivd_fields(self.ivd)]
        elif self.branch() is DeviceKind.GENERAL and self.general is not None:
            names += [f"general.{n}" for n in relevant_general_fields(self.core, self.general)]
        return names

    def missing(self) -> list[str]:
        """Relevant fields still unresolved, in the order they should be asked.

        next_question() takes missing()[0]. The list shortens as answers arrive
        and can also lengthen, because establishing one fact opens a branch.
        Classification must not run while this is non-empty.
        """
        out = []
        for dotted in self.relevant():
            section_name, field_name = dotted.split(".", 1)
            section = getattr(self, section_name)
            if section is None:
                continue
            answer = getattr(section, field_name)
            if isinstance(answer, Answer) and not answer.resolved:
                out.append(dotted)
        return out

    def unresolved_in(self, section: BaseModel) -> list[str]:
        """Every unresolved field in one section, relevant or not.

        Diagnostic only. Use missing() for the clarification loop.
        """
        return [
            name
            for name in type(section).model_fields
            if isinstance(getattr(section, name), Answer)
            and not getattr(section, name).resolved
        ]
