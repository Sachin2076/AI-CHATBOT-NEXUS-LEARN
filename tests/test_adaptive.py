"""
tests/test_adaptive.py — Adaptive learning loop tests (Gap 5)

Tests the new adaptive context system (Gap 1):
  • build_adaptive_context() — prompt context builder in llm.py
  • utils.extract_field()    — LLM output parser
  • get_performance_context  — via mocked quiz_results collection

Zero external dependencies.

Run with:
    pytest tests/test_adaptive.py -vs
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm   import build_adaptive_context
from utils import extract_field


# ═════════════════════════════════════════════════════════════
#  build_adaptive_context
# ═════════════════════════════════════════════════════════════

class TestBuildAdaptiveContext:

    def test_returns_empty_string_when_no_data(self):
        result = build_adaptive_context([], {})
        assert result == ""

    def test_returns_empty_when_both_args_empty(self):
        assert build_adaptive_context([], {}) == ""

    def test_includes_weak_topics_in_output(self):
        ctx = build_adaptive_context(["Python (55%)", "SQL (48%)"], {})
        assert "Python" in ctx
        assert "SQL" in ctx
        assert "70%" in ctx   # threshold mentioned

    def test_mentions_increase_depth_for_weak_topics(self):
        ctx = build_adaptive_context(["Python (55%)"], {})
        assert "depth" in ctx.lower() or "explanation" in ctx.lower()

    def test_includes_strong_topics_when_above_80(self):
        ctx = build_adaptive_context([], {"JavaScript": 85, "Python": 60})
        assert "JavaScript" in ctx
        # Python at 60 is not strong
        assert "Python" not in ctx or "strong" not in ctx

    def test_does_not_include_weak_in_strong_section(self):
        ctx = build_adaptive_context(["Python (55%)"], {"Python": 55, "JS": 90})
        assert "JS" in ctx
        # Python should be in weak section, not strong
        lines = ctx.split("\n")
        strong_lines = [l for l in lines if "strong" in l.lower() or "80%" in l]
        assert not any("Python" in l for l in strong_lines)

    def test_context_contains_performance_header(self):
        ctx = build_adaptive_context(["Topic (40%)"], {"Topic": 40})
        assert "PERFORMANCE CONTEXT" in ctx

    def test_context_has_closing_marker(self):
        ctx = build_adaptive_context(["Topic (40%)"], {})
        assert "END PERFORMANCE CONTEXT" in ctx

    def test_no_weak_topics_no_weak_section(self):
        ctx = build_adaptive_context([], {"Python": 90})
        assert "70%" not in ctx
        assert "attention" not in ctx.lower()

    def test_multiple_weak_topics_all_listed(self):
        weak = ["Python (55%)", "SQL (48%)", "Java (60%)"]
        ctx  = build_adaptive_context(weak, {})
        assert "Python" in ctx
        assert "SQL" in ctx
        assert "Java" in ctx


# ═════════════════════════════════════════════════════════════
#  extract_field (utils)
# ═════════════════════════════════════════════════════════════

class TestExtractField:

    def test_simple_field(self):
        raw = "NAME: Alice\nSCORE: 90"
        assert extract_field(raw, "NAME") == "Alice"

    def test_last_field_without_trailing_newline(self):
        raw = "NAME: Alice\nSCORE: 90"
        assert extract_field(raw, "SCORE") == "90"

    def test_multiline_value(self):
        raw = "COMMENT: line one\nline two\nNAME: Bob"
        assert extract_field(raw, "COMMENT") == "line one\nline two"

    def test_missing_key_returns_empty(self):
        raw = "NAME: Alice\nSCORE: 90"
        assert extract_field(raw, "MISSING") == ""

    def test_empty_raw_returns_empty(self):
        assert extract_field("", "NAME") == ""

    def test_strips_surrounding_whitespace(self):
        raw = "NAME:   Alice   \nSCORE: 90"
        assert extract_field(raw, "NAME") == "Alice"

    def test_does_not_bleed_into_next_field(self):
        raw = "INTRO: Hello world\nOUTRO: Goodbye"
        assert extract_field(raw, "INTRO") == "Hello world"

    def test_key_with_underscore(self):
        raw = "OVERALL_SCORE: 72\nVERDICT: PASS"
        assert extract_field(raw, "OVERALL_SCORE") == "72"

    def test_pipe_separated_values_preserved(self):
        raw = "TAGS: python|flask|unittest\nEND: done"
        assert extract_field(raw, "TAGS") == "python|flask|unittest"

    def test_numeric_value(self):
        raw = "SCORE: 87\nGRADE: B"
        assert extract_field(raw, "SCORE") == "87"


# ═════════════════════════════════════════════════════════════
#  get_performance_context (via mocked DB)
# ═════════════════════════════════════════════════════════════

class TestGetPerformanceContext:

    def _import_and_call(self, mock_results):
        """Helper: patch quiz_results and call get_performance_context."""
        with patch("app.quiz_results") as mock_qr:
            cursor = MagicMock()
            cursor.sort.return_value.limit.return_value = mock_results
            mock_qr.return_value.find.return_value = cursor
            # Import here to avoid circular imports at module level
            from app import get_performance_context
            return get_performance_context("fake_user_id")

    def test_empty_quiz_history_returns_empty_string(self):
        ctx = self._import_and_call([])
        assert ctx == ""

    def test_weak_topic_appears_in_context(self):
        results = [
            {"topic": "Python", "score": 45, "submitted_at": "2026-01-01"},
            {"topic": "Python", "score": 50, "submitted_at": "2026-01-02"},
        ]
        ctx = self._import_and_call(results)
        assert "Python" in ctx
        assert "47%" in ctx or "48%" in ctx or "47" in ctx or "48" in ctx

    def test_strong_topic_not_flagged_as_weak(self):
        results = [
            {"topic": "JavaScript", "score": 90, "submitted_at": "2026-01-01"},
            {"topic": "JavaScript", "score": 85, "submitted_at": "2026-01-02"},
        ]
        ctx = self._import_and_call(results)
        # Strong topic should appear, but not as a weak area
        if ctx:
            assert "attention" not in ctx.lower() or "JavaScript" not in ctx

    def test_mixed_results_identifies_weak_and_strong(self):
        results = [
            {"topic": "Python",     "score": 45, "submitted_at": "2026-01-01"},
            {"topic": "JavaScript", "score": 90, "submitted_at": "2026-01-02"},
        ]
        ctx = self._import_and_call(results)
        assert "Python" in ctx
        assert "JavaScript" in ctx

    def test_returns_string_type(self):
        results = [{"topic": "SQL", "score": 60, "submitted_at": "2026-01-01"}]
        ctx = self._import_and_call(results)
        assert isinstance(ctx, str)

    def test_context_is_empty_when_db_raises(self):
        with patch("app.quiz_results", side_effect=Exception("DB down")):
            from app import get_performance_context
            ctx = get_performance_context("fake_user_id")
        assert ctx == ""
