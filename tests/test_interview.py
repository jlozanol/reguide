"""The interview order (stage 1 step 4, piece 2).

What is checked:

- settle(): a software general function is non-invasive and touches no
  substances or injured skin by definition, recorded as DEFAULTED; a stated
  answer is never overwritten; the defaults go when the function stops being
  software; nothing is defaulted for hardware or an IVD;
- every general and IVD field has exactly one place in the order;
- the order: name and purpose first, then function names, the split, the
  gate for every function, and only then kinds and branch questions; the
  "Despite" questions lead each branch; rule questions come highest class
  first; the qualifiers come last, and only while a Class I result is still
  possible;
- the class stop (piece 4c): a function whose class the engine can already
  give is asked nothing more, and an unanswered "Despite" question is still
  asked;
- the gate early stop: a function the gate has decided is asked nothing
  past the gate, and a product whose functions have all stopped is not
  asked the qualifiers;
- next_question never changes the profile it is given, and returns None
  when nothing is left;
- the oracle: answering from each fixture, the interview reaches every
  fixture's verdict with no "not sure", never asks a field twice, and the
  screen counts do not grow past the ratchet below.
"""

import json
import statistics
from pathlib import Path

import pytest

from reguide import interview as I
from reguide import interview_oracle as O
from reguide import status as S
from reguide.profile import (
    Answer,
    Basis,
    DeviceProfile,
    FunctionProfile,
    GeneralDeviceProfile,
    Invasiveness,
    IvdProfile,
    Tri,
    Turn,
)
from reguide.scoring import EXCLUSIONS

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

# Ratchet. Lower these when a piece of step 4 brings the counts down; a test
# fails if a change makes the interview longer without anyone deciding to.
BLANK_MEDIAN_AT_MOST = 19
BLANK_MAX_AT_MOST = 49
EXTRACTED_MEDIAN_AT_MOST = 12
EXTRACTED_MAX_AT_MOST = 37


@pytest.fixture(scope="module", autouse=True)
def exclusions():
    saved = dict(S.EXCLUSION_TABLE)
    S.load_exclusions(EXCLUSIONS)
    yield
    S.EXCLUSION_TABLE.clear()
    S.EXCLUSION_TABLE.update(saved)


@pytest.fixture(scope="module")
def blank_runs(exclusions):
    return {run.slug: run for run in O.run_blank()}


@pytest.fixture(scope="module")
def extracted_runs(exclusions):
    return O.run_extracted()


def fixture(slug: str) -> dict:
    return json.loads((FIXTURES / f"{slug}.json").read_text())


def answered(value) -> Answer:
    return Answer(value=value, basis=Basis.ANSWERED, evidence="x")


def software_function(software=Tri.YES) -> FunctionProfile:
    return FunctionProfile(is_software=answered(software), general=GeneralDeviceProfile())


# --------------------------------------------------------------------------
# settle()
# --------------------------------------------------------------------------


def test_settle_defaults_a_software_function_by_definition():
    profile = I.settle(DeviceProfile(functions=[software_function()]))
    general = profile.functions[0].general
    assert general.invasiveness.value is Invasiveness.NON_INVASIVE
    assert general.handles_substances_for_administration.value is Tri.NO
    assert general.contacts_injured_skin_or_mucous_membrane.value is Tri.NO
    for name in I.SOFTWARE_DEFINITIONS:
        answer = getattr(general, name)
        assert answer.basis is Basis.DEFAULTED
        assert answer.evidence is None


def test_settle_never_overwrites_an_answer():
    function = software_function()
    function.general.contacts_injured_skin_or_mucous_membrane = answered(Tri.YES)
    I.settle(DeviceProfile(functions=[function]))
    assert function.general.contacts_injured_skin_or_mucous_membrane.value is Tri.YES
    assert function.general.contacts_injured_skin_or_mucous_membrane.basis is Basis.ANSWERED


def test_settle_takes_its_defaults_back_when_the_function_is_not_software():
    profile = I.settle(DeviceProfile(functions=[software_function()]))
    profile.functions[0].is_software = answered(Tri.NO)
    I.settle(profile)
    general = profile.functions[0].general
    for name in I.SOFTWARE_DEFINITIONS:
        assert not getattr(general, name).resolved


def test_settle_leaves_hardware_and_unknowns_alone():
    for software in (Tri.NO, Tri.UNKNOWN):
        profile = I.settle(DeviceProfile(functions=[software_function(software)]))
        assert not profile.functions[0].general.invasiveness.resolved
    unanswered = FunctionProfile(general=GeneralDeviceProfile())
    I.settle(DeviceProfile(functions=[unanswered]))
    assert not unanswered.general.invasiveness.resolved


