"""Tests for the regulatory status gate.

Three things are being tested and they are worth separating in your head:

1. Each clause produces the verdict it should, and cites itself.
2. Aggregation across functions is existential for device status and universal
   for exclusion and exemption.
3. Absence is never read as a negative. An unresolved field or an unloaded
   source produces UNDECIDED, never REGULATED and never NOT_A_DEVICE.
"""

import json

import pytest
from pydantic import ValidationError

from reguide.profile import (
    Answer,
    Basis,
    CoreProfile,
    DeviceKind,
    DeviceProfile,
    FunctionProfile,
    GeneralDeviceProfile,
    TherapeuticPurpose,
    Tri,
)
from reguide import status as S

SOURCE = (
    "A web app that flags abnormal chest x-rays for a radiologist and suggests a "
    "follow up interval. It also reminds people with mild seasonal allergies to "
    "take their own medication."
)


def answer(value, evidence, basis=Basis.STATED):
    return Answer(value=value, basis=basis, evidence=evidence)


@pytest.fixture(autouse=True)
def exclusion_table():
    """Every test starts with a known table, and none leaks into the next."""
    S.EXCLUSION_TABLE.clear()
    S.EXCLUSION_TABLE.update(
        {
            "14E": S.Exclusion(
                item="14E",
                citation="Schedule 1 item 14E",
                summary="digital mental health tool",
            )
        }
    )
    yield
    S.EXCLUSION_TABLE.clear()


def software_function(**overrides) -> FunctionProfile:
    """A software function that reaches the gate's third question."""
    function = FunctionProfile(
        name=answer("x-ray triage", "flags abnormal chest x-rays"),
        kind=answer(DeviceKind.GENERAL, "web app"),
        is_software=answer(Tri.YES, "A web app"),
        general=GeneralDeviceProfile(),
    )
    function.status.therapeutic_purpose = answer(
        TherapeuticPurpose.DISEASE, "flags abnormal chest x-rays"
    )
    function.status.principal_action_pharmacological = answer(Tri.NO, "web app")
    function.status.excluded_item = answer("none", "web app")
    function.status.cdss_sole_purpose_recommendation = answer(
        Tri.YES, "suggests a follow up interval"
    )
    function.status.cdss_processes_device_signal_or_image = answer(
        Tri.NO, "suggests a follow up interval"
    )
    function.status.cdss_replaces_clinical_judgement = answer(Tri.NO, "for a radiologist")
    for name, value in overrides.items():
        setattr(function.status, name, value)
    return function


def product(*functions) -> DeviceProfile:
    return DeviceProfile(core=CoreProfile(), functions=list(functions), source_text=SOURCE)


# --------------------------------------------------------------------------
# 1. Is it a device
# --------------------------------------------------------------------------


def test_no_purpose_and_not_an_accessory_is_not_a_device():
    function = FunctionProfile(is_software=answer(Tri.YES, "A web app"))
    function.status.therapeutic_purpose = answer(
        TherapeuticPurpose.NONE, "reminds people with mild seasonal allergies"
    )
    function.status.is_accessory_to_device = answer(Tri.NO, "web app")

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.NOT_A_DEVICE
    assert result.proceeds is False
    assert result.classifiable == []
    assert result.hits[0].citation.endswith("s41BD(1)")


def test_accessory_with_no_purpose_of_its_own_is_still_a_device():
    function = software_function()
    function.status.therapeutic_purpose = answer(TherapeuticPurpose.NONE, "web app")
    function.status.is_accessory_to_device = answer(Tri.YES, "for a radiologist")

    result = S.gate(product(function))

    assert result.outcome is not S.StatusOutcome.NOT_A_DEVICE
    assert any("41BD(3)" in hit.citation for hit in result.hits)


def test_pharmacological_principal_action_is_not_a_device():
    function = software_function()
    function.status.principal_action_pharmacological = answer(
        Tri.YES, "take their own medication"
    )

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.NOT_A_DEVICE
    assert result.hits[0].rule_id == "s41BD-principal-action"


def test_unknown_purpose_is_undecided_not_a_verdict():
    result = S.gate(product(FunctionProfile()))

    assert result.outcome is S.StatusOutcome.UNDECIDED
    assert "status.therapeutic_purpose" in result.unresolved


