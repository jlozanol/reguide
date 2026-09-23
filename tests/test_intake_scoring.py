"""Intake cases, the intake score, and the recorded cassettes.

The last class runs every recorded cassette through the checks and compares
the result with its fixture. A case with no cassette is skipped (record it
with scripts/record_intake.py); a stale one fails, so a prompt or schema
change cannot leave old recordings quietly passing.
"""

import json

import pytest

from reguide import intake_fields as F
from reguide import intake_scoring as S
from reguide.llm import CassetteClient
from reguide.profile import DeviceProfile

CASES = S.load_cases()
FIXTURES = {path.stem: json.loads(path.read_text())
            for path in S.FIXTURE_DIR.glob("*.json")}
SCREW = "screw_long_term"
SCREW_TEXT = FIXTURES[SCREW]["intake"]["cases"]["founder"]


def claim(target, value, evidence, index=0):
    return {"function_index": index, "target": target, "value": value, "evidence": evidence}


def screw_output(*claims, functions=1):
    one = {"name": "Bone screw", "name_evidence": "bone screws",
           "description": "We make titanium bone screws"}
    return {"functions": [one] * functions, "claims": list(claims)}


def score(output, case_variant="founder"):
    case = S.IntakeCase(SCREW, case_variant, SCREW_TEXT)
    return S.score_case(case, output, S.Cassette.OK, FIXTURES[SCREW])


class TestCases:
    def test_every_fixture_has_a_described_case(self):
        described = {c.slug for c in CASES if c.variant == "described"}
        assert described == set(FIXTURES)

    def test_there_are_founder_cases(self):
        founder = [c for c in CASES if c.variant == "founder"]
        assert len(founder) >= 8

    def test_case_names_are_unique(self):
        names = [c.name for c in CASES]
        assert len(names) == len(set(names))

    def test_every_text_is_non_empty(self):
        assert all(c.text.strip() for c in CASES)

    def test_a_described_case_starts_with_the_product_name(self):
        for case in CASES:
            if case.variant == "described":
                name = FIXTURES[case.slug]["profile"]["core"]["product_name"]["value"]
                assert case.text.startswith(name)

    def test_founder_texts_avoid_regulations_vocabulary(self):
        """A founder case is only a fair test if it does not echo the rules."""
        banned = ("secondary intent", "potentially hazardous", "therapeutic",
                  "in vitro", "invasive", "transient", "dermis", "clause")
        for case in CASES:
            if case.variant == "founder":
                for word in banned:
                    assert word not in case.text.lower(), (case.name, word)


class TestSpecificFacts:
    @pytest.mark.parametrize("slug", sorted(FIXTURES))
    def test_each_specific_fact_is_a_resolved_field_of_the_fixture(self, slug):
        profile = DeviceProfile.model_validate(FIXTURES[slug]["profile"])
        for dotted in FIXTURES[slug]["intake"]["specific"]:
            answer = profile.answer_at(dotted)
            assert answer is not None and answer.resolved, (slug, dotted)

    @pytest.mark.parametrize("slug", sorted(FIXTURES))
    def test_specific_facts_are_ones_extraction_may_claim(self, slug):
        for dotted in FIXTURES[slug]["intake"]["specific"]:
            parts = dotted.split(".")
            if parts[0] == "core":
                target = dotted
            elif len(parts) == 3:
                target = f"function.{parts[2]}"
            else:
                target = f"{parts[2]}.{parts[3]}"
            assert target in F.EXTRACTABLE, (slug, dotted)

    def test_every_function_s_kind_is_specific(self):
        for slug, data in FIXTURES.items():
            for index in range(len(data["profile"]["functions"])):
                assert f"functions.{index}.kind" in data["intake"]["specific"], slug

    def test_the_screw_s_specific_facts(self):
        assert FIXTURES[SCREW]["intake"]["specific"] == [
            "core.supplied_sterile",
            "functions.0.kind",
            "functions.0.status.therapeutic_purpose",
            "functions.0.general.invasiveness",
            "functions.0.general.duration",
            "functions.0.general.is_active_implantable",
        ]


