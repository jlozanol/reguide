"""Fixture integrity.

These do not check classification. They check that every fixture is a complete,
valid product profile, so that when a rule fails you know the fault is in the
rule and not in the fixture.

The gate itself is scored against these fixtures in test_status.py.
"""

import json
from pathlib import Path

import pytest

from reguide.profile import (
    DeviceKind,
    DeviceProfile,
    GeneralDeviceProfile,
    IvdProfile,
    StatusProfile,
    highest_class,
    relevant_general_fields,
    relevant_ivd_fields,
    relevant_status_fields,
)
from reguide.status import StatusOutcome

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURES = sorted(FIXTURE_DIR.glob("*.json"))

KNOWN_CLASSES = {
    "Class I", "Class Is", "Class Im", "Class IIa", "Class IIb", "Class III",
    "Class AIMD", "Class 1 IVD", "Class 2 IVD", "Class 3 IVD", "Class 4 IVD",
}

KNOWN_STATUSES = {outcome.value for outcome in StatusOutcome} - {"undecided"}
REGULATED = StatusOutcome.REGULATED.value


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def verified() -> list[Path]:
    return [p for p in FIXTURES if load(p)["verified"]]


def multi_function() -> list[Path]:
    return [p for p in FIXTURES if len(load(p)["functions"]) > 1]


def test_fixtures_exist():
    assert FIXTURES, "run: python scripts/build_fixtures.py"


def test_most_fixtures_are_verified():
    assert len(verified()) > len(FIXTURES) * 0.7


def test_multi_function_products_are_represented():
    """The schema exists for these. An empty set means untested machinery."""
    assert len(multi_function()) >= 3


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
class TestFixture:
    def test_has_required_keys(self, path):
        data = load(path)
        for key in ("expected_status", "expected_classes", "functions", "source",
                    "verified", "profile"):
            assert key in data, f"{path.name} is missing {key}"

    def test_profile_validates(self, path):
        DeviceProfile.model_validate(load(path)["profile"])

    def test_has_at_least_one_function(self, path):
        profile = DeviceProfile.model_validate(load(path)["profile"])
        assert profile.functions, "a product with no functions cannot be classified"

    def test_expectations_line_up_with_functions(self, path):
        data = load(path)
        profile = DeviceProfile.model_validate(data["profile"])
        assert len(data["functions"]) == len(profile.functions)
        for expected, function in zip(data["functions"], profile.functions):
            assert expected["name"] == function.name.value

    def test_every_expected_class_is_known(self, path):
        for function in load(path)["functions"]:
            if function["expected_status"] == REGULATED:
                assert function["expected_class"] in KNOWN_CLASSES

    def test_every_expected_status_is_known(self, path):
        """Undecided is never an expectation. A fixture is a settled answer."""
        data = load(path)
        assert data["expected_status"] in KNOWN_STATUSES
        for function in data["functions"]:
            assert function["expected_status"] in KNOWN_STATUSES

    def test_only_regulated_functions_carry_a_class(self, path):
        """A function the gate stops never reaches classification."""
        for function in load(path)["functions"]:
            has_class = function["expected_class"] is not None
            assert has_class == (function["expected_status"] == REGULATED)

    def test_a_regulated_product_has_a_regulated_function(self, path):
        data = load(path)
        statuses = [f["expected_status"] for f in data["functions"]]
        assert (data["expected_status"] == REGULATED) == (REGULATED in statuses)

    def test_product_class_is_the_highest_per_family(self, path):
        """Derived, never asserted separately, so it cannot drift."""
        data = load(path)
        expected = highest_class(f["expected_class"] for f in data["functions"])
        assert data["expected_classes"] == expected

    def test_every_function_declares_its_branch(self, path):
        profile = DeviceProfile.model_validate(load(path)["profile"])
        for function in profile.functions:
            kind = function.branch()
            assert kind is not None
            if kind is DeviceKind.IVD:
                assert function.ivd is not None and function.general is None
            else:
                assert function.general is not None and function.ivd is None

    def test_function_class_matches_function_branch(self, path):
        data = load(path)
        profile = DeviceProfile.model_validate(data["profile"])
        for expected, function in zip(data["functions"], profile.functions):
            if expected["expected_class"] is None:
                continue
            is_ivd_class = "IVD" in expected["expected_class"]
            assert is_ivd_class == (function.branch() is DeviceKind.IVD)

    def test_nothing_relevant_is_unresolved(self, path):
        profile = DeviceProfile.model_validate(load(path)["profile"])
        assert profile.missing() == []

    def test_no_function_answers_a_question_nobody_asked(self, path):
        """An over-filled fixture would pass even if gating were broken."""
        profile = DeviceProfile.model_validate(load(path)["profile"])
        for index, function in enumerate(profile.functions):
            if function.branch() is DeviceKind.IVD:
                asked, section = set(relevant_ivd_fields(function.ivd)), function.ivd
            else:
                asked, section = set(relevant_general_fields(function)), function.general
            extra = [n for n in type(section).model_fields
                     if getattr(section, n).resolved and n not in asked]
            assert not extra, f"function {index} answers unasked fields: {extra}"

    def test_all_evidence_is_quoted_from_the_source(self, path):
        profile = DeviceProfile.model_validate(load(path)["profile"])
        assert profile.untraceable_evidence() == []

    def test_an_unverified_fixture_explains_itself(self, path):
        data = load(path)
        if not data["verified"]:
            assert len(data["note"]) > 40, "say why it is unverified"