def test_settle_does_nothing_to_an_ivd():
    function = FunctionProfile(is_software=answered(Tri.YES), ivd=IvdProfile())
    before = function.ivd.model_dump()
    I.settle(DeviceProfile(functions=[function]))
    assert function.ivd.model_dump() == before


def test_settled_answers_pass_the_evidence_check():
    profile = I.settle(DeviceProfile(functions=[software_function()]))
    flagged = [d.split(".")[-1] for d in profile.untraceable_evidence()]
    assert not set(flagged) & set(I.SOFTWARE_DEFINITIONS)


# --------------------------------------------------------------------------
# The order tables
# --------------------------------------------------------------------------


@pytest.mark.parametrize("section,model", [("general", GeneralDeviceProfile), ("ivd", IvdProfile)])
def test_every_branch_field_has_exactly_one_place(section, model):
    despite, openers, rank = I.BRANCH_ORDER[section]
    places = list(despite) + list(openers) + list(rank)
    assert len(places) == len(set(places))
    assert set(places) == set(model.model_fields)


# --------------------------------------------------------------------------
# The order, seen through the oracle
# --------------------------------------------------------------------------


def _positions(asked: list[str], test) -> list[int]:
    return [n for n, dotted in enumerate(asked) if test(dotted)]


def test_name_and_purpose_come_first(blank_runs):
    for run in blank_runs.values():
        assert run.asked[:2] == ["core.product_name", "core.intended_purpose"]


def test_the_split_is_confirmed_before_the_gate(blank_runs):
    for run in blank_runs.values():
        split = run.asked.index("core.functions_confirmed")
        names = _positions(run.asked, lambda d: d.endswith((".name", ".description")))
        gate = _positions(run.asked, lambda d: ".status." in d or d.endswith(".is_software"))
        assert max(names) < split < min(gate)


def test_every_functions_gate_comes_before_any_branch_question(blank_runs):
    for run in blank_runs.values():
        gate = _positions(run.asked, lambda d: ".status." in d or d.endswith(".is_software"))
        branch = _positions(run.asked, lambda d: d.endswith(".kind")
                            or ".general." in d or ".ivd." in d)
        if branch:
            assert max(gate) < min(branch), run.slug


def test_the_despite_questions_lead_each_branch(blank_runs):
    for run in blank_runs.values():
        for index in range(len(run.profile.functions)):
            prefix = f"functions.{index}."
            branch = [d.removeprefix(prefix) for d in run.asked if d.startswith(prefix)]
            branch = [r for r in branch if r.split(".")[0] in ("general", "ivd")]
            if not branch:
                continue
            despite = I.BRANCH_ORDER[branch[0].split(".")[0]][0]
            names = [r.split(".", 1)[1] for r in branch]
            count = sum(n in despite for n in names)
            assert all(n in despite for n in names[:count]), (run.slug, index)


def test_rule_questions_come_highest_class_first(blank_runs):
    for run in blank_runs.values():
        for index in range(len(run.profile.functions)):
            ranks = []
            for dotted in run.asked:
                parts = dotted.split(".")
                if parts[:2] != ["functions", str(index)] or len(parts) != 4:
                    continue
                rank = I.BRANCH_ORDER.get(parts[2], (None, None, {}))[2]
                if parts[3] in rank:
                    ranks.append(rank[parts[3]])
            assert ranks == sorted(ranks, reverse=True), (run.slug, index, ranks)


def test_the_qualifiers_come_last(blank_runs):
    for run in blank_runs.values():
        tail = [d for d in run.asked if d in I.CORE_LAST]
        if tail:
            assert run.asked[-len(tail):] == tail, run.slug


def test_a_field_is_never_asked_twice(blank_runs, extracted_runs):
    for run in list(blank_runs.values()) + extracted_runs:
        assert len(run.asked) == len(set(run.asked)), run.start


# --------------------------------------------------------------------------
# Gate early stop
# --------------------------------------------------------------------------


def test_an_excluded_function_is_asked_nothing_past_the_gate(blank_runs):
    run = blank_runs["imaging_platform"]
    archive = [d for d in run.asked if d.startswith("functions.0.")]
    assert "functions.0.status.exclusion_conditions_met" in archive
    assert not [d for d in archive if d.endswith(".kind") or ".general." in d]


@pytest.mark.parametrize("slug", ["wellness_sleep_tracker", "anatomy_education_app",
                                  "cdss_followup_from_report_text"])
