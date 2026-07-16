"""Tests for JobReviewDialog interactive approval feature."""

import pytest

from src.tui.dialogs.job_review import JobReviewDialog
from src.tui.models.state import StateManager


class TestJobReviewDialog:
    """Tests for job review/approval dialog."""

    def test_dialog_initialization(self):
        """JobReviewDialog initializes with job data."""
        job_id = "job_1"
        job_data = {
            "title": "Python Developer",
            "company": "TechCorp",
            "location": "Remote",
            "clean_text": "Full job description here",
        }

        dialog = JobReviewDialog(job_id, job_data)
        assert dialog.job_id == job_id
        assert dialog.job_data == job_data
        assert dialog.decision is None

    def test_dialog_stores_decision_confirm(self):
        """Dialog stores confirm decision."""
        job_id = "job_1"
        job_data = {"title": "Test", "company": "Corp"}

        dialog = JobReviewDialog(job_id, job_data)
        dialog.decision = "confirm"
        assert dialog.decision == "confirm"

    def test_dialog_stores_decision_reject(self):
        """Dialog stores reject decision."""
        job_id = "job_1"
        job_data = {"title": "Test", "company": "Corp"}

        dialog = JobReviewDialog(job_id, job_data)
        dialog.decision = "reject"
        assert dialog.decision == "reject"

    def test_dialog_stores_decision_skip(self):
        """Dialog stores skip decision."""
        job_id = "job_1"
        job_data = {"title": "Test", "company": "Corp"}

        dialog = JobReviewDialog(job_id, job_data)
        dialog.decision = "skip"
        assert dialog.decision == "skip"


class TestJobApprovalWorkflow:
    """Tests for interactive approval workflow integration."""

    def test_state_manager_job_status_pending_review(self, state_manager):
        """New jobs default to pending_review status."""
        state_manager.add_job(
            job_id="job_1",
            title="Python Dev",
            company="TechCorp",
        )
        assert state_manager.jobs["job_1"]["status"] == "pending_review"

    def test_job_status_confirmed(self, state_manager):
        """Job status can be updated to confirmed."""
        state_manager.add_job(
            job_id="job_1",
            title="Python Dev",
            company="TechCorp",
        )
        state_manager.update_job("job_1", status="confirmed")
        assert state_manager.jobs["job_1"]["status"] == "confirmed"

    def test_job_status_rejected(self, state_manager):
        """Job status can be updated to rejected."""
        state_manager.add_job(
            job_id="job_1",
            title="Python Dev",
            company="TechCorp",
        )
        state_manager.update_job("job_1", status="rejected")
        assert state_manager.jobs["job_1"]["status"] == "rejected"

    def test_job_status_assessed(self, state_manager):
        """Job status can be updated to assessed."""
        state_manager.add_job(
            job_id="job_1",
            title="Python Dev",
            company="TechCorp",
        )
        state_manager.update_job("job_1", status="assessed")
        assert state_manager.jobs["job_1"]["status"] == "assessed"

    def test_multiple_jobs_different_statuses(self, state_manager):
        """Multiple jobs can have different statuses."""
        # Add 3 jobs
        for i in range(1, 4):
            state_manager.add_job(
                job_id=f"job_{i}",
                title=f"Job {i}",
                company="Corp",
            )

        # Set different statuses
        state_manager.update_job("job_1", status="confirmed")
        state_manager.update_job("job_2", status="rejected")
        # job_3 stays pending_review

        assert state_manager.jobs["job_1"]["status"] == "confirmed"
        assert state_manager.jobs["job_2"]["status"] == "rejected"
        assert state_manager.jobs["job_3"]["status"] == "pending_review"

    def test_count_jobs_by_status(self, state_manager):
        """Can count jobs by status for filtering."""
        # Add jobs with different statuses
        statuses = ["confirmed", "rejected", "pending_review", "confirmed"]
        for i, status in enumerate(statuses, 1):
            state_manager.add_job(
                job_id=f"job_{i}",
                title=f"Job {i}",
                company="Corp",
            )
            if status != "pending_review":
                state_manager.update_job(f"job_{i}", status=status)

        # Count by status
        confirmed = sum(
            1 for j in state_manager.jobs.values() if j["status"] == "confirmed"
        )
        rejected = sum(
            1 for j in state_manager.jobs.values() if j["status"] == "rejected"
        )
        pending = sum(
            1 for j in state_manager.jobs.values() if j["status"] == "pending_review"
        )

        assert confirmed == 2
        assert rejected == 1
        assert pending == 1

    def test_can_filter_jobs_to_assess(self, state_manager):
        """Can filter only confirmed/pending jobs for assessment."""
        # Add jobs with different statuses
        statuses = {
            "job_1": "confirmed",
            "job_2": "rejected",
            "job_3": "pending_review",
            "job_4": "confirmed",
        }

        for job_id, status in statuses.items():
            state_manager.add_job(
                job_id=job_id,
                title="Test",
                company="Corp",
            )
            if status != "pending_review":
                state_manager.update_job(job_id, status=status)

        # Filter for assessment (skip rejected)
        assessable = [
            j
            for j in state_manager.jobs.values()
            if j["status"] != "rejected"
        ]

        assert len(assessable) == 3  # confirmed, pending_review, confirmed
        assert all(j["status"] != "rejected" for j in assessable)
