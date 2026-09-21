"""Tests for the scoring harness itself.

The harness decides what "agree" means, so its verdicts are pinned here on
copies of real fixtures edited to produce each kind of miss.
"""

import copy
import json
from pathlib import Path

import pytest

from reguide import scoring as SC
from reguide.profile import DeviceKind
from reguide.rules import engine as E

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture(slug: str) -> dict:
    return json.loads((FIXTURES / f"{slug}.json").read_text())


@pytest.fixture(autouse=True)
def exclusions():
    SC.S.load_exclusions(SC.EXCLUSIONS)


class TestRuleReferences:
    @pytest.mark.parametrize("expected,got,match", [
        ("s2-3.2", "s2-3.2(2)", True),
        ("s2-3.2", "s2-3.2", True),
        ("s2a-1.6(2)(a)", "s2a-1.6(2)(a)", True),
        ("s2a-1.1", "s2a-1.10", False),
        ("s2a-1.6(2)(a)", "s2a-1.6(2)(b)", False),
        ("s2-4.5(2)", "s2-4.5(2)(b)", True),
        ("s2-2.2", "s2-2.2A", False),
    ])
    def test_a_reference_accepts_its_own_paragraphs_only(self, expected, got, match):
        assert SC.rule_matches(expected, got) is match

    def test_family_prefix_and_trailing_prose(self):
        assert SC.expected_rule_id(DeviceKind.IVD, "1.6(2)(c)") == "s2a-1.6(2)(c)"
        assert SC.expected_rule_id(DeviceKind.GENERAL, "2.4(3) with sterile supply") \
            == "s2-2.4(3)"
        assert SC.expected_rule_id(DeviceKind.GENERAL, "S1-14B") is None


class TestVerdicts:
    def test_agree(self):
        [row] = SC.score_fixture("culture_media", fixture("culture_media"))
        assert row.verdict == SC.AGREE
        assert (row.got_class, row.got_rules) == ("Class 1 IVD", ["s2a-1.6(2)(c)"])

    def test_wrong_class(self):
        data = fixture("culture_media")
        data["functions"][0]["expected_class"] = "Class 2 IVD"
        [row] = SC.score_fixture("x", data)
        assert row.verdict == SC.WRONG_CLASS
        assert row.detail == "cited s2a-1.6(2)(c)"

    def test_wrong_rule(self):
        data = fixture("culture_media")
        data["functions"][0]["expected_rule"] = "1.6(2)(a)"
        [row] = SC.score_fixture("x", data)
        assert row.verdict == SC.WRONG_RULE

    def test_gate(self):
        data = fixture("culture_media")
        data["functions"][0]["expected_status"] = "excluded_from_regulation"
        [row] = SC.score_fixture("x", data)
        assert row.verdict == SC.GATE
        assert row.got_class is None

    def test_no_result_names_what_stopped_it(self):
        [row] = SC.score_fixture("screw_transient", fixture("screw_transient"))
        assert row.verdict == SC.NO_RESULT
        assert row.detail == "s2 (Schedule 2 rules not implemented)"

    def test_an_excluded_function_agrees_without_being_classified(self, monkeypatch):
        seen = []
        real = SC.classify

        def spy(profile, indices):
            seen.extend(indices)
            return real(profile, indices)

        monkeypatch.setattr(SC, "classify", spy)
        rows = SC.score_fixture("imaging_platform", fixture("imaging_platform"))
        assert rows[0].verdict == SC.AGREE
        assert rows[0].got_class is None
        assert seen == [1, 2]

    def test_a_product_the_gate_stops_is_never_classified(self, monkeypatch):
        def refuse(profile, indices):
            raise AssertionError("classified a function the gate did not mark regulated")

        monkeypatch.setattr(SC, "classify", refuse)
        [row] = SC.score_fixture("wellness_sleep_tracker", fixture("wellness_sleep_tracker"))
        assert row.verdict == SC.AGREE


