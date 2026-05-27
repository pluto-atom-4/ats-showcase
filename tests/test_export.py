"""Tests for Phase 5: Export & Analytics."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.storage.assessment_store import AssessmentStore
from src.storage.export import ExportConfig, MarkdownExporter

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def temp_db():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def store_with_assessments(temp_db):
    """Create store with sample assessments."""
    store = AssessmentStore(temp_db)

    # Create sample assessments
    assessments = [
        {
            "job_id": "job1",
            "title": "Senior Python Engineer",
            "company": "TechCorp",
            "location": "San Francisco, CA",
            "overall_score": 92,
            "tech_score": 95,
            "seniority_score": 88,
            "location_score": 80,
            "recommendations": json.dumps(["Learn Kubernetes", "Improve Docker"]),
            "summary": "Excellent fit for senior role",
            "tokens_used": 650,
            "actual_cost": 0.002,
            "input_tokens": 600,
            "output_tokens": 50,
            "assessed_date": "2025-01-15 10:00:00",
        },
        {
            "job_id": "job2",
            "title": "ML Engineer",
            "company": "DataInc",
            "location": "New York, NY",
            "overall_score": 78,
            "tech_score": 85,
            "seniority_score": 75,
            "location_score": 60,
            "recommendations": json.dumps(["Study PyTorch"]),
            "summary": "Good fit, some gaps",
            "tokens_used": 670,
            "actual_cost": 0.002,
            "input_tokens": 620,
            "output_tokens": 50,
            "assessed_date": "2025-01-15 11:00:00",
        },
        {
            "job_id": "job3",
            "title": "Frontend Developer",
            "company": "WebDev Inc",
            "location": "Austin, TX",
            "overall_score": 65,
            "tech_score": 70,
            "seniority_score": 60,
            "location_score": 50,
            "recommendations": json.dumps([]),
            "summary": "Moderate fit",
            "tokens_used": 640,
            "actual_cost": 0.002,
            "input_tokens": 590,
            "output_tokens": 50,
            "assessed_date": "2025-01-15 12:00:00",
        },
    ]

    for assessment in assessments:
        store.save_assessment(
            job_id=assessment["job_id"],
            title=assessment["title"],
            company=assessment["company"],
            location=assessment["location"],
            overall_score=assessment["overall_score"],
            tech_score=assessment["tech_score"],
            seniority_score=assessment["seniority_score"],
            location_score=assessment["location_score"],
            recommendations=json.loads(assessment["recommendations"]),
            summary=assessment["summary"],
            tokens_used=assessment["tokens_used"],
            actual_cost=assessment["actual_cost"],
            input_tokens=assessment["input_tokens"],
            output_tokens=assessment["output_tokens"],
        )

    return store


# ============================================================================
# TestExportConfig
# ============================================================================


class TestExportConfig:
    """Test ExportConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ExportConfig()
        assert config.min_score == 0
        assert config.max_score == 100
        assert config.sort_by == "score"
        assert config.template_style == "detailed"
        assert config.include_recommendations is True
        assert config.include_stats is True

    def test_invalid_score_range(self):
        """Test validation of score range."""
        with pytest.raises(ValueError, match="min_score must be <= max_score"):
            ExportConfig(min_score=75, max_score=50)

    def test_invalid_min_score(self):
        """Test validation of min score."""
        with pytest.raises(ValueError, match="min_score must be 0-100"):
            ExportConfig(min_score=-1)
        with pytest.raises(ValueError, match="min_score must be 0-100"):
            ExportConfig(min_score=101)

    def test_invalid_sort_by(self):
        """Test validation of sort_by field."""
        with pytest.raises(ValueError, match="sort_by must be"):
            ExportConfig(sort_by="invalid")

    def test_invalid_template_style(self):
        """Test validation of template_style."""
        with pytest.raises(ValueError, match="template_style must be"):
            ExportConfig(template_style="html")

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = ExportConfig(min_score=75, template_style="summary")
        config_dict = config.to_dict()
        assert config_dict["min_score"] == 75
        assert config_dict["template_style"] == "summary"
        assert config_dict["include_recommendations"] is True


# ============================================================================
# TestMarkdownExporter
# ============================================================================


