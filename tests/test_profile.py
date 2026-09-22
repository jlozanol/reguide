"""Schema tests.

These do not test classification. They test the properties the rest of the
pipeline assumes: that unknown is distinguishable from no, that provenance
survives, that profiles do not share state, that a profile round-trips through
JSON, and that relevance gating asks for the right fields and no others.
"""

import json

import pytest
from pydantic import ValidationError

from reguide.profile import (
    IVD_AGENT_FIELDS,
    IVD_GENERAL_FIELDS,
    IVD_SELF_TEST_FIELDS,
    IVD_TYPING_FIELDS,
    PART_2_SUBSTANCE_FIELDS,
    PART_2_WOUND_FIELDS,
    ActiveType,
    Answer,
    Basis,
    BodyContact,
    ClinicalFunction,
    CoreProfile,
    DeviceKind,
    DeviceProfile,
    Duration,
    FunctionProfile,
    GeneralDeviceProfile,
    Invasiveness,
    IvdProfile,
    TherapeuticPurpose,
    Tri,
    highest_class,
    relevant_general_fields,
)


def stated(value, evidence="test evidence"):
    return Answer(value=value, basis=Basis.STATED, evidence=evidence)


def general_profile(**fields):
    """A single-function general-device product, for brevity in tests."""
    function = FunctionProfile(
        name=stated("function"),
        description=stated("a function"),
        kind=stated(DeviceKind.GENERAL),
        is_software=stated(fields.pop("is_software", Tri.NO)),
        general=GeneralDeviceProfile(),
    )
    profile = DeviceProfile(functions=[function])
    for name, value in fields.items():
        if name in CoreProfile.model_fields:
            setattr(profile.core, name, stated(value))
        elif name in FunctionProfile.model_fields:
            setattr(function, name, stated(value))
        else:
            setattr(function.general, name, stated(value))
    return profile


def ivd_profile():
    """A single-function IVD product."""
    function = FunctionProfile(
        name=stated("function"), description=stated("an IVD function"),
        kind=stated(DeviceKind.IVD), is_software=stated(Tri.NO), ivd=IvdProfile(),
    )
    return DeviceProfile(functions=[function])


def only(profile):
    return profile.functions[0]


class TestAnswer:
    def test_new_answer_is_unresolved(self):
        assert Answer().resolved is False
        assert Answer().value is None

    @pytest.mark.parametrize(
        "basis,expected",
        [(Basis.STATED, True), (Basis.ANSWERED, True),
         (Basis.DEFAULTED, True), (Basis.UNKNOWN, False)],
    )
    def test_resolved_follows_basis(self, basis, expected):
        evidence = "quoted" if basis in (Basis.STATED, Basis.ANSWERED) else None
        assert Answer(value="x", basis=basis, evidence=evidence).resolved is expected

    @pytest.mark.parametrize("basis", [Basis.STATED, Basis.ANSWERED])
    def test_a_claim_without_evidence_is_rejected(self, basis):
        """The citation promise is enforced at construction, not at report time."""
        with pytest.raises(ValidationError):
            Answer(value="x", basis=basis)

    def test_a_legal_default_needs_no_evidence(self):
        assert Answer(value="x", basis=Basis.DEFAULTED).resolved is True

    def test_a_value_without_a_basis_is_still_unresolved(self):
        """The failure that matters: a value appearing from nowhere."""
        assert Answer(value=Tri.YES).resolved is False

    def test_evidence_is_retained(self):
        assert stated(Tri.YES, "implanted for up to 12 months").evidence == (
            "implanted for up to 12 months"
        )


class TestTri:
    def test_unknown_is_not_no(self):
        assert Tri.UNKNOWN != Tri.NO


class TestProfileIsolation:
    def test_two_profiles_do_not_share_answer_objects(self):
        a, b = CoreProfile(), CoreProfile()
        a.product_name = stated("Product A")
        assert b.product_name.resolved is False

    def test_two_functions_do_not_share_answer_objects(self):
        a, b = FunctionProfile(), FunctionProfile()
        a.name = stated("Function A")
        assert b.name.resolved is False


