"""Ceilings on every paragraph without "Despite" (stage 1 step 4, piece 3).

Decision A: once a live hit is at or above everything still unanswered, the
class cannot change, so the engine gives it and the interview stops.

What is checked:

- every paragraph of Schedules 2 and 2A has a ceiling except the clauses
  that open "Despite", and the "Despite" list is exactly the clauses whose
  text opens with the word (checked against the clause files);
- each ceiling is the class its paragraph gives: the class literal in the
  rule's own code, and the class of every hit on every fixture;
- resolve(): an unanswered "Despite" clause always blocks; an unanswered
  paragraph at or below the best live hit is relieved and reported; one
  above it blocks;
- scoring: a fixture's rule left unanswered at the result's class agrees
  only when the caller says the interview stopped early.
"""

import importlib.util
import inspect
import json
import re
from pathlib import Path

import pytest

from reguide import legislation as LEG
from reguide import scoring as SC
from reguide.profile import (
    GENERAL_ORDER,
    IVD_ORDER,
    Answer,
    DeviceProfile,
    FunctionProfile,
    GeneralDeviceProfile,
    IvdProfile,
)
from reguide.rules import engine as E
from reguide.rules import schedule2 as S2
from reguide.rules import schedule2a as S2A

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
SPEC = importlib.util.spec_from_file_location(
    "load_legislation", ROOT / "scripts" / "load_legislation.py"
)
L = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(L)
needs_source = pytest.mark.skipif(
    not L.SOURCE.exists(), reason=f"legislation source not downloaded: {L.SOURCE.name}"
)

CLASS = re.compile(r'"(Class (?:I|IIa|IIb|III|[1-4] IVD))"')


def _general_rules():
    blank = FunctionProfile(general=GeneralDeviceProfile())
    for rule in S2.PART_2:
        yield rule, rule(blank.general)
    for rule in S2.PART_3 + S2.PART_4 + S2.PART_5:
        yield rule, rule(blank)


def _ivd_rules():
    blank = IvdProfile()
    for rule in S2A.ALL_RULES:
        yield rule, rule(blank)


def _fixture_profiles():
    for path in sorted(FIXTURES.glob("*.json")):
        yield path.stem, DeviceProfile.model_validate(json.loads(path.read_text())["profile"])


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("legislation")
    L.write(L.SOURCE, out)
    return LEG.load(out)


# --------------------------------------------------------------------------
# The tables
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rules,table,despite", [
    (_general_rules, S2.CEILINGS, S2.DESPITE),
    (_ivd_rules, S2A.CEILINGS, S2A.DESPITE),
], ids=["schedule 2", "schedule 2a"])
def test_every_paragraph_has_a_ceiling_or_opens_despite(rules, table, despite):
    seen = set()
    for rule, outcome in rules():
        assert isinstance(outcome, E.Pending), rule.__name__
        seen.add(outcome.rule_id)
        assert (outcome.rule_id in table) != (outcome.rule_id in despite), outcome.rule_id
    assert set(table) <= seen, set(table) - seen


@pytest.mark.parametrize("rules,table", [
    (_general_rules, S2.CEILINGS), (_ivd_rules, S2A.CEILINGS),
], ids=["schedule 2", "schedule 2a"])
def test_each_ceiling_is_the_class_the_rule_gives(rules, table):
    for rule, outcome in rules():
        literals = set(CLASS.findall(inspect.getsource(rule)))
        if outcome.rule_id in table and literals:
            assert literals == {table[outcome.rule_id]}, rule.__name__


def test_every_fixture_hit_is_at_its_paragraphs_ceiling():
    for slug, profile in _fixture_profiles():
        for function in profile.functions:
            if function.general is None and function.ivd is None:
                continue
            outcome = E.classify_function(function)
            table = S2A.CEILINGS if function.ivd is not None else S2.CEILINGS
            for hit in outcome.hits:
                if hit.rule_id in table:
                    assert hit.result == table[hit.rule_id], (slug, hit.rule_id)


@needs_source
def test_despite_is_exactly_the_clauses_whose_text_opens_with_it(corpus):
    opening = set()
    for clause_id, clause in corpus.items():
        if not clause_id.startswith(("s2-", "s2a-")):
            continue
        if re.search(r"(^|\n)(\(\d+\)\s+)?Despite\b", clause.text):
            opening.add(clause_id)
    despite = {E.clause_of(r) for r in S2.DESPITE | S2A.DESPITE}
    assert opening == despite == {"s2-5.8", "s2a-1.5", "s2a-1.6", "s2a-1.8"}


