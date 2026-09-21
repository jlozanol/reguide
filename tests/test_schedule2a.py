"""Tests for the Schedule 2A rules written so far and the engine's precedence.

Four things are being tested:

1. Each lookup fires on yes, stays silent on no, and reports an unresolved
   input as Pending, never as a no.
2. "Despite" clauses displace what they name, even when they give a lower
   class, and regulation 3.3(7) decides among what is left.
3. A rule nobody could evaluate blocks the result unless it is displaced.
4. Every docstring quotes its clause verbatim, checked against the clause
   files split from the real Regulations. Skipped when the source has not
   been downloaded.
"""

import importlib.util
import inspect
import json
import re
from pathlib import Path

import pytest

from reguide import legislation as LEG
from reguide.profile import (
    IVD_ORDER,
    Answer,
    Basis,
    DeviceKind,
    DeviceProfile,
    FunctionProfile,
    IvdProfile,
    Tri,
)
from reguide.rules import engine as E
from reguide.rules import schedule2a as S2A

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

EXCEPTIONS = (
    "is_ivd_instrument",
    "is_specimen_receptacle",
    "is_culture_medium",
    "is_quality_control_material",
    "is_export_only",
)


def stated(value, evidence="test evidence"):
    return Answer(value=value, basis=Basis.STATED, evidence=evidence)


def ivd(**yes) -> IvdProfile:
    """Every named exception answered no, then the given ones overridden."""
    fields = {name: stated(Tri.NO) for name in EXCEPTIONS}
    fields["is_self_test"] = stated(Tri.NO)
    fields.update({k: v if isinstance(v, Answer) else stated(v) for k, v in yes.items()})
    return IvdProfile(**fields)


# --------------------------------------------------------------------------
# 1. Each lookup
# --------------------------------------------------------------------------

LOOKUPS = [
    (S2A.rule_1_5, "is_quality_control_material", "s2a-1.5", "Class 2 IVD", "1.5"),
    (S2A.rule_1_6_2_a, "is_ivd_instrument", "s2a-1.6(2)(a)", "Class 1 IVD", "1.6(2)(a)"),
    (S2A.rule_1_6_2_b, "is_specimen_receptacle", "s2a-1.6(2)(b)", "Class 1 IVD",
     "1.6(2)(b)"),
    (S2A.rule_1_6_2_c, "is_culture_medium", "s2a-1.6(2)(c)", "Class 1 IVD", "1.6(2)(c)"),
    (S2A.rule_1_8, "is_export_only", "s2a-1.8", "Class 1 IVD", "1.8"),
]


@pytest.mark.parametrize("rule,field,rule_id,result,reference", LOOKUPS,
                         ids=[r[2] for r in LOOKUPS])
class TestLookup:
    def test_yes_fires_and_cites_its_clause(self, rule, field, rule_id, result, reference):
        hit = rule(ivd(**{field: stated(Tri.YES, "the founder's words")}))
        assert isinstance(hit, E.RuleHit)
        assert (hit.rule_id, hit.result) == (rule_id, result)
        assert hit.citation == (
            f"Therapeutic Goods (Medical Devices) Regulations 2002 Schedule 2A clause {reference}"
        )
        assert f'{field} is yes (stated: "the founder\'s words")' in hit.because

    def test_no_is_silent(self, rule, field, rule_id, result, reference):
        assert rule(ivd()) is None

    @pytest.mark.parametrize("answer", [Answer(), stated(Tri.UNKNOWN)],
                             ids=["unanswered", "stated_unknown"])
    def test_unresolved_is_pending_not_no(self, rule, field, rule_id, result, reference,
                                          answer):
        pending = rule(ivd(**{field: answer}))
        assert isinstance(pending, E.Pending)
        assert pending.rule_id == rule_id
        assert pending.fields == (f"ivd.{field}",)


