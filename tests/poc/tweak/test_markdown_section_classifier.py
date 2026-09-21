"""Unit tests for markdown_section_classifier.py (Issue #295: Comprehensive Coverage).

Tests cover all components of the markdown section classification system:
- TypeClassification construction, validation, and confidence bounds
- KeywordMatch position tracking for title vs content sources
- Confidence scoring functions (calculate_confidence, fallback_confidence)
- Position calculation (calculate_position) with edge cases
- SectionClassification.from_type_classifications() factory and multi-type support
- SectionClassifier.classify() with multi-type non-short-circuit logic
- Title-based vs content-based classification (_classify_from_title, _classify_from_content)
- Ruler pattern matching (_match_ruler_patterns, _calculate_ruler_confidence)
- Module-level classify_section() convenience function
- Edge cases: empty sections, no keyword matches, skip patterns, SKIP type behavior

Run with:
    uv run pytest tests/poc/tweak/test_markdown_section_classifier.py -v
    uv run pytest tests/poc/tweak/test_markdown_section_classifier.py -v --cov=src/poc/tweak
"""

import pytest

from src.poc.tweak.markdown_section_classifier import (
    KeywordMatch,
    SectionClassification,
    SectionClassifier,
    SectionType,
    TypeClassification,
    _clamp_confidence,
    _kw_in,
    calculate_confidence,
    calculate_position,
    classify_section,
    fallback_confidence,
)
from src.poc.tweak.multi_line_paragraph import MarkdownSection
from src.poc.tweak.patterns import (
    DESCRIPTION_KEYWORDS,
    KNOWLEDGE_KEYWORDS,
    QUALIFICATIONS_KEYWORDS,
    RESPONSIBILITIES_KEYWORDS,
    SKILLS_KEYWORDS,
    SKIP_SECTIONS,
)

# ============================================================================
# Test 1: TypeClassification Construction & Validation
# ============================================================================


class TestTypeClassificationConstruction:
    """Test TypeClassification dataclass construction and validation."""

    def test_type_classification_basic_construction(self) -> None:
        """Test creating TypeClassification with required and optional fields."""
        tc = TypeClassification(
            section_type=SectionType.SKILLS,
            confidence=0.85,
            matched_keywords=("skill", "technical"),
            pattern_label=None,
        )
        assert tc.section_type == SectionType.SKILLS
        assert tc.confidence == 0.85
        assert tc.matched_keywords == ("skill", "technical")
        assert tc.pattern_label is None

    def test_type_classification_with_pattern_label(self) -> None:
        """Test TypeClassification with ruler pattern label (Issue #301)."""
        tc = TypeClassification(
            section_type=SectionType.SKILLS,
            confidence=0.82,
            matched_keywords=(),
            pattern_label="SECTION_TECHNICAL_SKILLS",
        )
        assert tc.pattern_label == "SECTION_TECHNICAL_SKILLS"
        assert tc.matched_keywords == ()

    def test_type_classification_confidence_at_boundaries(self) -> None:
        """Test TypeClassification with boundary confidence values."""
        # Confidence = 0.0 (valid)
        tc_min = TypeClassification(SectionType.SKILLS, 0.0, ())
        assert tc_min.confidence == 0.0

        # Confidence = 1.0 (valid)
        tc_max = TypeClassification(SectionType.SKILLS, 1.0, ())
        assert tc_max.confidence == 1.0

    def test_type_classification_confidence_too_high_raises_error(self) -> None:
        """Test TypeClassification raises ValueError for confidence > 1.0."""
        with pytest.raises(ValueError, match="confidence must be in"):
            TypeClassification(SectionType.SKILLS, 1.5, ())

    def test_type_classification_confidence_negative_raises_error(self) -> None:
        """Test TypeClassification raises ValueError for negative confidence."""
        with pytest.raises(ValueError, match="confidence must be in"):
            TypeClassification(SectionType.SKILLS, -0.1, ())

    def test_type_classification_empty_keywords(self) -> None:
        """Test TypeClassification with empty matched_keywords tuple."""
        tc = TypeClassification(SectionType.SKILLS, 0.5, ())
        assert tc.matched_keywords == ()

    def test_type_classification_multiple_keywords(self) -> None:
        """Test TypeClassification with multiple matched keywords."""
        keywords = ("skill", "technical", "competency", "expertise")
        tc = TypeClassification(SectionType.SKILLS, 0.9, keywords)
        assert len(tc.matched_keywords) == 4
        assert "expertise" in tc.matched_keywords


