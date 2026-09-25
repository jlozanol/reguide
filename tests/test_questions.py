"""The founder-facing question catalogue (stage 1 step 4, piece 1).

What is checked:

- every profile field an interview can reach has exactly one question, and
  the catalogue names no field that does not exist;
- every option sets a value of the field's own type, every enum value is
  offered, and every question offers "Not sure";
- every relevant field of every fixture renders into a valid Question;
- multi-function products name the function in the text, the exclusion
  question lists every item with the function's kind first, and the
  conditions question names the item chosen;
- clause 1.4(a) is asked the positive way round and maps Yes to no;
- no text carries an em dash, and every source is a clause id that exists;
- docs/QUESTIONS.md is what the catalogue and clause files generate.
"""

import importlib.util
import json
import re
from enum import Enum
from pathlib import Path

import pytest

from reguide import intake_fields as F
from reguide import legislation as LEG
from reguide import questions as Q
from reguide import status as ST
from reguide.extract import Question
from reguide.profile import DeviceKind, DeviceProfile, TherapeuticPurpose, Tri

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

EM = "\u2014"
FREE_TEXT = {"core.product_name", "core.intended_purpose", "function.name",
             "function.description"}


def _schema_targets() -> set[str]:
    targets = set()
    for section, model in F.SECTION_MODELS.items():
        if section == "funding":
            continue
        for name in model.model_fields:
            if section == "function" and name in ("status", "general", "ivd"):
                continue
            targets.add(f"{section}.{name}")
    return targets


def _profiles() -> list[tuple[str, DeviceProfile]]:
    out = []
    for path in sorted(FIXTURES.glob("*.json")):
        out.append((path.stem, DeviceProfile.model_validate(
            json.loads(path.read_text())["profile"])))
    return out


PROFILES = _profiles()


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("legislation")
    L.write(L.SOURCE, out)
    return LEG.load(out)


# --------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------


def test_every_field_an_interview_can_reach_has_one_question():
    assert set(Q.CATALOGUE) == _schema_targets()


def test_funding_is_not_asked_yet():
    assert not [t for t in Q.CATALOGUE if t.startswith("funding.")]


def test_a_field_cannot_be_given_two_questions():
    with pytest.raises(ValueError):
        Q.yes_no("core.supplied_sterile", "Again?", "somewhere")


# --------------------------------------------------------------------------
# Options
# --------------------------------------------------------------------------


@pytest.mark.parametrize("target", sorted(Q.CATALOGUE))
def test_every_option_value_is_of_the_fields_type(target):
    entry = Q.CATALOGUE[target]
    for _, _, raw in entry.choices:
        value = Q.parse_value(target, raw)
        kind = F.value_type(target)
        if isinstance(kind, type) and issubclass(kind, Enum):
            assert isinstance(value, kind)


@pytest.mark.parametrize("target", sorted(t for t in Q.CATALOGUE
                                          if isinstance(F.value_type(t), type)
                                          and issubclass(F.value_type(t), Enum)))
def test_every_enum_value_is_offered_once(target):
    kind = F.value_type(target)
    offered = [raw for _, _, raw in Q.CATALOGUE[target].choices]
    assert len(offered) == len(set(offered))
    expected = {m.value for m in kind if m.value != "unknown"}
    assert set(offered) == expected


def test_no_therapeutic_purpose_can_be_answered():
    """Extraction may never claim it; an answer is the only way to reach it."""
    offered = {raw for _, _, raw in Q.CATALOGUE["status.therapeutic_purpose"].choices}
    assert TherapeuticPurpose.NONE.value in offered


def test_function_kind_offers_both_branches_and_never_unknown():
    offered = {raw for _, _, raw in Q.CATALOGUE["function.kind"].choices}
    assert offered == {DeviceKind.IVD.value, DeviceKind.GENERAL.value}


@pytest.mark.parametrize("target", sorted(FREE_TEXT))
def test_free_text_questions_have_no_choices(target):
    assert Q.CATALOGUE[target].choices == ()


def test_the_exclusion_item_is_the_only_other_question_without_fixed_choices():
    bare = {t for t, e in Q.CATALOGUE.items() if not e.choices}
    assert bare == FREE_TEXT | {"status.excluded_item"}


def test_clause_1_4_a_is_asked_positively_and_inverts():
    dotted = "functions.0.ivd.result_not_determining_serious_condition"
    profile = dict(PROFILES)["pregnancy_self_test"]
    question = Q.render(profile, dotted)
    by_id = {o.id: o for o in question.options}
    assert by_id["yes"].sets == {dotted: Tri.NO}
    assert by_id["no"].sets == {dotted: Tri.YES}


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