def test_1_6_1_is_the_one_paragraph_of_1_6_with_a_ceiling():
    assert "s2a-1.6(1)" in S2A.CEILINGS
    assert not [r for r in S2A.CEILINGS if r.startswith("s2a-1.6(2)")]


def test_a_rule_without_a_ceiling_is_refused():
    stray = E.Pending("s2-9.9", "c", "unresolved", ("general.x",))
    with pytest.raises(KeyError):
        E.apply_ceilings([stray], S2.CEILINGS, S2.DESPITE)


# --------------------------------------------------------------------------
# resolve()
# --------------------------------------------------------------------------


def _hit(rule_id, result):
    return E.RuleHit(rule_id, "c", result, "b")


def _pending(rule_id, field, ceiling=None):
    return E.Pending(rule_id, "c", "unresolved", (field,), ceiling)


def test_an_equal_or_lower_paragraph_is_relieved_and_reported():
    outcome = E.resolve([_hit("s2-5.4(1)", "Class IIa"),
                         _pending("s2-4.3(2)(a)", "general.a", "Class IIa"),
                         _pending("s2-2.1", "general.b", "Class I")], GENERAL_ORDER)
    assert outcome.confident and outcome.result == "Class IIa"
    assert [p.rule_id for p in outcome.relieved] == ["s2-4.3(2)(a)", "s2-2.1"]
    assert outcome.could_not_change == ["general.a", "general.b"]


def test_a_higher_paragraph_still_blocks():
    outcome = E.resolve([_hit("s2-5.4(1)", "Class IIa"),
                         _pending("s2-4.2(4)", "general.c", "Class III")], GENERAL_ORDER)
    assert not outcome.confident
    assert outcome.unresolved == ["general.c"]


def test_an_unanswered_despite_clause_blocks_even_a_class_iii_hit():
    outcomes = E.apply_ceilings([_hit("s2-5.9", "Class III"),
                                 _pending("s2-5.8", "general.is_export_only")],
                                S2.CEILINGS, S2.DESPITE)
    outcome = E.resolve(outcomes, GENERAL_ORDER)
    assert not outcome.confident
    assert outcome.unresolved == ["general.is_export_only"]


def test_nothing_is_relieved_without_a_result():
    outcome = E.resolve([_hit("s2-5.4(1)", "Class IIa"),
                         _pending("s2-4.2(4)", "general.c", "Class III"),
                         _pending("s2-2.1", "general.b", "Class I")], GENERAL_ORDER)
    assert outcome.result is None
    assert outcome.relieved == []
    assert outcome.could_not_change == []


def test_ivd_ceilings_follow_the_ivd_ladder():
    outcomes = E.apply_ceilings([_hit("s2a-1.3(a)", "Class 3 IVD"),
                                 _pending("s2a-1.4", "ivd.is_self_test")],
                                S2A.CEILINGS, S2A.DESPITE)
    outcome = E.resolve(outcomes, IVD_ORDER)
    assert outcome.confident and outcome.result == "Class 3 IVD"
    assert outcome.could_not_change == ["ivd.is_self_test"]


def test_a_real_profile_stops_once_the_class_is_settled():
    """The MRI fixture with a IIa paragraph blanked still classifies IIa."""
    profile = dict(_fixture_profiles())["mri_equipment"]
    profile.functions[0].general.supplies_absorbed_energy_for_diagnosis = Answer()
    outcome = E.classify_function(profile.functions[0])
    assert outcome.confident and outcome.result == "Class IIa"
    assert "general.supplies_absorbed_energy_for_diagnosis" in outcome.could_not_change


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def _blanked_mri() -> dict:
    data = json.loads((FIXTURES / "mri_equipment.json").read_text())
    profile = DeviceProfile.model_validate(data["profile"])
    profile.functions[0].general.supplies_absorbed_energy_for_diagnosis = Answer()
    data["profile"] = json.loads(profile.model_dump_json())
    return data


@pytest.fixture
def exclusions():
    SC.S.load_exclusions(SC.EXCLUSIONS)


def test_an_unasked_fixture_rule_is_a_wrong_rule_by_default(exclusions):
    [row] = SC.score_fixture("mri_equipment", _blanked_mri())
    assert row.verdict == SC.WRONG_RULE


def test_an_unasked_fixture_rule_agrees_after_an_early_stop(exclusions):
    [row] = SC.score_fixture("mri_equipment", _blanked_mri(), unasked_rule_ok=True)
    assert row.verdict == SC.AGREE
    assert "not asked, could not change the class" in row.detail
