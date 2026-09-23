"""Extraction: the model's claims in, a checked DeviceProfile out.

Most tests feed build_profile() a hand-written output, the way a hostile or
careless model might answer, and check that the bad claim is dropped with the
right reason while the good ones survive. The strict schema would stop some
of these at the provider; the checks do not rely on that.
"""

import pytest

from reguide import extract as X
from reguide import intake_fields as F
from reguide.llm import CassetteClient
from reguide.profile import (
    Basis,
    DecisionMaker,
    DeviceKind,
    Duration,
    Invasiveness,
    TherapeuticPurpose,
    Tri,
)

R = X.Reason

APP = (
    "SkinCheck is a smartphone app. It analyses a photo of a mole and tells the "
    "user whether to see a doctor about possible melanoma. It is software only; "
    "nothing is supplied sterile.\n\nThe app  does not   store images."
)

DRESSING = (
    "A sterile adhesive dressing strip for minor cuts and grazes. Worn for up to "
    "three days on the injured skin."
)


def claim(target, value, evidence, index=0):
    return {"function_index": index, "target": target, "value": value, "evidence": evidence}


def one_function(description, name="Mole checker", name_evidence="SkinCheck"):
    return [{"name": name, "name_evidence": name_evidence, "description": description}]


def build(claims, functions=None, source=APP):
    output = {"functions": functions if functions is not None
              else one_function("analyses a photo of a mole"),
              "claims": claims}
    return X.build_profile(output, source)


def reasons(rejections):
    return [r.reason for r in rejections]


# --------------------------------------------------------------------------
# Finding quotes
# --------------------------------------------------------------------------

class TestLocate:
    def test_an_exact_quote_is_returned_as_is(self):
        assert X.locate("a photo of a mole", APP) == "a photo of a mole"

    def test_spacing_differences_match_and_return_the_text_s_own_spacing(self):
        assert X.locate("The app does not store images", APP) == \
            "The app  does not   store images"

    def test_curly_quotes_and_dashes_match(self):
        source = "It's a device \u2013 not a toy."
        expected = "It's a device \u2013 not a toy"
        assert X.locate("It\u2019s a device - not a toy", source) == expected

    def test_case_differences_match(self):
        assert X.locate("skincheck is a smartphone app", APP) == "SkinCheck is a smartphone app"

    def test_a_trailing_full_stop_the_text_lacks_is_forgiven(self):
        assert X.locate("tells the user whether to see a doctor.", APP) == \
            "tells the user whether to see a doctor"

    @pytest.mark.parametrize("evidence", [
        "analyses a picture of a mole",       # paraphrase
        "a photo ... of a mole",              # ellipsis
        "", " ", "a",                         # nothing to quote
    ])
    def test_anything_else_is_not_found(self, evidence):
        assert X.locate(evidence, APP) is None


# --------------------------------------------------------------------------
# A clean extraction
# --------------------------------------------------------------------------

