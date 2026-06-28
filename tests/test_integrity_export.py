"""Tests for data export in various formats."""

import csv
import json
from datetime import datetime
from pathlib import Path

import pytest

from src.integrity import DataExporter, IntegrityIssue, IntegrityReport


@pytest.fixture
def exporter():
    """Create exporter instance."""
    return DataExporter()


@pytest.fixture
def sample_issues():
    """Create sample integrity issues."""
    return [
        IntegrityIssue(
            issue_type="orphaned_assessment",
            severity="error",
            table="job_assessments",
            record_id="job1",
            details="Assessment without matching job",
            suggested_action="Delete orphaned record",
        ),
        IntegrityIssue(
            issue_type="invalid_score",
            severity="error",
            table="job_assessments",
            record_id="job2",
            details="Score of 150 outside [0, 100] range",
            suggested_action="Delete assessment with invalid score",
        ),
        IntegrityIssue(
            issue_type="malformed_json",
            severity="warning",
            table="job_assessments",
            record_id="job3",
            details="Recommendations contain invalid JSON",
            suggested_action="Set recommendations to NULL",
        ),
    ]


@pytest.fixture
def sample_records():
    """Create sample records for export."""
    return [
        {
            "issue_type": "orphaned_assessment",
            "severity": "error",
            "table": "job_assessments",
            "record_id": "job1",
            "details": "Assessment without matching job",
        },
        {
            "issue_type": "invalid_score",
            "severity": "error",
            "table": "job_assessments",
            "record_id": "job2",
            "details": "Score of 150 outside [0, 100] range",
        },
    ]


def test_export_to_csv(exporter, sample_records, tmp_path):
    """Should export records to CSV format."""
    output_file = str(tmp_path / "test.csv")

    count = exporter.export_to_csv(sample_records, output_file)

    assert count == 2
    assert Path(output_file).exists()

    # Verify CSV content
    with open(output_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["issue_type"] == "orphaned_assessment"
        assert rows[0]["record_id"] == "job1"


def test_export_to_csv_empty(exporter, tmp_path):
    """Should handle empty records gracefully."""
    output_file = str(tmp_path / "empty.csv")

    count = exporter.export_to_csv([], output_file)
    assert count == 0


def test_export_to_json(exporter, sample_records, tmp_path):
    """Should export records to JSON format."""
    output_file = str(tmp_path / "test.json")

    count = exporter.export_to_json(sample_records, output_file)

    assert count == 2
    assert Path(output_file).exists()

    # Verify JSON content
    with open(output_file) as f:
        data = json.load(f)
        assert len(data) == 2
        assert data[0]["issue_type"] == "orphaned_assessment"
        assert data[1]["record_id"] == "job2"


def test_export_to_json_empty(exporter, tmp_path):
    """Should handle empty records in JSON."""
    output_file = str(tmp_path / "empty.json")

    count = exporter.export_to_json([], output_file)
    assert count == 0


def test_export_issues_to_markdown(exporter, sample_issues, tmp_path):
    """Should export issues to Markdown format."""
    output_file = str(tmp_path / "issues.md")

    count = exporter.export_issues_to_markdown(sample_issues, output_file)

    assert count == 3
    assert Path(output_file).exists()

    # Verify Markdown content
    with open(output_file) as f:
        content = f.read()
        assert "# Integrity Issues Report" in content
        assert "orphaned_assessment" in content
        assert "invalid_score" in content
        assert "malformed_json" in content
        assert "## Summary" in content
        assert "## Issue Details" in content


def test_export_report_to_markdown(exporter, sample_issues, tmp_path):
    """Should export full report to Markdown."""
    output_file = str(tmp_path / "report.md")

    report = IntegrityReport(
        timestamp=datetime.utcnow(),
        total_checks=9,
        issues_found=sample_issues,
        summary_by_type={"orphaned_assessment": 1, "invalid_score": 1, "malformed_json": 1},
        total_records_affected=3,
        purge_recommendations=["purge_orphaned_assessments", "purge_invalid_scores"],
    )

    count = exporter.export_report_to_markdown(report, output_file)

    assert count == 3
    assert Path(output_file).exists()

    # Verify Markdown content
    with open(output_file) as f:
        content = f.read()
        assert "# Database Integrity Report" in content
        assert "Total Issues Found" in content and "3" in content
        assert "Records Affected" in content and "3" in content
        assert "Errors" in content and "2" in content
        assert "Warnings" in content and "1" in content
        assert "## Recommended Actions" in content
        assert "purge_orphaned_assessments" in content


def test_generate_backup(exporter, sample_issues, tmp_path):
    """Should generate backup files grouped by issue type."""
    output_dir = str(tmp_path / "backup")

    exported = exporter.generate_backup(sample_issues, output_dir)

    assert len(exported) > 0
    assert "orphaned_assessment" in exported
    assert "invalid_score" in exported
    assert "malformed_json" in exported

    # Verify files exist
    for issue_type, filepath in exported.items():
        assert Path(filepath).exists()

        # Verify CSV format
        with open(filepath) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) > 0
            assert rows[0]["issue_type"] == issue_type


def test_export_report_empty_issues(exporter, tmp_path):
    """Should handle report with no issues."""
    output_file = str(tmp_path / "empty_report.md")

    report = IntegrityReport(
        timestamp=datetime.utcnow(),
        total_checks=9,
        issues_found=[],
        summary_by_type={},
        total_records_affected=0,
        purge_recommendations=[],
    )

    count = exporter.export_report_to_markdown(report, output_file)

    assert count == 0
    assert Path(output_file).exists()

    # Verify content
    with open(output_file) as f:
        content = f.read()
        assert "# Database Integrity Report" in content
        assert "Total Issues Found" in content and "0" in content


def test_csv_has_correct_headers(exporter, sample_records, tmp_path):
    """CSV should have proper headers from record keys."""
    output_file = str(tmp_path / "headers.csv")

    exporter.export_to_csv(sample_records, output_file)

    with open(output_file) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        assert "issue_type" in headers
        assert "severity" in headers
        assert "table" in headers
        assert "record_id" in headers
        assert "details" in headers


def test_json_with_special_characters(exporter, tmp_path):
    """JSON export should handle special characters."""
    records = [
        {
            "issue_type": "test",
            "details": 'Contains "quotes" and \'single quotes\' and special chars: é, ñ',
            "record_id": "job_special_chars_@#$",
        }
    ]
    output_file = str(tmp_path / "special.json")

    count = exporter.export_to_json(records, output_file)
    assert count == 1

    # Should parse correctly
    with open(output_file) as f:
        data = json.load(f)
        assert len(data) == 1
        assert "quotes" in data[0]["details"]
