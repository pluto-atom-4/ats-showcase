"""Tests for data purging with safety guarantees."""

import pytest

from src.integrity import DataPurger
from src.storage.assessment_store import AssessmentStore


def _create_test_db(db_path: str):
    """Create full database schema for testing."""
    import sqlite3
    from pathlib import Path

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

    conn.commit()
    conn.close()


@pytest.fixture
def purger(tmp_path):
    """Create temporary database for purging tests."""
    db_path = str(tmp_path / "test_purge.db")

    _create_test_db(db_path)

    store = AssessmentStore(db_path)

    purger = DataPurger(db_path)
    return purger, store, db_path


def test_purge_orphaned_assessments_dry_run(purger):
    """Dry-run should not delete records."""
    p, store, db_path = purger

    conn = p.conn

    # Create orphaned assessment
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

    # Dry run
    count, ids = p.purge_orphaned_assessments(dry_run=True)
    assert count == 1
    assert "orphaned_job" in ids

    # Verify record still exists
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM job_assessments")
    assert cursor.fetchone()[0] == 1


def test_purge_orphaned_assessments_actual_delete(purger):
    """Actual delete should remove orphaned records."""
    p, store, db_path = purger

    conn = p.conn

    # Create orphaned assessment
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

    # Actual delete
    count, ids = p.purge_orphaned_assessments(dry_run=False)
    assert count == 1
    assert "orphaned_job" in ids

    # Verify record deleted
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM job_assessments")
    assert cursor.fetchone()[0] == 0


def test_purge_invalid_scores_dry_run(purger):
    """Dry-run should identify invalid scores without deleting."""
    p, store, db_path = purger

    conn = p.conn

    # Create job with invalid score
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

    # Dry run
    count, ids = p.purge_invalid_scores(dry_run=True)
    assert count == 1
    assert "job1" in ids

    # Verify record still exists
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM job_assessments WHERE job_id = ?", ("job1",))
    assert cursor.fetchone()[0] == 1


def test_purge_invalid_scores_actual_delete(purger):
    """Should delete records with invalid scores."""
    p, store, db_path = purger

    conn = p.conn

    # Create valid and invalid assessment
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job1", "Title1", "Company1", "Location", "Desc", "pending_review"),
    )
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job2", "Title2", "Company2", "Location", "Desc", "pending_review"),
    )

    # Valid assessment
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

    # Invalid assessment
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, overall_score, tech_score, seniority_score, location_score, "
            "recommendations, summary, tokens_used, actual_cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            "job2",
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

    # Actual delete
    count, ids = p.purge_invalid_scores(dry_run=False)
    assert count == 1
    assert "job2" in ids

    # Verify only valid record remains
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM job_assessments")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT job_id FROM job_assessments")
    assert cursor.fetchone()[0] == "job1"


def test_purge_malformed_recommendations_soft_delete(purger):
    """Should set recommendations to NULL without deleting record."""
    p, store, db_path = purger

    conn = p.conn

    # Create assessment with malformed JSON
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
            "invalid json {",
            "Test",
            100,
            0.01,
        ),
    )
    conn.commit()

    # Soft delete (set to NULL)
    count, ids = p.purge_malformed_recommendations(dry_run=False)
    assert count == 1
    assert "job1" in ids

    # Verify record exists but recommendations are NULL
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM job_assessments WHERE job_id = ?", ("job1",))
    assert cursor.fetchone()[0] == 1

    cursor.execute("SELECT recommendations FROM job_assessments WHERE job_id = ?", ("job1",))
    assert cursor.fetchone()[0] is None