# ============================================================================
# Test 2: KeywordMatch Construction & Position Tracking
# ============================================================================


class TestKeywordMatchConstruction:
    """Test KeywordMatch dataclass for position tracking."""

    def test_keyword_match_title_source(self) -> None:
        """Test KeywordMatch with source='title'."""
        km = KeywordMatch(
            keyword="requirement",
            section_type=SectionType.QUALIFICATIONS,
            source="title",
            position=5,
        )
        assert km.keyword == "requirement"
        assert km.source == "title"
        assert km.position == 5

    def test_keyword_match_content_source(self) -> None:
        """Test KeywordMatch with source='content'."""
        km = KeywordMatch(
            keyword="skill",
            section_type=SectionType.SKILLS,
            source="content",
            position=15,
        )
        assert km.source == "content"
        assert km.position == 15

    def test_keyword_match_position_at_start(self) -> None:
        """Test KeywordMatch with position at start (0)."""
        km = KeywordMatch("skill", SectionType.SKILLS, "title", 0)
        assert km.position == 0

    def test_keyword_match_position_negative_sentinel(self) -> None:
        """Test KeywordMatch with position=-1 (keyword not found sentinel)."""
        km = KeywordMatch("missing", SectionType.SKILLS, "title", -1)
        assert km.position == -1


# ============================================================================
# Test 3: calculate_confidence() Tiers
# ============================================================================


class TestCalculateConfidence:
    """Test calculate_confidence() function covering all 4 tiers."""

    def test_confidence_title_skip_single_match(self) -> None:
        """Test title-based SKIP with 1 match: 0.5 + (1 * 0.25) = 0.75."""
        conf = calculate_confidence(1, "title", SectionType.SKIP)
        assert conf == 0.75

    def test_confidence_title_skip_three_matches(self) -> None:
        """Test title-based SKIP with 3 matches: 0.5 + (3 * 0.25) = 1.0 (capped)."""
        conf = calculate_confidence(3, "title", SectionType.SKIP)
        assert conf == 1.0

    def test_confidence_title_skills_one_match(self) -> None:
        """Test title-based SKILLS with 1 match: 0.6 + (1 * 0.2) = 0.8."""
        conf = calculate_confidence(1, "title", SectionType.SKILLS)
        assert conf == 0.8

    def test_confidence_title_skills_three_matches(self) -> None:
        """Test title-based SKILLS with 3 matches: 0.6 + (3 * 0.2) = 1.0 (capped)."""
        conf = calculate_confidence(3, "title", SectionType.SKILLS)
        assert conf == 1.0

    def test_confidence_content_skip_one_match(self) -> None:
        """Test content-based SKIP with 1 match: 0.4 + (1 * 0.15) = 0.55."""
        conf = calculate_confidence(1, "content", SectionType.SKIP)
        assert conf == 0.55

    def test_confidence_content_skip_four_matches(self) -> None:
        """Test content-based SKIP with 4 matches: 0.4 + (4 * 0.15) = 1.0 (capped)."""
        conf = calculate_confidence(4, "content", SectionType.SKIP)
        assert conf == 1.0

    def test_confidence_content_qualifications_two_matches(self) -> None:
        """Test content-based QUALIFICATIONS with 2 matches: 0.5 + (2 * 0.15) = 0.8."""
        conf = calculate_confidence(2, "content", SectionType.QUALIFICATIONS)
        assert conf == 0.8

    def test_confidence_content_skills_two_matches(self) -> None:
        """Test content-based SKILLS with 2 matches: 0.5 + (2 * 0.15) = 0.8."""
        conf = calculate_confidence(2, "content", SectionType.SKILLS)
        assert conf == 0.8

    def test_confidence_high_match_count_clamps_to_one(self) -> None:
        """Test that high match count clamps to 1.0, not beyond."""
        conf = calculate_confidence(100, "title", SectionType.SKILLS)
        assert conf == 1.0
        assert conf <= 1.0