class TestCleanExtraction:
    @pytest.fixture
    def result(self):
        return build([
            claim("core.product_name", "SkinCheck", "SkinCheck is a smartphone app", -1),
            claim("core.intended_purpose",
                  "It analyses a photo of a mole and tells the user whether to see a "
                  "doctor about possible melanoma.",
                  "It analyses a photo of a mole and tells the user whether to see a "
                  "doctor about possible melanoma.", -1),
            claim("function.kind", "general_device", "a smartphone app"),
            claim("function.is_software", "yes", "It is software only"),
            claim("status.therapeutic_purpose",
                  TherapeuticPurpose.DISEASE.value, "possible melanoma"),
            claim("general.diagnoses_or_screens", "yes", "whether to see a doctor about "
                  "possible melanoma"),
            claim("general.decision_maker", DecisionMaker.DEVICE_TO_LAY_USER.value,
                  "tells the user whether to see a doctor"),
            claim("general.records_images_or_anatomical_model", "no",
                  "does not store images"),
        ])

    def test_nothing_is_dropped(self, result):
        _, rejections = result
        assert rejections == []

    def test_every_populated_field_is_stated_and_traceable(self, result):
        profile, _ = result
        assert profile.untraceable_evidence() == []
        general = profile.functions[0].general
        for answer in (profile.core.product_name, general.diagnoses_or_screens,
                       general.decision_maker, profile.functions[0].kind):
            assert answer.basis is Basis.STATED

    def test_values_are_typed(self, result):
        profile, _ = result
        function = profile.functions[0]
        assert function.kind.value is DeviceKind.GENERAL
        assert function.is_software.value is Tri.YES
        assert function.general.decision_maker.value is DecisionMaker.DEVICE_TO_LAY_USER
        assert function.general.records_images_or_anatomical_model.value is Tri.NO

    def test_the_intended_purpose_is_the_founder_s_sentence(self, result):
        profile, _ = result
        purpose = profile.core.intended_purpose
        assert purpose.value == purpose.evidence
        assert purpose.value in APP

    def test_a_no_keeps_the_text_s_own_spacing_in_its_evidence(self, result):
        profile, _ = result
        stored = profile.functions[0].general.records_images_or_anatomical_model
        assert stored.evidence == "does not   store images"

    def test_the_profile_is_fresh(self, result):
        profile, _ = result
        assert profile.source_text == APP
        assert profile.transcript == []
        assert profile.schema_version == "0.12"
        assert profile.funding is None

    def test_what_the_text_does_not_say_stays_unknown(self, result):
        profile, _ = result
        general = profile.functions[0].general
        assert not general.condition_severity.resolved
        assert not general.public_health_risk.resolved
        assert not profile.core.functions_confirmed.resolved
        assert not profile.functions[0].status.excluded_item.resolved


# --------------------------------------------------------------------------
# Hostile outputs, one check at a time
# --------------------------------------------------------------------------

class TestEvidence:
    def test_a_paraphrased_quote_is_dropped(self):
        profile, rejections = build([
            claim("function.kind", "general_device", "a smartphone app"),
            claim("general.diagnoses_or_screens", "yes", "screens moles for skin cancer"),
        ])
        assert reasons(rejections) == [R.NO_EVIDENCE]
        assert not profile.functions[0].general.diagnoses_or_screens.resolved

    def test_evidence_the_model_invented_for_a_product_field_is_dropped(self):
        profile, rejections = build([
            claim("core.supplied_sterile", "yes", "supplied in a sterile pouch", -1),
        ])
        assert reasons(rejections) == [R.NO_EVIDENCE]
        assert not profile.core.supplied_sterile.resolved


class TestValues:
    @pytest.mark.parametrize("target,value", [
        ("general.decision_maker", "the_doctor"),
        ("general.duration", "3 days"),
        ("function.is_software", "maybe"),
        ("function.is_software", "unknown"),
        ("function.kind", "unknown"),
    ])
    def test_a_value_outside_the_options_is_dropped(self, target, value):
        profile, rejections = build([
            claim("function.kind", "general_device", "a smartphone app"),
            claim(target, value, "a smartphone app"),
        ] if target != "function.kind" else [claim(target, value, "a smartphone app")])
        assert R.BAD_VALUE in reasons(rejections)

    def test_no_therapeutic_purpose_is_never_extracted(self):
        profile, rejections = build([
            claim("status.therapeutic_purpose", TherapeuticPurpose.NONE.value,
                  "a smartphone app"),
        ])
        assert reasons(rejections) == [R.NONE_PURPOSE]
        assert not profile.functions[0].status.therapeutic_purpose.resolved

    def test_a_duration_in_words_is_converted_to_its_band(self):
        profile, rejections = build([
            claim("function.kind", "general_device", "adhesive dressing strip"),
            claim("general.duration", "short_term", "Worn for up to three days"),
        ], functions=one_function("A sterile adhesive dressing strip",
                                  "Dressing", "adhesive dressing strip"), source=DRESSING)
        assert rejections == []
        assert profile.functions[0].general.duration.value is Duration.SHORT_TERM


