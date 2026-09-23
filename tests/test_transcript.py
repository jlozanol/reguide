"""Schema v0.12: the intake transcript and what depends on it.

These do not test extraction or question choice, which do not exist yet.
They test the ground intake stands on:

- an ANSWERED field's evidence has to come from the reply to a question that
  covered that field, and a STATED field's evidence from the description;
- a "not sure" reply takes a field out of askable() without resolving it;
- the regulation 3.9 qualifier questions are asked only where the engine
  reads them, and the engine never waits on sterile supply for software;
- a Question cannot set a field it does not say it covers.
"""

import json

import pytest
from pydantic import ValidationError

from reguide import extract as X
from reguide.profile import (
    Answer,
    Basis,
    CoreProfile,
    DeviceKind,
    DeviceProfile,
    Duration,
    FunctionProfile,
    FundingProfile,
    GeneralDeviceProfile,
    Invasiveness,
    IvdProfile,
    Tri,
    Turn,
    relevant_core_fields,
)
from reguide.rules import engine as E

STERILE = "core.supplied_sterile"
MEASURING = "core.has_measuring_function"
DURATION = "functions.0.general.duration"


def stated(value, evidence="test evidence"):
    return Answer(value=value, basis=Basis.STATED, evidence=evidence)


def answered(value, evidence):
    return Answer(value=value, basis=Basis.ANSWERED, evidence=evidence)


def function(kind=DeviceKind.GENERAL, software=Tri.NO):
    return FunctionProfile(
        name=stated("function"),
        description=stated("a function"),
        kind=stated(kind),
        is_software=stated(software),
        general=GeneralDeviceProfile() if kind is DeviceKind.GENERAL else None,
        ivd=IvdProfile() if kind is DeviceKind.IVD else None,
    )


def product(*functions, source="a dressing for minor cuts"):
    return DeviceProfile(functions=list(functions), source_text=source)


def turn(fields, reply, unsure=False, question_id="q"):
    return Turn(question_id=question_id, fields=fields, asked="asked?", reply=reply,
                unsure=unsure)


class TestSchemaVersion:
    def test_a_new_profile_is_version_0_12_with_an_empty_transcript(self):
        profile = DeviceProfile()
        assert profile.schema_version == "0.12"
        assert profile.transcript == []

    def test_an_older_profile_is_refused(self):
        with pytest.raises(ValidationError):
            DeviceProfile.model_validate({"schema_version": "0.11"})

    def test_the_transcript_survives_json(self):
        profile = product(function())
        profile.transcript.append(turn([STERILE], "No, it ships clean but not sterile",
                                       question_id="sterile"))
        restored = DeviceProfile.model_validate(json.loads(profile.model_dump_json()))
        [saved] = restored.transcript
        assert saved.question_id == "sterile"
        assert saved.fields == [STERILE]
        assert saved.reply == "No, it ships clean but not sterile"
        assert saved.unsure is False


class TestAnsweredEvidence:
    def test_a_quote_from_the_reply_that_covered_the_field_passes(self):
        profile = product(function())
        profile.transcript.append(turn([STERILE], "No, it ships clean but not sterile"))
        profile.core.supplied_sterile = answered(Tri.NO, "not sterile")
        assert STERILE not in profile.untraceable_evidence()

    def test_the_whole_reply_is_a_valid_quote(self):
        profile = product(function())
        profile.transcript.append(turn([STERILE], "No"))
        profile.core.supplied_sterile = answered(Tri.NO, "No")
        assert not set(profile.untraceable_evidence()) & {STERILE, MEASURING}

    def test_a_quote_found_only_in_the_description_fails(self):
        """An answer has to come from the answer, not from the first pass."""
        profile = product(function(), source="sold sterile in a sealed pouch")
        profile.transcript.append(turn([STERILE], "yes"))
        profile.core.supplied_sterile = answered(Tri.YES, "sterile")
        assert STERILE in profile.untraceable_evidence()

    def test_a_quote_from_the_reply_to_another_question_fails(self):
        profile = product(function())
        profile.transcript.append(turn([MEASURING], "no, it does not measure anything"))
        profile.transcript.append(turn([STERILE], "yes"))
        profile.core.supplied_sterile = answered(Tri.NO, "no, it does not")
        assert STERILE in profile.untraceable_evidence()

    def test_an_answer_with_no_turn_at_all_fails(self):
        profile = product(function())
        profile.core.supplied_sterile = answered(Tri.NO, "No")
        assert STERILE in profile.untraceable_evidence()

    def test_a_checklist_turn_traces_every_field_it_covered(self):
        profile = product(function())
        fields = [STERILE, MEASURING]
        profile.transcript.append(turn(fields, "None of these"))
        profile.core.supplied_sterile = answered(Tri.NO, "None of these")
        profile.core.has_measuring_function = answered(Tri.NO, "None of these")
        assert not set(profile.untraceable_evidence()) & {STERILE, MEASURING}

    def test_a_function_field_is_traced_by_its_full_dotted_name(self):
        """A reply about the second function is not evidence for the first."""
        profile = product(function(), function())
        general = profile.functions[0].general
        general.invasiveness = stated(Invasiveness.BODY_ORIFICE, "dressing")
        profile.transcript.append(turn(["functions.1.general.duration"], "about an hour"))
        general.duration = answered(Duration.SHORT_TERM, "about an hour")
        assert DURATION in profile.untraceable_evidence()
        profile.transcript.append(turn([DURATION], "about an hour"))
        assert DURATION not in profile.untraceable_evidence()


