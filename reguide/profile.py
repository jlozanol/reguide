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
    """Product-level facts. True of the thing as supplied, not of one function."""

    product_name: Answer[str] = Answer()
    intended_purpose: Answer[str] = Answer()
    supplied_sterile: Answer[Tri] = Answer()          # drives Class Is
    has_measuring_function: Answer[Tri] = Answer()    # drives Class Im
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
    """Inputs to reimbursement triage. Product level, not per function."""

    care_setting: Answer[CareSetting] = Answer()
    operator: Answer[Operator] = Answer()
    is_first_in_class: Answer[Tri] = Answer()
    replaces_existing_service: Answer[str] = Answer()
    privately_insured_patients: Answer[Tri] = Answer()


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

    general: GeneralDeviceProfile | None = None
    ivd: IvdProfile | None = None

    def branch(self) -> DeviceKind | None:
        return self.kind.value

    def relevant(self) -> list[str]:
        """Field names this function requires, unprefixed."""
        names = ["name", "description", "kind", "is_software"]
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
        for section in (self.general, self.ivd):
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
        function_kind = _value(general.clinical_function)
        if function_kind in (
            ClinicalFunction.DIAGNOSE_OR_SCREEN,
            ClinicalFunction.MONITOR,
            ClinicalFunction.SPECIFY_THERAPY,
        ):
            fields += ["decision_maker", "condition_severity", "public_health_risk"]
        if function_kind is ClinicalFunction.ADMINISTER_SUBSTANCE:
            fields += ["administers_or_removes_medicine"]

    return _dedupe(fields)


def relevant_ivd_fields(ivd: IvdProfile) -> list[str]:
    """Which Schedule 2A fields this IVD function needs.

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
# Classification vocabulary and aggregation
# --------------------------------------------------------------------------

# Ordered by the conformity assessment burden each carries, which is what
# "highest" means when several functions classify differently. Is and Im are
# placed above I because they add a conformity assessment step, not because
# they carry more clinical risk.
GENERAL_ORDER = [
    "Class I", "Class Is", "Class Im", "Class IIa", "Class IIb", "Class III", "Class AIMD",
]
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
    schema_version: Literal["0.3"] = "0.3"

    @property
    def single_function(self) -> bool:
        return len(self.functions) == 1

    def kinds(self) -> set[DeviceKind]:
        """Which rule families this product touches. More than one is legal."""
        return {f.branch() for f in self.functions if f.branch() is not None}

    def relevant(self) -> list[str]:
        """Dotted names of every field this product requires."""
        names = [f"core.{n}" for n in CoreProfile.model_fields]
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
            for name in CoreProfile.model_fields
            if not getattr(self.core, name).resolved
        ]
        for index, function in enumerate(self.functions):
            out += [f"functions.{index}.{n}" for n in function.missing()]
        return out

    def missing_for(self, index: int) -> list[str]:
        """Unresolved fields for one function, so it can be completed alone."""
        return self.functions[index].missing()

    def untraceable_evidence(self) -> list[str]:
        """Fields whose evidence is not a phrase from source_text.

        Extraction is meant to quote, not paraphrase. Anything listed here is
        a field where the model wrote its own words into the evidence slot,
        which is the shape a fabricated fact takes.
        """
        out = []
        for dotted in self.relevant():
            answer = self
            for part in dotted.split("."):
                answer = answer[int(part)] if part.isdigit() else getattr(answer, part, None)
                if answer is None:
                    break
            if isinstance(answer, Answer) and answer.evidence:
                if answer.evidence not in self.source_text:
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
