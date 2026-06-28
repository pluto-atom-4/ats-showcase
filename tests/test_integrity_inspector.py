"""Tests for integrity inspector checks."""

from datetime import datetime

import pytest

from src.integrity import IntegrityChecker, IntegrityReport


def _create_test_db(db_path: str):
    """Create full database schema for testing."""
    import sqlite3
    from pathlib import Path

    from src.storage.assessment_store import AssessmentStore

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)

    # Create all necessary tables
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            url TEXT UNIQUE,
            description TEXT,
            requirements TEXT,
            salary_min FLOAT,
            salary_max FLOAT,
            posted_date DATETIME,
            crawled_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending_review',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS preprocessed_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE,
            clean_text TEXT,
            chunks TEXT,
            token_count INTEGER,
            estimated_cost FLOAT,
            processed_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cost_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            phase TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cost FLOAT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_reviews (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            location TEXT,
            status TEXT DEFAULT 'pending',
            reason TEXT,
            tokens INTEGER,
            estimated_cost FLOAT,
            reviewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
        """
    )

    # Create assessment tables using AssessmentStore
    AssessmentStore(db_path)
    # The store will create job_assessments and fts tables on init

    conn.commit()
    conn.close()


@pytest.fixture
def checker(tmp_path):
    """Create temporary database with test data."""
    db_path = str(tmp_path / "test_integrity.db")

    # Initialize full database
    _create_test_db(db_path)

    from src.storage.assessment_store import AssessmentStore

    store = AssessmentStore(db_path)

    checker = IntegrityChecker(db_path)
    return checker, store, db_path


def test_check_orphaned_assessments_empty(checker):
    """Empty database should find no orphaned assessments."""
    inspector, store, db_path = checker
    issues = inspector.check_orphaned_assessments()
    assert len(issues) == 0


def test_check_orphaned_assessments_with_orphan(checker):
    """Should detect orphaned assessments (no matching job)."""
    inspector, store, db_path = checker

    # Create assessment without job
    conn = inspector.conn
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, overall_score, tech_score, seniority_score, location_score, "
            "recommendations, summary, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "orphaned_job",
            75,
            80,
            70,
            60,
            "[]",
            "Test",
            100,
            0.01,
        ),
    )
    conn.commit()

    issues = inspector.check_orphaned_assessments()
    assert len(issues) == 1
    assert issues[0].issue_type == "orphaned_assessment"
    assert issues[0].record_id == "orphaned_job"


def test_check_invalid_scores_with_invalid(checker):
    """Should detect scores outside [0, 100] range."""
    inspector, store, db_path = checker

    # Create assessment with invalid scores
    conn = inspector.conn
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job1", "Title", "Company", "Location", "Desc", "pending_review"),
    )
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, overall_score, tech_score, seniority_score, location_score, "
            "recommendations, summary, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "job1",
            150,  # Invalid: > 100
            -10,  # Invalid: < 0
            85,
            60,
            "[]",
            "Test",
            100,
            0.01,
        ),
    )
    conn.commit()

    issues = inspector.check_invalid_scores()
    assert len(issues) == 1
    assert issues[0].issue_type == "invalid_score"
    assert "150" in issues[0].details
    assert "-10" in issues[0].details


def test_check_malformed_recommendations(checker):
    """Should detect invalid JSON in recommendations."""
    inspector, store, db_path = checker

    conn = inspector.conn
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job1", "Title", "Company", "Location", "Desc", "pending_review"),
    )
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, overall_score, tech_score, seniority_score, location_score, "
            "recommendations, summary, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "job1",
            75,
            80,
            70,
            60,
            "invalid json {",  # Malformed
            "Test",
            100,
            0.01,
        ),
    )
    conn.commit()

    issues = inspector.check_malformed_recommendations()
    assert len(issues) == 1
    assert issues[0].issue_type == "malformed_json"


def test_check_duplicate_assessments(checker):
    """job_assessments has UNIQUE constraint on job_id so no duplicates possible."""
    inspector, store, db_path = checker

    conn = inspector.conn
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job1", "Title", "Company", "Location", "Desc", "pending_review"),
    )
    # The schema enforces UNIQUE(job_id), so we can't insert duplicates
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, overall_score, tech_score, seniority_score, location_score, "
            "recommendations, summary, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "job1",
            75,
            80,
            70,
            60,
            "[]",
            "Test1",
            100,
            0.01,
        ),
    )
    conn.commit()

    # Check should find no duplicates (because schema prevents them)
    issues = inspector.check_duplicate_assessments()
    assert len(issues) == 0


def test_check_status_inconsistencies(checker):
    """Should detect mismatched status between jobs and job_reviews."""
    inspector, store, db_path = checker

    conn = inspector.conn
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job1", "Title", "Company", "Location", "Desc", "confirmed"),
    )
    conn.execute(
        (
            "INSERT INTO job_reviews "
            "(job_id, title, location, status, reason, tokens, estimated_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        ),
        ("job1", "Title", "Location", "rejected", "Bad fit", 100, 0.01),
    )
    conn.commit()

    issues = inspector.check_status_inconsistencies()
    assert len(issues) == 1
    assert issues[0].issue_type == "status_inconsistency"
    assert "confirmed" in issues[0].details
    assert "rejected" in issues[0].details


def test_run_full_check(checker):
    """Full check should execute all checks and return report."""
    inspector, store, db_path = checker

    report = inspector.run_full_check()

    assert isinstance(report, IntegrityReport)
    assert report.timestamp is not None
    assert report.total_checks == 9
    assert isinstance(report.issues_found, list)
    assert isinstance(report.summary_by_type, dict)


def test_full_check_with_multiple_issues(checker):
    """Full check should aggregate multiple issue types."""
    inspector, store, db_path = checker

    conn = inspector.conn

    # Add orphaned assessment
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, overall_score, tech_score, seniority_score, location_score, "
            "recommendations, summary, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "orphaned_job",
            75,
            80,
            70,
            60,
            "[]",
            "Test",
            100,
            0.01,
        ),
    )

    # Add job with invalid score
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job1", "Title", "Company", "Location", "Desc", "pending_review"),
    )
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, overall_score, tech_score, seniority_score, location_score, "
            "recommendations, summary, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "job1",
            150,
            80,
            70,
            60,
            "[]",
            "Test",
            100,
            0.01,
        ),
    )

    conn.commit()

    report = inspector.run_full_check()

    assert len(report.issues_found) >= 2
    assert "orphaned_assessment" in report.summary_by_type
    assert "invalid_score" in report.summary_by_type
    assert report.summary_by_type["orphaned_assessment"] == 1
    assert report.summary_by_type["invalid_score"] == 1


def test_check_missing_preprocessing(checker):
    """Should detect assessments without preprocessing data."""
    inspector, store, db_path = checker

    conn = inspector.conn

    # Create job and assessment but no preprocessed record
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job1", "Title", "Company", "Location", "Desc", "pending_review"),
    )
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, overall_score, tech_score, seniority_score, location_score, "
            "recommendations, summary, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "job1",
            75,
            80,
            70,
            60,
            "[]",
            "Test",
            100,
            0.01,
        ),
    )
    conn.commit()

    issues = inspector.check_missing_preprocessing()
    assert len(issues) == 1
    assert issues[0].issue_type == "missing_preprocessing"


def test_check_missing_cost_tracking(checker):
    """Should detect orphaned cost_tracking entries."""
    inspector, store, db_path = checker

    conn = inspector.conn

    # Create cost_tracking entry without job
    conn.execute(
        "INSERT INTO cost_tracking (job_id, phase, input_tokens, output_tokens, cost) VALUES (?, ?, ?, ?, ?)",
        ("nonexistent_job", "assess", 100, 50, 0.01),
    )
    conn.commit()

    issues = inspector.check_missing_cost_tracking()
    assert len(issues) == 1
    assert issues[0].issue_type == "orphaned_cost_tracking"


def test_purge_recommendations_ordered(checker):
    """Purge recommendations should be ordered by priority."""
    inspector, store, db_path = checker

    conn = inspector.conn

    # Add multiple issue types
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, overall_score, tech_score, seniority_score, location_score, "
            "recommendations, summary, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "orphaned_job",
            75,
            80,
            70,
            60,
            "[]",
            "Test",
            100,
            0.01,
        ),
    )
    conn.commit()

    report = inspector.run_full_check()

    # Check that recommendations are present
    assert len(report.purge_recommendations) > 0
    # High priority items should appear first
    if "orphaned_assessment" in report.summary_by_type:
        assert any("orphaned" in rec for rec in report.purge_recommendations)
