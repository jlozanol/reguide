"""Tests for the regulation 3.9 qualifiers on a Class I general device.

Schedule 2 gives Class I, IIa, IIb or III and nothing else. Sterile supply
and a measuring function are conformity assessment conditions on a Class I
device (regulations 1.4 and 3.9), so the engine reports them beside the
class, each with its own citation, rather than as classes of their own.
"""

import pytest

from reguide.profile import (
    GENERAL_ORDER,
    Answer,
    Basis,
    CoreProfile,
    DeviceKind,
    DeviceProfile,
    FunctionProfile,
    Tri,
)
from reguide.rules import engine as E


def stated(value, evidence="test evidence"):
    return Answer(value=value, basis=Basis.STATED, evidence=evidence)


def product(sterile=Tri.NO, measuring=Tri.NO, kind=DeviceKind.GENERAL) -> DeviceProfile:
    core = CoreProfile(
        supplied_sterile=sterile if isinstance(sterile, Answer) else stated(sterile, "sterile"),
        has_measuring_function=(measuring if isinstance(measuring, Answer)
                                else stated(measuring, "measures")),
    )
    return DeviceProfile(core=core, functions=[FunctionProfile(kind=stated(kind))])


def class_i() -> E.Classification:
    return E.Classification(result="Class I",
                            hits=[E.RuleHit("s2-2.4(3)", "c", "Class I", "b")])


def qualify(profile, outcome):
    return E.qualify(profile, profile.functions[0], outcome)


def test_the_general_ladder_is_the_schedule_2_classes_only():
    """No Is, no Im, and no AIMD: clause 5.7(1) makes an AIMD Class III."""
    assert GENERAL_ORDER == ["Class I", "Class IIa", "Class IIb", "Class III"]


def test_a_plain_class_i_device_has_no_qualifiers():
    outcome = qualify(product(), class_i())
    assert outcome.qualifiers == []
    assert outcome.confident


def test_sterile_supply_cites_regulation_3_9_2():
    outcome = qualify(product(sterile=Tri.YES), class_i())
    [q] = outcome.qualifiers
    assert q.code == "supplied_sterile"
    assert q.citation == ("Therapeutic Goods (Medical Devices) Regulations 2002 "
                          "regulation 3.9(2)")
    assert 'supplied_sterile is yes (stated) ("sterile")' == q.because
    assert outcome.result == "Class I"


def test_a_measuring_function_cites_regulations_1_4_and_3_9_3():
    [q] = qualify(product(measuring=Tri.YES), class_i()).qualifiers
    assert q.code == "measuring_function"
    assert q.citation.endswith("regulations 1.4 and 3.9(3)")


def test_a_device_can_carry_both():
    outcome = qualify(product(sterile=Tri.YES, measuring=Tri.YES), class_i())
    assert [q.code for q in outcome.qualifiers] == ["supplied_sterile", "measuring_function"]


@pytest.mark.parametrize("result", ["Class IIa", "Class IIb", "Class III"])
def test_only_class_i_is_qualified(result):
    outcome = E.Classification(result=result, hits=[E.RuleHit("s2-3.2(2)", "c", result, "b")])
    assert qualify(product(sterile=Tri.YES, measuring=Tri.YES), outcome).qualifiers == []


def test_an_ivd_is_never_qualified():
    """Regulation 1.4(2): the measuring function does not apply to an IVD."""
    outcome = E.Classification(result="Class 1 IVD")
    profile = product(sterile=Tri.YES, measuring=Tri.YES, kind=DeviceKind.IVD)
    assert qualify(profile, outcome).qualifiers == []


@pytest.mark.parametrize("field", ["supplied_sterile", "has_measuring_function"])
def test_an_unanswered_input_keeps_the_class_but_not_the_confidence(field):
    unanswered = {"sterile" if field == "supplied_sterile" else "measuring": Answer()}
    outcome = qualify(product(**unanswered), class_i())
    assert outcome.result == "Class I"
    assert outcome.unresolved == [f"core.{field}"]
    assert not outcome.confident


def test_an_unconfident_result_is_left_alone():
    outcome = E.Classification(result="Class I", unresolved=["s2-2.1 (not implemented)"])
    assert qualify(product(sterile=Tri.YES), outcome).qualifiers == []


def test_classify_applies_the_qualifiers(monkeypatch):
    monkeypatch.setattr(E, "classify_function", lambda function: class_i())
    outcome = E.classify(product(sterile=Tri.YES), [0])[0]
    assert [q.code for q in outcome.qualifiers] == ["supplied_sterile"]