class TestSpecimenReceptacle:
    def test_a_self_test_receptacle_is_outside_paragraph_b(self):
        assert S2A.rule_1_6_2_b(ivd(is_specimen_receptacle=Tri.YES,
                                    is_self_test=Tri.YES)) is None

    def test_self_testing_unresolved_is_pending(self):
        pending = S2A.rule_1_6_2_b(ivd(is_specimen_receptacle=Tri.YES,
                                       is_self_test=Answer()))
        assert pending.fields == ("ivd.is_self_test",)

    def test_the_hit_names_both_inputs(self):
        hit = S2A.rule_1_6_2_b(ivd(is_specimen_receptacle=Tri.YES))
        assert "is_specimen_receptacle is yes" in hit.because
        assert "is_self_test is no" in hit.because

    def test_a_self_test_receptacle_gets_no_class_yet(self):
        """It falls to 1.1 to 1.4, which are not written."""
        result = S2A.evaluate(ivd(is_specimen_receptacle=Tri.YES, is_self_test=Tri.YES))
        assert result.result is None
        assert "s2a-1.4 (not implemented)" in result.unresolved


# --------------------------------------------------------------------------
# 2. Precedence
# --------------------------------------------------------------------------


class TestPrecedence:
    def test_each_lookup_alone_is_confident(self):
        for _, field, rule_id, result, _ in LOOKUPS:
            outcome = S2A.evaluate(ivd(**{field: Tri.YES}))
            assert outcome.confident, field
            assert outcome.result == result
            assert [h.rule_id for h in outcome.governing] == [rule_id]

    def test_1_6_2_displaces_1_5_despite_the_lower_class(self):
        """Quality control material that is also an instrument: Class 1, not 2."""
        outcome = S2A.evaluate(ivd(is_quality_control_material=Tri.YES,
                                   is_ivd_instrument=Tri.YES))
        assert outcome.result == "Class 1 IVD"
        assert outcome.displaced == ["s2a-1.5"]
        assert {h.rule_id for h in outcome.hits} == {"s2a-1.5", "s2a-1.6(2)(a)"}

    def test_1_8_displaces_everything(self):
        outcome = S2A.evaluate(ivd(is_quality_control_material=Tri.YES,
                                   is_culture_medium=Tri.YES, is_export_only=Tri.YES))
        assert outcome.result == "Class 1 IVD"
        assert [h.rule_id for h in outcome.governing] == ["s2a-1.8"]
        assert set(outcome.displaced) == {"s2a-1.5", "s2a-1.6(2)(c)"}

    def test_highest_class_wins_among_hits_nothing_displaces(self):
        outcome = E.resolve([
            E.RuleHit("s2a-1.3", "c", "Class 3 IVD", "b"),
            E.RuleHit("s2a-1.4", "c", "Class 3 IVD", "b"),
            E.RuleHit("s2a-1.1", "c", "Class 4 IVD", "b"),
        ], IVD_ORDER)
        assert outcome.result == "Class 4 IVD"
        assert [h.rule_id for h in outcome.governing] == ["s2a-1.1"]

    def test_paragraphs_of_one_clause_share_its_displacement(self):
        assert E.clause_of("s2a-1.6(2)(a)") == "s2a-1.6"
        assert E.clause_of("s2-4.3(2)(a)") == "s2-4.3"
        assert E.clause_of("s2-2.2A") == "s2-2.2A"
        with pytest.raises(ValueError):
            E.clause_of("1.6")


# --------------------------------------------------------------------------
# 3. Blocking
# --------------------------------------------------------------------------


