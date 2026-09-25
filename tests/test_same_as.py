"""Same as an earlier part (stage 1 step 4, piece 5).

On a later function of a multi-function product, the gate and the branch
each open with one screen listing an earlier function's answers to a few
basic facts. Each fact ticked as the same is copied; each left unticked is
asked on its own.

What is checked:

- every fact is a real field with a single question, and none is a rule
  answer about what the part is for beyond the gate;
- the screen: one option per fact carrying the earlier value, a required
  "None of these are the same", and a reply naming every fact;
- what may be lent: never from a function the gate has stopped, never a
  definition's default, never a specific exclusion item, branch facts only
  from the same kind and only once this part's kind is known;
- the screen is shown at most once per function and group, and not at all
  for the first function or a single-function product;
- on the fixtures it is offered where it should be and every copied answer
  traces to the reply.
"""

import json
from pathlib import Path

import pytest

from reguide import interview as I
from reguide import interview_oracle as O
from reguide import questions as Q
from reguide import status as S
from reguide.profile import Answer, Basis, DeviceProfile, Tri
from reguide.scoring import EXCLUSIONS

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module", autouse=True)
def exclusions():
    saved = dict(S.EXCLUSION_TABLE)
    S.load_exclusions(EXCLUSIONS)
    yield
    S.EXCLUSION_TABLE.clear()
    S.EXCLUSION_TABLE.update(saved)


def fixture_profile(slug: str) -> DeviceProfile:
    data = json.loads((FIXTURES / f"{slug}.json").read_text())
    return DeviceProfile.model_validate(data["profile"])


@pytest.fixture(scope="module")
def blank_runs(exclusions):
    return {run.slug: run for run in O.run_blank()}


# --------------------------------------------------------------------------
# Definitions
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(set(Q.SAME_AS_GATE) | set(Q.SAME_AS_BRANCH)))
def test_every_fact_is_a_field_with_a_single_question(path):
    target, _ = Q.target_of(f"functions.0.{path}")
    assert target in Q.CATALOGUE


def test_no_fact_is_in_both_groups():
    assert not set(Q.SAME_AS_GATE) & set(Q.SAME_AS_BRANCH)


def test_the_branch_facts_are_about_what_the_part_is():
    """Openers and materials only: no graded rule answer is ever lent."""
    rule_answers = {"decision_maker", "condition_severity", "public_health_risk",
                    "monitoring_danger", "treatment_risk", "information_therapy_harm"}
    names = {p.split(".", 1)[1] for p in Q.SAME_AS_BRANCH}
    assert not names & rule_answers
    assert not names & {n.split(".", 1)[1] for n in Q.CHECKLIST_OF
                        if n.startswith("general.") and Q.CHECKLIST_OF[n].id != "particular_kinds"}


# --------------------------------------------------------------------------
# The screen
# --------------------------------------------------------------------------


def _pack_gate_screen():
    profile = fixture_profile("prothrombin_self_test_pack")
    target = profile.functions[1]
    target.is_software = Answer()
    target.status.therapeutic_purpose = Answer()
    target.status.principal_action_pharmacological = Answer()
    copies = I._copies(profile, 0, 1, "gate")
    return profile, copies, Q.render_same_as(profile, 1, 0, "gate", copies)


def test_the_screen_lists_each_fact_with_the_earlier_value():
    profile, copies, question = _pack_gate_screen()
    assert question.multi and question.id == "functions.1.same_as.gate"
    items = question.options[:-1]
    assert [o.sets for o in items] == [{d: v} for d, v in copies.items()]
    assert all(": " in o.label for o in items)
    assert question.options[-1].id == Q.SAME_AS_NONE and question.options[-1].sets == {}


def test_the_reply_names_every_fact():
    _, _, question = _pack_gate_screen()
    first = question.options[0]
    reply = Q.same_as_reply(question, [first.id])
    assert reply.startswith("The same: " + first.label)
    for option in question.options[1:-1]:
        assert option.label in reply


# --------------------------------------------------------------------------
# What may be lent
# --------------------------------------------------------------------------


def test_a_stopped_function_lends_nothing():
    profile = fixture_profile("imaging_platform")
    profile.functions[1].status.therapeutic_purpose = Answer()
    profile.functions[1].is_software = Answer()
    assert I._copies(profile, 0, 1, "gate") == {}


def test_a_specific_exclusion_item_is_never_lent():
    profile = fixture_profile("imaging_platform")
    profile.functions[0].status.exclusion_conditions_met = Answer()
    profile.functions[1].status.excluded_item = Answer()
    assert "functions.1.status.excluded_item" not in I._copies(profile, 0, 1, "gate")


def test_none_of_these_is_lent_as_an_exclusion_answer():
    profile = fixture_profile("prothrombin_self_test_pack")
    profile.functions[1].status.excluded_item = Answer()
    profile.functions[1].is_software = Answer()
    copies = I._copies(profile, 0, 1, "gate")
    assert copies["functions.1.status.excluded_item"] == "none"


def test_a_definitions_default_is_never_lent():
    profile = fixture_profile("imaging_platform")
    source = profile.functions[1].general
    source.invasiveness = Answer(value=source.invasiveness.value, basis=Basis.DEFAULTED)
    profile.functions[2].general.invasiveness = Answer()
    assert "functions.2.general.invasiveness" not in I._copies(profile, 1, 2, "branch")


def test_branch_facts_need_the_same_kind_and_a_known_kind():
    profile = fixture_profile("prothrombin_self_test_pack")
    lancet = profile.functions[2]
    lancet.general.is_export_only = Answer()
    assert I._copies(profile, 0, 2, "branch") == {}
    lancet.kind = Answer()
    assert I._copies(profile, 0, 2, "branch") == {}


def test_an_answered_or_unsure_fact_is_not_offered():
    profile = fixture_profile("prothrombin_self_test_pack")
    profile.functions[1].is_software = Answer()
    profile.functions[1].status.therapeutic_purpose = Answer()
    copies = I._copies(profile, 0, 1, "gate")
    assert set(copies) == {"functions.1.is_software", "functions.1.status.therapeutic_purpose"}
    assert Tri.NO in copies.values()


# --------------------------------------------------------------------------
# In the interview
# --------------------------------------------------------------------------


def test_the_first_function_and_single_products_never_see_it(blank_runs):
    for run in blank_runs.values():
        assert not [q for q in run.same_as if q.startswith("functions.0.")], run.slug
        if len(run.profile.functions) == 1:
            assert run.same_as == [], run.slug


def test_it_is_shown_at_most_once_per_function_and_group(blank_runs):
    for run in blank_runs.values():
        assert len(run.same_as) == len(set(run.same_as)), run.slug


def test_the_imaging_platform_is_offered_both_screens_for_its_third_part(blank_runs):
    offered = blank_runs["imaging_platform"].same_as
    assert "functions.2.same_as.gate" in offered
    assert "functions.2.same_as.branch" in offered
    assert "functions.1.same_as.gate" not in offered


def test_the_lancet_is_not_offered_the_meters_branch_facts(blank_runs):
    assert "functions.2.same_as.branch" not in blank_runs["prothrombin_self_test_pack"].same_as


def test_every_copied_answer_traces_to_the_reply(blank_runs):
    assert [s for s, r in blank_runs.items() if r.profile.untraceable_evidence()] == []