class TestRelevanceGating:
    def test_an_empty_profile_asks_only_the_opening_questions(self):
        """Before the route is known the list stays short."""
        profile = general_profile()
        fields = relevant_general_fields(only(profile))
        assert "invasiveness" in fields
        assert "duration" not in fields
        assert "barrier_compression_or_absorption" not in fields

    def test_establishing_the_route_opens_the_branch(self):
        profile = general_profile(invasiveness=Invasiveness.SURGICALLY_INVASIVE)
        fields = relevant_general_fields(only(profile))
        assert "duration" in fields
        assert "body_contact" in fields
        assert "contacts_injured_skin_or_mucous_membrane" not in fields

    def test_injured_skin_opens_the_2_4_questions(self):
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE,
            contacts_injured_skin_or_mucous_membrane=Tri.YES,
        )
        missing = profile.missing()
        assert "functions.0.general.barrier_compression_or_absorption" in missing
        assert ("functions.0.general.principally_for_breached_dermis_secondary_intent"
                in missing)
        assert "functions.0.general.channels_or_stores_blood_for_administration" not in missing

    def test_substances_open_the_2_2_and_2_3_questions(self):
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE,
            handles_substances_for_administration=Tri.YES,
        )
        missing = profile.missing()
        assert "functions.0.general.saline_only_flush_or_patency" in missing
        assert "functions.0.general.connected_to_active_device" not in missing
        assert "functions.0.general.barrier_compression_or_absorption" not in missing

    def test_answering_can_open_one_more_question(self):
        """Other liquids need the connection question; modifying needs 2.3(2)."""
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE,
            handles_substances_for_administration=Tri.YES,
            channels_or_stores_liquid_or_gas_for_administration=Tri.YES,
            modifies_composition_of_blood_or_infusion=Tri.YES,
        )
        missing = profile.missing()
        assert "functions.0.general.connected_to_active_device" in missing
        assert ("functions.0.general.treatment_is_filtration_centrifugation_or_exchange"
                in missing)

    def test_software_is_not_asked_about_animal_tissue(self):
        profile = general_profile(
            is_software=Tri.YES, invasiveness=Invasiveness.NON_INVASIVE
        )
        fields = relevant_general_fields(only(profile))
        assert "animal_or_microbial_origin" not in fields
        assert "human_blood_derivative" not in fields

    def test_a_bandage_is_not_asked_about_ionising_radiation(self):
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE, active_type=ActiveType.NOT_ACTIVE
        )
        fields = relevant_general_fields(only(profile))
        assert "delivers_ionising_radiation" not in fields

    def test_diagnostic_software_is_asked_who_decides(self):
        profile = general_profile(
            is_software=Tri.YES,
            invasiveness=Invasiveness.NON_INVASIVE,
            active_type=ActiveType.DIAGNOSTIC,
            clinical_function=ClinicalFunction.DIAGNOSE_OR_SCREEN,
        )
        missing = profile.missing()
        assert "functions.0.general.decision_maker" in missing
        assert "functions.0.general.condition_severity" in missing

    def test_relevant_never_repeats_a_field(self):
        profile = general_profile(
            invasiveness=Invasiveness.IMPLANTABLE, active_type=ActiveType.THERAPEUTIC
        )
        fields = relevant_general_fields(only(profile))
        assert len(fields) == len(set(fields))

    def test_gating_asks_far_fewer_than_every_field(self):
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE, active_type=ActiveType.NOT_ACTIVE
        )
        fields = relevant_general_fields(only(profile))
        assert len(fields) < len(GeneralDeviceProfile.model_fields) / 2


class TestPrune:
    def test_pruning_clears_fields_gating_never_asked_for(self):
        """An answer nobody asked for is a guess that survived."""
        profile = general_profile(
            invasiveness=Invasiveness.SURGICALLY_INVASIVE,
            duration=Duration.SHORT_TERM,
            body_contact=BodyContact.BREACHED_SKIN,
            absorbed_or_chemically_changed=Tri.NO,
            contacts_injured_skin_or_mucous_membrane=Tri.YES,
        )
        function = only(profile)
        assert function.general.contacts_injured_skin_or_mucous_membrane.resolved
        function.prune()
        assert function.general.contacts_injured_skin_or_mucous_membrane.resolved is False
        assert function.general.duration.resolved is True

    def test_pruning_leaves_a_complete_function_complete(self):
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE,
            active_type=ActiveType.NOT_ACTIVE,
            contacts_injured_skin_or_mucous_membrane=Tri.YES,
            barrier_compression_or_absorption=Tri.YES,
            principally_for_breached_dermis_secondary_intent=Tri.NO,
            handles_substances_for_administration=Tri.NO,
            incorporates_medicine=Tri.NO,
            contraceptive_or_sti_prevention=Tri.NO,
            disinfects_another_device=Tri.NO,
            human_blood_derivative=Tri.NO,
            is_export_only=Tri.NO,
            cares_for_contact_lenses=Tri.NO,
            records_images_or_anatomical_model=Tri.NO,
            contains_non_viable_animal_material=Tri.NO,
            is_blood_bag=Tri.NO,
            administers_by_inhalation=Tri.NO,
            is_substance_through_orifice_or_skin=Tri.NO,
        )
        before = only(profile).missing()
        only(profile).prune()
        assert only(profile).missing() == before