class TestMarkdownExporter:
    """Test MarkdownExporter class."""

    def test_generate_report(self, store_with_assessments):
        """Test full report generation."""
        config = ExportConfig()
        exporter = MarkdownExporter(store_with_assessments, config)
        report = exporter.generate_report()

        assert "# Job Assessment Report" in report
        assert "Generated:" in report
        assert "Total Assessed:" in report
        assert "## Top 5 Matches" in report
        assert "## Job Details" in report
        assert "## Analytics" in report
        assert "## Search Tips" in report

    def test_filter_min_score(self, store_with_assessments):
        """Test filtering by minimum score."""
        config = ExportConfig(min_score=75)
        exporter = MarkdownExporter(store_with_assessments, config)
        report = exporter.generate_report()

        # Should include job1 (92) and job2 (78), but not job3 (65)
        assert "TechCorp" in report
        assert "DataInc" in report
        assert "WebDev Inc" not in report

    def test_filter_max_score(self, store_with_assessments):
        """Test filtering by maximum score."""
        config = ExportConfig(max_score=80)
        exporter = MarkdownExporter(store_with_assessments, config)
        report = exporter.generate_report()

        # Should include job2 (78) and job3 (65), but not job1 (92)
        assert "TechCorp" not in report
        assert "DataInc" in report
        assert "WebDev Inc" in report

    def test_sort_by_score(self, store_with_assessments):
        """Test sorting by score (descending)."""
        config = ExportConfig(sort_by="score")
        exporter = MarkdownExporter(store_with_assessments, config)
        assessments = exporter._get_filtered_assessments()

        assert assessments[0]["overall_score"] == 92
        assert assessments[1]["overall_score"] == 78
        assert assessments[2]["overall_score"] == 65

    def test_sort_by_company(self, store_with_assessments):
        """Test sorting by company (ascending)."""
        config = ExportConfig(sort_by="company")
        exporter = MarkdownExporter(store_with_assessments, config)
        assessments = exporter._get_filtered_assessments()

        assert assessments[0]["company"] == "DataInc"
        assert assessments[1]["company"] == "TechCorp"
        assert assessments[2]["company"] == "WebDev Inc"

    def test_template_summary(self, store_with_assessments):
        """Test summary template."""
        config = ExportConfig(template_style="summary")
        exporter = MarkdownExporter(store_with_assessments, config)
        report = exporter.generate_summary()

        # Summary should have top 10 matches section
        assert "## Top 10 Matches" in report
        # But not full details for all jobs
        assert report.count("### [") <= 10

    def test_template_detailed(self, store_with_assessments):
        """Test detailed template."""
        config = ExportConfig(template_style="detailed")
        exporter = MarkdownExporter(store_with_assessments, config)
        report = exporter.generate_report()

        # Detailed should have top 5 matches
        assert "## Top 5 Matches" in report
        # And all jobs in details section
        assert "### [1]" in report
        assert "### [2]" in report
        assert "### [3]" in report

    def test_render_job_card(self, store_with_assessments):
        """Test individual job card rendering."""
        assessments = store_with_assessments.get_assessments_by_score()
        job = assessments[0]

        config = ExportConfig()
        exporter = MarkdownExporter(store_with_assessments, config)
        card = exporter._render_job_card(job, 1)

        assert "### [1]" in card
        assert job["company"] in card
        assert job["title"] in card
        assert "Overall Score:" in card

    def test_empty_results(self, store_with_assessments):
        """Test report with no matching jobs."""
        config = ExportConfig(min_score=95)  # No jobs above 95
        exporter = MarkdownExporter(store_with_assessments, config)
        report = exporter.generate_report()

        assert "No jobs found" in report

    def test_markdown_valid(self, store_with_assessments):
        """Test that generated markdown is valid."""
        config = ExportConfig()
        exporter = MarkdownExporter(store_with_assessments, config)
        report = exporter.generate_report()

        # Basic markdown validation
        assert report.startswith("# ")  # Has heading
        assert "##" in report  # Has subheadings
        assert report.count("```") % 2 == 0  # Code blocks are closed
        assert "-" * 3 in report  # Has horizontal rule

    def test_include_recommendations(self, store_with_assessments):
        """Test including/excluding recommendations."""
        config_with = ExportConfig(include_recommendations=True)
        exporter_with = MarkdownExporter(store_with_assessments, config_with)
        report_with = exporter_with.generate_report()

        config_without = ExportConfig(include_recommendations=False)
        exporter_without = MarkdownExporter(store_with_assessments, config_without)
        report_without = exporter_without.generate_report()

        # With recommendations should be longer
        assert len(report_with) > len(report_without)

    def test_include_stats(self, store_with_assessments):
        """Test including/excluding statistics."""
        config_with = ExportConfig(include_stats=True)
        exporter_with = MarkdownExporter(store_with_assessments, config_with)
        report_with = exporter_with.generate_report()

        config_without = ExportConfig(include_stats=False)
        exporter_without = MarkdownExporter(store_with_assessments, config_without)
        report_without = exporter_without.generate_report()

        # With stats should include analytics section
        assert "## Analytics" in report_with
        assert "## Analytics" not in report_without


