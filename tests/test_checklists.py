"""Checklists: several fields on one screen (stage 1 step 4, piece 4).

Decision C: a ticked item is yes, an unticked item is no, "None of these
apply" is required to submit nothing ticked, and "I'm not sure about some of
these" leaves the unticked items open to come back as single questions.

What is checked:

- every checklist item is a yes/no field with a statement label, belongs to
  one checklist only, and is never a "Despite" question;
- the rendered Question: one option per open item setting yes, "None of
  these apply" setting every item to no, and the partial option setting
  nothing without marking anything unsure;
- the recorded reply names every item, ticked and not, so each field's
  evidence is its own label;
- the interview shows a checklist once per function, only with two or more
  open items, and asks what a partial answer left open one at a time;
- the oracle's answers all trace to a reply.
"""

import json
from pathlib import Path

import pytest

from reguide import intake_fields as F
from reguide import interview as I
from reguide import interview_oracle as O
from reguide import questions as Q
from reguide import status as S
from reguide.profile import Answer, DeviceProfile, Tri, Turn
from reguide.scoring import EXCLUSIONS

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EM = "\u2014"


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


def blank_group(profile: DeviceProfile, index: int, checklist: Q.Checklist) -> list[str]:
    section = getattr(profile.functions[index], checklist.section)
    dotted = []
    for name in checklist.fields:
        setattr(section, name, Answer())
        dotted.append(f"functions.{index}.{checklist.section}.{name}")
    return dotted


# --------------------------------------------------------------------------
# Definitions
# --------------------------------------------------------------------------


def test_every_item_has_a_label_and_every_label_an_item():
    assert set(Q.ITEM_LABELS) == set(Q.CHECKLIST_OF)


def test_no_field_is_in_two_checklists():
    assert len(Q.CHECKLIST_OF) == sum(len(c.fields) for c in Q.CHECKLISTS)


def test_every_item_is_a_yes_no_field():
    assert [t for t in Q.CHECKLIST_OF if F.value_type(t) is not Tri] == []


def test_no_despite_question_is_in_a_checklist():
    despite = {f"general.{n}" for n in I.GENERAL_DESPITE} | {f"ivd.{n}" for n in I.IVD_DESPITE}
    assert not despite & set(Q.CHECKLIST_OF)


def test_labels_are_statements_without_em_dashes():
    for target, label in Q.ITEM_LABELS.items():
        assert EM not in label, target
        assert label.startswith("It ") and not label.endswith(("?", ".")), target


def test_every_item_is_also_a_single_question():
    """A partial answer sends items back as single questions, so each needs one."""
    assert set(Q.CHECKLIST_OF) <= set(Q.CATALOGUE)


# --------------------------------------------------------------------------
# Rendering and the reply
# --------------------------------------------------------------------------


def _tens_checklist():
    profile = fixture_profile("tens_device")
    checklist = next(c for c in Q.CHECKLISTS if c.id == "particular_kinds")
    fields = blank_group(profile, 0, checklist)[:3]
    return profile, checklist, Q.render_checklist(profile, 0, checklist, list(reversed(fields)))


def test_a_checklist_offers_each_item_then_none_then_partial():
    _, checklist, question = _tens_checklist()
    assert question.multi
    assert question.id == "functions.0.checklist.particular_kinds"
    ids = [o.id for o in question.options]
    assert ids == list(checklist.fields[:3]) + [Q.CHECKLIST_NONE, Q.CHECKLIST_PARTIAL]


def test_items_set_yes_and_none_sets_every_item_no():
    _, _, question = _tens_checklist()
    by_id = {o.id: o for o in question.options}
    for dotted in question.fields:
        item = by_id[dotted.rsplit(".", 1)[1]]
        assert item.sets == {dotted: Tri.YES}
    assert by_id[Q.CHECKLIST_NONE].sets == {d: Tri.NO for d in question.fields}


def test_the_partial_option_sets_nothing_and_is_not_unsure():
    _, _, question = _tens_checklist()
    partial = question.options[-1]
    assert partial.sets == {} and not partial.unsure


@pytest.mark.parametrize("chosen,heads", [
    (["corrects_heart_or_circulatory_defect_by_contact"], ["Ticked:", "Not ticked:"]),
    ([Q.CHECKLIST_NONE], ["None of these apply.", "Not ticked:"]),
    ([Q.CHECKLIST_PARTIAL], ["Not sure about:"]),
])
def test_the_reply_names_every_item(chosen, heads):
    _, _, question = _tens_checklist()
    reply = Q.checklist_reply(question, chosen)
    for head in heads:
        assert head in reply
    for option in question.options[:-2]:
        assert option.label in reply


# --------------------------------------------------------------------------
# In the interview
# --------------------------------------------------------------------------


def test_open_items_of_a_checklist_come_on_one_screen():
    profile = fixture_profile("chlamydia_test")
    checklist = next(c for c in Q.CHECKLISTS if c.id == "ivd_1_3")
    blank_group(profile, 0, checklist)
    question = I.next_question(profile)
    assert question.multi and question.id == "functions.0.checklist.ivd_1_3"
    assert len(question.fields) >= 2


def test_a_partial_answer_brings_the_open_items_back_one_at_a_time():
    profile = fixture_profile("chlamydia_test")
    checklist = next(c for c in Q.CHECKLISTS if c.id == "ivd_1_3")
    blank_group(profile, 0, checklist)
    shown = I.next_question(profile)
    profile.transcript.append(Turn(question_id=shown.id, fields=[], asked=shown.text,
                                   reply=Q.checklist_reply(shown, [Q.CHECKLIST_PARTIAL])))
    question = I.next_question(profile)
    assert not question.multi
    assert question.fields[0] in shown.fields


def test_a_single_open_item_is_asked_on_its_own():
    profile = fixture_profile("tens_device")
    profile.functions[0].general.contains_non_viable_animal_material = Answer()
    question = I.next_question(profile)
    assert not question.multi
    assert question.fields == ["functions.0.general.contains_non_viable_animal_material"]


@pytest.fixture(scope="module")
def runs(exclusions):
    return O.run_blank() + O.run_extracted()


def test_a_checklist_is_shown_once_per_function(runs):
    for run in runs:
        assert len(run.checklists) == len(set(run.checklists)), run.start


def test_every_oracle_answer_traces_to_a_reply(runs):
    assert [(r.slug, r.start) for r in runs if r.profile.untraceable_evidence()] == []


def test_most_products_see_the_particular_kinds_checklist(runs):
    seen = [r for r in runs if r.start == "blank"
            and any(c.endswith("particular_kinds") for c in r.checklists)]
    assert len(seen) >= 20