class TestBlocking:
    def test_an_unresolved_override_blocks_a_lower_clause(self):
        """1.8 could still displace 1.5, so 1.5 alone is not an answer."""
        outcome = S2A.evaluate(ivd(is_quality_control_material=Tri.YES,
                                   is_export_only=Answer()))
        assert outcome.result is None
        assert outcome.unresolved == ["ivd.is_export_only"]
        assert [h.rule_id for h in outcome.hits] == ["s2a-1.5"]

    def test_an_unresolved_clause_that_is_displaced_does_not_block(self):
        outcome = S2A.evaluate(ivd(is_export_only=Tri.YES, is_culture_medium=Answer(),
                                   is_quality_control_material=Answer()))
        assert outcome.confident
        assert outcome.result == "Class 1 IVD"

    def test_unwritten_clauses_block_when_no_lookup_applies(self):
        outcome = S2A.evaluate(ivd())
        assert outcome.result is None
        assert outcome.unresolved == [
            "s2a-1.1 (not implemented)", "s2a-1.2 (not implemented)",
            "s2a-1.3 (not implemented)", "s2a-1.4 (not implemented)",
            "s2a-1.7 (not implemented)",
        ]

    def test_1_5_displaces_the_unwritten_1_1_to_1_4(self):
        outcome = S2A.evaluate(ivd(is_quality_control_material=Tri.YES))
        assert outcome.confident

    def test_a_general_function_is_not_classified_yet(self):
        function = FunctionProfile(kind=stated(DeviceKind.GENERAL))
        outcome = E.classify_function(function)
        assert outcome.result is None
        assert outcome.unresolved


# --------------------------------------------------------------------------
# The lookup fixtures, directly
# --------------------------------------------------------------------------

LOOKUP_FIXTURES = [
    ("culture_media", 0),
    ("prothrombin_meter", 0),
    ("quality_control_material", 0),
    ("prothrombin_self_test_pack", 0),
]


@pytest.mark.parametrize("slug,index", LOOKUP_FIXTURES, ids=[f[0] for f in LOOKUP_FIXTURES])
def test_lookup_fixtures_agree(slug, index):
    data = json.loads((FIXTURES / f"{slug}.json").read_text())
    function = DeviceProfile.model_validate(data["profile"]).functions[index]
    expected = data["functions"][index]
    outcome = E.classify_function(function)
    assert outcome.confident
    assert outcome.result == expected["expected_class"]
    assert [h.rule_id for h in outcome.governing] == [f"s2a-{expected['expected_rule']}"]


# --------------------------------------------------------------------------
# 4. Docstrings against the Regulations
# --------------------------------------------------------------------------

SPEC = importlib.util.spec_from_file_location(
    "load_legislation", ROOT / "scripts" / "load_legislation.py"
)
L = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(L)

needs_source = pytest.mark.skipif(
    not L.SOURCE.exists(), reason=f"legislation source not downloaded: {L.SOURCE.name}"
)

WRITTEN = [S2A.rule_1_5, S2A.rule_1_6_2_a, S2A.rule_1_6_2_b, S2A.rule_1_6_2_c, S2A.rule_1_8]


def _flatten(text: str) -> str:
    text = re.sub(r"(?m)^[>\s]*(- )?", "", text)
    return " ".join(text.split())


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("legislation")
    L.write(L.SOURCE, out)
    return LEG.load(out)


@needs_source
@pytest.mark.parametrize("rule", WRITTEN, ids=[r.__name__ for r in WRITTEN])
def test_docstring_quotes_the_clause_verbatim(corpus, rule):
    heading, *paragraphs = inspect.getdoc(rule).split("\n\n")
    reference = heading.removeprefix("Schedule 2A clause ").rstrip(".")
    clause = corpus[E.clause_of(f"s2a-{reference}")]
    body = _flatten(clause.text)
    assert paragraphs, f"{rule.__name__} has no clause text"
    for paragraph in paragraphs:
        assert _flatten(paragraph) in body, f"{rule.__name__}: {paragraph!r}"


@needs_source
def test_every_rule_cites_a_clause_that_exists(corpus):
    for rule in S2A.ALL_RULES:
        outcome = rule(ivd(**{name: Tri.YES for name in EXCEPTIONS}))
        if outcome is not None:
            assert E.clause_of(outcome.rule_id) in corpus, rule.__name__
