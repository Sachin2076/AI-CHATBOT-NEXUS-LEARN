import re
import unittest


def _ex(raw, key):
    m = re.search(rf"{key}:\s*(.+?)(?=\n[A-Z_]{{2,}}:|$)", raw, re.DOTALL)
    return m.group(1).strip() if m else ""


def calc_grade(score):
    return "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"


def apply_verdict_rules(overall, intro, behaviour, technical, raw_verdict):
    verdict = raw_verdict.upper()
    if overall < 65 or min(intro, behaviour, technical) < 45:
        verdict = "FAIL"
    elif overall >= 65 and min(intro, behaviour, technical) >= 45:
        if verdict == "FAIL" and overall >= 75:
            verdict = "PASS"
    return verdict


def recalc_overall(intro, behaviour, technical):
    return round(intro * 0.20 + behaviour * 0.40 + technical * 0.40)


class TestExParser(unittest.TestCase):

    def test_simple_field(self):
        raw = "NAME: Alice\nSCORE: 90"
        self.assertEqual(_ex(raw, "NAME"), "Alice")

    def test_last_field_no_trailing_newline(self):
        raw = "NAME: Alice\nSCORE: 90"
        self.assertEqual(_ex(raw, "SCORE"), "90")

    def test_multiline_field(self):
        raw = "COMMENT: line one\nline two\nNAME: Bob"
        self.assertEqual(_ex(raw, "COMMENT"), "line one\nline two")

    def test_missing_key_returns_empty(self):
        raw = "NAME: Alice\nSCORE: 90"
        self.assertEqual(_ex(raw, "MISSING"), "")

    def test_empty_raw_returns_empty(self):
        self.assertEqual(_ex("", "NAME"), "")

    def test_strips_whitespace(self):
        raw = "NAME:   Alice   \nSCORE: 90"
        self.assertEqual(_ex(raw, "NAME"), "Alice")

    def test_does_not_bleed_into_next_field(self):
        raw = "INTRO: Hello world\nOUTRO: Goodbye"
        self.assertEqual(_ex(raw, "INTRO"), "Hello world")

    def test_numeric_score_field(self):
        raw = "SCORE: 87\nGRADE: B"
        self.assertEqual(_ex(raw, "SCORE"), "87")

    def test_key_with_underscore(self):
        raw = "OVERALL_SCORE: 72\nVERDICT: PASS"
        self.assertEqual(_ex(raw, "OVERALL_SCORE"), "72")

    def test_pipe_separated_values(self):
        raw = "TAGS: python|flask|unittest\nEND: done"
        self.assertEqual(_ex(raw, "TAGS"), "python|flask|unittest")


class TestGradeCalculation(unittest.TestCase):

    def test_90_is_A(self):
        self.assertEqual(calc_grade(90), "A")

    def test_100_is_A(self):
        self.assertEqual(calc_grade(100), "A")

    def test_75_is_B(self):
        self.assertEqual(calc_grade(75), "B")

    def test_89_is_B(self):
        self.assertEqual(calc_grade(89), "B")

    def test_60_is_C(self):
        self.assertEqual(calc_grade(60), "C")

    def test_74_is_C(self):
        self.assertEqual(calc_grade(74), "C")

    def test_40_is_D(self):
        self.assertEqual(calc_grade(40), "D")

    def test_59_is_D(self):
        self.assertEqual(calc_grade(59), "D")

    def test_39_is_F(self):
        self.assertEqual(calc_grade(39), "F")

    def test_0_is_F(self):
        self.assertEqual(calc_grade(0), "F")


class TestVerdictRules(unittest.TestCase):

    def test_pass_when_all_above_threshold(self):
        self.assertEqual(apply_verdict_rules(70, 50, 50, 50, "PASS"), "PASS")

    def test_fail_when_overall_below_65(self):
        self.assertEqual(apply_verdict_rules(64, 50, 50, 50, "PASS"), "FAIL")

    def test_fail_when_intro_below_45(self):
        self.assertEqual(apply_verdict_rules(70, 44, 50, 50, "PASS"), "FAIL")

    def test_fail_when_behaviour_below_45(self):
        self.assertEqual(apply_verdict_rules(70, 50, 44, 50, "PASS"), "FAIL")

    def test_fail_when_technical_below_45(self):
        self.assertEqual(apply_verdict_rules(70, 50, 50, 44, "PASS"), "FAIL")

    def test_model_fail_overridden_to_pass_at_75_plus(self):
        self.assertEqual(apply_verdict_rules(75, 50, 50, 50, "FAIL"), "PASS")

    def test_model_fail_not_overridden_below_75(self):
        self.assertEqual(apply_verdict_rules(70, 50, 50, 50, "FAIL"), "FAIL")

    def test_exact_boundary_65(self):
        self.assertEqual(apply_verdict_rules(65, 50, 50, 50, "PASS"), "PASS")

    def test_exact_boundary_45(self):
        self.assertEqual(apply_verdict_rules(70, 45, 45, 45, "PASS"), "PASS")


class TestRecalcOverall(unittest.TestCase):

    def test_equal_scores(self):
        self.assertEqual(recalc_overall(80, 80, 80), 80)

    def test_only_intro_100_gives_20(self):
        self.assertEqual(recalc_overall(100, 0, 0), 20)

    def test_full_score(self):
        self.assertEqual(recalc_overall(100, 100, 100), 100)

    def test_zero_score(self):
        self.assertEqual(recalc_overall(0, 0, 0), 0)

    def test_known_calculation(self):
        # 80*0.20 + 70*0.40 + 60*0.40 = 16 + 28 + 24 = 68
        self.assertEqual(recalc_overall(80, 70, 60), 68)


if __name__ == "__main__":
    unittest.main()
