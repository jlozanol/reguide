"""Tests for Schedule 2 Part 2 (non-invasive devices) and the unwritten Parts.

Four things are being tested:

1. Each paragraph of 2.1 to 2.4 fires on its conditions, stays silent when a
   condition is no or the device is not non-invasive, and reports anything
   unresolved as Pending, never as a no.
2. The "subject to" structure: 2.3(1) gives way to 2.3(2), and 2.4(2) gives
   way to 2.4(3) and 2.4(4). When 2.4(3) and 2.4(4) both apply, 2.4(4)
   governs as the higher class.
3. Parts 3, 4 and 5 block a result only where they could apply.
4. Every docstring quotes its clause verbatim, checked against the clause
   files split from the real Regulations. Skipped without the source.
"""

import importlib.util
import inspect
import json
import re
from pathlib import Path

import pytest

from reguide import legislation as LEG
from reguide.profile import (
    GENERAL_ORDER,
    ActiveType,
    Answer,
    Basis,
    DeviceKind,
    DeviceProfile,
    FunctionProfile,
    GeneralDeviceProfile,
    Invasiveness,
    Tri,
)
from reguide.rules import engine as E
from reguide.rules import schedule2 as S2

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

PART_2_FIELDS = [
    "handles_substances_for_administration",
    "channels_or_stores_blood_for_administration",
    "stores_organ_or_tissue_for_introduction",
    "channels_or_stores_liquid_or_gas_for_administration",
    "connected_to_active_device",
    "saline_only_flush_or_patency",
    "modifies_composition_of_blood_or_infusion",
    "treatment_is_filtration_centrifugation_or_exchange",
    "contacts_injured_skin_or_mucous_membrane",
    "barrier_compression_or_absorption",
    "principally_for_breached_dermis_secondary_intent",
]


def stated(value, evidence="test evidence"):
    return Answer(value=value, basis=Basis.STATED, evidence=evidence)


def general(**given) -> GeneralDeviceProfile:
    """A non-invasive, non-active device with every Part 2 field answered no."""
    fields = {name: stated(Tri.NO) for name in PART_2_FIELDS}
    fields["invasiveness"] = stated(Invasiveness.NON_INVASIVE)
    fields["active_type"] = stated(ActiveType.NOT_ACTIVE)
    fields.update({k: v if isinstance(v, Answer) else stated(v) for k, v in given.items()})
    return GeneralDeviceProfile(**fields)


def function(software=Tri.NO, **given) -> FunctionProfile:
    return FunctionProfile(kind=stated(DeviceKind.GENERAL), is_software=stated(software),
                           general=general(**given))


def part_2(g: GeneralDeviceProfile) -> E.Classification:
    """Part 2 alone, so the governing paragraph is visible while Part 5 waits."""
    return E.resolve([rule(g) for rule in S2.PART_2], GENERAL_ORDER)


SUBSTANCES = "handles_substances_for_administration"
WOUND = "contacts_injured_skin_or_mucous_membrane"

# rule, the answers that make it fire, rule id, class
PARAGRAPHS = [
    (S2.rule_2_1, {}, "s2-2.1", "Class I"),
    (S2.rule_2_2_1_a, {SUBSTANCES: Tri.YES, "channels_or_stores_blood_for_administration": Tri.YES},
     "s2-2.2(1)(a)", "Class IIa"),
    (S2.rule_2_2_1_b, {SUBSTANCES: Tri.YES, "stores_organ_or_tissue_for_introduction": Tri.YES},
     "s2-2.2(1)(b)", "Class IIa"),
    (S2.rule_2_2_1_c, {SUBSTANCES: Tri.YES,
                       "channels_or_stores_liquid_or_gas_for_administration": Tri.YES,
                       "connected_to_active_device": Tri.YES}, "s2-2.2(1)(c)", "Class IIa"),
    (S2.rule_2_2A, {SUBSTANCES: Tri.YES, "saline_only_flush_or_patency": Tri.YES},
     "s2-2.2A", "Class IIa"),
    (S2.rule_2_3_1, {SUBSTANCES: Tri.YES, "modifies_composition_of_blood_or_infusion": Tri.YES},
     "s2-2.3(1)", "Class IIb"),
    (S2.rule_2_3_2, {SUBSTANCES: Tri.YES, "modifies_composition_of_blood_or_infusion": Tri.YES,
                     "treatment_is_filtration_centrifugation_or_exchange": Tri.YES},
     "s2-2.3(2)", "Class IIa"),
    (S2.rule_2_4_2, {WOUND: Tri.YES}, "s2-2.4(2)", "Class IIa"),
    (S2.rule_2_4_3, {WOUND: Tri.YES, "barrier_compression_or_absorption": Tri.YES},
     "s2-2.4(3)", "Class I"),
    (S2.rule_2_4_4, {WOUND: Tri.YES, "principally_for_breached_dermis_secondary_intent": Tri.YES},
     "s2-2.4(4)", "Class IIb"),
]
IDS = [p[2] for p in PARAGRAPHS]