class TestQualifiers:
    """Schedule 2 is not written yet, so the engine is stood in for."""

    @staticmethod
    def _stand_in(monkeypatch, qualifiers):
        def fake(profile, indices):
            outcome = SC.Classification(
                result="Class I", hits=[E.RuleHit("s2-2.4(3)", "c", "Class I", "b")],
                qualifiers=[E.Qualifier(code, code, "c", "b") for code in qualifiers])
            return {i: outcome for i in indices}
        monkeypatch.setattr(SC, "classify", fake)

    def test_the_right_qualifier_agrees(self, monkeypatch):
        self._stand_in(monkeypatch, ["supplied_sterile"])
        [row] = SC.score_fixture("s", fixture("sterile_barrier_dressing"))
        assert row.verdict == SC.AGREE

    def test_a_missing_qualifier_is_a_miss(self, monkeypatch):
        self._stand_in(monkeypatch, [])
        [row] = SC.score_fixture("s", fixture("sterile_barrier_dressing"))
        assert row.verdict == SC.WRONG_QUALIFIER
        assert row.detail == "qualifiers none, fixture supplied_sterile"

    def test_an_extra_qualifier_is_a_miss(self, monkeypatch):
        self._stand_in(monkeypatch, ["supplied_sterile", "measuring_function"])
        [row] = SC.score_fixture("s", fixture("sterile_barrier_dressing"))
        assert row.verdict == SC.WRONG_QUALIFIER

    def test_the_report_shows_both_sides(self, monkeypatch):
        self._stand_in(monkeypatch, [])
        text = SC.report(SC.Score(SC.score_fixture("s", fixture("sterile_barrier_dressing"))))
        assert "| Class I + supplied_sterile (2.4(3)) | Class I (s2-2.4(3)) | wrong qualifier |" \
            in text


class TestScore:
    def test_a_fixture_agrees_only_when_every_function_does(self):
        pack = fixture("prothrombin_self_test_pack")
        score = SC.Score(SC.score_fixture("pack", pack))
        assert [r.verdict for r in score.rows] == [SC.AGREE, SC.AGREE, SC.NO_RESULT]
        assert score.agreeing_fixtures == []
        assert score.agreeing_functions == 2

    def test_misses_are_ordered_worst_first(self):
        wrong = copy.deepcopy(fixture("culture_media"))
        wrong["functions"][0]["expected_class"] = "Class 4 IVD"
        rows = (SC.score_fixture("b_refused", fixture("screw_transient"))
                + SC.score_fixture("a_wrong", wrong))
        assert [r.verdict for r in SC.Score(rows).misses] == [SC.WRONG_CLASS, SC.NO_RESULT]

    def test_run_scores_verified_only_by_default(self):
        assert len(SC.run().fixtures) < len(SC.run(include_unverified=True).fixtures)


class TestReport:
    def test_headline_and_table(self):
        rows = (SC.score_fixture("culture_media", fixture("culture_media"))
                + SC.score_fixture("screw_transient", fixture("screw_transient")))
        text = SC.report(SC.Score(rows))
        assert text.startswith("Agreement: 1/2 fixtures (50%), 1/2 functions\n")
        assert "Misses: 1 no result" in text
        assert "| fixture | function | expected | got | miss | detail |" in text
        assert "| screw_transient | Metal fixation screw, intraoperative | Class IIa (3.2(2)) " \
               "| none | no result |" in text

    def test_no_table_when_nothing_is_missed(self):
        text = SC.report(SC.Score(SC.score_fixture("culture_media", fixture("culture_media"))))
        assert "|" not in text

    def test_the_script_exits_non_zero_on_a_verified_wrong_class(self, monkeypatch, capsys):
        import importlib.util
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location("score", root / "scripts" / "score.py")
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)

        data = fixture("culture_media")
        data["functions"][0]["expected_class"] = "Class 2 IVD"
        monkeypatch.setattr(script, "run",
                            lambda include_unverified=False: SC.Score(SC.score_fixture("x", data)))
        assert script.main([]) == 1
        assert "wrong class" in capsys.readouterr().out
