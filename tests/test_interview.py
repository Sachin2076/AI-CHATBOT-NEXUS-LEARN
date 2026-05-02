"""
tests/test_interview.py — Interview scoring logic tests (Gap 5)

Tests the three scoring functions extracted to module level in interview.py:
  • recalc_overall()      — weighted score calculation
  • apply_verdict_rules() — pass/fail guardrail enforcement
  • calc_grade()          — letter grade mapping

These run with zero external dependencies (no DB, no Ollama, no Flask).

Run with:
    pytest tests/test_interview.py -v
"""

import pytest
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from interview import recalc_overall, apply_verdict_rules, calc_grade


# ═════════════════════════════════════════════════════════════
#  recalc_overall — weighted: intro 20%, behaviour 40%, technical 40%
# ═════════════════════════════════════════════════════════════

class TestRecalcOverall:

    def test_equal_scores_70(self):
        assert recalc_overall(70, 70, 70) == 70

    def test_equal_scores_100(self):
        assert recalc_overall(100, 100, 100) == 100

    def test_equal_scores_0(self):
        assert recalc_overall(0, 0, 0) == 0

    def test_weights_intro_dominance(self):
        # Only intro = 100, rest 0 → 20
        assert recalc_overall(100, 0, 0) == 20

    def test_weights_behaviour_dominance(self):
        # Only behaviour = 100, rest 0 → 40
        assert recalc_overall(0, 100, 0) == 40

    def test_weights_technical_dominance(self):
        # Only technical = 100, rest 0 → 40
        assert recalc_overall(0, 0, 100) == 40

    def test_behaviour_and_technical_equal_intro_half(self):
        # intro=50 (→10), behaviour=80 (→32), technical=80 (→32) = 74
        assert recalc_overall(50, 80, 80) == 74

    def test_boundary_pass_threshold(self):
        # 20+40+40 of 65 = 65 exactly
        assert recalc_overall(65, 65, 65) == 65

    def test_rounding_applied(self):
        # 75*0.20 + 72*0.40 + 73*0.40 = 15 + 28.8 + 29.2 = 73.0
        assert recalc_overall(75, 72, 73) == 73


# ═════════════════════════════════════════════════════════════
#  apply_verdict_rules
# ═════════════════════════════════════════════════════════════

class TestApplyVerdictRules:

    # Hard FAIL conditions
    def test_overall_below_65_forces_fail(self):
        assert apply_verdict_rules(60, 70, 70, 70, "PASS") == "FAIL"

    def test_overall_exactly_64_forces_fail(self):
        assert apply_verdict_rules(64, 70, 70, 70, "PASS") == "FAIL"

    def test_any_round_below_45_forces_fail(self):
        assert apply_verdict_rules(80, 44, 80, 80, "PASS") == "FAIL"

    def test_behaviour_below_45_forces_fail(self):
        assert apply_verdict_rules(80, 80, 40, 80, "PASS") == "FAIL"

    def test_technical_below_45_forces_fail(self):
        assert apply_verdict_rules(80, 80, 80, 44, "PASS") == "FAIL"

    def test_all_below_45_forces_fail(self):
        assert apply_verdict_rules(40, 30, 30, 30, "PASS") == "FAIL"

    # Pass override — model says FAIL but scores are good
    def test_pass_override_when_overall_75_and_all_rounds_gte_45(self):
        assert apply_verdict_rules(75, 50, 75, 75, "FAIL") == "PASS"

    def test_pass_override_requires_overall_gte_75(self):
        # overall=70 → not enough to override FAIL
        assert apply_verdict_rules(70, 50, 70, 70, "FAIL") == "FAIL"

    # Respect model verdict when valid
    def test_respects_pass_when_scores_good(self):
        assert apply_verdict_rules(80, 60, 80, 80, "PASS") == "PASS"

    def test_respects_fail_when_borderline(self):
        # overall=67, all rounds ≥ 45, but model said FAIL and overall < 75
        assert apply_verdict_rules(67, 50, 67, 67, "FAIL") == "FAIL"

    # Boundary values
    def test_boundary_exactly_65_all_rounds_gte_45_pass_verdict(self):
        assert apply_verdict_rules(65, 45, 65, 65, "PASS") == "PASS"

    def test_boundary_one_round_exactly_45(self):
        assert apply_verdict_rules(70, 45, 70, 70, "PASS") == "PASS"

    def test_boundary_one_round_exactly_44(self):
        assert apply_verdict_rules(70, 44, 70, 70, "PASS") == "FAIL"

    # Unknown/garbage verdict from model
    def test_unknown_verdict_string_treated_as_fail(self):
        result = apply_verdict_rules(60, 70, 70, 70, "MAYBE")
        assert result == "FAIL"   # overall < 65 triggers hard fail


# ═════════════════════════════════════════════════════════════
#  calc_grade
# ═════════════════════════════════════════════════════════════

class TestCalcGrade:

    def test_100_is_A(self):
        assert calc_grade(100) == "A"

    def test_90_is_A(self):
        assert calc_grade(90) == "A"

    def test_89_is_B(self):
        assert calc_grade(89) == "B"

    def test_75_is_B(self):
        assert calc_grade(75) == "B"

    def test_74_is_C(self):
        assert calc_grade(74) == "C"

    def test_65_is_C(self):
        assert calc_grade(65) == "C"

    def test_64_is_D(self):
        assert calc_grade(64) == "D"

    def test_50_is_D(self):
        assert calc_grade(50) == "D"

    def test_49_is_F(self):
        assert calc_grade(49) == "F"

    def test_0_is_F(self):
        assert calc_grade(0) == "F"