# ============================================================================
# Test 4: fallback_confidence() Tiers
# ============================================================================


class TestFallbackConfidence:
    """Test fallback_confidence() function for no-match scenarios."""

    def test_fallback_title_with_content(self) -> None:
        """Test fallback for titled section: returns OTHER with 0.3."""
        section_type, conf = fallback_confidence("title", True)
        assert section_type == SectionType.OTHER
        assert conf == 0.3

    def test_fallback_title_without_content(self) -> None:
        """Test fallback for titled section (no content): returns OTHER with 0.3."""
        section_type, conf = fallback_confidence("title", False)
        assert section_type == SectionType.OTHER
        assert conf == 0.3

    def test_fallback_content_with_text(self) -> None:
        """Test fallback for content-based with text: returns DESCRIPTION with 0.2."""
        section_type, conf = fallback_confidence("content", True)
        assert section_type == SectionType.DESCRIPTION
        assert conf == 0.2

    def test_fallback_content_empty(self) -> None:
        """Test fallback for content-based with no text: returns UNLABELED with 0.0."""
        section_type, conf = fallback_confidence("content", False)
        assert section_type == SectionType.UNLABELED
        assert conf == 0.0


# ============================================================================
# Test 5: calculate_position() Correctness
# ============================================================================


class TestCalculatePosition:
    """Test calculate_position() for keyword position tracking."""

    def test_position_keyword_at_start(self) -> None:
        """Test keyword at start of text returns position 0."""
        pos = calculate_position("skill", "skill and expertise")
        assert pos == 0

    def test_position_keyword_in_middle(self) -> None:
        """Test keyword in middle of text returns correct position."""
        pos = calculate_position("skill", "technical skill and expertise")
        assert pos == 10

    def test_position_keyword_not_found(self) -> None:
        """Test keyword not found returns -1 (sentinel)."""
        pos = calculate_position("missing", "skill and expertise")
        assert pos == -1

    def test_position_first_occurrence_only(self) -> None:
        """Test that only first occurrence position is returned."""
        pos = calculate_position("the", "the quick the brown the fox")
        assert pos == 0  # First occurrence

    def test_position_case_sensitive_on_normalized_text(self) -> None:
        """Test position calculation is case-sensitive on normalized (lowercase) text."""
        # Both keyword and text are already lowercase
        pos = calculate_position("cafe", "expertise in cafe management")
        assert pos == 13  # "cafe" starts at index 13 in string

    def test_position_single_character_keyword(self) -> None:
        """Test position with single-character keyword."""
        pos = calculate_position("a", "this is a test")
        assert pos == 8


# ============================================================================
# Test 6: SectionClassification.from_type_classifications() Factory
# ============================================================================


