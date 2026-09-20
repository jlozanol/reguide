"""Schema tests.

These do not test classification. They test the properties the rest of the
pipeline assumes: that unknown is distinguishable from no, that provenance
survives, that profiles do not share state, that a profile round-trips through
JSON, and that relevance gating asks for the right fields and no others.
"""

import json

import pytest

from reguide.profile import (
    ActiveType,
    Answer,
    Basis,
    BodyContact,
    ClinicalFunction,
    CoreProfile,
    DeviceKind,
    DeviceProfile,
    Duration,
    GeneralDeviceProfile,
    Invasiveness,
    IvdProfile,
    Tri,
    WoundFunction,
    relevant_general_fields,
)


def stated(value, evidence="test evidence"):
    return Answer(value=value, basis=Basis.STATED, evidence=evidence)


def general_profile(**fields):
    profile = DeviceProfile(general=GeneralDeviceProfile())
    profile.core.kind = stated(DeviceKind.GENERAL)
    for name, value in fields.items():
        section = profile.core if name in CoreProfile.model_fields else profile.general
        setattr(section, name, stated(value))
    return profile


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
        assert Answer(value="x", basis=basis).resolved is expected

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
        a.device_name = stated("Device A")
        assert b.device_name.resolved is False


class TestRelevanceGating:
    def test_an_empty_profile_asks_only_the_opening_questions(self):
        """Before the route is known the list stays short."""
        profile = general_profile()
        fields = relevant_general_fields(profile.core, profile.general)
        assert "invasiveness" in fields
        assert "duration" not in fields
        assert "wound_function" not in fields

    def test_establishing_the_route_opens_the_branch(self):
        profile = general_profile(invasiveness=Invasiveness.SURGICALLY_INVASIVE)
        fields = relevant_general_fields(profile.core, profile.general)
        assert "duration" in fields
        assert "body_contact" in fields
        assert "contacts_injured_skin" not in fields

    def test_injured_skin_opens_the_wound_function_question(self):
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE, contacts_injured_skin=Tri.YES
        )
        assert "general.wound_function" in profile.missing()

    def test_secondary_intent_opens_one_more_question(self):
        """Answering can lengthen the list. That is correct behaviour."""
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE,
            contacts_injured_skin=Tri.YES,
            wound_function=WoundFunction.SECONDARY_INTENT,
        )
        assert "general.breaches_dermis" in profile.missing()

    def test_a_barrier_dressing_is_never_asked_about_the_dermis(self):
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE,
            contacts_injured_skin=Tri.YES,
            wound_function=WoundFunction.MECHANICAL_BARRIER,
        )
        assert "general.breaches_dermis" not in profile.missing()

    def test_software_is_not_asked_about_animal_tissue(self):
        profile = general_profile(
            is_software_only=Tri.YES, invasiveness=Invasiveness.NON_INVASIVE
        )
        fields = relevant_general_fields(profile.core, profile.general)
        assert "animal_or_microbial_origin" not in fields
        assert "human_blood_derivative" not in fields

    def test_a_bandage_is_not_asked_about_ionising_radiation(self):
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE, active_type=ActiveType.NOT_ACTIVE
        )
        fields = relevant_general_fields(profile.core, profile.general)
        assert "delivers_ionising_radiation" not in fields

    def test_diagnostic_software_is_asked_who_decides(self):
        profile = general_profile(
            is_software_only=Tri.YES,
            invasiveness=Invasiveness.NON_INVASIVE,
            active_type=ActiveType.DIAGNOSTIC,
            clinical_function=ClinicalFunction.DIAGNOSE_OR_SCREEN,
        )
        missing = profile.missing()
        assert "general.decision_maker" in missing
        assert "general.condition_severity" in missing

    def test_relevant_never_repeats_a_field(self):
        profile = general_profile(
            invasiveness=Invasiveness.IMPLANTABLE, active_type=ActiveType.THERAPEUTIC
        )
        fields = relevant_general_fields(profile.core, profile.general)
        assert len(fields) == len(set(fields))

    def test_gating_asks_far_fewer_than_every_field(self):
        profile = general_profile(
            invasiveness=Invasiveness.NON_INVASIVE, active_type=ActiveType.NOT_ACTIVE
        )
        fields = relevant_general_fields(profile.core, profile.general)
        assert len(fields) < len(GeneralDeviceProfile.model_fields) / 2


class TestIvdGating:
    def test_a_named_exception_stops_the_questions(self):
        """A specimen receptacle is classified by that fact alone."""
        profile = DeviceProfile(ivd=IvdProfile())
        profile.core.kind = stated(DeviceKind.IVD)
        profile.ivd.is_instrument_or_receptacle = stated(Tri.YES)
        remaining = [m for m in profile.missing() if m.startswith("ivd.")]
        assert all("purpose" not in m and "self_test" not in m for m in remaining)

    def test_a_transmissible_agent_opens_the_risk_questions(self):
        profile = DeviceProfile(ivd=IvdProfile())
        profile.core.kind = stated(DeviceKind.IVD)
        profile.ivd.is_instrument_or_receptacle = stated(Tri.NO)
        profile.ivd.is_quality_control_material = stated(Tri.NO)
        profile.ivd.is_export_only = stated(Tri.NO)
        profile.ivd.detects_transmissible_agent = stated(Tri.YES)
        assert "ivd.transmission_risk_to_population" in profile.missing()


class TestBranching:
    def test_a_general_device_carries_no_ivd_section(self):
        profile = general_profile()
        assert profile.ivd is None
        assert profile.branch() is DeviceKind.GENERAL

    def test_branch_is_none_until_kind_is_established(self):
        assert DeviceProfile().branch() is None


class TestRoundTrip:
    def test_profile_survives_json(self):
        profile = general_profile(
            invasiveness=Invasiveness.SURGICALLY_INVASIVE,
            duration=Duration.SHORT_TERM,
            body_contact=BodyContact.CENTRAL_CIRCULATION,
        )
        profile.source_text = "a catheter"
        restored = DeviceProfile.model_validate(json.loads(profile.model_dump_json()))
        assert restored.general.body_contact.value is BodyContact.CENTRAL_CIRCULATION
        assert restored.general.duration.basis is Basis.STATED
        assert restored.general.invasiveness.evidence == "test evidence"
        assert restored.source_text == "a catheter"

    def test_unknown_fields_survive_json(self):
        restored = DeviceProfile.model_validate(
            json.loads(DeviceProfile(ivd=IvdProfile()).model_dump_json())
        )
        assert restored.ivd.purpose.resolved is False


class TestLegalVocabulary:
    def test_duration_bands_are_the_legal_ones(self):
        assert {d.value for d in Duration} == {"transient", "short_term", "long_term"}

    def test_wound_function_covers_every_limb_of_sub_rule_2_4(self):
        assert len(WoundFunction) == 4