# --------------------------------------------------------------------------
# 1. Each paragraph
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rule,answers,rule_id,result", PARAGRAPHS, ids=IDS)
class TestParagraph:
    def test_fires_and_cites_its_paragraph(self, rule, answers, rule_id, result):
        hit = rule(general(**answers))
        assert isinstance(hit, E.RuleHit)
        assert (hit.rule_id, hit.result) == (rule_id, result)
        assert hit.citation == ("Therapeutic Goods (Medical Devices) Regulations 2002 "
                                f"Schedule 2 clause {rule_id.removeprefix('s2-')}")
        assert "invasiveness is non_invasive" in hit.because

    def test_an_invasive_device_is_outside_part_2(self, rule, answers, rule_id, result):
        g = general(**answers, invasiveness=Invasiveness.SURGICALLY_INVASIVE)
        assert rule(g) is None

    def test_an_unknown_route_is_pending(self, rule, answers, rule_id, result):
        pending = rule(general(**answers, invasiveness=Answer()))
        assert isinstance(pending, E.Pending)
        assert pending.fields == ("general.invasiveness",)

    def test_each_condition_answered_no_silences_it(self, rule, answers, rule_id, result):
        for name in answers:
            assert rule(general(**{**answers, name: Tri.NO})) is None, name

    def test_each_condition_unanswered_is_pending_on_that_field(self, rule, answers, rule_id,
                                                               result):
        for name in answers:
            pending = rule(general(**{**answers, name: Answer()}))
            assert isinstance(pending, E.Pending), name
            assert pending.fields == (f"general.{name}",)


def test_2_2_1_a_needs_no_active_device():
    """Blood for administration is Class IIa on its own; only (c) needs one."""
    hit = S2.rule_2_2_1_a(general(**{SUBSTANCES: Tri.YES,
                                     "channels_or_stores_blood_for_administration": Tri.YES,
                                     "connected_to_active_device": Answer()}))
    assert isinstance(hit, E.RuleHit)


def test_a_closed_gate_never_asks_its_paragraphs():
    g = general(**{name: Answer() for name in PART_2_FIELDS
                   if name not in (SUBSTANCES, WOUND)})
    outcome = part_2(g)
    assert outcome.unresolved == []
    assert outcome.result == "Class I"


# --------------------------------------------------------------------------
# 2. "Subject to"
# --------------------------------------------------------------------------


class TestSubjectTo:
    def test_2_3_1_gives_way_to_2_3_2(self):
        outcome = part_2(general(**{SUBSTANCES: Tri.YES,
                                    "modifies_composition_of_blood_or_infusion": Tri.YES,
                                    "treatment_is_filtration_centrifugation_or_exchange": Tri.YES}))
        assert outcome.result == "Class IIa"
        assert "s2-2.3(1)" not in [h.rule_id for h in outcome.hits]

    def test_2_4_2_is_the_default_when_neither_3_nor_4_applies(self):
        outcome = part_2(general(**{WOUND: Tri.YES}))
        assert outcome.result == "Class IIa"
        assert [h.rule_id for h in outcome.governing] == ["s2-2.4(2)"]

    def test_2_4_3_takes_the_device_to_class_i(self):
        outcome = part_2(general(**{WOUND: Tri.YES, "barrier_compression_or_absorption": Tri.YES}))
        assert outcome.result == "Class I"
        assert "s2-2.4(2)" not in [h.rule_id for h in outcome.hits]

    def test_2_4_4_prevails_over_2_4_3(self):
        """An absorbent dressing for a secondary-intent wound: Class IIb."""
        outcome = part_2(general(**{WOUND: Tri.YES, "barrier_compression_or_absorption": Tri.YES,
                                    "principally_for_breached_dermis_secondary_intent": Tri.YES}))
        assert outcome.result == "Class IIb"
        assert [h.rule_id for h in outcome.governing] == ["s2-2.4(4)"]
        assert "s2-2.4(3)" in [h.rule_id for h in outcome.hits]

    def test_2_4_2_waits_for_an_unanswered_3_or_4(self):
        pending = S2.rule_2_4_2(general(**{WOUND: Tri.YES,
                                           "barrier_compression_or_absorption": Answer()}))
        assert pending.fields == ("general.barrier_compression_or_absorption",)

    def test_the_floor_and_a_higher_paragraph(self):
        outcome = part_2(general(**{SUBSTANCES: Tri.YES,
                                    "modifies_composition_of_blood_or_infusion": Tri.YES}))
        assert outcome.result == "Class IIb"
        assert {h.rule_id for h in outcome.hits} == {"s2-2.1", "s2-2.3(1)"}


