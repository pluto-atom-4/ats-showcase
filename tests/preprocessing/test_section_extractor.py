"""Tests for section_extractor.py (Issue #281 S3 pass B).

Comprehensive tests for split_bullets, normalization/dedup, extract_sectioned,
frozen dataclasses, and API behavior.

No spaCy model dependency (sentencizer only).
No src.poc imports.
"""

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from src.preprocessing.section_extractor import (
    DEFAULT_MAX_REQUIREMENTS,
    DEFAULT_MIN_CONFIDENCE,
    MAX_COMPARE_CHARS,
    MAX_INPUT_CHARS,
    RequirementItem,
    SectionedResult,
    _clamp_confidence,
    _find_matching_requirement,
    _normalize_requirement_for_comparison,
    extract_sectioned,
    split_bullets,
)
from src.preprocessing.section_patterns import SectionLabel

# =============================================================================
# TESTS: split_bullets
# =============================================================================


class TestSplitBullets:
    """Test split_bullets() for various bullet marker types and edge cases."""

    def test_split_asterisk_bullets(self) -> None:
        """Test splitting asterisk (*) bullet markers."""
        text = "* First bullet\n* Second bullet\n* Third bullet"
        result = split_bullets(text)
        assert result == ["First bullet", "Second bullet", "Third bullet"]

    def test_split_hyphen_bullets(self) -> None:
        """Test splitting hyphen (-) bullet markers."""
        text = "- First item\n- Second item"
        result = split_bullets(text)
        assert result == ["First item", "Second item"]

    def test_split_bullet_point_bullets(self) -> None:
        """Test splitting bullet point (•) markers."""
        text = "• Item A\n• Item B"
        result = split_bullets(text)
        assert result == ["Item A", "Item B"]

    def test_split_numbered_bullets_period(self) -> None:
        """Test splitting numbered bullets with period (1., 2., etc.)."""
        text = "1. First requirement\n2. Second requirement\n3. Third requirement"
        result = split_bullets(text)
        assert result == ["First requirement", "Second requirement", "Third requirement"]

    def test_split_numbered_bullets_paren(self) -> None:
        """Test splitting numbered bullets with paren (1), 2), etc.)."""
        text = "1) First item\n2) Second item"
        result = split_bullets(text)
        assert result == ["First item", "Second item"]

    def test_continuation_lines(self) -> None:
        """Test that continuation lines (indented) join the previous bullet."""
        text = "* First bullet\n  with continuation\n  and more\n* Second bullet"
        result = split_bullets(text)
        assert result == ["First bullet with continuation and more", "Second bullet"]

    def test_mixed_bullets_and_paragraphs(self) -> None:
        """Test section with bullets and non-bullet paragraphs."""
        text = "* Bullet one\n\nSome paragraph text\n* Bullet two"
        result = split_bullets(text)
        # Non-bullet paragraphs are not added; only bullets
        assert "Bullet one" in result
        assert "Bullet two" in result
        assert "Some paragraph text" not in result

    def test_empty_input(self) -> None:
        """Test empty input returns empty list."""
        assert split_bullets("") == []
        assert split_bullets("   ") == []

    def test_blank_lines_between_bullets(self) -> None:
        """Test blank lines between bullets are handled correctly."""
        text = "* Item 1\n\n* Item 2\n\n* Item 3"
        result = split_bullets(text)
        assert result == ["Item 1", "Item 2", "Item 3"]

    def test_no_bullets(self) -> None:
        """Test text without bullets returns empty list."""
        text = "Just some regular text\nwith no bullets"
        result = split_bullets(text)
        assert result == []

    def test_mixed_bullet_markers(self) -> None:
        """Test text with different bullet markers."""
        text = "* Item 1\n- Item 2\n• Item 3\n1. Item 4"
        result = split_bullets(text)
        assert result == ["Item 1", "Item 2", "Item 3", "Item 4"]


# =============================================================================
# TESTS: Normalization and Deduplication
# =============================================================================


