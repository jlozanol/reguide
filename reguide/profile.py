"""Device profile schema.

The structured object produced by intake and consumed by the rule engines.
Every field records where its value came from, so the report can cite the
founder's own words and the clarification loop knows what is still missing.
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


class ActiveType(str, Enum):
    NOT_ACTIVE = "not_active"
    THERAPEUTIC = "active_therapeutic"
    DIAGNOSTIC = "active_diagnostic"


class IvdPurpose(str, Enum):
    BLOOD_OR_TISSUE_SCREENING = "blood_or_tissue_screening"
    TRANSMISSIBLE_AGENT = "transmissible_agent_detection"
    DISEASE_DIAGNOSIS = "disease_diagnosis"
    MONITORING = "therapy_monitoring"
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
    intended_purpose: Answer[str] = Answer(
        # The legally operative statement. Extract it verbatim, never summarise.
    )
    kind: Answer[DeviceKind] = Answer()
    is_software_only: Answer[Tri] = Answer()
    supplied_sterile: Answer[Tri] = Answer()
    has_measuring_function: Answer[Tri] = Answer()


class GeneralDeviceProfile(BaseModel):
    """Inputs to the Schedule 2 rules."""

    invasiveness: Answer[Invasiveness] = Answer()
    duration: Answer[Duration] = Answer()
    body_contact: Answer[BodyContact] = Answer()
    active_type: Answer[ActiveType] = Answer()
    delivers_hazardous_energy: Answer[Tri] = Answer()
    administers_or_removes_medicine: Answer[Tri] = Answer()
    incorporates_medicine: Answer[Tri] = Answer()
    animal_or_microbial_origin: Answer[Tri] = Answer()
    human_blood_derivative: Answer[Tri] = Answer()
    reusable_surgical_instrument: Answer[Tri] = Answer()
    contraceptive_or_sti_prevention: Answer[Tri] = Answer()
    disinfects_another_device: Answer[Tri] = Answer()


class IvdProfile(BaseModel):
    """Inputs to the Schedule 2A rules."""

    purpose: Answer[IvdPurpose] = Answer()
    is_self_test: Answer[Tri] = Answer()
    detects_transmissible_agent: Answer[Tri] = Answer()
    transmission_risk_to_population: Answer[Tri] = Answer()
    result_drives_critical_decision: Answer[Tri] = Answer()
    sample_type: Answer[str] = Answer()


class FundingProfile(BaseModel):
    """Inputs to reimbursement triage. Not used by classification."""

    care_setting: Answer[CareSetting] = Answer()
    operator: Answer[Operator] = Answer()
    is_first_in_class: Answer[Tri] = Answer()
    replaces_existing_service: Answer[str] = Answer()
    privately_insured_patients: Answer[Tri] = Answer()


class DeviceProfile(BaseModel):
    core: CoreProfile = CoreProfile()
    general: GeneralDeviceProfile | None = None
    ivd: IvdProfile | None = None
    funding: FundingProfile | None = None

    source_text: str = ""
    schema_version: Literal["0.1"] = "0.1"

    def branch(self) -> DeviceKind | None:
        return self.core.kind.value

    def missing(self, section: BaseModel) -> list[str]:
        """Field names still unresolved, in declaration order.

        Drives the clarifying question loop: ask about missing()[0], re-extract,
        repeat. Classification must not run while the relevant branch has gaps.
        """
        out = []
        for name, _ in type(section).model_fields.items():
            answer = getattr(section, name)
            if isinstance(answer, Answer) and not answer.resolved:
                out.append(name)
        return out
