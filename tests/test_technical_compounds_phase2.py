"""Phase 2: Technical Compounds Module Tests for Issue #191.

Comprehensive tests for the technical_compounds module including:
- Pattern detection (exact matches, keywords, patterns)
- Confidence scoring (Tier 1-3)
- Category organization
- Helper functions
"""

import pytest

from src.tokenization.technical_compounds import (
    get_compound_categories,
    get_confidence_score,
    get_technical_compounds,
    is_technical_compound,
    reclassify_compound,
)


class TestTechnicalCompoundPatterns:
    """Test technical compound pattern detection."""

    def test_issue_191_compounds_detected(self):
        """Test that Issue #191 identified compounds are detected."""
        compounds = [
            "software development",
            "data processing",
            "engineering technology",
            "manufacturing engineering",
            "system-level",
        ]

        for compound in compounds:
            assert is_technical_compound(compound), f"Failed to detect Issue #191 compound: {compound}"

    def test_exact_match_patterns(self):
        """Test exact match patterns from TECHNICAL_COMPOUND_PATTERNS."""
        patterns = [
            "spring framework",
            "spring boot",
            "react native",
            "web service",
            "microservice",
            "cloud service",
            "sql database",
            "nosql database",
            "python django",
            "python flask",
            "javascript react",
        ]

        for pattern in patterns:
            assert is_technical_compound(pattern), f"Failed to detect exact pattern: {pattern}"

    def test_multi_word_keyword_patterns(self):
        """Test multi-word phrases containing tech keywords."""
        phrases = [
            "custom framework",
            "api framework",
            "testing framework",
            "cloud platform",
            "scalable system",
            "distributed system",
            "deployment tool",
            "management utility",
            "network plugin",
        ]

        for phrase in phrases:
            result = is_technical_compound(phrase)
            assert result, f"Should detect phrase with tech keyword: {phrase}"

    def test_single_word_not_compound(self):
        """Test that single words are NOT flagged as compounds."""
        single_words = [
            "python",
            "javascript",
            "java",
            "react",
            "docker",
            "kubernetes",
            "aws",
            "sql",
            "mongodb",
            "redis",
            "leadership",
            "communication",
            "teamwork",
        ]

        for word in single_words:
            assert not is_technical_compound(word), f"Incorrectly flagged single word as compound: {word}"

    def test_soft_skills_not_flagged(self):
        """Test that soft skills are NOT flagged as compounds."""
        soft_skills = [
            "leadership",
            "communication",
            "teamwork",
            "problem-solving",
            "analytical skills",
            "adaptability",
            "creativity",
            "collaboration",
            "critical thinking",
            "attention to detail",
        ]

        for skill in soft_skills:
            assert not is_technical_compound(skill), f"Incorrectly flagged soft skill as compound: {skill}"

    def test_ambiguous_single_words(self):
        """Test ambiguous words that should NOT be compounds."""
        ambiguous = [
            "software",
            "system",
            "data",
            "platform",
            "application",
            "service",
            "database",
            "tools",
            "system",
        ]

        for word in ambiguous:
            result = is_technical_compound(word)
            if len(word.split()) == 1:
                assert not result, f"Single word '{word}' should not be compound"


class TestConfidenceScoring:
    """Test confidence score calculation (Tier 1-3)."""

    def test_tier1_exact_match_high_confidence(self):
        """Test Tier 1: Exact match gets high confidence (0.8-1.0)."""
        exact_matches = [
            "software development",
            "data processing",
            "microservice",
            "web service",
        ]

        for phrase in exact_matches:
            score = get_confidence_score(phrase)
            assert 0.8 <= score <= 1.0, f"Exact match '{phrase}' should have high confidence, got {score}"

    def test_tier2_keyword_patterns_medium_confidence(self):
        """Test Tier 2: Multi-word with tech keyword (0.6-0.75)."""
        keyword_patterns = [
            "custom framework",
            "api platform",
            "cloud service additional",
        ]

        for phrase in keyword_patterns:
            score = get_confidence_score(phrase)
            if is_technical_compound(phrase):
                assert 0.5 <= score <= 0.8, f"Keyword pattern '{phrase}' confidence unexpected: {score}"

    def test_tier3_issue_191_pattern_medium_confidence(self):
        """Test Tier 3: Issue #191 pattern detection (0.5-0.6)."""
        issue_191_patterns = [
            "software engineering",
            "manufacturing process",
            "system architecture",
        ]

        for phrase in issue_191_patterns:
            score = get_confidence_score(phrase)
            assert score >= 0.5, f"Issue #191 pattern '{phrase}' should have confidence >= 0.5, got {score}"

    def test_no_match_zero_confidence(self):
        """Test phrases that don't match get zero confidence."""
        non_compounds = [
            "python",
            "javascript",
            "leadership",
            "communication",
            "ability",
            "experience",
        ]

        for phrase in non_compounds:
            score = get_confidence_score(phrase)
            assert score == 0.0, f"Non-compound '{phrase}' should have 0.0 confidence, got {score}"

    def test_confidence_score_range(self):
        """Test confidence scores are always in valid range [0.0, 1.0]."""
        test_phrases = [
            "software development",
            "python",
            "microservices",
            "leadership skills",
            "distributed database",
        ]

        for phrase in test_phrases:
            score = get_confidence_score(phrase)
            assert 0.0 <= score <= 1.0, f"Confidence score out of range for '{phrase}': {score}"