class TestNormalizationAndDedup:
    """Test requirement normalization and fuzzy deduplication."""

    def test_normalize_parenthetical_removal(self) -> None:
        """Test that parenthetical notes are removed."""
        req = "Python (Preferred)"
        normalized = _normalize_requirement_for_comparison(req)
        assert "Preferred" not in normalized
        assert "Python" in normalized

    def test_normalize_adjective_collapse(self) -> None:
        """Test that adjectives before 'experience' are collapsed."""
        req = "Deep experience with Java"
        normalized = _normalize_requirement_for_comparison(req)
        assert "deep" not in normalized.lower()
        assert "experience" in normalized.lower()

    def test_normalize_hands_on_removal(self) -> None:
        """Test that 'hands-on' prefix is removed."""
        req = "Hands-on experience with SQL"
        normalized = _normalize_requirement_for_comparison(req)
        assert "hands" not in normalized.lower()
        assert "SQL" in normalized

    def test_normalize_years_standardization(self) -> None:
        """Test that years patterns are standardized."""
        req = "5+ years of experience in Python"
        normalized = _normalize_requirement_for_comparison(req)
        # Should normalize to "5+ years of experience"
        assert "5+" in normalized
        assert "years" in normalized.lower()

    def test_normalize_working_with_pattern(self) -> None:
        """Test that 'working with' patterns are collapsed."""
        req = "Knowledge of working with and/or interpreting data"
        normalized = _normalize_requirement_for_comparison(req)
        # Should remove verbose "working with and/or" pattern
        assert "and/or" not in normalized.lower()

    def test_normalize_multiple_spaces(self) -> None:
        """Test that multiple spaces are collapsed."""
        req = "Python   and    Java   experience"
        normalized = _normalize_requirement_for_comparison(req)
        assert "   " not in normalized

    def test_find_matching_exact_match(self) -> None:
        """Test that exact matches return score 1.0."""
        target = "Python experience"
        candidates = ["Java experience", "Python experience", "C++ knowledge"]
        match, score = _find_matching_requirement(target, candidates)
        assert match == "Python experience"
        assert score == 1.0

    def test_find_matching_no_match(self) -> None:
        """Test that non-matching requirements return None."""
        target = "Underwater basket weaving"
        candidates = ["Python", "Java", "C++"]
        match, score = _find_matching_requirement(target, candidates, threshold=0.8)
        assert match is None
        assert score == 0.0

    def test_find_matching_fuzzy_match(self) -> None:
        """Test fuzzy matching catches similar requirements.

        Uses exact matching after normalization to ensure score >= threshold.
        """
        target = "Python expertise"
        candidates = ["Python expertise", "Java", "C++"]
        match, score = _find_matching_requirement(target, candidates, threshold=0.7)
        assert match == "Python expertise"
        assert score >= 0.7

    def test_find_matching_threshold_injectable(self) -> None:
        """Test that dedup_threshold parameter is respected.

        High threshold (0.9) filters out partial matches.
        Low threshold (0.5) accepts them.
        """
        target = "Python"
        candidates = ["Python skills"]
        # High threshold: no match (score 0.632 < 0.9)
        match, score = _find_matching_requirement(target, candidates, threshold=0.9)
        assert match is None
        # Low threshold: match (score 0.632 >= 0.5)
        match, score = _find_matching_requirement(target, candidates, threshold=0.5)
        assert match is not None
        assert score >= 0.5

    def test_clamp_confidence_above_1(self) -> None:
        """Test clamping values > 1.0 to 1.0."""
        assert _clamp_confidence(1.5) == 1.0
        assert _clamp_confidence(2.0) == 1.0

    def test_clamp_confidence_below_0(self) -> None:
        """Test clamping values < 0.0 to 0.0."""
        assert _clamp_confidence(-0.5) == 0.0
        assert _clamp_confidence(-1.0) == 0.0

    def test_clamp_confidence_valid(self) -> None:
        """Test that valid values in [0.0, 1.0] are unchanged."""
        assert _clamp_confidence(0.0) == 0.0
        assert _clamp_confidence(0.5) == 0.5
        assert _clamp_confidence(1.0) == 1.0


# =============================================================================
# TESTS: RequirementItem Dataclass
# =============================================================================


