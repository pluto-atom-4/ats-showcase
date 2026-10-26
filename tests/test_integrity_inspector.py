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
            crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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
    assert report.total_checks == 12
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


def test_check_fts_data_consistency_clean(checker):
    """FTS with matching job_ids should have no issues."""
    inspector, store, db_path = checker

    # Create job and assessment
    conn = inspector.conn
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job1", "Title", "Company", "Location", "Desc", "pending_review"),
    )
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, title, company, summary, overall_score, tech_score, "
            "seniority_score, location_score, recommendations, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "job1",
            "Title",
            "Company",
            "Summary",
            75,
            80,
            70,
            60,
            "[]",
            100,
            0.01,
        ),
    )
    conn.commit()

    # Populate FTS with valid data
    conn.execute(
        (
            "INSERT INTO job_assessments_fts "
            "(rowid, job_id, title, company, summary, recommendations) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        ),
        (1, "job1", "Title", "Company", "Summary", "[]"),
    )
    conn.commit()

    issues = inspector.check_fts_data_consistency()
    assert len(issues) == 0


def test_check_fts_data_consistency_null_job_ids(checker):
    """FTS with NULL job_ids should be detected."""
    inspector, store, db_path = checker

    # Create job and assessment
    conn = inspector.conn
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job1", "Title", "Company", "Location", "Desc", "pending_review"),
    )
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, title, company, summary, overall_score, tech_score, "
            "seniority_score, location_score, recommendations, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "job1",
            "Title",
            "Company",
            "Summary",
            75,
            80,
            70,
            60,
            "[]",
            100,
            0.01,
        ),
    )
    conn.commit()

    # Create FTS entry with NULL job_id (simulating out-of-sync)
    conn.execute(
        (
            "INSERT INTO job_assessments_fts "
            "(rowid, job_id, title, company, summary, recommendations) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        ),
        (1, None, "Title", "Company", "Summary", "[]"),
    )
    conn.commit()

    issues = inspector.check_fts_data_consistency()
    assert len(issues) == 1
    assert issues[0].issue_type == "fts_data_mismatch"
    assert "NULL job_id" in issues[0].details


def test_check_job_reviews_anomalies_null_job_id(checker):
    """job_reviews with NULL job_ids should be detected."""
    inspector, store, db_path = checker

    conn = inspector.conn

    # Create orphaned job_reviews with NULL job_id
    conn.execute(
        (
            "INSERT INTO job_reviews "
            "(job_id, title, location, status, reason, tokens, estimated_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        ),
        (None, "Deep Learning Engineer", "Remote", "confirmed", None, 100, 0.01),
    )
    conn.commit()

    issues = inspector.check_job_reviews_anomalies()
    assert len(issues) == 1
    assert issues[0].issue_type == "orphaned_job_review"
    assert "NULL job_id" in issues[0].details


def test_check_job_reviews_anomalies_orphaned_id(checker):
    """job_reviews with non-existent job_id should be detected."""
    inspector, store, db_path = checker

    conn = inspector.conn

    # Create assessment
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, title, company, summary, overall_score, tech_score, "
            "seniority_score, location_score, recommendations, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "real_job",
            "Engineer",
            "Company",
            "Summary",
            75,
            80,
            70,
            60,
            "[]",
            100,
            0.01,
        ),
    )

    # Create review with non-existent job_id
    conn.execute(
        (
            "INSERT INTO job_reviews "
            "(job_id, title, location, status, reason, tokens, estimated_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        ),
        ("nonexistent_job", "Title", "Remote", "confirmed", None, 100, 0.01),
    )
    conn.commit()

    issues = inspector.check_job_reviews_anomalies()
    assert len(issues) == 1
    assert issues[0].issue_type == "orphaned_job_review"
    assert "not in job_assessments" in issues[0].details


# ============================================================================
# Duplicate inspection (issue #786): read-only scans
# ============================================================================


def _write_json(path, payload):
    """Write JSON payload (or raw string) to path, creating parent dirs."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


def _fresh_checker(tmp_path):
    """Return IntegrityChecker on a fresh tmp DB (schema created by AssessmentStore)."""
    return IntegrityChecker(str(tmp_path / "inspect.db"))


def _insert_assessment(conn, job_id):
    """Insert minimal job_assessments row (no PK-dependent logic)."""
    conn.execute(
        "INSERT INTO job_assessments (job_id, overall_score, tech_score, seniority_score,"
        " location_score, recommendations, summary) VALUES (?, 50, 50, 50, 50, '[]', 's')",
        (job_id,),
    )


def test_scan_json_same_id_different_url_flagged(tmp_path):
    """Same id with >1 distinct url -> exactly one duplicate_id_json warning."""
    json_dir = tmp_path / "work"
    _write_json(
        json_dir / "acme_jobs.json",
        [
            {"id": "abc123", "url": "https://x.example/jobs/1"},
            {"id": "abc123", "url": "https://x.example/jobs/2"},
            {"id": "other", "url": "https://x.example/jobs/3"},
        ],
    )
    checker = _fresh_checker(tmp_path)

    issues = checker.scan_json_duplicate_ids(json_dir=str(json_dir))

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_type == "duplicate_id_json"
    assert issue.severity == "warning"
    assert issue.table == "acme_jobs.json"
    assert issue.record_id == "abc123"
    assert "2 rows share id 'abc123' across 2 distinct URLs" in issue.details
    assert "Manual review" in issue.suggested_action


def test_scan_json_same_id_same_url_not_flagged(tmp_path):
    """Exact re-export duplicates (same id AND url) are out of scope -> no issue."""
    json_dir = tmp_path / "work"
    _write_json(
        json_dir / "dupes_jobs.json",
        {
            "jobs": [
                {"id": "same", "url": "https://x.example/jobs/9"},
                {"id": "same", "url": "https://x.example/jobs/9"},
            ]
        },
    )
    checker = _fresh_checker(tmp_path)

    assert checker.scan_json_duplicate_ids(json_dir=str(json_dir)) == []


def test_scan_json_malformed_and_non_job_files_skipped(tmp_path):
    """Malformed JSON and non-job shapes are skipped; scan still finds valid dupes."""
    json_dir = tmp_path / "work"
    _write_json(json_dir / "broken.json", "{not valid json")
    _write_json(json_dir / "scalar.json", 42)
    _write_json(json_dir / "unrelated.json", {"settings": {"depth": 3}})
    _write_json(json_dir / "no_ids.json", [{"job_id": "x", "score": 1}, "string-row"])
    _write_json(
        json_dir / "good_jobs.json",
        [
            {"id": "d1", "url": "https://x.example/a"},
            {"id": "d1", "url": "https://x.example/b"},
        ],
    )
    checker = _fresh_checker(tmp_path)

    issues = checker.scan_json_duplicate_ids(json_dir=str(json_dir))

    assert len(issues) == 1
    assert issues[0].table == "good_jobs.json"
    assert issues[0].record_id == "d1"


def test_scan_db_duplicate_custom_job_id_flagged(tmp_path):
    """Duplicate custom:% job_id -> duplicate_id_db warning; singles -> custom_portal_row info.

    job_id is PRIMARY KEY in the real schema, so duplicates cannot be seeded there.
    This test recreates job_assessments and job_reviews WITHOUT the PK constraint
    (same columns, empty copy) to simulate legacy rows that predate the PK.
    """
    checker = _fresh_checker(tmp_path)
    conn = checker.conn
    for table in ("job_assessments", "job_reviews"):
        conn.execute(f"CREATE TABLE {table}_nopk AS SELECT * FROM {table} WHERE 0")
        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"ALTER TABLE {table}_nopk RENAME TO {table}")
    _insert_assessment(conn, "custom:dup")
    _insert_assessment(conn, "custom:dup")
    _insert_assessment(conn, "custom:solo")
    conn.commit()

    issues = checker.scan_db_custom_portal_rows()

    dup = [i for i in issues if i.issue_type == "duplicate_id_db"]
    solo = [i for i in issues if i.issue_type == "custom_portal_row"]
    assert len(dup) == 1
    assert dup[0].severity == "warning"
    assert dup[0].record_id == "custom:dup"
    assert len(solo) == 1
    assert solo[0].severity == "info"
    assert solo[0].record_id == "custom:solo"


def test_scan_db_empty_or_missing_tables_returns_empty(tmp_path):
    """Empty DB and missing tables must not raise; both scans return []."""
    checker = _fresh_checker(tmp_path)
    assert checker.scan_db_custom_portal_rows() == []

    checker.conn.execute("DROP TABLE job_assessments")
    checker.conn.execute("DROP TABLE job_reviews")
    checker.conn.commit()
    assert checker.scan_db_custom_portal_rows() == []

    empty_dir = tmp_path / "no_json"
    empty_dir.mkdir()
    assert checker.scan_json_duplicate_ids(json_dir=str(empty_dir)) == []


def test_run_duplicate_inspection_composes_both_scans(tmp_path):
    """run_duplicate_inspection returns report with total_checks=2 and both scans' issues."""
    json_dir = tmp_path / "work"
    _write_json(
        json_dir / "x_jobs.json",
        [
            {"id": "k", "url": "https://x.example/1"},
            {"id": "k", "url": "https://x.example/2"},
        ],
    )
    checker = _fresh_checker(tmp_path)
    _insert_assessment(checker.conn, "custom:one")
    checker.conn.commit()

    report = checker.run_duplicate_inspection(json_dir=str(json_dir))

    assert isinstance(report, IntegrityReport)
    assert report.total_checks == 2
    types = {i.issue_type for i in report.issues_found}
    assert types == {"duplicate_id_json", "custom_portal_row"}
    assert report.summary_by_type["duplicate_id_json"] == 1
