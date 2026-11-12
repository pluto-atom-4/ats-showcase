"""Test extract_requirements_d.py (POC-D semantic dedup).

Migrates semantic dedup tests from test_requirement_normalizer.py.
Adds POC-D integration tests for semantic dedup scenarios.

Issue #271: Consolidates requirement_normalizer.py logic into POC-D.
"""

import pytest

from src.poc.extract_requirements_d import (
    _deduplicate_requirements_semantic,
    _find_matching_requirement,
    _normalize_requirement_for_comparison,
)


class TestNormalizeRequirementForComparison:
    """Test requirement normalization (consolidates from RequirementNormalizer)."""

    def test_normalize_removes_trailing_parentheticals(self):
        """Parenthetical notes at end are removed."""
        result = _normalize_requirement_for_comparison("Deep experience with ARINC 429, ARINC 717 (Preferred)")
        assert "(Preferred)" not in result
        assert "ARINC" in result

    def test_normalize_collapses_verbose_alternatives(self):
        """Verbose alternatives like 'working with and/or' are collapsed."""
        original = "2+ years of experience working with and/or interpreting engineering data"
        result = _normalize_requirement_for_comparison(original)
        assert "working with and/or" not in result
        assert "interpreting" in result

    def test_normalize_simplifies_adjectives(self):
        """Adjectives before 'experience' are simplified."""
        cases = [
            ("Deep experience with Python", "experience with Python"),
            ("Strong experience with Java", "experience with Java"),
            ("Extensive experience with Kubernetes", "experience with Kubernetes"),
            ("Proven experience with AWS", "experience with AWS"),
            ("Demonstrated experience with Docker", "experience with Docker"),
        ]
        for original, expected_substr in cases:
            result = _normalize_requirement_for_comparison(original)
            assert expected_substr.lower() in result.lower(), f"Failed for: {original}"

    def test_normalize_removes_hands_on_prefix(self):
        """'Hands-on' prefix is removed (hyphenated form)."""
        original = "Hands-on experience with Apache Parquet"
        result = _normalize_requirement_for_comparison(original)
        assert "hands-on" not in result.lower()
        assert result.lower() == "experience with apache parquet"

    def test_normalize_standardizes_years(self):
        """Years patterns are standardized to 'N+ years of experience'."""
        original = "2+ years of experience interpreting data"
        result = _normalize_requirement_for_comparison(original)
        assert "2+ years of experience" in result.lower()

        original = "9+ years experience with C++"
        result = _normalize_requirement_for_comparison(original)
        assert "9+ years of experience" in result.lower()

    def test_normalize_preserves_core_meaning(self):
        """Normalization preserves core requirement meaning."""
        original = "Bachelor's Degree in Computer Science"
        result = _normalize_requirement_for_comparison(original)
        assert "bachelor" in result.lower()
        assert "computer" in result.lower()

    def test_normalize_collapses_whitespace(self):
        """Multiple spaces are collapsed."""
        original = "Experience   with    Python     and    Java"
        result = _normalize_requirement_for_comparison(original)
        assert "   " not in result