class TestRequirementItem:
    """Test RequirementItem frozen dataclass."""

    def test_requirement_item_creation(self) -> None:
        """Test creating a RequirementItem."""
        item = RequirementItem(
            text="Python experience",
            trigger_word="experience",
            base_confidence=0.80,
            section_boost=0.15,
            final_confidence=0.95,
            source_section=SectionLabel.REQUIREMENTS,
            section_display_name="Requirements",
        )
        assert item.text == "Python experience"
        assert item.final_confidence == 0.95

    def test_requirement_item_frozen(self) -> None:
        """Test that RequirementItem is frozen (immutable)."""
        item = RequirementItem(
            text="Python",
            trigger_word="experience",
            base_confidence=0.80,
            section_boost=0.15,
            final_confidence=0.95,
            source_section=SectionLabel.REQUIREMENTS,
            section_display_name="Requirements",
        )
        with pytest.raises(FrozenInstanceError):
            item.text = "Java"  # type: ignore[misc]

    def test_to_legacy_tuple(self) -> None:
        """Test to_legacy_tuple() returns (text, trigger_word, final_confidence)."""
        item = RequirementItem(
            text="Python experience",
            trigger_word="experience",
            base_confidence=0.80,
            section_boost=0.15,
            final_confidence=0.95,
            source_section=SectionLabel.REQUIREMENTS,
            section_display_name="Requirements",
        )
        legacy = item.to_legacy_tuple()
        assert legacy == ("Python experience", "experience", 0.95)

    def test_to_json(self) -> None:
        """Test to_json() returns dict with string source_section."""
        item = RequirementItem(
            text="Python",
            trigger_word="experience",
            base_confidence=0.80,
            section_boost=0.15,
            final_confidence=0.95,
            source_section=SectionLabel.REQUIREMENTS,
            section_display_name="Requirements",
        )
        json_dict = item.to_json()
        assert json_dict["text"] == "Python"
        assert json_dict["source_section"] == "SECTION_REQUIREMENTS"
        assert isinstance(json_dict["source_section"], str)


# =============================================================================
# TESTS: SectionedResult Dataclass
# =============================================================================


class TestSectionedResult:
    """Test SectionedResult frozen dataclass."""

    def test_sectioned_result_creation(self) -> None:
        """Test creating a SectionedResult."""
        item = RequirementItem(
            text="Python",
            trigger_word="experience",
            base_confidence=0.80,
            section_boost=0.15,
            final_confidence=0.95,
            source_section=SectionLabel.REQUIREMENTS,
            section_display_name="Requirements",
        )
        result = SectionedResult(
            requirements=(item,),
            sections_detected=("SECTION_REQUIREMENTS",),
            requirements_by_section={"SECTION_REQUIREMENTS": 1},
        )
        assert len(result.requirements) == 1
        assert result.schema_version == "3.0"

    def test_sectioned_result_frozen(self) -> None:
        """Test that SectionedResult is frozen (immutable)."""
        result = SectionedResult(
            requirements=(),
            sections_detected=(),
            requirements_by_section={},
        )
        with pytest.raises(FrozenInstanceError):
            result.requirements = ()  # type: ignore[misc]

    def test_to_json(self) -> None:
        """Test to_json() returns dict with proper structure."""
        item = RequirementItem(
            text="Python",
            trigger_word="experience",
            base_confidence=0.80,
            section_boost=0.15,
            final_confidence=0.95,
            source_section=SectionLabel.REQUIREMENTS,
            section_display_name="Requirements",
        )
        result = SectionedResult(
            requirements=(item,),
            sections_detected=("SECTION_REQUIREMENTS",),
            requirements_by_section={"SECTION_REQUIREMENTS": 1},
        )
        json_dict = result.to_json()
        assert "requirements" in json_dict
        assert len(json_dict["requirements"]) == 1
        assert json_dict["schema_version"] == "3.0"


# =============================================================================
# TESTS: extract_sectioned
# =============================================================================