class TestStatedEvidence:
    def test_a_quote_found_only_in_the_transcript_fails(self):
        """STATED means the description said it. A reply is not the description."""
        profile = product(function())
        profile.transcript.append(turn([STERILE], "it is sterile"))
        profile.core.supplied_sterile = stated(Tri.YES, "it is sterile")
        assert STERILE in profile.untraceable_evidence()

    def test_a_quote_from_the_description_passes(self):
        profile = product(function())
        profile.core.product_name = stated("Dressing", "dressing")
        assert "core.product_name" not in profile.untraceable_evidence()


class TestFundingEvidence:
    def test_funding_evidence_is_checked_when_the_section_exists(self):
        profile = product(function())
        profile.funding = FundingProfile(operator=stated("patient_or_carer", "invented"))
        assert "funding.operator" in profile.untraceable_evidence()

    def test_quoted_funding_evidence_passes(self):
        profile = product(function(), source="used at home by the patient")
        profile.funding = FundingProfile(operator=stated("patient_or_carer", "at home"))
        assert "funding.operator" not in profile.untraceable_evidence()

    def test_no_funding_section_means_nothing_to_check(self):
        profile = product(function())
        assert not any(n.startswith("funding.") for n in profile.untraceable_evidence())


class TestUnsure:
    def test_an_unsure_reply_leaves_the_field_missing_but_not_askable(self):
        profile = product(function())
        profile.transcript.append(turn([STERILE], "I don't know", unsure=True))
        assert STERILE in profile.missing()
        assert STERILE in profile.unsure()
        assert STERILE not in profile.askable()

    def test_a_field_nobody_asked_about_is_askable(self):
        profile = product(function())
        assert STERILE in profile.askable()
        assert profile.unsure() == []

    def test_a_later_answer_takes_the_field_off_the_unsure_list(self):
        profile = product(function())
        profile.transcript.append(turn([STERILE], "I don't know", unsure=True))
        profile.transcript.append(turn([STERILE], "It turns out it is not sterile"))
        profile.core.supplied_sterile = answered(Tri.NO, "not sterile")
        assert STERILE not in profile.missing()
        assert STERILE not in profile.unsure()
        assert not set(profile.untraceable_evidence()) & {STERILE, MEASURING}

    def test_unsure_on_one_field_does_not_hide_another(self):
        profile = product(function())
        profile.transcript.append(turn([STERILE], "no idea", unsure=True))
        assert MEASURING in profile.askable()

    def test_askable_keeps_the_order_of_missing(self):
        profile = product(function())
        profile.transcript.append(turn([STERILE], "no idea", unsure=True))
        assert profile.askable() == [n for n in profile.missing() if n != STERILE]


class TestQualifierGating:
    def test_an_unknown_product_is_asked_both(self):
        names = relevant_core_fields([])
        assert "supplied_sterile" in names
        assert "has_measuring_function" in names

    def test_hardware_is_asked_both(self):
        names = relevant_core_fields([function()])
        assert {"supplied_sterile", "has_measuring_function"} <= set(names)

    def test_all_software_is_not_asked_about_sterile_supply(self):
        names = relevant_core_fields([function(software=Tri.YES)])
        assert "supplied_sterile" not in names
        assert "has_measuring_function" in names

    def test_software_whose_status_is_open_is_still_asked(self):
        """Nothing is dropped on a guess."""
        open_function = function()
        open_function.is_software = Answer()
        assert "supplied_sterile" in relevant_core_fields([open_function])

    def test_software_and_hardware_together_are_asked_about_sterile_supply(self):
        names = relevant_core_fields([function(software=Tri.YES), function()])
        assert "supplied_sterile" in names

    def test_an_ivd_only_product_is_asked_neither(self):
        """Regulations 1.4(2) and 3.9A: neither qualifier applies to an IVD."""
        names = relevant_core_fields([function(kind=DeviceKind.IVD)])
        assert "supplied_sterile" not in names
        assert "has_measuring_function" not in names

    def test_an_ivd_beside_a_general_device_keeps_both(self):
        names = relevant_core_fields([function(kind=DeviceKind.IVD), function()])
        assert {"supplied_sterile", "has_measuring_function"} <= set(names)

    def test_the_other_core_fields_are_always_asked(self):
        for functions in ([], [function(kind=DeviceKind.IVD)], [function(software=Tri.YES)]):
            names = relevant_core_fields(functions)
            assert {"product_name", "intended_purpose", "functions_confirmed"} <= set(names)

    def test_missing_follows_the_gating(self):
        profile = product(function(software=Tri.YES))
        assert STERILE not in profile.missing()
        assert MEASURING in profile.missing()

    def test_relevant_follows_the_gating(self):
        profile = product(function(kind=DeviceKind.IVD))
        assert STERILE not in profile.relevant()
        assert MEASURING not in profile.relevant()