def test_a_product_that_stops_at_the_gate_skips_the_rest(blank_runs, slug):
    run = blank_runs[slug]
    assert not [d for d in run.asked
                if d.endswith(".kind") or ".general." in d or ".ivd." in d
                or d in I.CORE_LAST]


def test_without_the_exclusion_table_nothing_stops_on_an_exclusion(monkeypatch):
    monkeypatch.setattr(S, "EXCLUSION_TABLE", {})
    profile = DeviceProfile.model_validate(fixture("wellness_sleep_tracker")["profile"])
    assert not I.stopped(profile.functions[0], 0)


# --------------------------------------------------------------------------
# Class stop and qualifiers
# --------------------------------------------------------------------------


def test_every_regulated_function_ends_settled(blank_runs):
    for run in blank_runs.values():
        for index, function in enumerate(run.profile.functions):
            if I.stopped(function, index):
                continue
            assert I.settled(function), (run.slug, index)


def test_a_question_that_cannot_change_the_class_is_not_asked():
    profile = DeviceProfile.model_validate(fixture("mri_equipment")["profile"])
    profile.functions[0].general.supplies_absorbed_energy_for_diagnosis = Answer()
    assert I.next_question(profile) is None


def test_an_unanswered_despite_question_is_still_asked():
    profile = DeviceProfile.model_validate(fixture("mri_equipment")["profile"])
    profile.functions[0].general.is_export_only = Answer()
    assert I.next_question(profile).fields == ["functions.0.general.is_export_only"]


@pytest.mark.parametrize("slug", ["measuring_thermometer", "sterile_barrier_dressing",
                                  "reusable_surgical_instrument"])
def test_a_class_i_device_is_asked_the_qualifiers(blank_runs, slug):
    asked = blank_runs[slug].asked
    assert set(I.CORE_LAST) <= set(asked)


@pytest.mark.parametrize("slug", ["tens_device", "screw_central_circulation", "mri_equipment"])
def test_a_device_above_class_i_is_not(blank_runs, slug):
    assert not set(I.CORE_LAST) & set(blank_runs[slug].asked)


def test_an_open_export_question_keeps_class_i_possible():
    function = software_function(Tri.NO)
    function.general.is_active_device = answered(Tri.YES)
    assert I.could_be_class_i(function)


# --------------------------------------------------------------------------
# next_question
# --------------------------------------------------------------------------


def test_next_question_does_not_change_the_profile():
    profile = DeviceProfile(functions=[software_function()])
    before = profile.model_dump()
    I.next_question(profile)
    assert profile.model_dump() == before


def test_next_question_skips_what_the_definitions_settle():
    profile = DeviceProfile(functions=[software_function()])
    order = I.plan(I.settle(profile.model_copy(deep=True)))
    assert not [d for d in order if d.split(".")[-1] in I.SOFTWARE_DEFINITIONS]


@pytest.mark.parametrize("slug", ["tens_device", "imaging_platform", "chlamydia_test"])
def test_a_finished_profile_has_no_next_question(slug):
    profile = DeviceProfile.model_validate(fixture(slug)["profile"])
    assert I.next_question(profile) is None


def test_an_unsure_field_is_not_asked_again():
    profile = DeviceProfile()
    first = I.next_question(profile)
    profile.transcript.append(Turn(question_id=first.id, fields=first.fields,
                                   asked=first.text, reply="Not sure", unsure=True))
    assert I.next_question(profile).fields != first.fields


# --------------------------------------------------------------------------
# The oracle
# --------------------------------------------------------------------------


def test_every_blank_run_reaches_the_fixtures_verdict(blank_runs):
    missed = {slug: run.verdicts for slug, run in blank_runs.items() if not run.agrees}
    assert missed == {}


def test_no_blank_run_needs_a_not_sure(blank_runs):
    assert {slug: run.unsure for slug, run in blank_runs.items() if run.unsure} == {}


def test_every_extracted_run_finishes(extracted_runs):
    assert len(extracted_runs) == 55
    assert all(run.profile is not None for run in extracted_runs)


def test_blank_counts_do_not_grow(blank_runs):
    counts = [run.questions for run in blank_runs.values()]
    assert statistics.median(counts) <= BLANK_MEDIAN_AT_MOST
    assert max(counts) <= BLANK_MAX_AT_MOST


def test_extracted_counts_do_not_grow(extracted_runs):
    counts = [run.questions for run in extracted_runs]
    assert statistics.median(counts) <= EXTRACTED_MEDIAN_AT_MOST
    assert max(counts) <= EXTRACTED_MAX_AT_MOST