@pytest.mark.parametrize("slug,profile", PROFILES, ids=[s for s, _ in PROFILES])
def test_every_relevant_field_of_every_fixture_renders(slug, profile):
    for dotted in profile.relevant():
        question = Q.render(profile, dotted)
        assert isinstance(question, Question)
        assert question.fields == [dotted]
        assert question.id == dotted
        assert question.options[-1].unsure
        assert question.clause
        for option in question.options:
            assert set(option.sets) <= {dotted}


def test_an_empty_profile_renders_its_first_questions():
    profile = DeviceProfile()
    for dotted in profile.relevant():
        assert Q.render(profile, dotted).fields == [dotted]


def test_a_multi_function_question_names_the_function():
    profile = dict(PROFILES)["imaging_platform"]
    text = Q.render(profile, "functions.1.status.therapeutic_purpose").text
    assert text.startswith('About "Abnormality triage": ')


def test_a_single_function_question_does_not():
    profile = dict(PROFILES)["tens_device"]
    text = Q.render(profile, "functions.0.status.therapeutic_purpose").text
    assert not text.startswith("About")


def test_the_split_question_lists_the_functions():
    profile = dict(PROFILES)["imaging_platform"]
    text = Q.render(profile, "core.functions_confirmed").text
    assert "3 separate things" in text
    assert "1. Study archive; 2. Abnormality triage; 3. Follow-up interval suggestion" in text


def test_the_exclusion_question_lists_every_item_kind_first():
    items = Q.exclusions()
    profile = dict(PROFILES)["imaging_platform"]
    question = Q.render(profile, "functions.0.status.excluded_item")
    ids = [o.id for o in question.options]
    assert len(ids) == len(items) + 2
    assert ids[-2:] == ["none", "unsure"]
    software = [i.key for i in items if i.software]
    assert ids[:len(software)] == software

    hardware = dict(PROFILES)["tens_device"]
    ids = [o.id for o in Q.render(hardware, "functions.0.status.excluded_item").options]
    assert ids[0] == "S1-1"
    assert set(software) <= set(ids)


def test_the_conditions_question_names_the_item_chosen():
    profile = dict(PROFILES)["imaging_platform"]
    text = Q.render(profile, "functions.0.status.exclusion_conditions_met").text
    assert "Item S1-14H covers:" in text


def test_rendering_does_not_fill_the_gates_exclusion_table(monkeypatch):
    monkeypatch.setattr(ST, "EXCLUSION_TABLE", {})
    profile = dict(PROFILES)["imaging_platform"]
    Q.render(profile, "functions.0.status.excluded_item")
    assert ST.EXCLUSION_TABLE == {}


def test_target_of():
    assert Q.target_of("functions.2.general.duration") == ("general.duration", 2)
    assert Q.target_of("functions.0.kind") == ("function.kind", 0)
    assert Q.target_of("core.supplied_sterile") == ("core.supplied_sterile", None)


# --------------------------------------------------------------------------
# Wording and sources
# --------------------------------------------------------------------------


def _texts():
    for entry in Q.CATALOGUE.values():
        yield entry.target, entry.text
        yield entry.target, entry.hint
        yield entry.target, entry.clause
        for _, label, _ in entry.choices:
            yield entry.target, label


def test_no_em_dashes_anywhere():
    assert [t for t, text in _texts() if EM in text] == []


def test_every_question_is_a_question():
    assert [t for t, e in Q.CATALOGUE.items() if not e.text.endswith("?")] == []


def test_sources_are_clause_ids():
    pattern = re.compile(r"^s2a?-\d+\.\d+[A-Z]?$")
    bad = [(t, s) for t, e in Q.CATALOGUE.items() for s in e.sources if not pattern.match(s)]
    assert bad == []


def test_every_schedule_field_names_a_source():
    """general.* and ivd.* are decided by Schedules 2 and 2A, which are in the corpus."""
    bare = [t for t, e in Q.CATALOGUE.items()
            if t.split(".")[0] in ("general", "ivd") and not e.sources]
    assert bare == []


@needs_source
def test_every_source_exists_in_the_corpus(corpus):
    missing = [(t, s) for t, e in Q.CATALOGUE.items() for s in e.sources if s not in corpus]
    assert missing == []


@needs_source
def test_the_review_document_is_current(corpus):
    committed = (ROOT / "docs" / "QUESTIONS.md").read_text(encoding="utf-8")
    assert Q.review_markdown(corpus) == committed, (
        "docs/QUESTIONS.md is out of date: run scripts/review_questions.py")


def test_the_review_document_builds_without_the_corpus():
    text = Q.review_markdown(None)
    assert "Clause text is not shown" in text
    assert text.count("### `") == len(Q.CATALOGUE)
    assert text.count("### Checklist") == len(Q.CHECKLISTS)
    assert EM not in text