class TestSoftwareQualifiers:
    """The engine side of the gating: software never waits on sterile supply."""

    @staticmethod
    def class_i():
        return E.Classification(result="Class I",
                                hits=[E.RuleHit("s2-4.5(2)", "c", "Class I", "b")])

    def test_software_class_i_is_confident_without_a_sterile_answer(self):
        profile = DeviceProfile(
            core=CoreProfile(has_measuring_function=stated(Tri.NO)),
            functions=[function(software=Tri.YES)],
        )
        outcome = E.qualify(profile, profile.functions[0], self.class_i())
        assert outcome.confident
        assert outcome.qualifiers == []

    def test_software_never_carries_the_sterile_qualifier(self):
        profile = DeviceProfile(
            core=CoreProfile(supplied_sterile=stated(Tri.YES),
                             has_measuring_function=stated(Tri.NO)),
            functions=[function(software=Tri.YES)],
        )
        outcome = E.qualify(profile, profile.functions[0], self.class_i())
        assert outcome.qualifiers == []

    def test_software_still_waits_on_the_measuring_function(self):
        profile = DeviceProfile(functions=[function(software=Tri.YES)])
        outcome = E.qualify(profile, profile.functions[0], self.class_i())
        assert outcome.unresolved == [MEASURING]

    def test_hardware_still_waits_on_sterile_supply(self):
        profile = DeviceProfile(
            core=CoreProfile(has_measuring_function=stated(Tri.NO)),
            functions=[function()],
        )
        outcome = E.qualify(profile, profile.functions[0], self.class_i())
        assert outcome.unresolved == [STERILE]


class TestAnswerAt:
    def test_reaches_core_function_and_section_fields(self):
        profile = product(function())
        assert profile.answer_at("core.product_name") is profile.core.product_name
        assert profile.answer_at("functions.0.kind") is profile.functions[0].kind
        assert profile.answer_at(DURATION) is profile.functions[0].general.duration

    @pytest.mark.parametrize("dotted", [
        "functions.3.kind", "core.nothing", "functions.0.ivd.is_self_test", "functions",
    ])
    def test_a_path_that_reaches_no_answer_gives_none(self, dotted):
        assert product(function()).answer_at(dotted) is None


class TestQuestion:
    @staticmethod
    def yes_no(field=STERILE):
        return X.Question(
            id="sterile",
            text="Is it sold sterile?",
            fields=[field],
            options=[
                X.Option(id="yes", label="Yes", sets={field: Tri.YES}),
                X.Option(id="no", label="No", sets={field: Tri.NO}),
                X.Option(id="unsure", label="Not sure", unsure=True),
            ],
        )

    def test_a_well_formed_question_builds(self):
        question = self.yes_no()
        assert [o.id for o in question.options] == ["yes", "no", "unsure"]
        assert question.multi is False

    def test_an_option_cannot_set_a_field_outside_the_question(self):
        with pytest.raises(ValidationError):
            X.Question(id="q", text="?", fields=[STERILE],
                       options=[X.Option(id="a", label="A", sets={MEASURING: Tri.NO})])

    def test_an_unsure_option_cannot_set_a_value(self):
        with pytest.raises(ValidationError):
            X.Option(id="u", label="Not sure", unsure=True, sets={STERILE: Tri.NO})

    def test_option_ids_are_unique(self):
        with pytest.raises(ValidationError):
            X.Question(id="q", text="?", fields=[STERILE],
                       options=[X.Option(id="a", label="A"), X.Option(id="a", label="B")])


class TestContract:
    """The three entry points exist with their stage 1 signatures."""

    def test_extract_is_not_built_yet(self):
        with pytest.raises(NotImplementedError):
            X.extract("a dressing")

    def test_next_question_is_not_built_yet(self):
        with pytest.raises(NotImplementedError):
            X.next_question(DeviceProfile())

    def test_apply_answer_is_not_built_yet(self):
        with pytest.raises(NotImplementedError):
            X.apply_answer(DeviceProfile(), TestQuestion.yes_no(), ["no"])
