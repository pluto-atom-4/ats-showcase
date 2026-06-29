"""Tests for company filtering in AssessmentStore."""

import json
from pathlib import Path

import pytest

from storage.assessment_store import AssessmentStore


@pytest.fixture
def store(tmp_path):
    """Create temporary assessment store for testing."""
    db_path = str(tmp_path / "test.db")
    store = AssessmentStore(db_path)

    # Add test data with different companies
    store.save_assessment(
        job_id="google_1",
        title="Senior Python Engineer",
        company="Google",
        location="Mountain View, CA",
        overall_score=92,
        tech_score=95,
        seniority_score=90,
        location_score=80,
        recommendations=["Strong match", "Apply immediately"],
        summary="Python + 5 years experience",
        tokens_used=1200,
        actual_cost=0.0036,
    )

    store.save_assessment(
        job_id="google_2",
        title="ML Engineer",
        company="Google",
        location="Mountain View, CA",
        overall_score=88,
        tech_score=92,
        seniority_score=85,
        location_score=80,
        recommendations=["Good fit"],
        summary="Machine learning + TensorFlow",
        tokens_used=1300,
        actual_cost=0.0039,
    )

    store.save_assessment(
        job_id="amazon_1",
        title="Backend Engineer",
        company="Amazon",
        location="Seattle, WA",
        overall_score=75,
        tech_score=80,
        seniority_score=70,
        location_score=85,
        recommendations=["Consider applying"],
        summary="Python + AWS + 3 years",
        tokens_used=1100,
        actual_cost=0.0033,
    )

    store.save_assessment(
        job_id="meta_1",
        title="Frontend Engineer",
        company="Meta",
        location="Menlo Park, CA",
        overall_score=65,
        tech_score=70,
        seniority_score=60,
        location_score=75,
        recommendations=["Possible match"],
        summary="React + JavaScript",
        tokens_used=900,
        actual_cost=0.0027,
    )

    yield store
    store._close_db()


class TestCompanyFiltering:
    """Test company filtering in query methods."""

    def test_get_assessments_by_score_no_company_filter(self, store):
        """Get assessments without company filter should return all."""
        results = store.get_assessments_by_score(min_score=60, max_score=100)
        assert len(results) == 4
        companies = {r["company"] for r in results}
        assert companies == {"Google", "Amazon", "Meta"}

    def test_get_assessments_by_score_with_company_filter(self, store):
        """Get assessments with company filter should return only that company."""
        results = store.get_assessments_by_score(min_score=70, max_score=100, company="Google")
        assert len(results) == 2
        assert all(r["company"] == "Google" for r in results)

    def test_get_assessments_by_score_company_filter_no_results(self, store):
        """Company filter returning no results."""
        results = store.get_assessments_by_score(min_score=90, max_score=100, company="Amazon")
        assert len(results) == 0

    def test_search_by_keyword_no_company_filter(self, store):
        """Search without company filter should return all matches."""
        results = store.search_by_keyword("engineer", min_score=0)
        assert len(results) >= 3  # Python, ML, Backend, Frontend engineers
        companies = {r["company"] for r in results}
        assert "Google" in companies
        assert "Amazon" in companies

    def test_search_by_keyword_with_company_filter(self, store):
        """Search with company filter should return only that company."""
        results = store.search_by_keyword("engineer", min_score=0, company="Google")
        assert len(results) == 2
        assert all(r["company"] == "Google" for r in results)

    def test_search_by_keyword_company_and_score_filter(self, store):
        """Search with both company and score filters."""
        results = store.search_by_keyword(
            "engineer", min_score=85, max_score=100, company="Google"
        )
        assert len(results) == 2
        assert all(r["company"] == "Google" for r in results)
        assert all(r["overall_score"] >= 85 for r in results)

    def test_get_companies(self, store):
        """Get list of distinct companies."""
        companies = store.get_companies()
        assert len(companies) == 3
        assert "Google" in companies
        assert "Amazon" in companies
        assert "Meta" in companies

    def test_get_company_summary(self, store):
        """Get aggregated stats per company."""
        summary = store.get_company_summary()
        assert len(summary) == 3

        google_stats = next(s for s in summary if s["company"] == "Google")
        assert google_stats["count"] == 2
        assert google_stats["avg_score"] == 90.0
        assert google_stats["max_score"] == 92
        assert google_stats["min_score"] == 88

        amazon_stats = next(s for s in summary if s["company"] == "Amazon")
        assert amazon_stats["count"] == 1
        assert amazon_stats["avg_score"] == 75.0

    def test_get_stats_by_company(self, store):
        """Get detailed stats for specific company."""
        stats = store.get_stats_by_company("Google")
        assert stats["company"] == "Google"
        assert stats["total_assessments"] == 2
        assert stats["avg_score"] == 90.0
        assert stats["total_tokens"] == 2500
        assert stats["score_distribution"]["high (75+)"] == 2
        assert stats["score_distribution"]["medium (50-74)"] == 0

    def test_get_top_keywords(self, store):
        """Extract top keywords from job descriptions."""
        keywords = store.get_top_keywords(limit=5)
        assert len(keywords) > 0
        # Should be list of (keyword, frequency) tuples
        assert all(isinstance(k, tuple) and len(k) == 2 for k in keywords)
        # Keywords should be sorted by frequency (descending)
        freqs = [k[1] for k in keywords]
        assert freqs == sorted(freqs, reverse=True)

    def test_get_top_keywords_with_company_filter(self, store):
        """Extract top keywords for specific company."""
        keywords = store.get_top_keywords(limit=5, company="Google")
        assert len(keywords) > 0
        # All keywords should be from Google's job descriptions
        assert all(isinstance(k, tuple) for k in keywords)

    def test_get_top_keywords_filters_common_words(self, store):
        """Top keywords should filter out common words."""
        keywords = store.get_top_keywords(limit=10)
        keyword_words = [k[0] for k in keywords]
        # Should not include common words like 'and', 'the', 'for'
        assert "and" not in keyword_words
        assert "the" not in keyword_words
        assert "for" not in keyword_words