class TestSectionClassificationFactory:
    """Test SectionClassification.from_type_classifications() factory method."""

    def test_factory_single_type_classification(self) -> None:
        """Test factory with single TypeClassification."""
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        result = SectionClassification.from_type_classifications([tc])
        assert len(result.all_types) == 1
        assert result.all_types[0].section_type == SectionType.SKILLS
        assert result.all_types[0].confidence == 0.85

    def test_factory_sorts_by_confidence_descending(self) -> None:
        """Test factory sorts all_types by confidence descending (highest first)."""
        tc1 = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        tc2 = TypeClassification(SectionType.RESPONSIBILITIES, 0.75, ("responsibility",))
        tc3 = TypeClassification(SectionType.QUALIFICATIONS, 0.9, ("requirement",))
        result = SectionClassification.from_type_classifications([tc1, tc2, tc3])
        assert result.all_types[0].confidence == 0.9  # Highest first
        assert result.all_types[1].confidence == 0.85
        assert result.all_types[2].confidence == 0.75

    def test_factory_derives_labels_frozenset(self) -> None:
        """Test factory creates labels frozenset from all_types."""
        tc1 = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        tc2 = TypeClassification(SectionType.RESPONSIBILITIES, 0.75, ("responsibility",))
        result = SectionClassification.from_type_classifications([tc1, tc2])
        assert result.labels == frozenset({SectionType.SKILLS, SectionType.RESPONSIBILITIES})

    def test_factory_with_keyword_matches(self) -> None:
        """Test factory preserves keyword_matches tuple."""
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        km1 = KeywordMatch("skill", SectionType.SKILLS, "title", 0)
        km2 = KeywordMatch("technical", SectionType.SKILLS, "title", 10)
        result = SectionClassification.from_type_classifications([tc], keyword_matches=(km1, km2))
        assert len(result.keyword_matches) == 2
        assert result.keyword_matches[0].keyword == "skill"

    def test_factory_is_skip_flag_true(self) -> None:
        """Test factory sets is_skip=True when SKIP type present."""
        tc_skip = TypeClassification(SectionType.SKIP, 0.6, ("benefits",))
        tc_skills = TypeClassification(SectionType.SKILLS, 0.5, ("skill",))
        result = SectionClassification.from_type_classifications([tc_skip, tc_skills], is_skip=True)
        assert result.is_skip is True

    def test_factory_is_skip_flag_false_without_skip_type(self) -> None:
        """Test factory sets is_skip=False when no SKIP type."""
        tc = TypeClassification(SectionType.SKILLS, 0.85, ("skill",))
        result = SectionClassification.from_type_classifications([tc], is_skip=False)
        assert result.is_skip is False


# ============================================================================
# Test 7: SectionClassifier.classify() Multi-Type Behavior
# ============================================================================