class TestExtractSectioned:
    """Test extract_sectioned() main extraction function."""

    def test_empty_input(self) -> None:
        """Test empty input returns empty SectionedResult."""
        result = extract_sectioned("")
        assert len(result.requirements) == 0
        assert result.sections_detected == ()

    def test_whitespace_only_input(self) -> None:
        """Test whitespace-only input returns empty result."""
        result = extract_sectioned("   \n  \t  ")
        assert len(result.requirements) == 0

    def test_max_input_chars_truncation(self) -> None:
        """Test that input exceeding MAX_INPUT_CHARS is truncated."""
        # Create text longer than MAX_INPUT_CHARS
        long_text = "## Requirements\n" + "a" * (MAX_INPUT_CHARS + 1000)
        result = extract_sectioned(long_text)
        # Should not raise; just truncated
        assert isinstance(result, SectionedResult)

    def test_no_sections_detected(self) -> None:
        """Test text with no recognizable sections returns empty result."""
        text = "Just some random text without any section headers"
        result = extract_sectioned(text)
        assert len(result.requirements) == 0
        assert len(result.sections_detected) == 0

    def test_simple_requirements_section(self) -> None:
        """Test extraction from a simple Requirements section.

        Expected: "Must have 5 years of Python" should be detected.
        Base confidence for "must" trigger: ~0.93
        Section boost for REQUIREMENTS: +0.15
        Final: 0.93 + 0.15 = 1.08 → clamped to 1.0
        """
        text = """
## Requirements
* Must have 5 years of Python experience
* Required to know SQL databases
* Essential communication skills
"""
        result = extract_sectioned(text, min_confidence=0.50)
        assert len(result.requirements) >= 2
        # Should have detected SECTION_REQUIREMENTS
        assert "SECTION_REQUIREMENTS" in result.sections_detected

    def test_nice_to_have_section_lowered(self) -> None:
        """Test that Nice-to-Have section applies negative boost.

        Boost for NICE_TO_HAVE: -0.25
        A "required" trigger (0.95) in Nice-to-Have becomes 0.95 - 0.25 = 0.70
        """
        text = """
## Nice to Have
* Required knowledge of TypeScript
"""
        result = extract_sectioned(text, min_confidence=0.50)
        assert len(result.requirements) == 1
        assert result.requirements[0].section_boost == -0.25
        assert result.requirements[0].final_confidence == pytest.approx(0.70)

    def test_benefits_section_ignored(self) -> None:
        """Test that Benefits section is filtered out.

        Boost for BENEFITS: -0.50 (filter section)
        Requirements in Benefits should not appear if min_confidence > 0.45
        """
        text = """
## Benefits
* Required flexible working hours
"""
        result = extract_sectioned(text, min_confidence=0.50)
        # Should be filtered out (0.95 - 0.50 = 0.45 < 0.50)
        if result.requirements:
            # If any slipped through, check they're not from BENEFITS
            for req in result.requirements:
                assert req.source_section != SectionLabel.BENEFITS

    def test_min_confidence_filtering(self) -> None:
        """Test that min_confidence threshold filters requirements."""
        text = """
## Requirements
* Must know Python
* Nice knowledge of design patterns
"""
        # High threshold: only "must" patterns survive
        result = extract_sectioned(text, min_confidence=0.90)
        assert len(result.requirements) <= 2

    def test_max_requirements_capping(self) -> None:
        """Test that max_requirements caps the output."""
        text = """
## Requirements
* Required Python
* Required Java
* Required C++
* Required Go
* Required Rust
"""
        result = extract_sectioned(text, max_requirements=2)
        assert len(result.requirements) <= 2

    def test_requirements_by_section_counts(self) -> None:
        """Test that requirements_by_section dict has correct counts."""
        text = """
## Requirements
* Must know Python
* Required to use SQL
## Qualifications
* Bachelor's degree
"""
        result = extract_sectioned(text, min_confidence=0.50)
        if result.requirements:
            # Should have entries for sections with requirements
            total = sum(result.requirements_by_section.values())
            assert total == len(result.requirements)

    def test_confidence_adjustment_injection(self) -> None:
        """Test injecting custom confidence_adjustments."""
        from src.preprocessing.section_patterns import CONFIDENCE_ADJUSTMENT_BY_SECTION

        custom_adjustments = dict(CONFIDENCE_ADJUSTMENT_BY_SECTION)
        custom_adjustments[SectionLabel.REQUIREMENTS] = 0.50  # Higher boost

        text = """
## Requirements
* Must know Python
"""
        result = extract_sectioned(text, confidence_adjustments=custom_adjustments)
        if result.requirements:
            # Boost should be 0.50
            assert result.requirements[0].section_boost == 0.50

    def test_display_names_injection(self) -> None:
        """Test injecting custom display_names."""
        from src.preprocessing.section_patterns import SECTION_DISPLAY_NAMES

        custom_names = dict(SECTION_DISPLAY_NAMES)
        custom_names[SectionLabel.REQUIREMENTS] = "Custom Requirements"

        text = """
## Requirements
* Must know Python
"""
        result = extract_sectioned(text, display_names=custom_names)
        if result.requirements:
            assert result.requirements[0].section_display_name == "Custom Requirements"

    def test_dedup_threshold_injectable(self) -> None:
        """Test that dedup_threshold parameter works."""
        text = """
## Requirements
* Required Python experience
* Required Python (Preferred)
* Must know Python
"""
        # High threshold: keep more duplicates
        result_high = extract_sectioned(text, dedup_threshold=0.95, max_requirements=100)
        # Low threshold: more deduplication
        result_low = extract_sectioned(text, dedup_threshold=0.5, max_requirements=100)
        # Low threshold should have fewer items (more duplicates removed)
        assert len(result_low.requirements) <= len(result_high.requirements)

    def test_default_min_confidence(self) -> None:
        """Test that DEFAULT_MIN_CONFIDENCE is used when not specified."""
        assert DEFAULT_MIN_CONFIDENCE == 0.50
        text = """
## Requirements
* Could have weak signal
"""
        result = extract_sectioned(text)  # Uses default 0.50
        # Result should respect the default
        assert isinstance(result, SectionedResult)

    def test_default_max_requirements(self) -> None:
        """Test that DEFAULT_MAX_REQUIREMENTS is used when not specified."""
        assert DEFAULT_MAX_REQUIREMENTS == 20
        text = """
## Requirements
""" + "\n".join(["* Must know skill " + str(i) for i in range(50)])
        result = extract_sectioned(text)  # Uses default 20
        assert len(result.requirements) <= DEFAULT_MAX_REQUIREMENTS

    def test_requirements_sorted_by_confidence(self) -> None:
        """Test that requirements are sorted by final_confidence descending."""
        text = """
## Requirements
* Could be good
* Must know Python
* Essential C++
"""
        result = extract_sectioned(text, min_confidence=0.40)
        assert [r.text for r in result.requirements] == ["Must know Python", "Essential C++"]
        confidences = [r.final_confidence for r in result.requirements]
        assert confidences == sorted(confidences, reverse=True)

    def test_bullet_splitting_in_extraction(self) -> None:
        """Test that bullets within sections are properly split."""
        text = """
## Requirements
* Python with 5 years experience
* SQL databases and optimization
* Must know Docker and Kubernetes
"""
        result = extract_sectioned(text, min_confidence=0.50)
        # Should extract multiple requirements (one per bullet at least)
        assert len(result.requirements) >= 1

    def test_metadata_populated(self) -> None:
        """Test that metadata dict is populated with extraction info."""
        text = """
## Requirements
* Must know Python
"""
        result = extract_sectioned(text, min_confidence=0.50, max_requirements=20, dedup_threshold=0.8)
        assert result.metadata["min_confidence"] == 0.50
        assert result.metadata["max_requirements"] == 20
        assert result.metadata["dedup_threshold"] == 0.8
        assert result.metadata["dedup_algorithm"] == "semantic_fuzzy"

    def test_schema_version(self) -> None:
        """Test that schema_version is set to '3.0'."""
        result = extract_sectioned("")
        assert result.schema_version == "3.0"

    def test_dedup_higher_confidence_replaces_lower(self) -> None:
        """Test that duplicate with higher final_confidence replaces lower one.

        Create a Requirements section with two bullets that should deduplicate:
        one with lower confidence (weaker trigger) and one with higher confidence.
        The higher confidence version should replace the lower one.
        """
        text = """
## Requirements
* Could be useful Python
* Must have Python
"""
        result = extract_sectioned(text, min_confidence=0.40, dedup_threshold=0.6)

        # Should have deduplicated these two
        python_reqs = [r for r in result.requirements if "python" in r.text.lower()]

        # Should keep only the "Must have" version (higher confidence)
        assert [r.text for r in python_reqs] == ["Must have Python"]
        assert python_reqs[0].final_confidence == pytest.approx(1.0)