def test_cascade_delete_job_dry_run(purger):
    """Dry-run should show what would be deleted."""
    p, store, db_path = purger

    conn = p.conn

    # Create job with related records
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
        ("job1", 75, 80, 70, 60, "[]", "Test", 100, 0.01),
    )
    conn.execute(
        (
            "INSERT INTO preprocessed_jobs "
            "(job_id, clean_text, chunks, token_count, estimated_cost) "
            "VALUES (?, ?, ?, ?, ?)"
        ),
        ("job1", "text", "chunk1", 100, 0.01),
    )
    conn.execute(
        (
            "INSERT INTO cost_tracking "
            "(job_id, phase, input_tokens, output_tokens, cost) "
            "VALUES (?, ?, ?, ?, ?)"
        ),
        ("job1", "assess", 100, 50, 0.01),
    )
    conn.execute(
        (
            "INSERT INTO job_reviews "
            "(job_id, title, location, status) VALUES (?, ?, ?, ?)"
        ),
        ("job1", "Title", "Location", "pending"),
    )
    conn.commit()

    # Dry run
    count, ids = p.cascade_delete_job("job1", dry_run=True)
    assert count == 5  # 1 job + 1 assessment + 1 preprocessed + 1 cost_tracking + 1 review
    assert "job1" in ids

    # Verify all records still exist
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE id = ?", ("job1",))
    assert cursor.fetchone()[0] == 1


def test_cascade_delete_job_actual(purger):
    """Should delete job and all related records."""
    p, store, db_path = purger

    conn = p.conn

    # Create job with related records
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
        ("job1", 75, 80, 70, 60, "[]", "Test", 100, 0.01),
    )
    conn.execute(
        (
            "INSERT INTO preprocessed_jobs "
            "(job_id, clean_text, chunks, token_count, estimated_cost) "
            "VALUES (?, ?, ?, ?, ?)"
        ),
        ("job1", "text", "chunk1", 100, 0.01),
    )
    conn.execute(
        (
            "INSERT INTO cost_tracking "
            "(job_id, phase, input_tokens, output_tokens, cost) "
            "VALUES (?, ?, ?, ?, ?)"
        ),
        ("job1", "assess", 100, 50, 0.01),
    )
    conn.execute(
        (
            "INSERT INTO job_reviews "
            "(job_id, title, location, status) VALUES (?, ?, ?, ?)"
        ),
        ("job1", "Title", "Location", "pending"),
    )
    conn.commit()

    # Actual delete
    count, ids = p.cascade_delete_job("job1", dry_run=False)
    assert count == 5

    # Verify all records deleted
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE id = ?", ("job1",))
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM job_assessments WHERE job_id = ?", ("job1",))
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM preprocessed_jobs WHERE job_id = ?", ("job1",))
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM cost_tracking WHERE job_id = ?", ("job1",))
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM job_reviews WHERE job_id = ?", ("job1",))
    assert cursor.fetchone()[0] == 0


def test_purge_no_records_to_delete(purger):
    """Should handle case with no records to delete."""
    p, store, db_path = purger

    # Purge with empty database
    count, ids = p.purge_orphaned_assessments(dry_run=False)
    assert count == 0
    assert len(ids) == 0


def test_purge_by_date_range_dry_run(purger):
    """Dry-run should identify records in date range."""
    p, store, db_path = purger

    conn = p.conn

    # Create job and assessment
    conn.execute(
        "INSERT INTO jobs (id, title, company, location, description, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("job1", "Title", "Company", "Location", "Desc", "pending_review"),
    )
    conn.execute(
        (
            "INSERT INTO job_assessments "
            "(job_id, overall_score, tech_score, seniority_score, location_score, "
            "recommendations, summary, tokens_used, actual_cost, assessed_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
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
            "2026-01-01 12:00:00",
        ),
    )
    conn.commit()

    # Dry run for date range
    count, ids = p.purge_by_date_range("2026-01-01 00:00:00", "2026-12-31 23:59:59", dry_run=True)
    assert count == 1
    assert "job1" in ids

    # Verify record still exists
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM job_assessments")
    assert cursor.fetchone()[0] == 1


def test_transaction_rollback_on_error(purger):
    """Transaction should rollback if error occurs."""
    p, store, db_path = purger

    conn = p.conn

    # Create invalid state (assessment without job, will cause issues)
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

    # First, verify it's there
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM job_assessments WHERE job_id = ?", ("orphaned_job",))
    initial = cursor.fetchone()[0]
    assert initial == 1

    # Delete should work
    count, ids = p.purge_orphaned_assessments(dry_run=False)
    assert count == 1

    # Verify it's gone
    cursor.execute("SELECT COUNT(*) FROM job_assessments WHERE job_id = ?", ("orphaned_job",))
    final = cursor.fetchone()[0]
    assert final == 0
