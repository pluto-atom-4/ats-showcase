"""Tests for heading_text helpers (Issue #268, #724, #731).

Coverage:
- normalize_heading_text strips **, _, #, trailing colon, mixed whitespace
- is_heading_only: None/empty heading handling
- All 6 KNOWN_HEADING_PHRASES in bold/colon/plain/uppercase variants -> True
- Boilerplate notice matched by _BOILERPLATE_PATTERN via is_heading_only, kept out of KNOWN_HEADING_PHRASES
- Trailing-period handling consistent across heading-equality and known-phrase paths
- Generic-title trade-off (candidate == section title is dropped) pinned
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

BOILERPLATE_SENTENCE = "applicants who do not meet these qualifications will not be forwarded to the hiring department"


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

    def test_interior_period_kept_trailing_period_stripped(self) -> None:
        assert normalize_heading_text("Node.js and e.g. Python.") == "node.js and e.g. python"

    def test_attached_trailing_hash_kept(self) -> None:
        assert normalize_heading_text("C#") == "c#"
        assert normalize_heading_text("**C#**") == "c#"

    def test_closing_atx_hashes_stripped(self) -> None:
        assert normalize_heading_text("## Minimum Qualifications ##") == "minimum qualifications"

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("**Minimum Qualifications** ##", "minimum qualifications"),
            ("## **Minimum Qualifications** ##", "minimum qualifications"),
            ("**Minimum Qualifications ##**", "minimum qualifications"),
            ("## Minimum Qualifications ##", "minimum qualifications"),
            ("**Required Qualifications**.", "required qualifications"),
            ("C#", "c#"),
            ("**C#**", "c#"),
            ("C++", "c++"),
        ],
    )
    def test_marker_orders_and_attached_symbols(self, raw: str, expected: str) -> None:
        assert normalize_heading_text(raw) == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("**Python**.", "python"),
            ("**Python.**", "python"),
            ("**Python**..", "python"),
            ("_Python_.", "python"),
        ],
    )
    def test_period_after_closing_marker_stripped(self, raw: str, expected: str) -> None:
        assert normalize_heading_text(raw) == expected


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
        assert len(KNOWN_HEADING_PHRASES) == 6

    def test_boilerplate_not_in_known_heading_phrases(self) -> None:
        assert BOILERPLATE_SENTENCE not in KNOWN_HEADING_PHRASES
        # Matched by the boilerplate regex path, not by set membership.
        assert is_heading_only(BOILERPLATE_SENTENCE) is True

    @pytest.mark.parametrize(
        "candidate",
        [
            "Applicants who do not meet the minimum qualifications will not be forwarded to the hiring department",
            "Applicants who do not meet the qualifications will not be forwarded to the hiring department",
            "**Applicants who do not meet these qualifications will not be forwarded to the hiring department.**",
        ],
    )
    def test_boilerplate_regex_variants_true(self, candidate: str) -> None:
        assert is_heading_only(candidate) is True

    @pytest.mark.parametrize(
        "candidate",
        [
            "Applicants who do not meet these qualifications will not be forwarded to the hiring department of Acme",
            "Applicants who meet these qualifications will be forwarded.",
            "Applicants must meet these qualifications.",
        ],
    )
    def test_boilerplate_regex_near_misses_false(self, candidate: str) -> None:
        assert is_heading_only(candidate) is False

    def test_bold_bullet_value_under_required_qualifications_is_false(self) -> None:
        assert is_heading_only("**5+ years of experience**", "Required Qualifications") is False

    def test_trailing_period_on_known_phrase_true(self) -> None:
        assert is_heading_only("Required Qualifications.") is True
        assert is_heading_only("**Required Qualifications.**") is True

    def test_heading_equality_ignores_trailing_period_on_candidate(self) -> None:
        assert is_heading_only("Python.", "Python") is True

    def test_heading_equality_ignores_trailing_period_on_heading(self) -> None:
        assert is_heading_only("Python", "Python.") is True

    def test_heading_equality_ignores_period_on_both(self) -> None:
        assert is_heading_only("**Team Overview.**", "Team Overview.") is True

    def test_period_only_candidate_is_false(self) -> None:
        assert is_heading_only(".", "Python") is False
        assert is_heading_only(".", ".") is False

    def test_generic_title_equal_to_heading_is_dropped(self) -> None:
        # Accepted trade-off: a real one-word requirement equal to its section
        # title is dropped. Pinned so any change to this behavior is deliberate.
        assert is_heading_only("Python", "Python") is True

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

    @pytest.mark.parametrize(
        "variant",
        [
            "{s}",
            "{s}.",
            "**{s}**",
            "**{s}.**",
            "**{s}**.",
            "{title}",
            "{title}.",
        ],
    )
    def test_boilerplate_sentence_variants_true(self, variant: str) -> None:
        text = variant.format(s=BOILERPLATE_SENTENCE, title=BOILERPLATE_SENTENCE.capitalize())
        assert is_heading_only(text) is True

    @pytest.mark.parametrize("phrase", sorted(KNOWN_HEADING_PHRASES))
    @pytest.mark.parametrize("variant", ["**{p}**.", "**{p}.**", "**{p}:**.", "_{p}_."])
    def test_known_phrase_closing_marker_period_true(self, phrase: str, variant: str) -> None:
        assert is_heading_only(variant.format(p=phrase)) is True

    @pytest.mark.parametrize(
        "candidate, heading",
        [
            ("**Python**.", "Python"),
            ("**Python.**", "Python"),
            ("Python", "**Python**."),
            ("**Team Overview**.", "Team Overview"),
            ("**Team Overview.**", "**Team Overview**."),
        ],
    )
    def test_heading_equality_with_closing_marker_period_true(self, candidate: str, heading: str) -> None:
        assert is_heading_only(candidate, heading) is True

    def test_closing_marker_period_on_requirement_is_false(self) -> None:
        assert is_heading_only("**Python experience**.", "Team Overview") is False

    def test_bare_csharp_not_dropped_as_heading(self) -> None:
        # Trailing '#' attached to a word is content, not an ATX closer.
        assert is_heading_only("C#", "C") is False
        assert is_heading_only("C#") is False

    def test_cplusplus_not_dropped_as_heading(self) -> None:
        assert is_heading_only("C++", "C") is False

    def test_bold_csharp_equals_heading(self) -> None:
        assert is_heading_only("**C#**", "C#") is True

    def test_closing_atx_heading_still_heading_only(self) -> None:
        assert is_heading_only("## Minimum Qualifications ##") is True

    def test_experience_with_csharp_is_false(self) -> None:
        assert is_heading_only("Experience with C#") is False

    @pytest.mark.parametrize(
        "candidate",
        [
            "**Minimum Qualifications** ##",
            "## **Minimum Qualifications** ##",
            "## Minimum Qualifications ##",
            "**Required Qualifications**.",
        ],
    )
    def test_marker_order_variants_heading_only_true(self, candidate: str) -> None:
        assert is_heading_only(candidate) is True

    @pytest.mark.parametrize("candidate", ["Experience with C#", "Python experience"])
    def test_non_heading_with_hash_or_text_is_false(self, candidate: str) -> None:
        assert is_heading_only(candidate) is False
