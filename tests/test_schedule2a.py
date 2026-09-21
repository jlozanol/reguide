"""Tests for the Schedule 2A rules and the engine's precedence.

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
from reguide.flags import Severity
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


def ivd(**given) -> IvdProfile:
    """Every Schedule 2A field answered no, then the given ones overridden."""
    fields = {name: stated(Tri.NO) for name in IvdProfile.model_fields}
    fields.update({k: v if isinstance(v, Answer) else stated(v) for k, v in given.items()})
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

    def test_a_self_test_receptacle_falls_to_clause_1_4(self):
        result = S2A.evaluate(ivd(is_specimen_receptacle=Tri.YES, is_self_test=Tri.YES))
        assert result.result == "Class 3 IVD"
        assert [h.rule_id for h in result.governing] == ["s2a-1.4"]


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

    def test_the_unwritten_fallback_blocks_when_no_clause_applies(self):
        """1.6(1) and 1.7 are not written, so no clause means no class."""
        outcome = S2A.evaluate(ivd())
        assert outcome.result is None
        assert outcome.unresolved == ["s2a-1.7 (not implemented)"]

    def test_an_unanswered_gate_blocks_its_paragraphs(self):
        outcome = S2A.evaluate(ivd(detects_infectious_agent=Answer()))
        assert outcome.result is None
        assert outcome.unresolved[0] == "ivd.detects_infectious_agent"
        assert outcome.unresolved.count("ivd.detects_infectious_agent") == 1

    def test_1_5_displaces_unanswered_paragraphs_of_1_1_to_1_4(self):
        outcome = S2A.evaluate(ivd(is_quality_control_material=Tri.YES,
                                   detects_infectious_agent=Answer(), is_self_test=Answer()))
        assert outcome.confident
        assert outcome.result == "Class 2 IVD"

    def test_a_general_function_is_not_classified_yet(self):
        function = FunctionProfile(kind=stated(DeviceKind.GENERAL))
        outcome = E.classify_function(function)
        assert outcome.result is None
        assert outcome.unresolved


# --------------------------------------------------------------------------
# Clauses 1.1 to 1.4
# --------------------------------------------------------------------------

AGENT = "detects_infectious_agent"
TYPING = "types_blood_or_tissue"

PARAGRAPHS = [
    (S2A.rule_1_1_a, "screens_donations_for_transmissible_agents", AGENT, "s2a-1.1(a)",
     "Class 4 IVD"),
    (S2A.rule_1_1_b, "agent_serious_with_high_propagation_risk", AGENT, "s2a-1.1(b)",
     "Class 4 IVD"),
    (S2A.rule_1_2_2, "detects_listed_blood_group_marker", TYPING, "s2a-1.2(2)", "Class 4 IVD"),
    (S2A.rule_1_3_a, "detects_sexually_transmitted_agent", AGENT, "s2a-1.3(a)", "Class 3 IVD"),
    (S2A.rule_1_3_b, "detects_limited_propagation_agent_in_csf_or_blood", AGENT, "s2a-1.3(b)",
     "Class 3 IVD"),
    (S2A.rule_1_3_c, "error_could_cause_death_or_severe_disability", AGENT, "s2a-1.3(c)",
     "Class 3 IVD"),
    (S2A.rule_1_3_d, "prenatal_immune_status_screening", AGENT, "s2a-1.3(d)", "Class 3 IVD"),
    (S2A.rule_1_3_e, "infective_status_error_life_threatening", AGENT, "s2a-1.3(e)",
     "Class 3 IVD"),
    (S2A.rule_1_3_f_i, "selects_patients_for_therapy", None, "s2a-1.3(f)(i)", "Class 3 IVD"),
    (S2A.rule_1_3_f_ii, "selects_patients_for_disease_staging", None, "s2a-1.3(f)(ii)",
     "Class 3 IVD"),
    (S2A.rule_1_3_f_iii, "selects_patients_in_cancer_diagnosis", None, "s2a-1.3(f)(iii)",
     "Class 3 IVD"),
    (S2A.rule_1_3_fa, "is_companion_diagnostic", None, "s2a-1.3(fa)", "Class 3 IVD"),
    (S2A.rule_1_3_g, "is_human_genetic_test", None, "s2a-1.3(g)", "Class 3 IVD"),
    (S2A.rule_1_3_h, "monitors_levels_error_life_threatening", None, "s2a-1.3(h)", "Class 3 IVD"),
    (S2A.rule_1_3_i, "manages_life_threatening_infectious_disease", AGENT, "s2a-1.3(i)",
     "Class 3 IVD"),
    (S2A.rule_1_3_j, "screens_foetus_for_congenital_disorders", None, "s2a-1.3(j)", "Class 3 IVD"),
]


def _open(gate):
    return {gate: Tri.YES} if gate else {}


@pytest.mark.parametrize("rule,field,gate,rule_id,result", PARAGRAPHS,
                         ids=[p[3] for p in PARAGRAPHS])
class TestParagraph:
    def test_yes_behind_an_open_gate_fires(self, rule, field, gate, rule_id, result):
        hit = rule(ivd(**_open(gate), **{field: Tri.YES}))
        assert isinstance(hit, E.RuleHit)
        assert (hit.rule_id, hit.result) == (rule_id, result)
        assert hit.citation.endswith(f"Schedule 2A clause {rule_id.removeprefix('s2a-')}")
        assert f"{field} is yes" in hit.because

    def test_no_is_silent(self, rule, field, gate, rule_id, result):
        assert rule(ivd(**_open(gate))) is None

    def test_unanswered_is_pending(self, rule, field, gate, rule_id, result):
        pending = rule(ivd(**_open(gate), **{field: Answer()}))
        assert isinstance(pending, E.Pending)
        assert pending.fields == (f"ivd.{field}",)



GATED = [p for p in PARAGRAPHS if p[2] is not None]


@pytest.mark.parametrize("rule,field,gate,rule_id,result", GATED, ids=[p[3] for p in GATED])
class TestGate:
    def test_a_closed_gate_silences_it_without_asking(self, rule, field, gate, rule_id, result):
        assert rule(ivd(**{gate: Tri.NO, field: Answer()})) is None

    def test_an_unanswered_gate_is_pending_on_the_gate(self, rule, field, gate, rule_id,
                                                       result):
        pending = rule(ivd(**{gate: Answer(), field: Tri.YES}))
        assert pending.fields == (f"ivd.{gate}",)


class TestClause12:
    def test_compatibility_alone_is_class_3(self):
        outcome = S2A.evaluate(ivd(types_blood_or_tissue=Tri.YES,
                                   assesses_transfusion_or_transplant_compatibility=Tri.YES))
        assert outcome.result == "Class 3 IVD"
        assert [h.rule_id for h in outcome.governing] == ["s2a-1.2(1)"]

    def test_a_listed_marker_is_class_4_and_leaves_1_2_1_out(self):
        """Paragraph 1.2(1)(b): not a device mentioned in subclause (2)."""
        outcome = S2A.evaluate(ivd(types_blood_or_tissue=Tri.YES,
                                   assesses_transfusion_or_transplant_compatibility=Tri.YES,
                                   detects_listed_blood_group_marker=Tri.YES))
        assert outcome.result == "Class 4 IVD"
        assert [h.rule_id for h in outcome.hits] == ["s2a-1.2(2)"]

    def test_an_unanswered_marker_question_blocks_1_2_1(self):
        pending = S2A.rule_1_2_1(ivd(types_blood_or_tissue=Tri.YES,
                                     assesses_transfusion_or_transplant_compatibility=Tri.YES,
                                     detects_listed_blood_group_marker=Answer()))
        assert pending.fields == ("ivd.detects_listed_blood_group_marker",)


class TestClause14:
    def test_self_testing_is_class_3(self):
        hit = S2A.rule_1_4(ivd(is_self_test=Tri.YES))
        assert (hit.rule_id, hit.result) == ("s2a-1.4", "Class 3 IVD")
        assert hit.citation.endswith("Schedule 2A clause 1.4")

    @pytest.mark.parametrize("exception", ["result_not_determining_serious_condition",
                                           "preliminary_with_follow_up_testing"])
    def test_either_exception_takes_it_out(self, exception):
        assert S2A.rule_1_4(ivd(is_self_test=Tri.YES, **{exception: Tri.YES})) is None

    def test_an_excepted_self_test_gets_no_class_until_1_7_is_written(self):
        outcome = S2A.evaluate(ivd(is_self_test=Tri.YES,
                                   preliminary_with_follow_up_testing=Tri.YES))
        assert outcome.result is None
        assert outcome.unresolved == ["s2a-1.7 (not implemented)"]

    def test_an_unanswered_exception_is_pending(self):
        pending = S2A.rule_1_4(ivd(is_self_test=Tri.YES,
                                   result_not_determining_serious_condition=Answer()))
        assert pending.fields == ("ivd.result_not_determining_serious_condition",)

    def test_not_a_self_test_is_silent(self):
        assert S2A.rule_1_4(ivd()) is None


class TestOrdinaryPrecedence:
    def test_the_highest_paragraph_wins(self):
        """An HIV self-test: 1.1(b) Class 4 over 1.4 Class 3, regulation 3.3(7)."""
        outcome = S2A.evaluate(ivd(detects_infectious_agent=Tri.YES,
                                   agent_serious_with_high_propagation_risk=Tri.YES,
                                   is_self_test=Tri.YES))
        assert outcome.result == "Class 4 IVD"
        assert [h.rule_id for h in outcome.governing] == ["s2a-1.1(b)"]
        assert "s2a-1.4" in [h.rule_id for h in outcome.hits]
        assert outcome.displaced == []

    def test_every_paragraph_at_the_top_class_is_cited(self):
        outcome = S2A.evaluate(ivd(detects_infectious_agent=Tri.YES,
                                   detects_sexually_transmitted_agent=Tri.YES,
                                   is_human_genetic_test=Tri.YES))
        assert [h.rule_id for h in outcome.governing] == ["s2a-1.3(a)", "s2a-1.3(g)"]

    def test_a_despite_clause_still_beats_a_higher_paragraph(self):
        """Quality control material for an STI assay: 1.5 displaces 1.3, Class 2."""
        outcome = S2A.evaluate(ivd(is_quality_control_material=Tri.YES,
                                   detects_infectious_agent=Tri.YES,
                                   detects_sexually_transmitted_agent=Tri.YES))
        assert outcome.result == "Class 2 IVD"
        assert outcome.displaced == ["s2a-1.3(a)"]


class TestNoteTo13f:
    def test_the_note_is_flagged_when_1_3_f_alone_decides(self):
        outcome = S2A.evaluate(ivd(selects_patients_for_therapy=Tri.YES))
        assert outcome.result == "Class 3 IVD"
        assert [f.code for f in outcome.flags] == ["s2a_1_3f_note"]
        assert outcome.flags[0].severity is Severity.AMBER

    def test_no_flag_for_a_companion_diagnostic(self):
        outcome = S2A.evaluate(ivd(selects_patients_for_therapy=Tri.YES,
                                   is_companion_diagnostic=Tri.YES))
        assert outcome.flags == []

    def test_no_flag_when_another_paragraph_gives_the_same_class(self):
        outcome = S2A.evaluate(ivd(selects_patients_for_disease_staging=Tri.YES,
                                   is_human_genetic_test=Tri.YES))
        assert outcome.flags == []

    def test_no_flag_when_a_higher_class_governs(self):
        outcome = S2A.evaluate(ivd(selects_patients_in_cancer_diagnosis=Tri.YES,
                                   types_blood_or_tissue=Tri.YES,
                                   detects_listed_blood_group_marker=Tri.YES))
        assert outcome.result == "Class 4 IVD"
        assert outcome.flags == []

    def test_classify_stamps_the_function_index(self):
        function = FunctionProfile(kind=stated(DeviceKind.IVD),
                                   ivd=ivd(selects_patients_for_therapy=Tri.YES))
        profile = DeviceProfile(functions=[FunctionProfile(kind=stated(DeviceKind.GENERAL)),
                                           function])
        outcome = E.classify(profile, [1])[1]
        assert outcome.flags[0].functions == (1,)


# --------------------------------------------------------------------------
# The lookup fixtures, directly
# --------------------------------------------------------------------------

LOOKUP_FIXTURES = [
    ("culture_media", 0),
    ("prothrombin_meter", 0),
    ("quality_control_material", 0),
    ("prothrombin_self_test_pack", 0),
    ("prothrombin_self_test_pack", 1),
    ("prothrombin_self_test", 0),
    ("chlamydia_test", 0),
    ("hiv_donor_screening", 0),
    ("abo_reagent_red_cells", 0),
]


@pytest.mark.parametrize("slug,index", LOOKUP_FIXTURES,
                         ids=[f"{f[0]}-{f[1]}" for f in LOOKUP_FIXTURES])
def test_ivd_fixtures_agree(slug, index):
    data = json.loads((FIXTURES / f"{slug}.json").read_text())
    function = DeviceProfile.model_validate(data["profile"]).functions[index]
    expected = data["functions"][index]
    outcome = E.classify_function(function)
    assert outcome.confident
    assert outcome.result == expected["expected_class"]
    assert f"s2a-{expected['expected_rule']}" in [h.rule_id for h in outcome.governing]


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

WRITTEN = S2A.ALL_RULES


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
