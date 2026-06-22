"""End-to-end tests for date filtering workflows."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from storage.assessment_store import AssessmentStore
from storage.export import ExportConfig, MarkdownExporter, parse_date_str


@pytest.fixture
def temp_db_with_dated_assessments():
    """Create temp DB with assessments across date range."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = AssessmentStore(db_path)

    # Create assessments with specific dates via direct SQL
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    assessments = [
        {
            "job_id": "job_2025_01",
            "title": "Python Engineer",
            "company": "CompanyA",
            "location": "SF",
            "overall_score": 95,
            "tech_score": 98,
            "seniority_score": 92,
            "location_score": 85,
            "summary": "Excellent match",
            "recommendations": json.dumps(["Learn Rust"]),
            "tokens_used": 500,
            "input_tokens": 450,
            "output_tokens": 50,
            "actual_cost": 0.001,
            "assessed_date": "2025-01-15 10:00:00",
        },
        {
            "job_id": "job_2025_06",
            "title": "ML Engineer",
            "company": "CompanyB",
            "location": "NYC",
            "overall_score": 85,
            "tech_score": 90,
            "seniority_score": 80,
            "location_score": 75,
            "summary": "Good fit",
            "recommendations": json.dumps(["Study PyTorch"]),
            "tokens_used": 520,
            "input_tokens": 470,
            "output_tokens": 50,
            "actual_cost": 0.001,
            "assessed_date": "2025-06-20 14:30:00",
        },
        {
            "job_id": "job_2025_12",
            "title": "Data Scientist",
            "company": "CompanyC",
            "location": "Boston",
            "overall_score": 78,
            "tech_score": 82,
            "seniority_score": 75,
            "location_score": 60,
            "summary": "Moderate fit",
            "recommendations": json.dumps([]),
            "tokens_used": 510,
            "input_tokens": 460,
            "output_tokens": 50,
            "actual_cost": 0.001,
            "assessed_date": "2025-12-10 09:15:00",
        },
    ]

    for a in assessments:
        cursor.execute(
            """INSERT INTO job_assessments
               (job_id, title, company, location, overall_score, tech_score,
                seniority_score, location_score, recommendations, summary,
                tokens_used, input_tokens, output_tokens, actual_cost, assessed_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                a["job_id"],
                a["title"],
                a["company"],
                a["location"],
                a["overall_score"],
                a["tech_score"],
                a["seniority_score"],
                a["location_score"],
                a["recommendations"],
                a["summary"],
                a["tokens_used"],
                a["input_tokens"],
                a["output_tokens"],
                a["actual_cost"],
                a["assessed_date"],
            ),
        )

        # Also insert into FTS
        cursor.execute(
            """INSERT INTO job_assessments_fts
               (job_id, title, company, summary, recommendations)
               VALUES (?, ?, ?, ?, ?)""",
            (
                a["job_id"],
                a["title"],
                a["company"],
                a["summary"],
                a["recommendations"],
            ),
        )

    conn.commit()
    conn.close()

    yield store, db_path

    Path(db_path).unlink(missing_ok=True)


class TestExportDateFilteringWorkflow:
    """Test export with date filtering workflows."""

    def test_export_no_filters_all_assessments(self, temp_db_with_dated_assessments):
        """Export without filters returns all assessments."""
        store, _ = temp_db_with_dated_assessments

        config = ExportConfig()
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        assert "3" in report  # 3 assessments
        assert "Python Engineer" in report
        assert "ML Engineer" in report
        assert "Data Scientist" in report

    def test_export_by_date_from(self, temp_db_with_dated_assessments):
        """Export with from-date filters correctly."""
        store, _ = temp_db_with_dated_assessments

        date_from = parse_date_str("2025-06-01")
        config = ExportConfig(date_from=date_from)
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        # Should include June and December assessments
        assert "ML Engineer" in report
        assert "Data Scientist" in report
        assert "Python Engineer" not in report  # January is before June

    def test_export_by_date_to(self, temp_db_with_dated_assessments):
        """Export with to-date filters correctly."""
        store, _ = temp_db_with_dated_assessments

        date_to = parse_date_str("2025-06-30")
        config = ExportConfig(date_to=date_to)
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        # Should include January and June assessments
        assert "Python Engineer" in report
        assert "ML Engineer" in report
        assert "Data Scientist" not in report  # December is after June

    def test_export_date_range(self, temp_db_with_dated_assessments):
        """Export with date range filters exactly."""
        store, _ = temp_db_with_dated_assessments

        date_from = parse_date_str("2025-06-01")
        date_to = parse_date_str("2025-12-31")
        config = ExportConfig(date_from=date_from, date_to=date_to)
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        # Should include June and December
        assert "ML Engineer" in report
        assert "Data Scientist" in report
        assert "Python Engineer" not in report

    def test_export_single_day(self, temp_db_with_dated_assessments):
        """Export with single day filter."""
        store, _ = temp_db_with_dated_assessments

        # Note: assessments are on dates like 2025-06-20, not 2026-06-20
        date_from = parse_date_str("2025-06-19")
        date_to = parse_date_str("2025-06-21")
        config = ExportConfig(date_from=date_from, date_to=date_to)
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        # Should include only June assessment
        assert "ML Engineer" in report
        assert "Python Engineer" not in report
        assert "Data Scientist" not in report

    def test_export_date_and_score_filters(self, temp_db_with_dated_assessments):
        """Export with both date and score filters."""
        store, _ = temp_db_with_dated_assessments

        date_from = parse_date_str("2025-06-01")
        config = ExportConfig(date_from=date_from, min_score=80)
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        # Should include ML Engineer (85) but not Data Scientist (78)
        assert "ML Engineer" in report
        assert "Data Scientist" not in report

    def test_export_header_shows_filters(self, temp_db_with_dated_assessments):
        """Export report header displays applied filters."""
        store, _ = temp_db_with_dated_assessments

        date_from = parse_date_str("2025-06-01")
        date_to = parse_date_str("2025-12-31")
        config = ExportConfig(
            date_from=date_from, date_to=date_to, min_score=75, max_score=95
        )
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        assert "Score: 75-95" in report
        assert "Date: 2025-06-01 to 2025-12-31" in report

    def test_export_no_matches_with_filter(self, temp_db_with_dated_assessments):
        """Export with filter matching no assessments."""
        store, _ = temp_db_with_dated_assessments

        # Filter for future date
        date_from = parse_date_str("2030-01-01")
        config = ExportConfig(date_from=date_from)
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        assert "No jobs found" in report
        assert "Python Engineer" not in report


class TestPurgeDateFilteringWorkflow:
    """Test purge with date filtering workflows."""

    def test_purge_dry_run_shows_count(self, temp_db_with_dated_assessments):
        """Dry-run purge shows count without deleting."""
        store, _ = temp_db_with_dated_assessments

        assert store.count_assessments() == 3

        result = store.purge_by_date(before_date="2025-07-01", dry_run=True)

        assert result["count"] == 2  # Jan and June
        assert result["dry_run"] is True
        assert store.count_assessments() == 3  # Nothing deleted

    def test_purge_before_date_deletes(self, temp_db_with_dated_assessments):
        """Purge before-date actually deletes."""
        store, _ = temp_db_with_dated_assessments

        assert store.count_assessments() == 3

        result = store.purge_by_date(before_date="2025-07-01", dry_run=False)

        assert result["count"] == 2
        assert result["dry_run"] is False
        assert store.count_assessments() == 1

    def test_purge_after_date_deletes(self, temp_db_with_dated_assessments):
        """Purge after-date actually deletes."""
        store, _ = temp_db_with_dated_assessments

        result = store.purge_by_date(after_date="2025-06-01", dry_run=False)

        # Should delete June and December (after June 1)
        assert result["count"] == 2
        assert store.count_assessments() == 1

    def test_purge_between_dates(self, temp_db_with_dated_assessments):
        """Purge with both before and after dates."""
        store, _ = temp_db_with_dated_assessments

        result = store.purge_by_date(
            after_date="2025-01-31", before_date="2025-12-01", dry_run=False
        )

        # Should delete June (between Jan 31 and Dec 1)
        assert result["count"] == 1
        assert store.count_assessments() == 2

    def test_purge_preserves_unmatched(self, temp_db_with_dated_assessments):
        """Purge only removes matched assessments."""
        store, _ = temp_db_with_dated_assessments

        store.purge_by_date(before_date="2025-06-01", dry_run=False)

        # Only January should be deleted, June and December remain
        remaining = store.get_top_matches(limit=10)
        assert len(remaining) == 2

        job_ids = [j["job_id"] for j in remaining]
        assert "job_2025_01" not in job_ids
        assert "job_2025_06" in job_ids
        assert "job_2025_12" in job_ids


class TestCombinedWorkflows:
    """Test combined export and purge workflows."""

    def test_export_then_purge(self, temp_db_with_dated_assessments):
        """Export filtered results, then purge old records."""
        store, _ = temp_db_with_dated_assessments

        # Export recent assessments
        date_from = parse_date_str("2025-06-01")
        config = ExportConfig(date_from=date_from)
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        assert "ML Engineer" in report
        assert "Data Scientist" in report

        # Purge old assessments
        purge_result = store.purge_by_date(before_date="2025-06-01", dry_run=False)
        assert purge_result["count"] == 1

        # Export after purge
        config2 = ExportConfig()
        exporter2 = MarkdownExporter(store, config2)
        report2 = exporter2.generate_report()

        # Only June and December remain
        assert "ML Engineer" in report2
        assert "Data Scientist" in report2
        assert "Python Engineer" not in report2

    def test_purge_dry_run_preview(self, temp_db_with_dated_assessments):
        """Dry-run purge lets user preview before deletion."""
        store, _ = temp_db_with_dated_assessments

        # Check what would be deleted
        result = store.purge_by_date(before_date="2025-07-01", dry_run=True)
        preview_count = result["count"]

        # Delete for real
        result2 = store.purge_by_date(before_date="2025-07-01", dry_run=False)

        # Counts should match
        assert result2["count"] == preview_count
        assert store.count_assessments() == 3 - preview_count

    def test_safety_confirm_flag_pattern(self, temp_db_with_dated_assessments):
        """Verify dry-run default prevents accidental deletion."""
        store, _ = temp_db_with_dated_assessments

        # Without dry_run=False, should not delete
        result = store.purge_by_date(before_date="2025-12-31")

        # Default is dry_run=True
        assert result["dry_run"] is True
        assert store.count_assessments() == 3  # Nothing deleted


class TestEdgeCasesAndErrors:
    """Test edge cases and error handling."""

    def test_export_empty_database(self):
        """Export from empty database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        store = AssessmentStore(db_path)

        config = ExportConfig()
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        assert "No jobs found" in report

        Path(db_path).unlink(missing_ok=True)

    def test_purge_empty_database(self):
        """Purge from empty database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        store = AssessmentStore(db_path)

        result = store.purge_by_date(before_date="2099-12-31", dry_run=False)

        assert result["count"] == 0

        Path(db_path).unlink(missing_ok=True)

    def test_invalid_date_parse_error(self):
        """Invalid date raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date_str("invalid-date")

    def test_invalid_date_range_raises_error(self):
        """Invalid date range raises ValueError."""
        from storage.export import ExportConfig

        date_from = parse_date_str("2025-12-31")
        date_to = parse_date_str("2025-01-01")

        with pytest.raises(ValueError, match="date_from must be <= date_to"):
            ExportConfig(date_from=date_from, date_to=date_to)

    def test_export_with_missing_assessment_data(self, temp_db_with_dated_assessments):
        """Export handles assessments with partial data."""
        store, _ = temp_db_with_dated_assessments

        config = ExportConfig()
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        # Should still generate valid report
        assert "Job Details" in report
        assert len(report) > 100


class TestPerformanceAndScale:
    """Test performance with larger datasets."""

    def test_export_with_many_assessments(self):
        """Export with 100+ assessments."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        store = AssessmentStore(db_path)
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create 100 assessments
        for i in range(100):
            cursor.execute(
                """INSERT INTO job_assessments
                   (job_id, title, company, location, overall_score, tech_score,
                    seniority_score, location_score, recommendations, summary,
                    tokens_used, input_tokens, output_tokens, actual_cost, assessed_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"job_{i}",
                    f"Job {i}",
                    f"Company {i % 10}",
                    f"City {i % 5}",
                    50 + i % 50,
                    50 + i % 50,
                    50 + i % 50,
                    50 + i % 50,
                    json.dumps([]),
                    f"Summary {i}",
                    500 + i,
                    450 + i,
                    50,
                    0.001,
                    f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d} 10:00:00",
                ),
            )

        conn.commit()
        conn.close()

        # Export with filter should be fast
        date_from = parse_date_str("2025-06-01")
        config = ExportConfig(date_from=date_from, min_score=75)
        exporter = MarkdownExporter(store, config)
        report = exporter.generate_report()

        # Should have generated report
        assert len(report) > 100

        Path(db_path).unlink(missing_ok=True)

    def test_purge_with_many_assessments(self):
        """Purge with 100+ assessments."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        store = AssessmentStore(db_path)
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create 100 assessments
        for i in range(100):
            cursor.execute(
                """INSERT INTO job_assessments
                   (job_id, title, company, location, overall_score, tech_score,
                    seniority_score, location_score, recommendations, summary,
                    tokens_used, input_tokens, output_tokens, actual_cost, assessed_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"job_{i}",
                    f"Job {i}",
                    f"Company {i % 10}",
                    f"City {i % 5}",
                    50 + i % 50,
                    50 + i % 50,
                    50 + i % 50,
                    50 + i % 50,
                    json.dumps([]),
                    f"Summary {i}",
                    500 + i,
                    450 + i,
                    50,
                    0.001,
                    f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d} 10:00:00",
                ),
            )

        conn.commit()
        conn.close()

        # Purge should handle large dataset
        result = store.purge_by_date(before_date="2025-06-01", dry_run=False)

        assert result["count"] > 0
        assert store.count_assessments() == 100 - result["count"]

        Path(db_path).unlink(missing_ok=True)