class TestTermination:
    """Gating can lengthen the question list. It must still end."""

    def test_answering_every_question_terminates(self):
        profile = general_profile()
        answers = {
            "invasiveness": Invasiveness.NON_INVASIVE,
            "active_type": ActiveType.DIAGNOSTIC,
            "clinical_function": ClinicalFunction.DIAGNOSE_OR_SCREEN,
            "contacts_injured_skin_or_mucous_membrane": Tri.YES,
            "barrier_compression_or_absorption": Tri.NO,
            "principally_for_breached_dermis_secondary_intent": Tri.YES,
            "handles_substances_for_administration": Tri.NO,
            "therapeutic_purpose": TherapeuticPurpose.DISEASE,
            "excluded_item": "none",
        }
        for _ in range(60):
            missing = profile.missing()
            if not missing:
                break
            dotted = missing[0]
            name = dotted.rsplit(".", 1)[1]
            target = profile.core
            if dotted.startswith("functions."):
                function = only(profile)
                target = function
                if ".general." in dotted:
                    target = function.general
                elif ".status." in dotted:
                    target = function.status
            value = answers.get(name, Tri.NO if name != "sample_type" else "serum")
            setattr(target, name, stated(value))
        else:
            pytest.fail("the interview did not terminate in 60 questions")
        assert profile.missing() == []


class TestEvidenceTraceability:
    def test_evidence_outside_the_source_is_flagged(self):
        profile = general_profile()
        profile.source_text = "a wound dressing for minor cuts"
        profile.core.product_name = Answer(
            value="Dressing", basis=Basis.STATED, evidence="invented phrase"
        )
        assert "core.product_name" in profile.untraceable_evidence()

    def test_quoted_evidence_passes(self):
        profile = general_profile()
        profile.source_text = "a wound dressing for minor cuts"
        profile.core.product_name = Answer(
            value="Dressing", basis=Basis.STATED, evidence="wound dressing"
        )
        assert "core.product_name" not in profile.untraceable_evidence()


class TestIvdGating:
    def test_a_named_exception_stops_the_questions(self):
        """An instrument is classified by that fact alone, clause 1.6(2)(a)."""
        profile = ivd_profile()
        only(profile).ivd.is_ivd_instrument = stated(Tri.YES)
        remaining = [m for m in profile.missing() if ".ivd." in m]
        assert all("purpose" not in m and "self_test" not in m for m in remaining)

    def test_a_specimen_receptacle_asks_only_about_self_testing(self):
        """Clause 1.6(2)(b) excludes a receptacle intended for self-testing."""
        profile = ivd_profile()
        only(profile).ivd.is_specimen_receptacle = stated(Tri.YES)
        remaining = [m for m in profile.missing() if ".ivd." in m]
        assert "functions.0.ivd.is_self_test" in remaining
        assert all("purpose" not in m for m in remaining)

        only(profile).ivd.is_self_test = stated(Tri.NO)
        assert all("purpose" not in m for m in profile.missing() if ".ivd." in m)

    def test_a_self_test_receptacle_falls_back_to_the_ordinary_rules(self):
        profile = ivd_profile()
        only(profile).ivd.is_specimen_receptacle = stated(Tri.YES)
        only(profile).ivd.is_self_test = stated(Tri.YES)
        assert "functions.0.ivd.detects_infectious_agent" in profile.missing()
        assert "functions.0.ivd.result_not_determining_serious_condition" in profile.missing()

    @staticmethod
    def _ordinary(profile):
        """No named exception applies, so the ordinary rules are asked."""
        section = only(profile).ivd
        for name in ("is_ivd_instrument", "is_specimen_receptacle", "is_culture_medium",
                     "is_quality_control_material", "is_export_only"):
            setattr(section, name, stated(Tri.NO))
        return section

    def _ivd_missing(self, profile):
        return {m.rsplit(".", 1)[1] for m in profile.missing() if ".ivd." in m}

    def test_the_gates_close_their_paragraphs(self):
        profile = ivd_profile()
        section = self._ordinary(profile)
        for gate in ("detects_infectious_agent", "types_blood_or_tissue", "is_self_test"):
            setattr(section, gate, stated(Tri.NO))
        missing = self._ivd_missing(profile)
        assert missing == set(IVD_GENERAL_FIELDS)

    @pytest.mark.parametrize("gate,opened", [
        ("detects_infectious_agent", IVD_AGENT_FIELDS),
        ("types_blood_or_tissue", IVD_TYPING_FIELDS),
        ("is_self_test", IVD_SELF_TEST_FIELDS),
    ])
    def test_each_gate_opens_its_paragraphs(self, gate, opened):
        """Schedule 2A clauses 1.1 and 1.3 agents, 1.2 typing, 1.4 self-testing."""
        profile = ivd_profile()
        section = self._ordinary(profile)
        for name in ("detects_infectious_agent", "types_blood_or_tissue", "is_self_test"):
            setattr(section, name, stated(Tri.YES if name == gate else Tri.NO))
        missing = self._ivd_missing(profile)
        assert set(opened) <= missing
        others = set(IVD_AGENT_FIELDS + IVD_TYPING_FIELDS + IVD_SELF_TEST_FIELDS) - set(opened)
        assert not (others & missing)


