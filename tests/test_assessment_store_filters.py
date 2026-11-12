"""Tests for AssessmentStore filtering methods (Phase 2 - issue #100)."""

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from storage.assessment_store import AssessmentStore


@pytest.fixture
def temp_db():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def store_with_test_data(temp_db):
    """Create store with test data for filtering."""
    store = AssessmentStore(temp_db)

    if store.conn:
        cursor = store.conn.cursor()

        cursor.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
               id TEXT PRIMARY KEY,
               title TEXT,
               company TEXT,
               crawled_at TEXT,
               status TEXT DEFAULT 'pending_review'
            )"""
        )

        cursor.execute(
            """CREATE TABLE IF NOT EXISTS job_reviews (
               job_id TEXT PRIMARY KEY,
               title TEXT,
               company TEXT,
               status TEXT,
               crawled_at TEXT,
               reviewed_at TIMESTAMP
            )"""
        )

        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        cursor.execute(
            "INSERT INTO jobs VALUES ('job_1', 'Engineer', 'TechCorp', ?, 'pending_review')",
            (today.isoformat(),),
        )
        cursor.execute(
            "INSERT INTO jobs VALUES ('job_2', 'Designer', 'DesignInc', ?, 'pending_review')",
            (yesterday.isoformat(),),
        )
        cursor.execute(
            "INSERT INTO jobs VALUES ('job_3', 'Manager', 'ManagerCorp', ?, 'pending_review')",
            (week_ago.isoformat(),),
        )
        cursor.execute(
            "INSERT INTO jobs VALUES ('job_4', 'Analyst', 'DataInc', ?, 'pending_review')",
            (today.isoformat(),),
        )

        cursor.execute(
            "INSERT INTO job_reviews VALUES ('job_2', 'Designer', 'DesignInc', 'confirmed', ?, ?)",
            (yesterday.isoformat(), datetime.now().isoformat()),
        )

        cursor.execute(
            """INSERT INTO job_assessments
               (job_id, title, company, location, overall_score, tech_score,
                seniority_score, location_score, recommendations, summary,
                tokens_used, input_tokens, output_tokens, actual_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "job_3",
                "Manager",
                "ManagerCorp",
                "SF",
                85.0,
                90.0,
                85.0,
                80.0,
                "[]",
                "Good fit",
                100,
                80,
                20,
                0.0003,
            ),
        )

        store.conn.commit()

    yield store

    if store.conn:
        store.conn.close()


class TestGetAssessmentStatus:
    """Test get_assessment_status method."""

    def test_assessed_job(self, store_with_test_data):
        """Test getting status for assessed job."""
        status = store_with_test_data.get_assessment_status("job_3")
        assert status == "assessed"

    def test_confirmed_job(self, store_with_test_data):
        """Test getting status for confirmed job."""
        status = store_with_test_data.get_assessment_status("job_2")
        assert status == "confirmed"

    def test_pending_job(self, store_with_test_data):
        """Test getting status for pending job."""
        status = store_with_test_data.get_assessment_status("job_1")
        assert status == "pending"

    def test_nonexistent_job(self, store_with_test_data):
        """Test getting status for nonexistent job."""
        status = store_with_test_data.get_assessment_status("job_999")
        assert status == "pending"


class TestGetJobsNeedingAssessment:
    """Test get_jobs_needing_assessment method."""

    def test_returns_confirmed_not_assessed(self, store_with_test_data):
        """Test returns only confirmed jobs without assessments."""
        jobs = store_with_test_data.get_jobs_needing_assessment(limit=10)
        job_ids = [j["job_id"] for j in jobs]
        assert "job_2" in job_ids
        assert "job_3" not in job_ids
        assert "job_1" not in job_ids

    def test_ordered_by_crawled_at(self, store_with_test_data):
        """Test results ordered by crawled_at DESC."""
        jobs = store_with_test_data.get_jobs_needing_assessment(limit=10)
        if jobs:
            assert jobs[0]["job_id"] == "job_2"

    def test_limit_respected(self, store_with_test_data):
        """Test limit parameter is respected."""
        if store_with_test_data.conn:
            cursor = store_with_test_data.conn.cursor()
            today = datetime.now().date()
            for i in range(4, 8):
                cursor.execute(
                    "INSERT INTO job_reviews VALUES (?, ?, ?, ?, ?, ?)",
                    (f"job_{i}", f"Role {i}", "Company", "confirmed", today.isoformat(), datetime.now().isoformat()),
                )
            store_with_test_data.conn.commit()

        jobs = store_with_test_data.get_jobs_needing_assessment(limit=2)
        assert len(jobs) <= 2


