"""Tests for the POC-side copied section-header keyword vocabulary (Issue #733).

The 16 literals were snapshotted from production _SECTION_HEADER_KEYWORDS at Issue #733.
There is no live sync with production; drift is accepted by design.

Coverage:
- Exactly the literal expected set (16 entries)
- Entries are non-empty, lowercase, free of surrounding whitespace, colons and leading markers
- Disjoint from heading_text.KNOWN_HEADING_PHRASES and heading_promoter._PROMOTER_ONLY_HEADINGS

Run with:
    uv run pytest tests/poc/tweak/spacy_pipeline/test_section_header_keywords.py -v
"""

from src.poc.tweak.spacy_pipeline.heading_promoter import _PROMOTER_ONLY_HEADINGS
from src.poc.tweak.spacy_pipeline.heading_text import KNOWN_HEADING_PHRASES
from src.poc.tweak.spacy_pipeline.section_header_keywords import (
    COPIED_SECTION_HEADER_KEYWORDS_ONLY,
)

EXPECTED_ENTRIES = frozenset(
    {
        "accountabilities",
        "background",
        "competencies",
        "duties",
        "education",
        "must haves",
        "must-have",
        "must-haves",
        "needed",
        "nice to have",
        "nice to haves",
        "nice-to-have",
        "nice-to-haves",
        "understanding",
        "what we're looking for",
        "what you'll do",
    }
)


class TestCopiedSectionHeaderKeywords:
    """Shape and content of the copied vocabulary."""

    def test_matches_exact_literal_set(self) -> None:
        assert len(COPIED_SECTION_HEADER_KEYWORDS_ONLY) == 16
        assert COPIED_SECTION_HEADER_KEYWORDS_ONLY == EXPECTED_ENTRIES

    def test_no_entry_is_empty(self) -> None:
        assert all(entry for entry in COPIED_SECTION_HEADER_KEYWORDS_ONLY)

    def test_no_entry_has_surrounding_whitespace(self) -> None:
        assert all(entry == entry.strip() for entry in COPIED_SECTION_HEADER_KEYWORDS_ONLY)

    def test_no_entry_has_colon(self) -> None:
        assert all(":" not in entry for entry in COPIED_SECTION_HEADER_KEYWORDS_ONLY)

    def test_no_entry_has_leading_marker(self) -> None:
        assert all(not entry.startswith(("#", "*", "_")) for entry in COPIED_SECTION_HEADER_KEYWORDS_ONLY)

    def test_all_entries_lowercase(self) -> None:
        assert all(entry == entry.lower() for entry in COPIED_SECTION_HEADER_KEYWORDS_ONLY)


class TestDisjointness:
    """Copied entries must not overlap the existing POC vocabularies."""

    def test_disjoint_from_known_heading_phrases(self) -> None:
        assert COPIED_SECTION_HEADER_KEYWORDS_ONLY.isdisjoint(KNOWN_HEADING_PHRASES)

    def test_disjoint_from_promoter_only_headings(self) -> None:
        assert COPIED_SECTION_HEADER_KEYWORDS_ONLY.isdisjoint(_PROMOTER_ONLY_HEADINGS)