class TestSilenceIsNotNo:
    def test_a_no_without_a_negation_is_dropped(self):
        """The dressing text never mentions animal material. That is not a no."""
        profile, rejections = build([
            claim("function.kind", "general_device", "adhesive dressing strip"),
            claim("general.contains_non_viable_animal_material", "no",
                  "A sterile adhesive dressing strip"),
        ], functions=one_function("A sterile adhesive dressing strip",
                                  "Dressing", "adhesive dressing strip"), source=DRESSING)
        assert reasons(rejections) == [R.SILENT_NO]
        assert not profile.functions[0].general.contains_non_viable_animal_material.resolved

    @pytest.mark.parametrize("evidence", [
        "does not   store images", "nothing is supplied sterile", "It is software only",
    ])
    def test_a_no_with_a_negation_is_kept(self, evidence):
        profile, rejections = build([
            claim("function.kind", "general_device", "a smartphone app"),
            claim("general.records_images_or_anatomical_model", "no", evidence),
        ])
        assert rejections == []

    def test_whether_it_is_software_may_be_no_from_a_positive_description(self):
        profile, rejections = build([
            claim("function.is_software", "no", "adhesive dressing strip"),
        ], functions=one_function("A sterile adhesive dressing strip",
                                  "Dressing", "adhesive dressing strip"), source=DRESSING)
        assert rejections == []
        assert profile.functions[0].is_software.value is Tri.NO

    def test_a_yes_needs_no_negation(self):
        profile, rejections = build([
            claim("core.supplied_sterile", "yes", "A sterile adhesive dressing strip", -1),
        ], functions=one_function("A sterile adhesive dressing strip",
                                  "Dressing", "adhesive dressing strip"), source=DRESSING)
        assert rejections == []
        assert profile.core.supplied_sterile.value is Tri.YES


class TestFreeText:
    def test_a_paraphrased_intended_purpose_is_dropped(self):
        profile, rejections = build([
            claim("core.intended_purpose", "Screens moles for melanoma risk.",
                  "It analyses a photo of a mole and tells the user whether to see a "
                  "doctor about possible melanoma.", -1),
        ])
        assert reasons(rejections) == [R.NOT_VERBATIM]
        assert not profile.core.intended_purpose.resolved

    def test_an_intended_purpose_that_is_only_part_of_its_evidence_is_dropped(self):
        profile, rejections = build([
            claim("core.intended_purpose", "It analyses a photo of a mole",
                  "It analyses a photo of a mole and tells the user whether to see a "
                  "doctor", -1),
        ])
        assert reasons(rejections) == [R.NOT_VERBATIM]

    def test_a_product_name_not_inside_its_evidence_is_dropped(self):
        profile, rejections = build([
            claim("core.product_name", "MoleScan", "SkinCheck is a smartphone app", -1),
        ])
        assert reasons(rejections) == [R.VALUE_OUTSIDE_EVIDENCE]

    def test_a_product_name_takes_the_text_s_own_casing(self):
        profile, rejections = build([
            claim("core.product_name", "skincheck", "SkinCheck is a smartphone app", -1),
        ])
        assert rejections == []
        assert profile.core.product_name.value == "SkinCheck"