class TestBoundaryFamilies:
    """The families exist to isolate one variable. Guard that they still do."""

    def test_the_screw_family_differs_only_in_route_and_duration(self):
        names = [p.stem for p in FIXTURES if p.stem.startswith("screw_")]
        assert len(names) == 4
        classes = {load(FIXTURE_DIR / f"{n}.json")["functions"][0]["expected_class"]
                   for n in names}
        assert classes == {"Class IIa", "Class IIb", "Class III"}

    def test_the_dressing_family_differs_only_in_intended_function(self):
        names = ["dressing_mechanical_barrier", "dressing_microenvironment",
                 "dressing_secondary_intent"]
        profiles = {n: DeviceProfile.model_validate(
            load(FIXTURE_DIR / f"{n}.json")["profile"]) for n in names}
        functions = {n: p.functions[0].general for n, p in profiles.items()}
        for general in functions.values():
            assert general.contacts_injured_skin.value.value == "yes"
        assert len({g.wound_function.value for g in functions.values()}) == 3
        classes = {load(FIXTURE_DIR / f"{n}.json")["functions"][0]["expected_class"]
                   for n in names}
        assert classes == {"Class I", "Class IIa", "Class IIb"}

    def test_the_software_pairs_share_a_rule_family(self):
        pairs = [("melanoma_screening_app", "emphysema_ct_software", "4.5"),
                 ("spect_cardiac_monitoring", "emg_dystrophy_monitoring", "4.6")]
        for high, low, family in pairs:
            hi = load(FIXTURE_DIR / f"{high}.json")["functions"][0]
            lo = load(FIXTURE_DIR / f"{low}.json")["functions"][0]
            assert hi["expected_rule"].startswith(family)
            assert lo["expected_rule"].startswith(family)
            assert hi["expected_class"] != lo["expected_class"]


class TestMultiFunction:
    def test_a_pack_can_hold_two_rule_families(self):
        """The prothrombin pack is IVD and general at once. Two ARTG answers."""
        data = load(FIXTURE_DIR / "prothrombin_self_test_pack.json")
        profile = DeviceProfile.model_validate(data["profile"])
        assert profile.kinds() == {DeviceKind.IVD, DeviceKind.GENERAL}
        assert set(data["expected_classes"]) == {"ivd", "general"}

    def test_the_pack_does_not_collapse_into_one_class(self):
        data = load(FIXTURE_DIR / "prothrombin_self_test_pack.json")
        assert data["expected_classes"]["ivd"] == "Class 3 IVD"
        assert data["expected_classes"]["general"] == "Class IIa"

    def test_the_meter_and_strips_stay_separate(self):
        """Same pack, same family, different classes. The reason for functions."""
        data = load(FIXTURE_DIR / "prothrombin_self_test_pack.json")
        by_name = {f["name"]: f["expected_class"] for f in data["functions"]}
        assert by_name["Portable prothrombin time meter"] == "Class 1 IVD"
        assert by_name["Prothrombin time test strips"] == "Class 3 IVD"

    def test_one_regulated_function_governs_the_product(self):
        data = load(FIXTURE_DIR / "wellness_app_with_symptom_checker.json")
        assert data["expected_classes"]["general"] == "Class IIa"

    def test_every_function_of_a_product_is_asked_separately(self):
        profile = DeviceProfile.model_validate(
            load(FIXTURE_DIR / "imaging_platform.json")["profile"])
        blanked = profile.model_copy(deep=True)
        blanked.functions[1].general.decision_maker = type(
            blanked.functions[1].general.decision_maker)()
        missing = blanked.missing()
        assert missing == ["functions.1.general.decision_maker"]


class TestSchemaCoverage:
    """Every schema field must be reachable, or it is dead weight.

    A field the interview never asks for would always read UNKNOWN at rule
    time, and the rule that depends on it would never fire. Better to find
    that here than after writing the rule.
    """


    def _asked(self):
        general, ivd = set(), set()
        for path in FIXTURES:
            profile = DeviceProfile.model_validate(load(path)["profile"])
            for function in profile.functions:
                if function.branch() is DeviceKind.IVD:
                    ivd |= set(relevant_ivd_fields(function.ivd))
                else:
                    general |= set(relevant_general_fields(function))
        return general, ivd

    def test_every_general_field_is_reached_by_some_fixture(self):
        general, _ = self._asked()
        assert set(GeneralDeviceProfile.model_fields) - general == set()

    def test_every_ivd_field_is_reached_by_some_fixture(self):
        _, ivd = self._asked()
        assert set(IvdProfile.model_fields) - ivd == set()

    def test_every_status_field_is_reached_by_some_fixture(self):
        asked = set()
        for path in FIXTURES:
            profile = DeviceProfile.model_validate(load(path)["profile"])
            for function in profile.functions:
                asked |= set(relevant_status_fields(function))
        assert set(StatusProfile.model_fields) - asked == set()
