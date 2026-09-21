"""Tests for the regulatory status gate.

Three things are being tested and they are worth separating in your head:

1. Each clause produces the verdict it should, and cites itself.
2. Aggregation across functions is existential for device status and universal
   for exclusion and exemption.
3. Absence is never read as a negative. An unresolved field or an unloaded
   source produces UNDECIDED, never REGULATED and never NOT_A_DEVICE.
"""

import json
from pathlib import Path

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


REAL_TABLE = (Path(__file__).resolve().parent.parent
              / "data" / "legislation" / "excluded_goods_determination_2018.json")


@pytest.fixture(autouse=True)
def exclusion_table():
    """Every test starts with a known one-item table, and none leaks into the next."""
    S.EXCLUSION_TABLE.clear()
    S.EXCLUSION_TABLE.update(
        {
            "S1-14E": S.Exclusion(
                key="S1-14E",
                schedule=1,
                item="14E",
                citation="Schedule 1 item 14E",
                software=True,
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
    assert result.hits[0].citation.endswith("s41BD(1)(a) and (b)")


def test_accessory_with_no_purpose_of_its_own_is_still_a_device():
    function = software_function()
    function.status.therapeutic_purpose = answer(TherapeuticPurpose.NONE, "web app")
    function.status.is_accessory_to_device = answer(Tri.YES, "for a radiologist")

    result = S.gate(product(function))

    assert result.outcome is not S.StatusOutcome.NOT_A_DEVICE
    assert any(hit.citation.endswith("s41BD(1)(b)") for hit in result.hits)


def test_pharmacological_principal_action_is_not_a_device():
    function = software_function()
    function.status.principal_action_pharmacological = answer(
        Tri.YES, "take their own medication"
    )

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.NOT_A_DEVICE
    assert result.hits[0].rule_id == "s41BD-principal-action"


@pytest.mark.parametrize(
    "purpose, limb",
    [
        (TherapeuticPurpose.DISEASE, "(i)"),
        (TherapeuticPurpose.INJURY, "(ii)"),
        (TherapeuticPurpose.ANATOMY, "(iii)"),
        (TherapeuticPurpose.CONCEPTION, "(iv)"),
        (TherapeuticPurpose.IN_VITRO_SPECIMEN, "(v)"),
    ],
)
def test_the_device_finding_cites_its_limb(purpose, limb):
    function = software_function()
    function.status.therapeutic_purpose = answer(purpose, "flags abnormal chest x-rays")

    result = S.gate(product(function))

    assert result.hits[0].citation.endswith(f"s41BD(1)(a){limb}")


def test_the_principal_action_proviso_is_cited_from_paragraph_a():
    function = software_function()
    function.status.principal_action_pharmacological = answer(
        Tri.YES, "take their own medication"
    )

    assert S.gate(product(function)).hits[0].citation.endswith(
        "s41BD(1)(a), closing words"
    )


def test_an_accessory_is_cited_from_paragraph_b():
    function = software_function()
    function.status.therapeutic_purpose = answer(TherapeuticPurpose.NONE, "web app")
    function.status.is_accessory_to_device = answer(Tri.YES, "for a radiologist")

    assert S.gate(product(function)).hits[0].citation.endswith("s41BD(1)(b)")


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
    function.status.excluded_item = answer("S1-14E", "reminds people")
    function.status.exclusion_conditions_met = answer(Tri.YES, "mild seasonal allergies")

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.EXCLUDED
    assert any("item 14E" in hit.citation for hit in result.hits)
    assert result.hits[-1].rule_id == "egd-S1-14E"


def test_excluded_item_with_conditions_unmet_falls_through_to_the_exemption():
    function = software_function()
    function.status.excluded_item = answer("S1-14E", "reminds people")
    function.status.exclusion_conditions_met = answer(Tri.NO, "for a radiologist")

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.EXEMPT_CDSS  # falls through to question 3


def test_item_absent_from_the_table_is_unresolved_not_excluded():
    function = software_function()
    function.status.excluded_item = answer("S1-99Z", "web app")
    function.status.exclusion_conditions_met = answer(Tri.YES, "web app")

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.UNDECIDED
    assert any("S1-99Z" in name for name in result.unresolved)


def test_an_unqualified_item_number_is_not_guessed():
    """Item 5 exists in both Schedules. The gate never picks one."""
    function = software_function()
    function.status.excluded_item = answer("14E", "reminds people")
    function.status.exclusion_conditions_met = answer(Tri.YES, "mild seasonal allergies")

    result = S.gate(product(function))

    assert result.outcome is S.StatusOutcome.UNDECIDED


def test_item_keys_are_normalised():
    function = software_function()
    function.status.excluded_item = answer(" s1-14e ", "reminds people")
    function.status.exclusion_conditions_met = answer(Tri.YES, "mild seasonal allergies")

    assert S.gate(product(function)).outcome is S.StatusOutcome.EXCLUDED


# --------------------------------------------------------------------------
# 3. Is it exempt CDSS
# --------------------------------------------------------------------------


def test_all_three_criteria_met_is_exempt_with_a_notification_obligation():
    result = S.gate(product(software_function()))

    assert result.outcome is S.StatusOutcome.EXEMPT_CDSS
    assert result.proceeds is False
    assert any("20 working days" in text for text in result.obligations)
    assert result.hits[-1].citation.endswith("Schedule 4 Part 2 item 2.15")


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
    excluded.status.excluded_item = answer("S1-14E", "reminds people")
    excluded.status.exclusion_conditions_met = answer(Tri.YES, "mild seasonal allergies")

    result = S.gate(product(excluded, regulated_function()))

    assert result.outcome is S.StatusOutcome.REGULATED


def test_excluded_and_not_a_device_together_is_excluded():
    excluded = software_function()
    excluded.status.excluded_item = answer("S1-14E", "reminds people")
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


def test_an_excluded_function_is_not_asked_the_cdss_criteria():
    function = software_function()
    function.status.excluded_item = answer("S1-14E", "reminds people")
    function.status.exclusion_conditions_met = answer(Tri.YES, "mild seasonal allergies")
    asked = [name for name in function.relevant() if name.startswith("status.")]

    assert "status.exclusion_conditions_met" in asked
    assert not any("cdss" in name for name in asked)


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


# --------------------------------------------------------------------------
# Flags: things the report must raise beside the verdict
# --------------------------------------------------------------------------


def excluded_function() -> FunctionProfile:
    function = software_function()
    function.name = answer("Appointment booking", "web app")
    function.status.excluded_item = answer("S1-14E", "reminds people")
    function.status.exclusion_conditions_met = answer(Tri.YES, "mild seasonal allergies")
    return function


def test_exempt_plus_excluded_is_exempt_with_an_amber_flag():
    result = S.gate(product(software_function(), excluded_function()))

    assert result.outcome is S.StatusOutcome.EXEMPT_CDSS
    assert result.obligations  # the exemption's duties still apply
    [flag] = [f for f in result.flags if f.code == "mixed_exempt_and_excluded"]
    assert flag.severity is S.Severity.AMBER
    assert flag.functions == (0, 1)
    assert "Appointment booking" in flag.message


def test_excluded_plus_not_a_device_raises_no_mixed_flag():
    result = S.gate(product(excluded_function(), not_a_device_function()))

    assert result.outcome is S.StatusOutcome.EXCLUDED
    assert not any(f.code == "mixed_exempt_and_excluded" for f in result.flags)


def test_a_plain_exempt_product_raises_no_flag():
    assert S.gate(product(software_function())).flags == []


def test_an_exclusion_with_a_caution_raises_it_as_a_flag():
    S.EXCLUSION_TABLE["S1-14E"] = S.Exclusion(
        key="S1-14E", schedule=1, item="14E", citation="Schedule 1 item 14E",
        software=True, summary="digital mental health tool",
        caution="check the guidelines are displayed",
    )
    result = S.gate(product(excluded_function()))

    [flag] = result.flags
    assert flag.code == "exclusion_caution_S1-14E"
    assert flag.severity is S.Severity.AMBER
    assert flag.message == "Appointment booking: check the guidelines are displayed"


def test_the_caution_is_raised_even_inside_a_regulated_product():
    """The imaging platform is regulated, but its archive still needs the warning."""
    S.load_exclusions(REAL_TABLE)
    data = json.loads((Path(__file__).parent / "fixtures" / "imaging_platform.json").read_text())

    result = S.gate(DeviceProfile.model_validate(data["profile"]))

    assert result.outcome is S.StatusOutcome.REGULATED
    [flag] = result.flags
    assert flag.code == "exclusion_caution_S1-14H"
    assert "displays images" in flag.message


# --------------------------------------------------------------------------
# Scored against the fixtures
# --------------------------------------------------------------------------

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.json"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_gate_agrees_with_the_fixture(path):
    """Every fixture records the verdict by hand. The gate has to reach it.

    Runs against the real exclusion table, not the placeholder.
    """
    S.load_exclusions(REAL_TABLE)
    data = json.loads(path.read_text())
    profile = DeviceProfile.model_validate(data["profile"])

    result = S.gate(profile)

    assert [f.outcome.value for f in result.functions] == [
        f["expected_status"] for f in data["functions"]
    ]
    assert result.outcome.value == data["expected_status"]
    assert result.missing_sources == []


def entry(schedule, item):
    return {
        "key": f"s{schedule}-{item}",
        "schedule": schedule,
        "item": item,
        "citation": f"Schedule {schedule} item {item}",
        "software": False,
        "summary": "test entry",
    }


def test_load_exclusions_reads_the_table_format(tmp_path):
    path = tmp_path / "egd.json"
    path.write_text(json.dumps({"items": [entry(1, "14a"), entry(2, "5")]}))

    assert S.load_exclusions(path) == 2
    assert "S1-14A" in S.EXCLUSION_TABLE  # keys are normalised


def test_the_same_item_number_in_both_schedules_stays_distinct(tmp_path):
    path = tmp_path / "egd.json"
    path.write_text(json.dumps({"items": [entry(1, "5"), entry(2, "5")]}))

    assert S.load_exclusions(path) == 2
    assert S.EXCLUSION_TABLE["S1-5"].schedule == 1
    assert S.EXCLUSION_TABLE["S2-5"].schedule == 2


class TestTheRealTable:
    """The committed table, built by scripts/build_exclusions.py."""

    def test_it_holds_every_item_of_both_schedules(self):
        assert S.load_exclusions(REAL_TABLE) == 59
        schedules = [e.schedule for e in S.EXCLUSION_TABLE.values()]
        assert schedules.count(1) == 43 and schedules.count(2) == 16

    def test_the_software_items_are_14a_to_14o(self):
        S.load_exclusions(REAL_TABLE)
        software = sorted(e.item for e in S.EXCLUSION_TABLE.values() if e.software)
        assert software == [f"14{letter}" for letter in "ABCDEFGHIJKLMNO"]

    def test_it_records_which_compilation_it_came_from(self):
        payload = json.loads(REAL_TABLE.read_text())
        assert payload["register_id"] == "F2018L01350"
        assert payload["compilation"] == 11

    def test_14h_warns_that_display_is_not_covered(self):
        S.load_exclusions(REAL_TABLE)
        caution = S.EXCLUSION_TABLE["S1-14H"].caution
        assert "displays images for diagnosis or screening" in caution
        assert "TGA guidance" in caution

    def test_every_citation_names_its_schedule(self):
        S.load_exclusions(REAL_TABLE)
        for exclusion in S.EXCLUSION_TABLE.values():
            assert f"Schedule {exclusion.schedule} item {exclusion.item}" in exclusion.citation