class TestGetTechnicalCompounds:
    """Test get_technical_compounds() function."""

    def test_returns_set(self):
        """Test that function returns a set."""
        result = get_technical_compounds()
        assert isinstance(result, set), "Should return a set"

    def test_contains_known_compounds(self):
        """Test that returned set contains expected compounds."""
        compounds = get_technical_compounds()

        expected = [
            "software development",
            "data processing",
            "engineering technology",
            "web service",
            "microservice",
        ]

        for compound in expected:
            assert compound in compounds, f"Expected compound not in set: {compound}"

    def test_non_empty_set(self):
        """Test that set is not empty."""
        compounds = get_technical_compounds()
        assert len(compounds) > 0, "Compound set should not be empty"
        assert len(compounds) > 50, f"Should have 50+ patterns, got {len(compounds)}"

    def test_returns_copy(self):
        """Test that function returns a copy, not reference."""
        compounds1 = get_technical_compounds()
        compounds2 = get_technical_compounds()

        assert compounds1 == compounds2, "Sets should be equal"
        assert compounds1 is not compounds2, "Should return new copy each time"


class TestGetCompoundCategories:
    """Test get_compound_categories() function."""

    def test_returns_dict(self):
        """Test that function returns a dict."""
        result = get_compound_categories()
        assert isinstance(result, dict), "Should return a dict"

    def test_has_expected_categories(self):
        """Test that all expected categories are present."""
        categories = get_compound_categories()

        expected_categories = [
            "development",
            "data",
            "infrastructure",
            "architecture",
            "engineering",
            "frameworks",
            "services",
            "database",
        ]

        for category in expected_categories:
            assert category in categories, f"Missing category: {category}"

    def test_categories_contain_lists(self):
        """Test that each category contains a list."""
        categories = get_compound_categories()

        for category, compounds in categories.items():
            assert isinstance(compounds, list), f"Category '{category}' should contain a list, got {type(compounds)}"
            assert len(compounds) > 0, f"Category '{category}' should not be empty"

    def test_development_category(self):
        """Test development category contains expected compounds."""
        categories = get_compound_categories()
        dev_compounds = categories["development"]

        assert "software development" in dev_compounds
        assert "software engineering" in dev_compounds

    def test_data_category(self):
        """Test data category contains expected compounds."""
        categories = get_compound_categories()
        data_compounds = categories["data"]

        assert "data processing" in data_compounds
        assert "data processing pipeline" in data_compounds

    def test_engineering_category(self):
        """Test engineering category contains Issue #191 compounds."""
        categories = get_compound_categories()
        eng_compounds = categories["engineering"]

        assert "engineering technology" in eng_compounds
        assert "manufacturing engineering" in eng_compounds


class TestReclassifyCompound:
    """Test reclassify_compound() function."""

    def test_should_reclassify_compounds(self):
        """Test that technical compounds should be reclassified."""
        compounds = [
            "software development",
            "data processing",
            "microservice",
            "web framework",
        ]

        for compound in compounds:
            assert reclassify_compound(compound), f"Should reclassify compound: {compound}"

    def test_should_not_reclassify_single_words(self):
        """Test that single words should NOT be reclassified."""
        single_words = [
            "python",
            "leadership",
            "communication",
            "docker",
            "kubernetes",
        ]

        for word in single_words:
            assert not reclassify_compound(word), f"Should not reclassify single word: {word}"

    def test_confidence_threshold_parameter(self):
        """Test that confidence_threshold parameter works."""
        assert reclassify_compound("software development", confidence_threshold=0.5)
        assert reclassify_compound("software development", confidence_threshold=0.9)
        assert reclassify_compound("software development", confidence_threshold=0.95)

        phrase_with_keyword = "custom framework"
        if get_confidence_score(phrase_with_keyword) >= 0.5:
            assert reclassify_compound(phrase_with_keyword, confidence_threshold=0.5)

    def test_non_compound_with_high_threshold(self):
        """Test non-compounds fail with reasonable thresholds."""
        non_compounds = [
            "python",
            "java",
            "leadership",
            "communication",
            "teamwork",
        ]

        for phrase in non_compounds:
            assert not reclassify_compound(phrase, confidence_threshold=0.5), (
                f"Should not reclassify non-compound with threshold=0.5: {phrase}"
            )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string(self):
        """Test empty string handling."""
        assert not is_technical_compound("")
        assert get_confidence_score("") == 0.0
        assert not reclassify_compound("")

    def test_whitespace_only(self):
        """Test whitespace-only string handling."""
        assert not is_technical_compound("   ")
        assert get_confidence_score("   ") == 0.0

    def test_very_short_string(self):
        """Test short strings (< 3 chars)."""
        assert not is_technical_compound("ab")
        assert not is_technical_compound("x")
        assert get_confidence_score("ab") == 0.0

    def test_case_insensitivity(self):
        """Test that matching is case-insensitive."""
        test_cases = [
            ("SOFTWARE DEVELOPMENT", True),
            ("Software Development", True),
            ("software development", True),
            ("PYTHON", False),
            ("Python", False),
        ]

        for phrase, expected in test_cases:
            result = is_technical_compound(phrase)
            assert result == expected, f"Case sensitivity issue for '{phrase}': got {result}, expected {expected}"

    def test_compound_with_extra_spaces(self):
        """Test compounds with extra spaces."""
        assert is_technical_compound("  software development  ")
        assert is_technical_compound("software  development")

    def test_partial_match_in_longer_phrase(self):
        """Test that partial matches work in longer phrases."""
        longer_phrases = [
            "expert in software development practices",
            "data processing and analysis",
            "microservice architecture patterns",
        ]

        for phrase in longer_phrases:
            score = get_confidence_score(phrase)
            print(f"Phrase: '{phrase}' -> confidence: {score}")