class TestWhereAClaimLands:
    def test_a_product_field_on_a_function_index_is_dropped(self):
        _, rejections = build([claim("core.supplied_sterile", "no",
                                     "nothing is supplied sterile", 0)])
        assert reasons(rejections) == [R.WRONG_INDEX]

    @pytest.mark.parametrize("index", [-1, 1, 7])
    def test_a_function_field_on_a_missing_function_is_dropped(self, index):
        _, rejections = build([claim("function.is_software", "yes", "It is software only",
                                     index)])
        assert reasons(rejections) == [R.WRONG_INDEX]

    def test_a_general_claim_on_an_ivd_function_is_dropped(self):
        profile, rejections = build([
            claim("function.kind", "ivd", "a smartphone app"),
            claim("general.diagnoses_or_screens", "yes", "possible melanoma"),
        ])
        assert reasons(rejections) == [R.WRONG_SECTION]
        assert profile.functions[0].general is None

    def test_a_section_claim_on_a_function_of_unknown_kind_is_dropped(self):
        profile, rejections = build([
            claim("general.diagnoses_or_screens", "yes", "possible melanoma"),
        ])
        assert reasons(rejections) == [R.WRONG_SECTION]
        assert profile.functions[0].general is None
        assert profile.functions[0].ivd is None

    def test_the_kind_opens_the_matching_section_only(self):
        profile, _ = build([claim("function.kind", "ivd", "a smartphone app")])
        assert profile.functions[0].ivd is not None
        assert profile.functions[0].general is None

    def test_a_status_claim_needs_no_kind(self):
        profile, rejections = build([
            claim("status.cdss_replaces_clinical_judgement", "yes",
                  "tells the user whether to see a doctor"),
        ])
        assert rejections == []
        assert profile.functions[0].status.cdss_replaces_clinical_judgement.value is Tri.YES

    def test_an_ask_only_field_is_dropped_even_if_the_schema_let_it_through(self):
        profile, rejections = build([
            claim("status.excluded_item", "S1-14B", "a smartphone app"),
            claim("core.functions_confirmed", "yes", "a smartphone app", -1),
        ])
        assert reasons(rejections) == [R.NOT_EXTRACTABLE, R.NOT_EXTRACTABLE]
        assert not profile.functions[0].status.excluded_item.resolved

    def test_a_funding_claim_creates_the_funding_section(self):
        profile, rejections = build([
            claim("funding.operator", "patient_or_carer", "tells the user", -1),
        ])
        assert rejections == []
        assert profile.funding.operator.value.value == "patient_or_carer"
        assert profile.untraceable_evidence() == []


class TestConflicts:
    def test_disagreeing_claims_cancel_each_other(self):
        profile, rejections = build([
            claim("function.is_software", "yes", "It is software only"),
            claim("function.is_software", "no", "a smartphone app"),
        ])
        assert reasons(rejections) == [R.CONFLICT, R.CONFLICT]
        assert not profile.functions[0].is_software.resolved

    def test_agreeing_duplicates_keep_the_first(self):
        profile, rejections = build([
            claim("function.is_software", "yes", "It is software only"),
            claim("function.is_software", "yes", "a smartphone app"),
        ])
        assert rejections == []
        assert profile.functions[0].is_software.evidence == "It is software only"

    def test_the_same_field_on_two_functions_is_not_a_conflict(self):
        functions = one_function("analyses a photo of a mole") + \
            one_function("does not   store images", "Storage", "store images")
        profile, rejections = build([
            claim("function.is_software", "yes", "It is software only", 0),
            claim("function.is_software", "no", "a smartphone app", 1),
        ], functions=functions)
        assert rejections == []


