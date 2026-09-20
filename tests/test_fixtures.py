"""Fixture integrity.

These do not check classification. They check that every fixture is a complete,
valid profile, so that when a rule fails you know the fault is in the rule and
not in the fixture.
"""

import json
from pathlib import Path

import pytest

from reguide.profile import DeviceKind, DeviceProfile

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURES = sorted(FIXTURE_DIR.glob("*.json"))

KNOWN_CLASSES = {
    "Class I", "Class Is", "Class Im", "Class IIa", "Class IIb", "Class III",
    "Class AIMD", "Class 1 IVD", "Class 2 IVD", "Class 3 IVD", "Class 4 IVD",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def verified() -> list[Path]:
    return [p for p in FIXTURES if load(p)["verified"]]


def test_fixtures_exist():
    assert FIXTURES, "run: python scripts/build_fixtures.py"


def test_most_fixtures_are_verified():
    """Unverified fixtures are allowed, but they must stay the minority."""
    assert len(verified()) > len(FIXTURES) * 0.7


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
class TestFixture:
    def test_has_required_keys(self, path):
        data = load(path)
        for key in ("expected_class", "expected_rule", "source", "verified", "profile"):
            assert key in data, f"{path.name} is missing {key}"

    def test_profile_validates(self, path):
        DeviceProfile.model_validate(load(path)["profile"])

    def test_expected_class_is_known(self, path):
        assert load(path)["expected_class"] in KNOWN_CLASSES

    def test_branch_matches_populated_section(self, path):
        profile = DeviceProfile.model_validate(load(path)["profile"])
        kind = profile.branch()
        assert kind is not None, "every fixture must establish its kind"
        if kind is DeviceKind.IVD:
            assert profile.ivd is not None and profile.general is None
        else:
            assert profile.general is not None and profile.ivd is None

    def test_nothing_relevant_is_unresolved(self, path):
        """A fixture with gaps would fail classification for the wrong reason."""
        profile = DeviceProfile.model_validate(load(path)["profile"])
        assert profile.missing() == []

    def test_expected_class_matches_the_branch(self, path):
        data = load(path)
        profile = DeviceProfile.model_validate(data["profile"])
        assert ("IVD" in data["expected_class"]) == (profile.branch() is DeviceKind.IVD)

    def test_an_unverified_fixture_explains_itself(self, path):
        data = load(path)
        if not data["verified"]:
            assert len(data["note"]) > 40, "say why it is unverified"


class TestBoundaryFamilies:
    """The families exist to isolate one variable. Guard that they still do."""

    def test_the_screw_family_differs_only_in_route_and_duration(self):
        screws = {p.stem: DeviceProfile.model_validate(load(p)["profile"])
                  for p in FIXTURES if p.stem.startswith("screw_")}
        assert len(screws) == 4
        classes = {load(FIXTURE_DIR / f"{n}.json")["expected_class"] for n in screws}
        assert classes == {"Class IIa", "Class IIb", "Class III"}

    def test_the_dressing_family_differs_only_in_intended_function(self):
        names = ["dressing_mechanical_barrier", "dressing_microenvironment",
                 "dressing_secondary_intent"]
        profiles = {n: DeviceProfile.model_validate(
            load(FIXTURE_DIR / f"{n}.json")["profile"]) for n in names}
        for profile in profiles.values():
            assert profile.general.contacts_injured_skin.value.value == "yes"
        functions = {p.general.wound_function.value for p in profiles.values()}
        assert len(functions) == 3
        classes = {load(FIXTURE_DIR / f"{n}.json")["expected_class"] for n in names}
        assert classes == {"Class I", "Class IIa", "Class IIb"}

    def test_the_software_pairs_share_a_rule_family(self):
        pairs = [("melanoma_screening_app", "emphysema_ct_software", "4.5"),
                 ("spect_cardiac_monitoring", "emg_dystrophy_monitoring", "4.6")]
        for high, low, family in pairs:
            hi, lo = load(FIXTURE_DIR / f"{high}.json"), load(FIXTURE_DIR / f"{low}.json")
            assert hi["expected_rule"].startswith(family)
            assert lo["expected_rule"].startswith(family)
            assert hi["expected_class"] != lo["expected_class"]

    def test_the_prothrombin_pack_is_split_not_merged(self):
        meter = load(FIXTURE_DIR / "prothrombin_meter.json")
        strips = load(FIXTURE_DIR / "prothrombin_self_test.json")
        assert meter["expected_class"] == "Class 1 IVD"
        assert strips["expected_class"] == "Class 3 IVD"