class TestCompanyFilteringEdgeCases:
    """Test edge cases for company filtering."""

    def test_empty_database(self, tmp_path):
        """Company filtering on empty database."""
        db_path = str(tmp_path / "empty.db")
        store = AssessmentStore(db_path)

        assert store.get_companies() == []
        assert store.get_company_summary() == []
        # get_stats_by_company returns a dict with 0 counts for empty company
        stats = store.get_stats_by_company("Google")
        assert stats.get("total_assessments", 0) == 0
        assert store.get_top_keywords(company="Google") == []
        assert store.search_by_keyword("test", company="Google") == []
        assert store.get_assessments_by_score(company="Google") == []

        store._close_db()

    def test_company_with_special_characters(self, tmp_path):
        """Company names with special characters."""
        db_path = str(tmp_path / "special.db")
        store = AssessmentStore(db_path)

        store.save_assessment(
            job_id="test_1",
            title="Engineer",
            company="O'Reilly & Associates",
            location="Nowhere",
            overall_score=80,
            tech_score=80,
            seniority_score=80,
            location_score=80,
            recommendations=[],
            summary="Test",
            tokens_used=100,
            actual_cost=0.0,
        )

        companies = store.get_companies()
        assert "O'Reilly & Associates" in companies

        results = store.search_by_keyword("engineer", company="O'Reilly & Associates")
        assert len(results) == 1

        store._close_db()

    def test_null_company_values(self, tmp_path):
        """Assessments with NULL company should be handled correctly."""
        db_path = str(tmp_path / "null.db")
        store = AssessmentStore(db_path)

        store.save_assessment(
            job_id="test_1",
            title="Engineer",
            company=None,
            location="Nowhere",
            overall_score=80,
            tech_score=80,
            seniority_score=80,
            location_score=80,
            recommendations=[],
            summary="Test",
            tokens_used=100,
            actual_cost=0.0,
        )

        companies = store.get_companies()
        # NULL company should not appear in distinct list
        assert None not in companies
        assert len(companies) == 0

        store._close_db()