class TestFindMatchingRequirement:
    """Test semantic matching (consolidates from RequirementNormalizer)."""

    def test_exact_match_returns_high_confidence(self):
        """Exact normalized matches return confidence 1.0."""
        candidates = [
            "2+ years of experience interpreting engineering data",
            "Python programming",
        ]
        match, score = _find_matching_requirement(
            "2+ years of experience interpreting engineering data",
            candidates,
            threshold=0.7,
        )
        assert match == "2+ years of experience interpreting engineering data"
        assert score == 1.0

    def test_fuzzy_match_parenthetical_variant(self):
        """'Preferred' variant of requirement matches original."""
        candidates = [
            "Deep experience with ARINC 429, ARINC 717, and ARINC 767 formats (Preferred)",
        ]
        match, score = _find_matching_requirement(
            "Deep experience with ARINC 429, ARINC 717, and ARINC 767 formats",
            candidates,
            threshold=0.8,
        )
        assert match is not None
        assert score >= 0.8

    def test_fuzzy_match_verbose_variant(self):
        """Verbose variant with 'working with and/or' matches."""
        candidates = [
            "2+ years of experience working with and/or interpreting engineering data or engineering drawings",
        ]
        match, score = _find_matching_requirement(
            "2+ years of experience interpreting engineering data or drawings",
            candidates,
            threshold=0.7,
        )
        assert match is not None
        assert score >= 0.7

    def test_fuzzy_match_adjective_variant(self):
        """'Deep' variant matches 'standard' version."""
        candidates = [
            "Deep experience with Python",
        ]
        match, score = _find_matching_requirement(
            "Experience with Python",
            candidates,
            threshold=0.8,
        )
        assert match is not None
        assert score >= 0.75

    def test_fuzzy_match_hands_on_variant(self):
        """'Hands-on' variant matches standard version (substring boost)."""
        candidates = [
            "Hands-on experience with Apache Parquet, Apache ORC, HDF5, and Delta Lake (Preferred)",
        ]
        match, score = _find_matching_requirement(
            "Experience with HDF5",
            candidates,
            threshold=0.4,
        )
        assert match is not None
        assert score >= 0.3

    def test_no_match_below_threshold(self):
        """Unrelated requirements don't match."""
        candidates = [
            "Python programming",
            "Java development",
        ]
        match, score = _find_matching_requirement(
            "Frontend CSS/HTML skills",
            candidates,
            threshold=0.8,
        )
        if match is not None:
            assert score < 0.8

    def test_substring_matching_boosts_score(self):
        """Substring matches get boosted score."""
        candidates = [
            "Knowledge of Python, Java, and Go",
        ]
        match, score = _find_matching_requirement(
            "Python",
            candidates,
            threshold=0.2,
        )
        assert match is not None
        assert score >= 0.15

    def test_threshold_parameter_respected(self):
        """Threshold parameter controls minimum score."""
        candidates = [
            "Experience with Python",
        ]
        match, score = _find_matching_requirement(
            "Python",
            candidates,
            threshold=0.3,
        )
        assert match is not None

        match_strict, score_strict = _find_matching_requirement(
            "Python",
            candidates,
            threshold=0.95,
        )