def test_unknown_accessory_answer_is_undecided():
    function = FunctionProfile()
    function.status.therapeutic_purpose = answer(TherapeuticPurpose.NONE, "web app")

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.UNDECIDED


# --------------------------------------------------------------------------
# 2. Is it excluded
# --------------------------------------------------------------------------


def test_unloaded_exclusion_table_blocks_rather_than_clearing():
    S.EXCLUSION_TABLE.clear()
    result = S.gate(product(software_function()))

    assert result.outcome is S.StatusOutcome.UNDECIDED
    assert S.EXCLUSION_SOURCE in result.missing_sources


def test_matching_excluded_item_with_conditions_met_is_excluded():
    function = software_function()
    function.status.excluded_item = answer("14E", "reminds people")
    function.status.exclusion_conditions_met = answer(Tri.YES, "mild seasonal allergies")

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.EXCLUDED
    assert any("item 14E" in hit.citation for hit in result.hits)


def test_excluded_item_with_conditions_unmet_falls_through_to_the_exemption():
    function = software_function()
    function.status.excluded_item = answer("14E", "reminds people")
    function.status.exclusion_conditions_met = answer(Tri.NO, "for a radiologist")

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.EXEMPT_CDSS  # falls through to question 3


def test_item_absent_from_the_table_is_unresolved_not_excluded():
    function = software_function()
    function.status.excluded_item = answer("99Z", "web app")
    function.status.exclusion_conditions_met = answer(Tri.YES, "web app")

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.UNDECIDED
    assert any("99Z" in name for name in result.unresolved)


# --------------------------------------------------------------------------
# 3. Is it exempt CDSS
# --------------------------------------------------------------------------


def test_all_three_criteria_met_is_exempt_with_a_notification_obligation():
    result = S.gate(product(software_function()))

    assert result.outcome is S.StatusOutcome.EXEMPT_CDSS
    assert result.proceeds is False
    assert any("30 working days" in text for text in result.obligations)
    assert any("Schedule 4 Part 2" in hit.citation for hit in result.hits)


@pytest.mark.parametrize(
    "field, value",
    [
        ("cdss_sole_purpose_recommendation", Tri.NO),
        ("cdss_processes_device_signal_or_image", Tri.YES),
        ("cdss_replaces_clinical_judgement", Tri.YES),
    ],
)
def test_failing_any_one_criterion_leaves_it_regulated(field, value):
    function = software_function()
    setattr(function.status, field, answer(value, "chest x-rays"))

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.REGULATED
    assert result.proceeds is True


@pytest.mark.parametrize(
    "field",
    [
        "cdss_sole_purpose_recommendation",
        "cdss_processes_device_signal_or_image",
        "cdss_replaces_clinical_judgement",
    ],
)
def test_an_unanswered_criterion_is_undecided_not_regulated(field):
    function = software_function()
    setattr(function.status, field, Answer())

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.UNDECIDED


def test_hardware_is_never_exempt_cdss():
    function = software_function()
    function.is_software = answer(Tri.NO, "chest x-rays")

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.REGULATED


# --------------------------------------------------------------------------
# Aggregation across functions
# --------------------------------------------------------------------------


def not_a_device_function() -> FunctionProfile:
    function = FunctionProfile(is_software=answer(Tri.YES, "A web app"))
    function.status.therapeutic_purpose = answer(
        TherapeuticPurpose.NONE, "reminds people with mild seasonal allergies"
    )
    function.status.is_accessory_to_device = answer(Tri.NO, "web app")
    return function


def regulated_function() -> FunctionProfile:
    function = software_function()
    function.status.cdss_processes_device_signal_or_image = answer(
        Tri.YES, "abnormal chest x-rays"
    )
    return function


def test_one_regulated_function_regulates_the_product():
    result = S.gate(product(not_a_device_function(), regulated_function()))

    assert result.outcome is S.StatusOutcome.REGULATED
    assert result.classifiable == [1]