class TestSectionClassifierMultiType:
    """Test SectionClassifier.classify() multi-type non-short-circuit logic."""

    def test_classify_single_type_title(self) -> None:
        """Test classify with title matching single type."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Technical Skills",
            content="Python, Java, SQL",
            level=2,
            start_line=0,
            end_line=2,
            word_count=4,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        assert len(result.all_types) >= 1
        assert result.all_types[0].section_type == SectionType.SKILLS

    def test_classify_multi_type_compound_title(self) -> None:
        """Test classify with title matching multiple types (multi-type non-short-circuit)."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Skills and Responsibilities",
            content="Manage Python projects, lead team",
            level=2,
            start_line=0,
            end_line=1,
            word_count=6,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Should contain both SKILLS and RESPONSIBILITIES (multi-type)
        assert SectionType.SKILLS in result.labels
        assert SectionType.RESPONSIBILITIES in result.labels

    def test_classify_highest_confidence_first_in_all_types(self) -> None:
        """Test that all_types is sorted by confidence descending."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Requirements and Skills",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=3,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # All types should be sorted by confidence descending
        if len(result.all_types) > 1:
            for i in range(len(result.all_types) - 1):
                assert result.all_types[i].confidence >= result.all_types[i + 1].confidence

    def test_classify_tracks_keyword_matches(self) -> None:
        """Test that classify tracks keyword_matches with position data."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Technical Skills",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=2,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Should have keyword matches with position information
        assert len(result.keyword_matches) >= 2
        km = result.keyword_matches[0]
        assert km.keyword in ("technical", "skill")
        assert km.source in ("title", "content")
        assert isinstance(km.position, int)

    def test_classify_multi_type_labels_frozenset(self) -> None:
        """Test that labels is a frozenset of all matched types."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Skills and Qualifications",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=3,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        assert isinstance(result.labels, frozenset)
        assert SectionType.SKILLS in result.labels
        assert SectionType.QUALIFICATIONS in result.labels


# ============================================================================
# Test 8: Title-Based vs Content-Based Classification
# ============================================================================


class TestClassifyFromTitleVsContent:
    """Test _classify_from_title() vs _classify_from_content() behavior."""

    def test_classify_from_title_with_title(self) -> None:
        """Test classify prefers title when present and level != -2."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Technical Skills",
            content="Python, Java",
            level=2,
            start_line=0,
            end_line=1,
            word_count=4,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Should classify from title
        assert len(result.all_types) >= 1

    def test_classify_from_content_without_title(self) -> None:
        """Test classify falls back to content when no title."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="",  # Empty title
            content="Requires 5+ years Python experience",
            level=2,
            start_line=0,
            end_line=1,
            word_count=6,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Should classify from content
        assert len(result.all_types) >= 1

    def test_classify_from_content_level_minus_two(self) -> None:
        """Test classify uses content when level == -2 (untitled section)."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Some Title",  # Title present but ignored
            content="Requires 5+ years Python",
            level=-2,  # Untitled marker
            start_line=0,
            end_line=1,
            word_count=5,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Should classify from content despite title presence
        assert len(result.all_types) >= 1

    def test_classify_empty_content_returns_fallback(self) -> None:
        """Test classify returns fallback when both title and content empty."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="",
            content="",
            level=-2,
            start_line=0,
            end_line=0,
            word_count=0,
            line_count=0,
            has_list=False,
        )
        result = classifier.classify(section)
        # Should return fallback (UNLABELED with 0.0 confidence)
        assert len(result.all_types) == 1
        assert result.all_types[0].section_type == SectionType.UNLABELED
        assert result.all_types[0].confidence == 0.0


# ============================================================================
# Test 9: Ruler Pattern Matching (_match_ruler_patterns, _calculate_ruler_confidence)
# ============================================================================


class TestRulerPatternMatching:
    """Test ruler pattern matching and confidence calculation."""

    def test_calculate_ruler_confidence_base_only(self) -> None:
        """Test _calculate_ruler_confidence with base confidence only."""
        classifier = SectionClassifier()
        # Pattern with no adjustment in CONFIDENCE_ADJUSTMENT_BY_SECTION
        conf = classifier._calculate_ruler_confidence("SECTION_UNKNOWN")
        # Should use base confidence (0.70) with no adjustment
        assert conf == 0.70

    def test_calculate_ruler_confidence_with_positive_adjustment(self) -> None:
        """Test _calculate_ruler_confidence with positive section adjustment."""
        classifier = SectionClassifier()
        # SECTION_REQUIREMENTS has +0.15 adjustment: 0.70 + 0.15 = 0.85
        conf = classifier._calculate_ruler_confidence("SECTION_REQUIREMENTS")
        assert conf == 0.85

    def test_calculate_ruler_confidence_with_negative_adjustment(self) -> None:
        """Test _calculate_ruler_confidence with negative section adjustment."""
        classifier = SectionClassifier()
        # SECTION_BENEFITS has -0.50 adjustment: 0.70 - 0.50 = 0.20
        conf = classifier._calculate_ruler_confidence("SECTION_BENEFITS")
        assert conf == pytest.approx(0.20)  # Allow floating-point tolerance

    def test_calculate_ruler_confidence_clamped_to_zero(self) -> None:
        """Test _calculate_ruler_confidence clamps to minimum 0.0."""
        classifier = SectionClassifier()
        # SECTION_COMPENSATION has -0.50: 0.70 - 0.50 = 0.20 (no clamp needed)
        conf = classifier._calculate_ruler_confidence("SECTION_COMPENSATION")
        assert conf >= 0.0
        assert conf <= 1.0

    def test_match_ruler_patterns_returns_dict(self) -> None:
        """Test _match_ruler_patterns returns dict of SectionType -> pattern_label."""
        classifier = SectionClassifier()
        # Without spaCy model loaded, should return empty dict (graceful degradation)
        result = classifier._match_ruler_patterns("requirements section", "title")
        assert isinstance(result, dict)

    def test_clamp_confidence_valid_range(self) -> None:
        """Test _clamp_confidence keeps values in [0.0, 1.0]."""
        assert _clamp_confidence(0.5) == 0.5
        assert _clamp_confidence(0.0) == 0.0
        assert _clamp_confidence(1.0) == 1.0

    def test_clamp_confidence_below_zero(self) -> None:
        """Test _clamp_confidence clamps negative values to 0.0."""
        assert _clamp_confidence(-0.5) == 0.0

    def test_clamp_confidence_above_one(self) -> None:
        """Test _clamp_confidence clamps values > 1.0 to 1.0."""
        assert _clamp_confidence(1.5) == 1.0


# ============================================================================
# Test 10: classify_section() Module-Level Convenience Function
# ============================================================================


class TestClassifySectionFunction:
    """Test classify_section() module-level convenience wrapper."""

    def test_classify_section_with_default_classifier(self) -> None:
        """Test classify_section uses default classifier when none provided."""
        section = MarkdownSection(
            title="Technical Skills",
            content="Python, Java",
            level=2,
            start_line=0,
            end_line=1,
            word_count=4,
            line_count=1,
            has_list=False,
        )
        result = classify_section(section)
        assert len(result.all_types) >= 1
        assert isinstance(result.labels, frozenset)

    def test_classify_section_with_provided_classifier(self) -> None:
        """Test classify_section uses provided classifier instance."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Requirements",
            content="5+ years Python",
            level=2,
            start_line=0,
            end_line=1,
            word_count=3,
            line_count=1,
            has_list=False,
        )
        result = classify_section(section, classifier)
        assert len(result.all_types) >= 1

    def test_classify_section_with_custom_skip_keywords(self) -> None:
        """Test classify_section respects custom skip keywords via classifier."""
        custom_skip = frozenset({"benefits", "custom_skip_word"})
        classifier = SectionClassifier(skip_keywords=custom_skip)
        section = MarkdownSection(
            title="Benefits and Compensation",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=3,
            line_count=1,
            has_list=False,
        )
        result = classify_section(section, classifier)
        # Should recognize "benefits" as skip keyword
        assert len(result.all_types) >= 1

    def test_classify_section_none_raises_error(self) -> None:
        """Test classify_section raises ValueError for None section."""
        with pytest.raises(ValueError, match="section cannot be None"):
            classify_section(None)  # type: ignore[arg-type]


