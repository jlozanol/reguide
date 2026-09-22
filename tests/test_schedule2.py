"""Tests for Schedule 2 Parts 2, 3 and 5, and the unwritten Part 4.

Six things are being tested:

1. Each paragraph of 2.1 to 2.4 fires on its conditions, stays silent when a
   condition is no or the device is not non-invasive, and reports anything
   unresolved as Pending, never as a no.
2. The "subject to" structure: 2.3(1) gives way to 2.3(2), and 2.4(2) gives
   way to 2.4(3) and 2.4(4). When 2.4(3) and 2.4(4) both apply, 2.4(4)
   governs as the higher class.
3. Each Part 5 clause, its applicability (software, route, active), 5.8
   displacing everything, and the 5.5(2) no-contact flag.
4. Each Part 3 paragraph by route and duration band, the "subject to"
   defaults, the 5.10/5.11 exclusion from 3.1 and the Class I connection
   gap in 3.1.
5. Part 4 blocks a result only where it could apply.
6. Every docstring quotes its clause verbatim, checked against the clause
   files split from the real Regulations. Skipped without the source. The
   rules write the clause's em dashes as spaced en dashes; the check treats
   them as the same.
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


PART_5_FIELDS = [
    "is_export_only", "incorporates_medicine", "human_blood_derivative",
    "contraceptive_or_sti_prevention", "cares_for_contact_lenses",
    "disinfects_another_device", "records_images_or_anatomical_model",
    "records_patient_images_outside_visible_spectrum", "is_anatomical_model_for_diagnosis",
    "generates_virtual_anatomical_model", "contains_non_viable_animal_material",
    "contacts_intact_skin_only", "is_blood_bag", "is_active_implantable",
    "implantable_accessory_to_active_implantable", "controls_active_implantable",
    "is_mammary_implant", "administers_by_inhalation", "inhalation_mode_of_action_essential",
    "inhalation_treats_life_threatening_condition", "is_substance_through_orifice_or_skin",
    "substance_acts_in_nose_mouth_or_on_skin",
]


PART_3_FIELDS = [
    "connected_to_an_active_device", "liable_to_be_absorbed_by_mucous_membrane",
    "corrects_heart_or_circulatory_defect_by_contact",
    "direct_contact_heart_circulation_or_nervous_system", "reusable_surgical_instrument",
    "delivers_ionising_radiation", "has_biological_effect", "wholly_or_mostly_absorbed",
    "undergoes_chemical_change", "placed_in_teeth",
    "administers_medicine_hazardously_by_delivery_system", "administers_medicine",
    "joint_replacement_or_surgical_mesh", "spinal_motion_preserving",
]


def general(**given) -> GeneralDeviceProfile:
    """A non-invasive, non-active device with every Part 2, 3 and 5 field answered no."""
    fields = {name: stated(Tri.NO) for name in PART_2_FIELDS + PART_3_FIELDS + PART_5_FIELDS}
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
    def test_part_4_waits_only_for_an_active_device_or_software(self):
        assert S2.part_4(function()) is None
        assert S2.part_4(function(active_type=ActiveType.THERAPEUTIC)).reason.startswith(
            "not implemented")
        assert S2.part_4(function(software=Tri.YES)).reason.startswith("not implemented")
        unknown = S2.part_4(function(active_type=Answer()))
        assert unknown.fields == ("general.active_type",)

    def test_a_non_invasive_passive_device_is_classified(self):
        outcome = S2.evaluate(function(**{WOUND: Tri.YES,
                                          "barrier_compression_or_absorption": Tri.YES}))
        assert outcome.confident
        assert outcome.result == "Class I"

    def test_an_invasive_passive_device_is_classified(self):
        outcome = S2.evaluate(function(invasiveness=Invasiveness.SURGICALLY_INVASIVE,
                                       duration="long_term"))
        assert outcome.confident
        assert outcome.result == "Class IIb"

    def test_classify_function_routes_general_devices_here(self):
        outcome = E.classify_function(function())
        assert "s2-2.1" in [h.rule_id for h in outcome.hits]


# --------------------------------------------------------------------------
# Part 5
# --------------------------------------------------------------------------

LOOKUPS_5 = [
    (S2.rule_5_1, {"incorporates_medicine": Tri.YES}, "s2-5.1(2)", "Class III"),
    (S2.rule_5_1, {"human_blood_derivative": Tri.YES}, "s2-5.1(2)", "Class III"),
    (S2.rule_5_2_1, {"contraceptive_or_sti_prevention": Tri.YES}, "s2-5.2(1)", "Class IIb"),
    (S2.rule_5_3_1, {"cares_for_contact_lenses": Tri.YES}, "s2-5.3(1)", "Class IIb"),
    (S2.rule_5_3_2, {"disinfects_another_device": Tri.YES}, "s2-5.3(2)", "Class IIb"),
    (S2.rule_5_4_1, {"records_images_or_anatomical_model": Tri.YES,
                     "records_patient_images_outside_visible_spectrum": Tri.YES},
     "s2-5.4(1)", "Class IIa"),
    (S2.rule_5_4_2, {"records_images_or_anatomical_model": Tri.YES,
                     "is_anatomical_model_for_diagnosis": Tri.YES}, "s2-5.4(2)", "Class IIa"),
    (S2.rule_5_5, {"contains_non_viable_animal_material": Tri.YES}, "s2-5.5(3)", "Class III"),
    (S2.rule_5_6, {"is_blood_bag": Tri.YES}, "s2-5.6", "Class IIb"),
    (S2.rule_5_8, {"is_export_only": Tri.YES}, "s2-5.8", "Class I"),
    (S2.rule_5_10_a, {"administers_by_inhalation": Tri.YES,
                      "inhalation_mode_of_action_essential": Tri.YES}, "s2-5.10(a)", "Class IIb"),
    (S2.rule_5_10_b, {"administers_by_inhalation": Tri.YES,
                      "inhalation_treats_life_threatening_condition": Tri.YES},
     "s2-5.10(b)", "Class IIb"),
    (S2.rule_5_10_c, {"administers_by_inhalation": Tri.YES}, "s2-5.10(c)", "Class IIa"),
    (S2.rule_5_11_c, {"is_substance_through_orifice_or_skin": Tri.YES,
                      "substance_acts_in_nose_mouth_or_on_skin": Tri.YES},
     "s2-5.11(c)", "Class IIa"),
    (S2.rule_5_11_d, {"is_substance_through_orifice_or_skin": Tri.YES}, "s2-5.11(d)",
     "Class IIb"),
]


@pytest.mark.parametrize("rule,answers,rule_id,result", LOOKUPS_5,
                         ids=[f"{p[2]}-{next(iter(p[1]))}" for p in LOOKUPS_5])
class TestPart5:
    def test_fires_and_cites_its_paragraph(self, rule, answers, rule_id, result):
        hit = rule(function(**answers))
        assert isinstance(hit, E.RuleHit)
        assert (hit.rule_id, hit.result) == (rule_id, result)

    def test_silent_when_every_answer_is_no(self, rule, answers, rule_id, result):
        assert rule(function()) is None

    def test_an_unanswered_trigger_is_pending(self, rule, answers, rule_id, result):
        name = list(answers)[-1]
        pending = rule(function(**{**answers, name: Answer()}))
        assert isinstance(pending, E.Pending)
        assert pending.fields == (f"general.{name}",)


MATERIAL_RULES = [S2.rule_5_5, S2.rule_5_6, S2.rule_5_10_a, S2.rule_5_10_c, S2.rule_5_11_d]


@pytest.mark.parametrize("rule", MATERIAL_RULES, ids=[r.__name__ for r in MATERIAL_RULES])
def test_material_clauses_are_silent_for_software(rule):
    everything = {name: Tri.YES for name in PART_5_FIELDS}
    everything.update(contacts_intact_skin_only=Tri.NO,
                      substance_acts_in_nose_mouth_or_on_skin=Tri.NO,
                      inhalation_mode_of_action_essential=Tri.NO,
                      inhalation_treats_life_threatening_condition=Tri.NO)
    assert rule(function(software=Tri.YES, **everything)) is None


class TestClause52:
    def test_a_transient_orifice_device_is_5_2_1(self):
        f = function(contraceptive_or_sti_prevention=Tri.YES,
                     invasiveness=Invasiveness.BODY_ORIFICE, duration="transient")
        assert S2.rule_5_2_1(f).result == "Class IIb"
        assert S2.rule_5_2_2(f) is None

    @pytest.mark.parametrize("route,duration", [
        (Invasiveness.IMPLANTABLE, "long_term"),
        (Invasiveness.BODY_ORIFICE, "long_term"),
    ])
    def test_implantable_or_long_term_invasive_is_5_2_2(self, route, duration):
        f = function(contraceptive_or_sti_prevention=Tri.YES, invasiveness=route,
                     duration=duration)
        assert S2.rule_5_2_2(f).result == "Class III"
        assert S2.rule_5_2_1(f) is None

    def test_an_unknown_duration_blocks_both(self):
        f = function(contraceptive_or_sti_prevention=Tri.YES,
                     invasiveness=Invasiveness.BODY_ORIFICE, duration=Answer())
        assert S2.rule_5_2_1(f).fields == ("general.duration",)
        assert S2.rule_5_2_2(f).fields == ("general.duration",)


class TestApplicability:
    def test_implant_clauses_need_the_implantable_route(self):
        for rule, field in [(S2.rule_5_7_1, "is_active_implantable"),
                            (S2.rule_5_7_2, "implantable_accessory_to_active_implantable"),
                            (S2.rule_5_9, "is_mammary_implant")]:
            assert rule(function(**{field: Tri.YES})) is None, rule.__name__
            hit = rule(function(**{field: Tri.YES}, invasiveness=Invasiveness.IMPLANTABLE,
                                duration="long_term"))
            assert hit.result == "Class III", rule.__name__

    def test_5_7_3_needs_an_active_device_or_software(self):
        assert S2.rule_5_7_3(function(controls_active_implantable=Tri.YES)) is None
        hit = S2.rule_5_7_3(function(controls_active_implantable=Tri.YES,
                                     active_type=ActiveType.THERAPEUTIC))
        assert (hit.rule_id, hit.result) == ("s2-5.7(3)", "Class III")
        assert S2.rule_5_7_3(function(software=Tri.YES, controls_active_implantable=Tri.YES))

    def test_5_4_3_is_software_only(self):
        answers = {"records_images_or_anatomical_model": Tri.YES,
                   "generates_virtual_anatomical_model": Tri.YES}
        assert S2.rule_5_4_3(function(**answers)) is None
        assert S2.rule_5_4_3(function(software=Tri.YES, **answers)).result == "Class IIa"

    def test_intact_skin_only_takes_a_device_outside_5_5(self):
        """5.5(2): leather straps on a limb prosthesis."""
        f = function(contains_non_viable_animal_material=Tri.YES,
                     contacts_intact_skin_only=Tri.YES)
        assert S2.rule_5_5(f) is None


class TestExportOnly:
    def test_5_8_displaces_every_other_clause(self):
        outcome = S2.evaluate(function(is_export_only=Tri.YES, incorporates_medicine=Tri.YES,
                                       invasiveness=Invasiveness.IMPLANTABLE,
                                       duration="long_term", is_mammary_implant=Tri.YES))
        assert outcome.result == "Class I"
        assert outcome.confident
        assert [h.rule_id for h in outcome.governing] == ["s2-5.8"]
        assert set(outcome.displaced) >= {"s2-5.1(2)", "s2-5.9"}

    def test_5_8_also_clears_the_unwritten_parts(self):
        outcome = S2.evaluate(function(is_export_only=Tri.YES, software=Tri.YES,
                                       active_type=ActiveType.DIAGNOSTIC))
        assert outcome.unresolved == []


class TestNoContactFlag:
    def test_animal_material_with_no_patient_contact_is_flagged(self):
        outcome = S2.evaluate(function(contains_non_viable_animal_material=Tri.YES))
        assert outcome.result == "Class III"
        assert [f.code for f in outcome.flags] == ["s2_5_5_no_patient_contact"]

    def test_no_flag_when_the_device_contacts_injured_skin(self):
        outcome = S2.evaluate(function(contains_non_viable_animal_material=Tri.YES,
                                       **{WOUND: Tri.YES}))
        assert outcome.flags == []


# --------------------------------------------------------------------------
# Part 3
# --------------------------------------------------------------------------


def orifice(duration, site="other_body_orifice", **given):
    return function(invasiveness=Invasiveness.BODY_ORIFICE, duration=duration,
                    orifice_site=site, **given)


def surgical(duration, **given):
    return function(invasiveness=Invasiveness.SURGICALLY_INVASIVE, duration=duration, **given)


def governing(f):
    outcome = S2.evaluate(f)
    return outcome.result, [h.rule_id for h in outcome.governing], outcome


class TestClause31:
    @pytest.mark.parametrize("duration,site,rule_id,result", [
        ("transient", "other_body_orifice", "s2-3.1(2)(a)", "Class I"),
        ("short_term", "other_body_orifice", "s2-3.1(2)(b)(i)", "Class IIa"),
        ("short_term", "oral_cavity_as_far_as_pharynx", "s2-3.1(2)(b)(ii)", "Class I"),
        ("short_term", "nasal_cavity", "s2-3.1(2)(b)(ii)", "Class I"),
        ("long_term", "other_body_orifice", "s2-3.1(2)(c)(i)", "Class IIb"),
        ("long_term", "stoma", "s2-3.1(2)(c)(i)", "Class IIb"),
        ("long_term", "ear_canal_up_to_eardrum", "s2-3.1(2)(c)(ii)", "Class IIa"),
        ("long_term", "nasal_cavity", "s2-3.1(2)(c)(ii)", "Class IIa"),
    ])
    def test_duration_and_site(self, duration, site, rule_id, result):
        got, rules, outcome = governing(orifice(duration, site))
        assert (got, rules) == (result, [rule_id])
        assert outcome.flags == []

    def test_a_long_term_nasal_device_liable_to_be_absorbed_stays_at_c_i(self):
        got, rules, _ = governing(orifice("long_term", "nasal_cavity",
                                          liable_to_be_absorbed_by_mucous_membrane=Tri.YES))
        assert (got, rules) == ("Class IIb", ["s2-3.1(2)(c)(i)"])

    def test_connection_to_a_class_iia_active_device_is_3_1_3_only(self):
        got, rules, outcome = governing(orifice("long_term", connected_to_an_active_device=Tri.YES,
                                                connected_to_active_device=Tri.YES))
        assert (got, rules) == ("Class IIa", ["s2-3.1(3)"])
        assert not any(h.rule_id.startswith("s2-3.1(2)") for h in outcome.hits)

    def test_connection_to_a_class_i_active_device_uses_2_with_a_flag(self):
        got, rules, outcome = governing(orifice("short_term", connected_to_an_active_device=Tri.YES,
                                                connected_to_active_device=Tri.NO))
        assert (got, rules) == ("Class IIa", ["s2-3.1(2)(b)(i)"])
        assert [f.code for f in outcome.flags] == ["s2_3_1_class_i_active_connection"]

    def test_an_unanswered_connection_is_pending(self):
        pending = S2.rule_3_1_2_a(orifice("transient", connected_to_an_active_device=Answer()))
        assert pending.fields == ("general.connected_to_an_active_device",)

    def test_a_5_11_substance_is_outside_3_1(self):
        f = orifice("transient", "nasal_cavity", is_substance_through_orifice_or_skin=Tri.YES,
                    substance_acts_in_nose_mouth_or_on_skin=Tri.YES)
        assert all(rule(f) is None for rule in S2.PART_3)
        got, rules, _ = governing(f)
        assert (got, rules) == ("Class IIa", ["s2-5.11(c)"])

    def test_a_5_10_inhalation_device_is_outside_3_1(self):
        f = orifice("transient", administers_by_inhalation=Tri.YES)
        assert all(rule(f) is None for rule in S2.PART_3)

    def test_a_surgical_device_is_outside_3_1(self):
        assert S2.rule_3_1_2_a(surgical("transient")) is None


class TestClause32:
    def test_the_default_is_iia(self):
        assert governing(surgical("transient"))[:2] == ("Class IIa", ["s2-3.2(2)"])

    @pytest.mark.parametrize("field,rule_id,result", [
        ("corrects_heart_or_circulatory_defect_by_contact", "s2-3.2(3)", "Class III"),
        ("direct_contact_heart_circulation_or_nervous_system", "s2-3.2(3A)", "Class III"),
        ("reusable_surgical_instrument", "s2-3.2(4)", "Class I"),
        ("delivers_ionising_radiation", "s2-3.2(5)(a)", "Class IIb"),
        ("has_biological_effect", "s2-3.2(5)(b)", "Class IIb"),
        ("wholly_or_mostly_absorbed", "s2-3.2(5)(c)", "Class IIb"),
        ("administers_medicine_hazardously_by_delivery_system", "s2-3.2(5)(d)", "Class IIb"),
    ])
    def test_each_subclause_replaces_the_default(self, field, rule_id, result):
        got, rules, outcome = governing(surgical("transient", **{field: Tri.YES}))
        assert (got, rules) == (result, [rule_id])
        assert "s2-3.2(2)" not in [h.rule_id for h in outcome.hits]

    def test_3A_does_not_reach_a_reusable_instrument(self):
        got, rules, outcome = governing(surgical(
            "transient", reusable_surgical_instrument=Tri.YES,
            direct_contact_heart_circulation_or_nervous_system=Tri.YES))
        assert (got, rules) == ("Class I", ["s2-3.2(4)"])

    def test_the_highest_subclause_wins(self):
        """A reusable instrument that supplies ionising radiation: IIb over I."""
        got, rules, outcome = governing(surgical("transient", reusable_surgical_instrument=Tri.YES,
                                                 delivers_ionising_radiation=Tri.YES))
        assert (got, rules) == ("Class IIb", ["s2-3.2(5)(a)"])
        assert "s2-3.2(4)" in [h.rule_id for h in outcome.hits]


class TestClause33:
    def test_the_default_is_iia(self):
        assert governing(surgical("short_term"))[:2] == ("Class IIa", ["s2-3.3(2)"])

    @pytest.mark.parametrize("field,rule_id,result", [
        ("delivers_ionising_radiation", "s2-3.3(3)(a)", "Class IIb"),
        ("undergoes_chemical_change", "s2-3.3(3)(b)", "Class IIb"),
        ("administers_medicine", "s2-3.3(3)(c)", "Class IIb"),
        ("corrects_heart_or_circulatory_defect_by_contact", "s2-3.3(4)(a)", "Class III"),
        ("direct_contact_heart_circulation_or_nervous_system", "s2-3.3(4)(b)", "Class III"),
        ("has_biological_effect", "s2-3.3(4)(c)", "Class III"),
        ("wholly_or_mostly_absorbed", "s2-3.3(4)(d)", "Class III"),
    ])
    def test_each_subclause(self, field, rule_id, result):
        assert governing(surgical("short_term", **{field: Tri.YES}))[:2] == (result, [rule_id])

    def test_chemical_change_in_the_teeth_stays_at_iia(self):
        """The note to 3.3(3)(b): placed in the teeth, back to subclause (2)."""
        got, rules, _ = governing(surgical("short_term", undergoes_chemical_change=Tri.YES,
                                           placed_in_teeth=Tri.YES))
        assert (got, rules) == ("Class IIa", ["s2-3.3(2)"])

    def test_absorbed_and_chemical_change_give_different_classes(self):
        """The two conditions the old merged field could not tell apart."""
        assert governing(surgical("short_term", wholly_or_mostly_absorbed=Tri.YES))[0] == \
            "Class III"
        assert governing(surgical("short_term", undergoes_chemical_change=Tri.YES))[0] == \
            "Class IIb"


class TestClause34:
    def test_the_default_is_iib(self):
        assert governing(surgical("long_term"))[:2] == ("Class IIb", ["s2-3.4(2)"])

    def test_every_implantable_device_is_in_3_4(self):
        f = function(invasiveness=Invasiveness.IMPLANTABLE, duration="short_term")
        assert governing(f)[:2] == ("Class IIb", ["s2-3.4(2)"])

    @pytest.mark.parametrize("field,rule_id,result", [
        ("placed_in_teeth", "s2-3.4(3)", "Class IIa"),
        ("direct_contact_heart_circulation_or_nervous_system", "s2-3.4(4)(a)", "Class III"),
        ("has_biological_effect", "s2-3.4(4)(b)", "Class III"),
        ("wholly_or_mostly_absorbed", "s2-3.4(4)(c)", "Class III"),
        ("undergoes_chemical_change", "s2-3.4(4)(d)", "Class III"),
        ("administers_medicine", "s2-3.4(4)(e)", "Class III"),
        ("joint_replacement_or_surgical_mesh", "s2-3.4(4A)", "Class III"),
        ("spinal_motion_preserving", "s2-3.4(4B)", "Class III"),
    ])
    def test_each_subclause(self, field, rule_id, result):
        assert governing(surgical("long_term", **{field: Tri.YES}))[:2] == (result, [rule_id])

    def test_teeth_and_medicine_is_iii(self):
        got, rules, _ = governing(surgical("long_term", placed_in_teeth=Tri.YES,
                                           administers_medicine=Tri.YES))
        assert (got, rules) == ("Class III", ["s2-3.4(4)(e)"])

    def test_chemical_change_in_the_teeth_is_not_4_d(self):
        got, rules, _ = governing(surgical("long_term", placed_in_teeth=Tri.YES,
                                           undergoes_chemical_change=Tri.YES))
        assert (got, rules) == ("Class IIa", ["s2-3.4(3)"])


def test_an_unknown_duration_blocks_the_surgical_clauses():
    pending = S2.rule_3_2_2(surgical(Answer()))
    assert pending.fields == ("general.duration",)


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

DECIDED_BY_PART_5 = [
    "dressing_collagen_deep_wound",
    "trauma_covering_anaesthetic",
    "saline_nasal_spray",
    "condom_with_spermicide",
    "heparin_coated_catheter",
]

DECIDED_BY_PART_3 = [
    "screw_transient",
    "screw_short_term",
    "screw_long_term",
    "screw_central_circulation",
    "reusable_surgical_instrument",
    "orifice_long_term",
    "nasal_device_long_term",
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


def test_the_collagen_dressing_reaches_2_4_4_and_5_5_takes_it_to_class_iii():
    data = json.loads((FIXTURES / "dressing_collagen_deep_wound.json").read_text())
    profile = DeviceProfile.model_validate(data["profile"])
    outcome = E.classify_function(profile.functions[0])
    assert "s2-2.4(4)" in [h.rule_id for h in outcome.hits]
    assert outcome.result == "Class III"
    assert [h.rule_id for h in outcome.governing] == ["s2-5.5(3)"]
    assert outcome.flags == []


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
    text = text.replace("\u2014", " \u2013 ")
    return " ".join(text.split())


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("legislation")
    L.write(L.SOURCE, out)
    return LEG.load(out)


@pytest.mark.parametrize("slug", DECIDED_BY_PART_5 + DECIDED_BY_PART_3)
def test_parts_3_and_5_decide_the_fixtures_they_decide(slug):
    data = json.loads((FIXTURES / f"{slug}.json").read_text())
    profile = DeviceProfile.model_validate(data["profile"])
    expected = data["functions"][0]
    outcome = E.classify_function(profile.functions[0])
    assert outcome.confident
    assert outcome.result == expected["expected_class"]
    assert any(h.rule_id.startswith(f"s2-{expected['expected_rule']}") for h in outcome.governing)


@needs_source
@pytest.mark.parametrize("rule", S2.PART_2 + S2.PART_3 + S2.PART_5,
                         ids=[r.__name__ for r in S2.PART_2 + S2.PART_3 + S2.PART_5])
def test_docstring_quotes_the_clause_verbatim(corpus, rule):
    heading, *paragraphs = inspect.getdoc(rule).split("\n\n")
    reference = heading.removeprefix("Schedule 2 clause ").rstrip(".")
    clause = corpus[E.clause_of(f"s2-{reference}")]
    body = _flatten(clause.text)
    assert paragraphs, f"{rule.__name__} has no clause text"
    for paragraph in paragraphs:
        assert _flatten(paragraph) in body, f"{rule.__name__}: {paragraph!r}"