class TestCompare:
    def test_matching_facts_agree_and_count_as_coverage(self):
        result = score(screw_output(
            claim("core.supplied_sterile", "yes", "packed sterile", -1),
            claim("function.kind", "general_device", "bone screws"),
            claim("general.duration", "long_term", "They stay in the patient permanently"),
        ))
        assert [f.kind for f in result.findings] == [S.Kind.AGREED] * 3
        assert result.covered == ["core.supplied_sterile", "functions.0.kind",
                                  "functions.0.general.duration"]
        assert result.clean

    def test_a_wrong_specific_fact_is_a_specific_contradiction(self):
        result = score(screw_output(
            claim("function.kind", "general_device", "bone screws"),
            claim("general.duration", "short_term", "They stay in the patient permanently"),
        ))
        [bad] = result.contradictions
        assert bad.kind is S.Kind.CONTRADICTS_SPECIFIC
        assert (bad.field, bad.extracted, bad.expected) == \
            ("functions.0.general.duration", "short_term", "long_term")
        assert not result.clean

    def test_a_yes_against_a_builder_default_is_a_default_contradiction(self):
        result = score(screw_output(
            claim("function.kind", "general_device", "bone screws"),
            claim("general.is_export_only", "yes", "titanium bone screws"),
        ))
        [bad] = result.contradictions
        assert bad.kind is S.Kind.CONTRADICTS_DEFAULT
        assert bad.field == "functions.0.general.is_export_only"

    def test_a_field_the_fixture_does_not_hold_is_an_extra(self):
        result = score(screw_output(
            claim("function.kind", "general_device", "bone screws"),
            claim("funding.operator", "medical_specialist", "surgeons", -1),
        ))
        [extra] = result.of(S.Kind.EXTRA)
        assert extra.field == "funding.operator"
        assert result.clean

    def test_free_text_is_not_compared(self):
        result = score(screw_output(
            claim("core.intended_purpose", "They stay in the patient permanently.",
                  "They stay in the patient permanently.", -1),
        ))
        assert result.findings == []

    def test_a_different_split_skips_function_fields_but_keeps_product_fields(self):
        result = score(screw_output(
            claim("core.supplied_sterile", "yes", "packed sterile", -1),
            claim("general.duration", "short_term", "permanently", 1),
            functions=2,
        ))
        assert not result.split_matches
        assert [f.field for f in result.findings] == ["core.supplied_sterile"]

    def test_dropped_claims_are_reported_not_compared(self):
        result = score(screw_output(
            claim("function.kind", "general_device", "bone screws"),
            claim("general.duration", "short_term", "held for three weeks"),
        ))
        assert result.contradictions == []
        assert [r.reason for r in result.rejections] == ["evidence_not_in_text"]

    def test_questions_left_are_counted(self):
        result = score(screw_output(claim("function.kind", "general_device", "bone screws")))
        assert result.askable > 0


class TestCassetteState:
    CASE = S.IntakeCase(SCREW, "founder", SCREW_TEXT)

    def test_no_file_is_missing(self, tmp_path):
        assert S.cassette_state(self.CASE, tmp_path)[0] is S.Cassette.MISSING

    def test_a_current_recording_is_ok(self, tmp_path):
        CassetteClient(tmp_path).record(self.CASE.name, SCREW_TEXT, screw_output())
        state, output = S.cassette_state(self.CASE, tmp_path)
        assert state is S.Cassette.OK
        assert output == screw_output()

    def test_a_recording_of_other_text_is_stale(self, tmp_path):
        CassetteClient(tmp_path).record(self.CASE.name, SCREW_TEXT + " Edited.",
                                        screw_output())
        assert S.cassette_state(self.CASE, tmp_path)[0] is S.Cassette.STALE

    def test_a_missing_cassette_is_not_scored(self, tmp_path):
        result = S.score_case(self.CASE, None, S.Cassette.MISSING, FIXTURES[SCREW])
        assert result.findings == []
        assert not result.clean


class TestRecordedCassettes:
    """Every recorded reply, checked against its fixture."""

    @pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
    def test_the_recording_agrees_with_its_fixture(self, case):
        state, output = S.cassette_state(case)
        if state is S.Cassette.MISSING:
            pytest.skip("not recorded: uv run python scripts/record_intake.py")
        assert state is S.Cassette.OK, (
            f"{case.name}: the cassette no longer matches the instructions, schema, "
            f"model or text; re-record with scripts/record_intake.py")
        result = S.score_case(case, output, state, FIXTURES[case.slug])
        assert result.untraceable == []
        assert [(f.field, f.extracted, f.expected) for f in result.contradictions] == []