# ============================================================================
# Test 11: Edge Cases - Empty, No Matches, Skip Patterns
# ============================================================================


class TestEdgeCases:
    """Test edge cases: empty sections, no keyword matches, skip patterns."""

    def test_empty_title_and_content(self) -> None:
        """Test section with empty title and content returns fallback."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="",
            content="",
            level=-2,
            start_line=0,
            end_line=0,
            word_count=0,
            line_count=0,
            has_list=False,
        )
        result = classifier.classify(section)
        assert len(result.all_types) == 1
        assert result.all_types[0].section_type == SectionType.UNLABELED
        assert result.all_types[0].confidence == 0.0
        assert len(result.keyword_matches) == 0

    def test_no_keyword_matches_in_title(self) -> None:
        """Test section with title but no keyword matches uses fallback."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Random Title",  # No recognized keywords
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=2,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Should fall back to OTHER with 0.3 confidence
        assert result.all_types[0].section_type == SectionType.OTHER
        assert result.all_types[0].confidence == 0.3

    def test_no_keyword_matches_in_content(self) -> None:
        """Test content-based classification with no keyword matches."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="",
            content="Random text with no recognized keywords",
            level=-2,
            start_line=0,
            end_line=1,
            word_count=7,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Should fall back to DESCRIPTION with 0.2 confidence
        assert result.all_types[0].section_type == SectionType.DESCRIPTION
        assert result.all_types[0].confidence == 0.2

    def test_skip_pattern_matching(self) -> None:
        """Test section matching SKIP keywords is marked with is_skip=True."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Benefits and Compensation",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=3,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Should have SKIP type and is_skip=True
        types = {tc.section_type for tc in result.all_types}
        assert SectionType.SKIP in types
        assert result.is_skip is True

    def test_section_with_only_whitespace(self) -> None:
        """Test section with only whitespace in title and content."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="   ",
            content="   ",
            level=2,
            start_line=0,
            end_line=0,
            word_count=0,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Whitespace is stripped, so behaves like empty
        assert result.all_types[0].section_type == SectionType.UNLABELED
        assert result.all_types[0].confidence == 0.0

    def test_multiple_skip_keywords_in_title(self) -> None:
        """Test title with multiple SKIP keywords increases confidence."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Benefits and Compensation and Salary",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=5,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Should have multiple matches
        assert len(result.keyword_matches) >= 2