class TestBranching:
    def test_a_general_function_carries_no_ivd_section(self):
        profile = general_profile()
        assert only(profile).ivd is None
        assert only(profile).branch() is DeviceKind.GENERAL

    def test_a_product_with_no_functions_has_no_kinds(self):
        assert DeviceProfile().kinds() == set()

    def test_a_product_can_touch_two_rule_families(self):
        profile = general_profile()
        profile.functions.append(FunctionProfile(kind=stated(DeviceKind.IVD),
                                                 ivd=IvdProfile()))
        assert profile.kinds() == {DeviceKind.GENERAL, DeviceKind.IVD}


class TestHighestClass:
    def test_the_highest_general_class_governs(self):
        assert highest_class(["Class I", "Class IIb", "Class IIa"]) == {
            "general": "Class IIb"
        }

    def test_families_do_not_collapse_into_one_answer(self):
        """A product with both kinds needs two ARTG entries, so two answers."""
        result = highest_class(["Class IIa", "Class 3 IVD", "Class 1 IVD"])
        assert result == {"general": "Class IIa", "ivd": "Class 3 IVD"}

    def test_a_generator_argument_is_not_exhausted_by_the_first_family(self):
        result = highest_class(c for c in ["Class IIa", "Class 3 IVD"])
        assert set(result) == {"general", "ivd"}

    def test_an_empty_input_gives_an_empty_answer(self):
        assert highest_class([]) == {}


class TestRoundTrip:
    def test_profile_survives_json(self):
        profile = general_profile(
            invasiveness=Invasiveness.SURGICALLY_INVASIVE,
            duration=Duration.SHORT_TERM,
            body_contact=BodyContact.CENTRAL_CIRCULATION,
        )
        profile.source_text = "a catheter"
        restored = DeviceProfile.model_validate(json.loads(profile.model_dump_json()))
        general = restored.functions[0].general
        assert general.body_contact.value is BodyContact.CENTRAL_CIRCULATION
        assert general.duration.basis is Basis.STATED
        assert general.invasiveness.evidence == "test evidence"
        assert restored.source_text == "a catheter"

    def test_unknown_fields_survive_json(self):
        restored = DeviceProfile.model_validate(
            json.loads(ivd_profile().model_dump_json())
        )
        assert restored.functions[0].ivd.detects_infectious_agent.resolved is False

    def test_a_multi_function_product_survives_json(self):
        profile = general_profile()
        profile.functions.append(FunctionProfile(
            name=stated("second"), description=stated("an IVD function"),
            kind=stated(DeviceKind.IVD), is_software=stated(Tri.NO),
            ivd=IvdProfile()))
        restored = DeviceProfile.model_validate(json.loads(profile.model_dump_json()))
        assert len(restored.functions) == 2
        assert restored.functions[1].branch() is DeviceKind.IVD


class TestLegalVocabulary:
    def test_duration_bands_are_the_legal_ones(self):
        assert {d.value for d in Duration} == {"transient", "short_term", "long_term"}

    def test_part_2_has_a_field_for_every_paragraph(self):
        """2.2(1)(a)-(c), 2.2A, 2.3(1)-(2), 2.4(3)-(4), plus the two gates."""
        names = set(GeneralDeviceProfile.model_fields)
        for field in PART_2_SUBSTANCE_FIELDS + PART_2_WOUND_FIELDS + [
            "handles_substances_for_administration",
            "contacts_injured_skin_or_mucous_membrane",
            "connected_to_active_device",
            "treatment_is_filtration_centrifugation_or_exchange",
        ]:
            assert field in names