class TestGetJobsByScoreThreshold:
    """Test get_jobs_by_score_threshold method."""

    def test_filter_by_min_score(self, store_with_test_data):
        """Test filtering by minimum score."""
        if store_with_test_data.conn:
            cursor = store_with_test_data.conn.cursor()
            for job_id, score in [("job_1", 75.0), ("job_2", 90.0), ("job_4", 60.0)]:
                cursor.execute(
                    """INSERT INTO job_assessments
                       (job_id, title, company, location, overall_score, tech_score,
                        seniority_score, location_score, recommendations, summary,
                        tokens_used, input_tokens, output_tokens, actual_cost)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (job_id, "Role", "Company", "Loc", score, score, score, score, "[]", "Test", 100, 80, 20, 0.0003),
                )
            store_with_test_data.conn.commit()

        jobs = store_with_test_data.get_jobs_by_score_threshold(min_score=80, max_score=100)
        job_ids = [j["job_id"] for j in jobs]
        assert "job_2" in job_ids
        assert "job_3" in job_ids
        assert "job_1" not in job_ids
        assert "job_4" not in job_ids

    def test_filter_by_max_score(self, store_with_test_data):
        """Test filtering by maximum score."""
        if store_with_test_data.conn:
            cursor = store_with_test_data.conn.cursor()
            for job_id, score in [("job_1", 75.0), ("job_2", 90.0), ("job_4", 60.0)]:
                cursor.execute(
                    """INSERT INTO job_assessments
                       (job_id, title, company, location, overall_score, tech_score,
                        seniority_score, location_score, recommendations, summary,
                        tokens_used, input_tokens, output_tokens, actual_cost)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (job_id, "Role", "Company", "Loc", score, score, score, score, "[]", "Test", 100, 80, 20, 0.0003),
                )
            store_with_test_data.conn.commit()

        jobs = store_with_test_data.get_jobs_by_score_threshold(min_score=0, max_score=80)
        job_ids = [j["job_id"] for j in jobs]
        assert "job_1" in job_ids
        assert "job_4" in job_ids
        assert "job_3" not in job_ids


class TestGetJobsSince:
    """Test get_jobs_since method."""

    def test_get_jobs_since_date(self, store_with_test_data):
        """Test getting jobs crawled since a date."""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        jobs = store_with_test_data.get_jobs_since(yesterday.isoformat())
        job_ids = [j.get("job_id") or j.get("id") for j in jobs]
        assert "job_2" in job_ids

        future = (today + timedelta(days=1)).isoformat()
        future_jobs = store_with_test_data.get_jobs_since(future)
        assert len(future_jobs) == 0

    def test_get_jobs_since_includes_exact_date(self, store_with_test_data):
        """Test that exact date is included."""
        yesterday = datetime.now().date() - timedelta(days=1)
        jobs = store_with_test_data.get_jobs_since(yesterday.isoformat())
        job_ids = [j.get("job_id") or j.get("id") for j in jobs]
        assert "job_2" in job_ids

    def test_get_jobs_since_limit(self, store_with_test_data):
        """Test limit parameter with date filter."""
        today = datetime.now().date()
        jobs = store_with_test_data.get_jobs_since(today.isoformat(), limit=1)
        assert len(jobs) <= 1

    def test_get_jobs_since_fallback_to_jobs_table(self, temp_db):
        """Test fallback to jobs table when job_reviews missing."""
        store = AssessmentStore(temp_db)

        if store.conn:
            cursor = store.conn.cursor()
            # Only the jobs table, deliberately no job_reviews, to force the fallback; jobs uses id not job_id.
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                   id TEXT PRIMARY KEY,
                   title TEXT,
                   company TEXT,
                   crawled_at TEXT,
                   status TEXT DEFAULT 'pending_review'
                )"""
            )

            today = datetime.now().date()
            cursor.execute(
                "INSERT INTO jobs VALUES ('job_1', 'Engineer', 'TechCorp', ?, 'pending_review')",
                (today.isoformat(),),
            )
            store.conn.commit()

        jobs = store.get_jobs_since(today.isoformat())
        assert len(jobs) > 0
        assert jobs[0].get("id") == "job_1" or jobs[0].get("job_id") == "job_1"