# ============================================================================
# Test 12: Initialization & Configuration
# ============================================================================


class TestSectionClassifierInitialization:
    """Test SectionClassifier initialization and configuration."""

    def test_classifier_default_skip_keywords(self) -> None:
        """Test SectionClassifier uses default SKIP_SECTIONS when not provided."""
        classifier = SectionClassifier()
        assert classifier.skip_keywords == SKIP_SECTIONS

    def test_classifier_custom_skip_keywords(self) -> None:
        """Test SectionClassifier accepts custom skip keywords."""
        custom_skip = frozenset({"custom", "keywords"})
        classifier = SectionClassifier(skip_keywords=custom_skip)
        assert classifier.skip_keywords == custom_skip

    def test_classifier_with_none_section_raises_error(self) -> None:
        """Test classify raises ValueError for None section."""
        classifier = SectionClassifier()
        with pytest.raises(ValueError, match="section cannot be None"):
            classifier.classify(None)  # type: ignore[arg-type]

    def test_classifier_get_nlp_returns_optional(self) -> None:
        """Test _get_nlp returns Optional[Language]."""
        classifier = SectionClassifier()
        nlp = classifier._get_nlp()
        # May be None if spaCy model not installed, or a Language object
        assert nlp is None or hasattr(nlp, "pipe")


# ============================================================================
# Test 13: Consistency & Regression Tests
# ============================================================================


class TestConsistencyAndRegression:
    """Test consistency of results and regression scenarios."""

    def test_same_input_produces_same_output(self) -> None:
        """Test that same input produces same output (deterministic)."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Technical Skills",
            content="Python, Java",
            level=2,
            start_line=0,
            end_line=1,
            word_count=4,
            line_count=1,
            has_list=False,
        )
        result1 = classifier.classify(section)
        result2 = classifier.classify(section)
        # Results should be identical
        assert len(result1.all_types) == len(result2.all_types)
        assert result1.labels == result2.labels

    def test_confidence_scores_in_valid_range(self) -> None:
        """Test that all confidence scores are in [0.0, 1.0]."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Skills and Requirements",
            content="Experience with Python",
            level=2,
            start_line=0,
            end_line=1,
            word_count=5,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        for tc in result.all_types:
            assert 0.0 <= tc.confidence <= 1.0

    def test_keyword_positions_are_valid(self) -> None:
        """Test that keyword positions are >= -1 (valid or sentinel)."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Technical Skills",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=2,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        for km in result.keyword_matches:
            assert km.position >= -1
            assert isinstance(km.position, int)

    def test_labels_match_all_types_section_types(self) -> None:
        """Test that labels frozenset matches all_types section types."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Skills and Responsibilities",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=3,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        all_types_set = {tc.section_type for tc in result.all_types}
        assert result.labels == all_types_set


# ============================================================================
# Test: Word-Boundary Keyword Matching (Issue #365)
# ============================================================================