def test_exclusion_requires_every_function():
    excluded = software_function()
    excluded.status.excluded_item = answer("14E", "reminds people")
    excluded.status.exclusion_conditions_met = answer(Tri.YES, "mild seasonal allergies")

    result = S.gate(product(excluded, regulated_function()))

    assert result.outcome is S.StatusOutcome.REGULATED


def test_excluded_and_not_a_device_together_is_excluded():
    excluded = software_function()
    excluded.status.excluded_item = answer("14E", "reminds people")
    excluded.status.exclusion_conditions_met = answer(Tri.YES, "mild seasonal allergies")

    result = S.gate(product(excluded, not_a_device_function()))

    assert result.outcome is S.StatusOutcome.EXCLUDED


def test_an_undecided_function_blocks_the_product():
    result = S.gate(product(not_a_device_function(), FunctionProfile()))

    assert result.outcome is S.StatusOutcome.UNDECIDED


def test_a_product_with_no_functions_is_undecided():
    result = S.gate(DeviceProfile(source_text=SOURCE))

    assert result.outcome is S.StatusOutcome.UNDECIDED
    assert result.proceeds is False


def test_per_function_verdicts_are_retained():
    result = S.gate(product(not_a_device_function(), regulated_function()))

    assert [f.outcome for f in result.functions] == [
        S.StatusOutcome.NOT_A_DEVICE,
        S.StatusOutcome.REGULATED,
    ]
    assert result.functions[1].index == 1


# --------------------------------------------------------------------------
# Schema behaviour the gate depends on
# --------------------------------------------------------------------------


def test_a_function_out_of_scope_is_asked_almost_nothing():
    """Relevance gating has to stop at the first question for a non-device."""
    function = not_a_device_function()
    asked = [name for name in function.relevant() if name.startswith("status.")]

    assert asked == ["status.therapeutic_purpose", "status.is_accessory_to_device"]


def test_a_software_device_is_asked_the_cdss_criteria():
    asked = [name for name in software_function().relevant() if name.startswith("status.")]

    assert "status.cdss_replaces_clinical_judgement" in asked
    assert "status.excluded_item" in asked


def test_hardware_is_not_asked_the_cdss_criteria():
    function = software_function()
    function.is_software = answer(Tri.NO, "chest x-rays")
    asked = [name for name in function.relevant() if name.startswith("status.")]

    assert not any("cdss" in name for name in asked)


def test_prune_keeps_status_answers_the_gating_asked_for():
    function = software_function()
    function.prune()

    assert function.status.therapeutic_purpose.value is TherapeuticPurpose.DISEASE
    assert function.status.cdss_replaces_clinical_judgement.value is Tri.NO


def test_prune_clears_a_status_answer_nobody_asked_for():
    function = not_a_device_function()
    function.status.cdss_replaces_clinical_judgement = answer(Tri.NO, "web app")
    function.prune()

    assert function.status.cdss_replaces_clinical_judgement.resolved is False


def test_branch_ignores_an_unresolved_kind():
    function = FunctionProfile(kind=Answer(value=DeviceKind.GENERAL, basis=Basis.UNKNOWN))

    assert function.branch() is None


def test_evidence_invariant_still_holds_on_status_fields():
    with pytest.raises(ValidationError):
        Answer(value=Tri.YES, basis=Basis.STATED)


def test_untraceable_evidence_catches_a_paraphrased_status_field():
    function = software_function()
    function.status.therapeutic_purpose = answer(
        TherapeuticPurpose.DISEASE, "detects lung disease from imaging"
    )
    profile = product(function)

    assert "functions.0.status.therapeutic_purpose" in profile.untraceable_evidence()


# --------------------------------------------------------------------------
# Loading the table
# --------------------------------------------------------------------------


def test_load_exclusions_reads_the_determination(tmp_path):
    path = tmp_path / "egd.json"
    path.write_text(
        json.dumps(
            [
                {"item": "14a", "citation": "Schedule 1 item 14A", "summary": "consumer health"},
                {"item": "14E", "citation": "Schedule 1 item 14E", "summary": "mental health"},
            ]
        )
    )

    assert S.load_exclusions(path) == 2
    assert "14A" in S.EXCLUSION_TABLE  # keys are normalised