# --------------------------------------------------------------------------
# 3. The unwritten Parts
# --------------------------------------------------------------------------


class TestUnwrittenParts:
    def test_part_3_waits_only_for_an_invasive_route(self):
        assert S2.part_3(function()) is None
        pending = S2.part_3(function(invasiveness=Invasiveness.BODY_ORIFICE))
        assert pending.reason.startswith("not implemented")
        assert S2.part_3(function(invasiveness=Answer())).fields == ("general.invasiveness",)

    def test_part_4_waits_only_for_an_active_device_or_software(self):
        assert S2.part_4(function()) is None
        assert S2.part_4(function(active_type=ActiveType.THERAPEUTIC)).reason.startswith(
            "not implemented")
        assert S2.part_4(function(software=Tri.YES)).reason.startswith("not implemented")
        unknown = S2.part_4(function(active_type=Answer()))
        assert unknown.fields == ("general.active_type",)

    def test_part_5_always_waits(self):
        assert S2.part_5(function()).reason.startswith("not implemented")

    def test_a_non_invasive_passive_device_waits_only_for_part_5(self):
        outcome = S2.evaluate(function(**{WOUND: Tri.YES,
                                          "barrier_compression_or_absorption": Tri.YES}))
        assert outcome.result is None
        assert outcome.unresolved == ["s2-5.1 (not implemented: Part 5, clauses 5.1 to 5.11)"]

    def test_classify_function_routes_general_devices_here(self):
        outcome = E.classify_function(function())
        assert "s2-2.1" in [h.rule_id for h in outcome.hits]


# --------------------------------------------------------------------------
# Part 2 against the answer key
# --------------------------------------------------------------------------

DECIDED_BY_PART_2 = [
    "dressing_mechanical_barrier",
    "dressing_microenvironment",
    "dressing_secondary_intent",
    "sterile_barrier_dressing",
    "measuring_thermometer",
    "infusion_pump_syringe",
    "haemodialyser",
]


@pytest.mark.parametrize("slug", DECIDED_BY_PART_2)
def test_part_2_matches_the_fixtures_it_decides(slug):
    """What Part 2 alone concludes, once Part 5 no longer blocks it."""
    data = json.loads((FIXTURES / f"{slug}.json").read_text())
    profile = DeviceProfile.model_validate(data["profile"])
    expected = data["functions"][0]
    outcome = part_2(profile.functions[0].general)
    assert outcome.confident
    assert outcome.result == expected["expected_class"]
    assert f"s2-{expected['expected_rule']}" in [h.rule_id for h in outcome.governing]


def test_the_collagen_dressing_reaches_2_4_4_and_waits_for_5_5():
    data = json.loads((FIXTURES / "dressing_collagen_deep_wound.json").read_text())
    profile = DeviceProfile.model_validate(data["profile"])
    outcome = E.classify_function(profile.functions[0])
    assert "s2-2.4(4)" in [h.rule_id for h in outcome.hits]
    assert outcome.result is None


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


def _flatten(text: str) -> str:
    text = re.sub(r"(?m)^[>\s]*(- )?", "", text)
    return " ".join(text.split())


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("legislation")
    L.write(L.SOURCE, out)
    return LEG.load(out)


@needs_source
@pytest.mark.parametrize("rule", S2.PART_2, ids=[r.__name__ for r in S2.PART_2])
def test_docstring_quotes_the_clause_verbatim(corpus, rule):
    heading, *paragraphs = inspect.getdoc(rule).split("\n\n")
    reference = heading.removeprefix("Schedule 2 clause ").rstrip(".")
    clause = corpus[E.clause_of(f"s2-{reference}")]
    body = _flatten(clause.text)
    assert paragraphs, f"{rule.__name__} has no clause text"
    for paragraph in paragraphs:
        assert _flatten(paragraph) in body, f"{rule.__name__}: {paragraph!r}"