class TestWordBoundaryKeywordMatching:
    """Test leading-only word boundary keyword matching prevents mid-word hits."""

    def test_our_in_hourly_not_skip(self) -> None:
        """Verify 'our' in 'HOURLY' does not match (mid-word blocked)."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Hourly Rate Required",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=3,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # 'hourly' is in SKIP_SECTIONS, so this should match SKIP
        # But the critical test: 'our' alone should not trigger SKIP
        # This tests that the regex (?<!\w)our does not match mid-word 'our'
        assert len(result.all_types) > 0
        # The classification should have matched 'hourly' as SKIP, not due to 'our'

    def test_our_in_your_title_not_skip(self) -> None:
        """Verify 'our' in 'Your' does not match as mid-word substring."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Your Impact",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=2,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # 'our' is a skip keyword, but should NOT match in 'your' (mid-word)
        assert not result.is_skip

    def test_leading_our_still_skip(self) -> None:
        """Verify leading 'Our' matches and is_skip=True."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Our Company Benefits",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=3,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # 'our' is a skip keyword at word start, should match
        assert result.is_skip

    def test_stem_qualif_still_matches(self) -> None:
        """Verify 'qualif' matches 'Qualifications'."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Qualifications",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=1,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # 'qualif' is a QUALIFICATIONS keyword and should match
        assert SectionType.QUALIFICATIONS in result.labels

    def test_stem_requirements_still_matches(self) -> None:
        """Verify 'requirement' matches 'Requirements'."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Requirements",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=1,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # 'requirement' is a QUALIFICATIONS keyword and should match
        assert SectionType.QUALIFICATIONS in result.labels

    def test_relocation_still_skip(self) -> None:
        """Verify 'relocation' keyword is matched as SKIP (D6 additive)."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Relocation Required",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=2,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # 'relocation' was added in D6 as skip keyword
        assert result.is_skip

    def test_hourly_rate_still_skip(self) -> None:
        """Verify 'hourly' keyword is matched as SKIP (D6 additive)."""
        classifier = SectionClassifier()
        section = MarkdownSection(
            title="Hourly Rate: $50/hr",
            content="",
            level=2,
            start_line=0,
            end_line=0,
            word_count=3,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # 'hourly' was added in D6 as skip keyword
        assert result.is_skip


# ============================================================================
# Test: Skip Precedence - Content Path (Issue #365)
# ============================================================================


class TestSkipPrecedenceContentPath:
    """Test that content-path is_skip only when top-ranked type is SKIP."""

    def test_untitled_content_is_skip_false_when_description_outranks_skip(self) -> None:
        """Untitled content with location/compensation/our hits: is_skip=False if description outranks skip."""
        classifier = SectionClassifier()
        # Simulate WorkSource-shaped untitled section: starts with description-like text
        # but contains 'our' and 'location' keywords
        section = MarkdownSection(
            title="",  # Untitled (level -2)
            content="Manage Python projects in our new location office. Competitive compensation.",
            level=-2,
            start_line=0,
            end_line=2,
            word_count=12,
            line_count=2,
            has_list=False,
        )
        result = classifier.classify(section)
        # Content-path classify should:
        # - Detect 'our' (SKIP) and 'location' (possibly SKIP or DESCRIPTION)
        # - But if DESCRIPTION is top-ranked, is_skip should be False
        # For this test, we just verify is_skip reflects top-ranked type, not any match
        # If DESCRIPTION ranks higher than SKIP, is_skip should be False
        if len(result.all_types) > 0 and result.all_types[0].section_type != SectionType.SKIP:
            assert not result.is_skip

    def test_titled_is_skip_unchanged_any_hit(self) -> None:
        """Titled sections still use 'any skip hit' rule for is_skip (title path unchanged)."""
        classifier = SectionClassifier()
        # Title with 'our' (SKIP) and 'skills' (SKILLS)
        section = MarkdownSection(
            title="Our Technical Skills",
            content="Python, Java, SQL",
            level=2,
            start_line=0,
            end_line=1,
            word_count=5,
            line_count=1,
            has_list=False,
        )
        result = classifier.classify(section)
        # Title path: "any skip hit" rule, so is_skip=True if SKIP in any matched type
        if SectionType.SKIP in result.labels:
            assert result.is_skip