# ============================================================================
# TestAssessmentStoreSearch
# ============================================================================


class TestAssessmentStoreSearch:
    """Test AssessmentStore search methods."""

    def test_search_by_keyword(self, store_with_assessments):
        """Test keyword search."""
        results = store_with_assessments.search_by_keyword("Python")

        assert len(results) > 0
        assert any("Python" in r.get("title", "") for r in results)

    def test_search_with_score_filter(self, store_with_assessments):
        """Test search with score filtering."""
        results = store_with_assessments.search_by_keyword("Engineer", min_score=75)

        for result in results:
            assert result["overall_score"] >= 75

    def test_search_no_results(self, store_with_assessments):
        """Test search with no results."""
        results = store_with_assessments.search_by_keyword("Nonexistent")

        assert results == []

    def test_get_score_ranges(self, store_with_assessments):
        """Test score range distribution."""
        ranges = store_with_assessments.get_score_ranges()

        assert "0-25" in ranges
        assert "25-50" in ranges
        assert "50-75" in ranges
        assert "75-100" in ranges
        assert ranges["75-100"] == 2  # job1 (92) and job2 (78)
        assert ranges["50-75"] == 1  # job3 (65)

    def test_get_top_keywords(self, store_with_assessments):
        """Test top keywords extraction."""
        keywords = store_with_assessments.get_top_keywords(limit=5)

        # Should return list of tuples
        assert isinstance(keywords, list)

    def test_get_recommendations_summary(self, store_with_assessments):
        """Test recommendations aggregation."""
        summary = store_with_assessments.get_recommendations_summary()

        # Should count recommendations
        assert "Learn Kubernetes" in summary
        assert "Improve Docker" in summary
        assert "Study PyTorch" in summary

    def test_search_performance(self, store_with_assessments):
        """Test search performance with mock data."""
        # Add more assessments for performance testing
        for i in range(10):
            store_with_assessments.save_assessment(
                job_id=f"perf_job_{i}",
                title="Performance Test",
                company="PerfCorp",
                location="Test City",
                overall_score=70 + i,
                tech_score=75 + i,
                seniority_score=65 + i,
                location_score=60 + i,
                recommendations=["Test skill"],
                summary="Test",
                tokens_used=600,
                actual_cost=0.002,
            )

        # Search should complete quickly
        results = store_with_assessments.search_by_keyword("Test", limit=5)

        assert len(results) <= 5


# ============================================================================
# TestAssessmentStoreEnhancements
# ============================================================================


class TestAssessmentStoreEnhancements:
    """Test AssessmentStore enhancements for Phase 5."""

    def test_get_stats_includes_tokens(self, store_with_assessments):
        """Test that stats include token counts."""
        stats = store_with_assessments.get_stats()

        assert "total_input_tokens" in stats
        assert "total_output_tokens" in stats
        assert stats["total_input_tokens"] > 0
        assert stats["total_output_tokens"] > 0

    def test_get_stats_calculation(self, store_with_assessments):
        """Test stats calculations."""
        stats = store_with_assessments.get_stats()

        assert stats["total_assessments"] == 3
        assert stats["total_cost"] > 0
        assert stats["avg_score"] == (92 + 78 + 65) / 3


# ============================================================================
# TestIntegration
# ============================================================================


class TestIntegration:
    """Integration tests for Phase 5."""

    def test_export_and_search_workflow(self, store_with_assessments):
        """Test complete export and search workflow."""
        # Generate report
        config = ExportConfig(min_score=75)
        exporter = MarkdownExporter(store_with_assessments, config)
        report = exporter.generate_report()

        assert len(report) > 0

        # Search
        results = store_with_assessments.search_by_keyword("Engineer", min_score=75)

        assert len(results) > 0

    def test_multiple_filters_and_sorts(self, store_with_assessments):
        """Test combining multiple filters and sorts."""
        config = ExportConfig(
            min_score=60,
            max_score=90,
            sort_by="company",
            template_style="summary",
        )
        exporter = MarkdownExporter(store_with_assessments, config)
        assessments = exporter._get_filtered_assessments()

        # All scores should be in range
        for a in assessments:
            assert 60 <= a["overall_score"] <= 90

        # Should be sorted by company
        if len(assessments) > 1:
            for i in range(len(assessments) - 1):
                assert assessments[i]["company"].lower() <= assessments[i + 1]["company"].lower()