class TestFunctions:
    def test_no_proposed_function_gives_one_blank_function(self):
        profile, _ = build([], functions=[])
        assert len(profile.functions) == 1
        assert not profile.functions[0].name.resolved

    def test_a_paraphrased_description_leaves_it_unknown(self):
        profile, rejections = build([], functions=one_function("checks moles for cancer"))
        assert reasons(rejections) == [R.NO_EVIDENCE]
        assert not profile.functions[0].description.resolved
        assert profile.functions[0].name.resolved

    def test_a_name_with_no_quote_behind_it_is_left_unknown(self):
        profile, rejections = build([], functions=one_function(
            "analyses a photo of a mole", name="Mole AI", name_evidence="Mole AI"))
        assert reasons(rejections) == [R.NO_EVIDENCE]
        assert not profile.functions[0].name.resolved

    def test_the_description_is_the_text_s_own_words(self):
        profile, _ = build([], functions=one_function("analyses a photo of a mole"))
        description = profile.functions[0].description
        assert description.value == description.evidence == "analyses a photo of a mole"

    def test_functions_past_the_cap_are_dropped(self):
        many = one_function("analyses a photo of a mole") * (X.MAX_FUNCTIONS + 2)
        profile, rejections = build([], functions=many)
        assert len(profile.functions) == X.MAX_FUNCTIONS
        assert reasons(rejections) == [R.TOO_MANY_FUNCTIONS] * 2


class TestMalformed:
    @pytest.mark.parametrize("output", [None, [], {"claims": "x"}, {"functions": "x"}])
    def test_a_malformed_output_gives_an_empty_profile(self, output):
        profile, _ = X.build_profile(output, APP)
        assert len(profile.functions) == 1
        assert profile.missing()

    @pytest.mark.parametrize("raw", [
        "a string", {"target": "function.kind"},
        {"function_index": "0", "target": "function.kind", "value": "ivd", "evidence": "app"},
    ])
    def test_a_malformed_claim_is_dropped(self, raw):
        _, rejections = build([raw])
        assert reasons(rejections) == [R.MALFORMED]


class TestEntryPoints:
    OUTPUT = {"functions": one_function("analyses a photo of a mole"),
              "claims": [claim("function.is_software", "yes", "It is software only")]}

    def test_extract_replays_a_cassette(self, tmp_path):
        cassettes = CassetteClient(tmp_path)
        cassettes.record("skincheck", APP, self.OUTPUT)
        profile = X.extract(APP, client=CassetteClient(tmp_path))
        assert profile.functions[0].is_software.value is Tri.YES

    def test_extract_with_report_returns_the_same_profile_and_the_drops(self, tmp_path):
        output = dict(self.OUTPUT, claims=self.OUTPUT["claims"] + [
            claim("function.kind", "general_device", "invented")])
        CassetteClient(tmp_path).record("skincheck", APP, output)
        profile, rejections = X.extract_with_report(APP, client=CassetteClient(tmp_path))
        assert reasons(rejections) == [R.NO_EVIDENCE]
        assert profile.model_dump() == X.extract(APP, CassetteClient(tmp_path)).model_dump()

    def test_extract_without_a_client_would_go_live_and_the_suite_refuses(self):
        with pytest.raises(RuntimeError, match="live OpenAI client"):
            X.extract(APP)


class TestInstructions:
    def test_the_instructions_list_every_extractable_field(self):
        for target in F.EXTRACTABLE:
            assert f"- {target} [" in F.INSTRUCTIONS

    def test_the_instructions_never_offer_an_ask_only_field(self):
        for target in F.ASK_ONLY:
            assert f"- {target} [" not in F.INSTRUCTIONS

    def test_the_instructions_never_offer_unknown_or_no_purpose(self):
        assert "no_therapeutic_purpose |" not in F.INSTRUCTIONS
        assert "| unknown" not in F.INSTRUCTIONS

    def test_the_catalogue_covers_the_whole_schema(self):
        """A field added to profile.py must be declared extractable or ask-only."""
        every = {
            f"{section}.{name}"
            for section, model in F.SECTION_MODELS.items()
            for name in model.model_fields
            if not (section == "function" and name in F.FUNCTION_STRUCTURE)
        }
        declared = set(F.EXTRACTABLE) | set(F.ASK_ONLY)
        assert every == declared
        assert not set(F.EXTRACTABLE) & set(F.ASK_ONLY)

    def test_every_invasiveness_option_is_described(self):
        for route in Invasiveness:
            assert route.value in F.EXTRACTABLE["general.invasiveness"]