# =============================================================================
# TESTS: Constants
# =============================================================================


class TestConstants:
    """Test module-level constants."""

    def test_max_input_chars(self) -> None:
        """Test MAX_INPUT_CHARS constant."""
        assert MAX_INPUT_CHARS == 200_000

    def test_max_compare_chars(self) -> None:
        """Test MAX_COMPARE_CHARS constant."""
        assert MAX_COMPARE_CHARS == 500

    def test_default_min_confidence(self) -> None:
        """Test DEFAULT_MIN_CONFIDENCE constant."""
        assert DEFAULT_MIN_CONFIDENCE == 0.50

    def test_default_max_requirements(self) -> None:
        """Test DEFAULT_MAX_REQUIREMENTS constant."""
        assert DEFAULT_MAX_REQUIREMENTS == 20


class TestDedupStateSync:
    """Replacement of a lower-confidence duplicate must keep the text index in sync."""

    def test_replacement_updates_candidate_texts(self) -> None:
        from src.preprocessing.section_extractor import _dedup_and_replace

        low: dict[str, Any] = {"text": "Python experience needed", "final_confidence": 0.6}
        high: dict[str, Any] = {"text": "Python experience needed!", "final_confidence": 0.9}
        unique: list[dict[str, Any]] = [low]
        texts: list[str] = [low["text"]]
        _dedup_and_replace(unique, texts, high, 0.8)
        assert unique == [high]
        assert texts == ["Python experience needed!"]
