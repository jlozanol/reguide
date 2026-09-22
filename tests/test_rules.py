"""Agreement against known classifications.

Fixtures in tests/fixtures/ are device profiles whose real ARTG classification is
known. The percentage of fixtures the engine gets right is the project's only
meaningful quality measure. Add a fixture before fixing a rule, not after.

The number itself is printed by scripts/score.py. These tests hold two lines:

- No verified fixture may ever get a confident wrong class. A refusal is
  acceptable while rules are being written; a wrong answer never is.
- Agreement only moves forward. KNOWN_AGREEING lists the fixtures that agree
  today; a change that loses one fails here. Add to it as rules land.
"""

import re

import pytest

from reguide import legislation as LEG
from reguide.profile import DeviceKind
from reguide.scoring import AGREE, FAMILY_PREFIX, NO_RESULT, RULE_REFERENCE, WRONG_CLASS, run

KNOWN_AGREEING = {
    "abo_reagent_red_cells",
    "cbt_app_bipolar",
    "chlamydia_test",
    "condom_with_spermicide",
    "culture_media",
    "diagnostic_ultrasound",
    "dressing_collagen_deep_wound",
    "dressing_mechanical_barrier",
    "dressing_microenvironment",
    "dressing_secondary_intent",
    "emg_dystrophy_monitoring",
    "emphysema_ct_software",
    "haemodialyser",
    "heparin_coated_catheter",
    "hiv_donor_screening",
    "infusion_pump",
    "infusion_pump_syringe",
    "measuring_thermometer",
    "melanoma_screening_app",
    "mri_equipment",
    "nebuliser",
    "orifice_long_term",
    "prothrombin_meter",
    "prothrombin_self_test",
    "prothrombin_self_test_pack",
    "quality_control_material",
    "radiotherapy_afterloading_control",
    "reusable_surgical_instrument",
    "saline_nasal_spray",
    "screw_central_circulation",
    "screw_long_term",
    "screw_short_term",
    "screw_transient",
    "spect_cardiac_monitoring",
    "sterile_barrier_dressing",
    "tens_device",
    "trauma_covering_anaesthetic",
    "virtual_anatomical_model_software",
}


@pytest.fixture(scope="module")
def verified():
    return run()


@pytest.fixture(scope="module")
def everything():
    return run(include_unverified=True)


def test_no_verified_fixture_gets_a_confident_wrong_class(verified):
    wrong = [f"{r.fixture}: {r.function}" for r in verified.rows if r.verdict == WRONG_CLASS]
    assert wrong == []


def test_agreement_does_not_go_backwards(verified):
    lost = KNOWN_AGREEING - set(verified.agreeing_fixtures)
    assert not lost, f"no longer agreeing: {sorted(lost)}"


def test_known_agreeing_is_up_to_date(verified):
    """A newly agreeing fixture should be recorded, so the ratchet holds it."""
    gained = set(verified.agreeing_fixtures) - KNOWN_AGREEING
    assert not gained, f"add to KNOWN_AGREEING: {sorted(gained)}"


def test_every_verified_fixture_is_scored(verified, everything):
    assert len(verified.fixtures) == 38
    assert len(everything.fixtures) == 44


def test_unverified_fixtures_get_no_confident_wrong_class_either(everything):
    wrong = [r.fixture for r in everything.rows if r.verdict == WRONG_CLASS]
    assert wrong == []


def test_every_function_the_fixture_expects_regulated_reaches_the_engine(everything):
    """The gate agrees with every fixture, so no miss is the gate's."""
    assert [r.fixture for r in everything.rows if r.verdict not in (AGREE, NO_RESULT)] == []


# --------------------------------------------------------------------------
# Fixture rule references against the Regulations
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "load_legislation", root / "scripts" / "load_legislation.py"
    )
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    if not loader.SOURCE.exists():
        pytest.skip(f"legislation source not downloaded: {loader.SOURCE.name}")
    out = tmp_path_factory.mktemp("legislation")
    loader.write(loader.SOURCE, out)
    return LEG.load(out)


def test_every_fixture_rule_names_a_clause_and_paragraphs_that_exist(everything, corpus):
    """Existence only. Whether the paragraph gives that class is a human check."""
    problems = []
    for row in everything.rows:
        if row.expected_class is None:
            continue
        kind = DeviceKind.IVD if row.expected_class.endswith("IVD") else DeviceKind.GENERAL
        reference = RULE_REFERENCE.match(row.expected_rule).group(0)
        number, labels = re.match(r"^([^(]+)(.*)$", reference).groups()
        clause = corpus.get(f"{FAMILY_PREFIX[kind]}-{number}")
        if clause is None:
            problems.append(f"{row.fixture}: no clause {number}")
            continue
        missing = [label for label in re.findall(r"\([^)]+\)", labels)
                   if label not in clause.text]
        if missing:
            problems.append(f"{row.fixture}: {number} has no {''.join(missing)}")
    assert problems == []
