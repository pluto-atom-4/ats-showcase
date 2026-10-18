"""Tests for heading_text helpers (Issue #268, #724).

Coverage:
- normalize_heading_text strips **, _, #, trailing colon, mixed whitespace
- is_heading_only: None/empty heading handling
- All 7 KNOWN_HEADING_PHRASES in bold/colon/plain/uppercase variants -> True
- Heading equality -> True
- Requirement sentences containing colons or periods -> False

Run with:
    uv run pytest tests/poc/tweak/spacy_pipeline/test_heading_text.py -v
"""

import pytest

from src.poc.tweak.spacy_pipeline.heading_text import (
    KNOWN_HEADING_PHRASES,
    is_heading_only,
    normalize_heading_text,
)


class TestNormalizeHeadingText:
    """Marker stripping and normalization."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("**Required Qualifications**", "required qualifications"),
            ("__Preferred Qualifications__", "preferred qualifications"),
            ("## Working Conditions", "working conditions"),
            ("**Required Qualifications:**", "required qualifications"),
            ("Key Responsibilities:", "key responsibilities"),
            ("  \t**  Minimum   Qualifications \t:**  ", "minimum qualifications"),
            ("Python", "python"),
        ],
    )
    def test_strips_markers_and_normalizes(self, raw: str, expected: str) -> None:
        assert normalize_heading_text(raw) == expected

    def test_empty_returns_empty(self) -> None:
        assert normalize_heading_text("") == ""

    def test_markers_only_returns_empty(self) -> None:
        assert normalize_heading_text("**__##  ::") == ""

    def test_interior_markers_preserved(self) -> None:
        assert normalize_heading_text("C++ and snake_case") == "c++ and snake_case"


class TestIsHeadingOnly:
    """is_heading_only behavior."""

    @pytest.mark.parametrize("heading", [None, ""])
    def test_none_or_empty_heading_uses_known_phrases(self, heading: str | None) -> None:
        assert is_heading_only("**Required Qualifications**", heading) is True
        assert is_heading_only("Python experience", heading) is False

    def test_empty_candidate_is_false(self) -> None:
        assert is_heading_only("") is False
        assert is_heading_only("   ") is False
        assert is_heading_only("**::**") is False

    def test_empty_candidate_with_heading_is_false(self) -> None:
        assert is_heading_only("", "Required Qualifications") is False

    def test_heading_equality_true(self) -> None:
        assert is_heading_only("**Team Overview:**", "Team Overview") is True
        assert is_heading_only("team   overview", "**Team Overview**") is True

    def test_heading_not_equal_is_false(self) -> None:
        assert is_heading_only("Python experience", "Team Overview") is False

    def test_blank_heading_does_not_match_everything(self) -> None:
        assert is_heading_only("Python experience", "**::**") is False

    def test_requirement_with_colon_is_false(self) -> None:
        assert is_heading_only("Required: Python") is False

    def test_long_requirement_sentence_is_false(self) -> None:
        assert is_heading_only("5+ years of software engineering experience.") is False

    def test_known_phrases_count(self) -> None:
        assert len(KNOWN_HEADING_PHRASES) == 7

    @pytest.mark.parametrize("phrase", sorted(KNOWN_HEADING_PHRASES))
    @pytest.mark.parametrize(
        "variant",
        [
            "{p}",
            "**{p}**",
            "{p}:",
            "**{p}:**",
            "**{upper}**",
            "{title}",
        ],
    )
    def test_known_phrase_variants_true(self, phrase: str, variant: str) -> None:
        text = variant.format(p=phrase, upper=phrase.upper(), title=phrase.title())
        assert is_heading_only(text) is True

    def test_applicants_sentence_with_trailing_period_true(self) -> None:
        sentence = "Applicants who do not meet these qualifications will not be forwarded to the hiring department."
        assert is_heading_only(sentence) is True