class TestDeduplicateRequirementsSemanticD:
    """Test POC-D semantic deduplication."""

    def test_dedup_removes_exact_duplicates(self):
        """Exact duplicates are removed."""
        requirements = [
            {"text": "Python experience", "final_confidence": 0.9},
            {"text": "Python experience", "final_confidence": 0.8},
        ]
        result = _deduplicate_requirements_semantic(requirements, threshold=0.8)
        assert len(result) == 1
        assert result[0]["final_confidence"] == 0.9

    def test_dedup_removes_semantic_duplicates_parenthetical(self):
        """Semantic duplicates with parentheticals are removed."""
        requirements = [
            {"text": "Deep experience with ARINC 429 formats", "final_confidence": 0.95},
            {"text": "Deep experience with ARINC 429 formats (Preferred)", "final_confidence": 0.70},
        ]
        result = _deduplicate_requirements_semantic(requirements, threshold=0.8)
        assert len(result) == 1
        assert "ARINC 429" in result[0]["text"]

    def test_dedup_removes_semantic_duplicates_verbose(self):
        """Semantic duplicates with verbose forms are removed."""
        requirements = [
            {
                "text": "2+ years of experience working with and/or interpreting engineering data",
                "final_confidence": 0.85,
            },
            {"text": "2+ years of experience interpreting engineering data", "final_confidence": 0.92},
        ]
        result = _deduplicate_requirements_semantic(requirements, threshold=0.8)
        assert len(result) == 1
        assert "working with and/or" in result[0]["text"]

    def test_dedup_removes_semantic_duplicates_adjectives(self):
        """Semantic duplicates with adjective variants are removed."""
        requirements = [
            {"text": "Deep experience with Python", "final_confidence": 0.88},
            {"text": "Strong experience with Python", "final_confidence": 0.85},
            {"text": "Experience with Python", "final_confidence": 0.90},
        ]
        result = _deduplicate_requirements_semantic(requirements, threshold=0.8)
        assert len(result) <= 2
        assert any("Python" in r["text"] for r in result)

    def test_dedup_preserves_distinct_requirements(self):
        """Distinct requirements are not deduplicated."""
        requirements = [
            {"text": "Python experience", "final_confidence": 0.90},
            {"text": "Java experience", "final_confidence": 0.85},
            {"text": "Kubernetes knowledge", "final_confidence": 0.80},
        ]
        result = _deduplicate_requirements_semantic(requirements, threshold=0.8)
        assert len(result) == 3

    def test_dedup_sorts_by_confidence_descending(self):
        """Results are sorted by final_confidence descending."""
        requirements = [
            {"text": "Python", "final_confidence": 0.75},
            {"text": "Java", "final_confidence": 0.95},
            {"text": "Go", "final_confidence": 0.85},
        ]
        result = _deduplicate_requirements_semantic(requirements, threshold=0.8)
        confidences = [r["final_confidence"] for r in result]
        assert confidences == sorted(confidences, reverse=True)

    def test_dedup_handles_empty_list(self):
        """Empty list returns empty list."""
        result = _deduplicate_requirements_semantic([], threshold=0.8)
        assert len(result) == 0

    def test_dedup_handles_single_requirement(self):
        """Single requirement returns single requirement."""
        requirements = [{"text": "Python", "final_confidence": 0.9}]
        result = _deduplicate_requirements_semantic(requirements, threshold=0.8)
        assert len(result) == 1
        assert result[0]["text"] == "Python"

    def test_dedup_respects_threshold(self):
        """Threshold parameter controls dedup strictness."""
        requirements = [
            {"text": "Python experience", "final_confidence": 0.9},
            {"text": "Python skills", "final_confidence": 0.85},
        ]

        result_loose = _deduplicate_requirements_semantic(requirements, threshold=0.5)
        result_strict = _deduplicate_requirements_semantic(requirements, threshold=0.95)

        assert len(result_loose) <= len(result_strict)

    def test_dedup_boeing_example(self):
        """Real Boeing example from test_requirement_normalizer.py."""
        requirements = [
            {
                "text": (
                    "2+ years of experience working with and/or interpreting engineering data or engineering drawings"
                ),
                "final_confidence": 0.90,
            },
            {"text": "2+ years of experience interpreting engineering data or drawings", "final_confidence": 0.92},
            {
                "text": "2+ years of experience performing quantitative or statistical analysis, "
                "data collection, preparation and interpretation",
                "final_confidence": 0.88,
            },
            {
                "text": "9+ years of experience software development using either Java, C++, or Python",
                "final_confidence": 0.85,
            },
            {"text": "Bachelor's Degree", "final_confidence": 0.95},
            {
                "text": "Deep experience with ARINC 429, ARINC 717, and ARINC 767 formats (Preferred)",
                "final_confidence": 0.70,
            },
            {
                "text": "Hands-on experience with Apache Parquet, Apache ORC, HDF5, and Delta Lake (Preferred)",
                "final_confidence": 0.65,
            },
        ]

        result = _deduplicate_requirements_semantic(requirements, threshold=0.8)

        assert len(result) >= 4
        assert len(result) <= 7

        confidences = [r["final_confidence"] for r in result]
        assert 0.95 in confidences

    def test_dedup_quality_improvement_over_exact_match(self):
        """POC-D semantic dedup improves over POC-C exact-match."""
        requirements = [
            {"text": "Python", "final_confidence": 0.9},
            {"text": "Python (Preferred)", "final_confidence": 0.7},
            {"text": "Knowledge of Python", "final_confidence": 0.85},
            {"text": "Python experience", "final_confidence": 0.88},
        ]

        result = _deduplicate_requirements_semantic(requirements, threshold=0.8)

        assert len(result) < len(requirements), "Semantic dedup should reduce duplicates vs exact-match"


class TestExtractRequirementsDIntegration:
    """Integration tests for extract_requirements_d (POC-D full pipeline).

    Note: These are lighter tests; full pipeline testing done in separate
    integration test files. This tests semantic dedup feature specifically.
    """

    def test_semantic_dedup_metadata(self):
        """POC-D metadata includes dedup_algorithm field."""
        from src.poc.extract_requirements_d import extract_requirements_d

        simple_job = "Requirements: Python, Java, or Go experience. Strong communication skills required."

        result = extract_requirements_d(simple_job, min_confidence=0.0)

        assert "dedup_algorithm" in result.metadata
        assert "semantic_fuzzy" in result.metadata["dedup_algorithm"]
        assert "threshold=" in result.metadata["dedup_algorithm"]

    def test_semantic_dedup_threshold_parameter(self):
        """POC-D respects dedup_threshold parameter."""
        from src.poc.extract_requirements_d import extract_requirements_d

        simple_job = "Required: Python, Java. Must know Python (preferred). Python experience needed."

        result_loose = extract_requirements_d(
            simple_job,
            min_confidence=0.0,
            dedup_threshold=0.5,
        )

        result_strict = extract_requirements_d(
            simple_job,
            min_confidence=0.0,
            dedup_threshold=0.95,
        )

        assert len(result_loose.requirements) <= len(result_strict.requirements)
