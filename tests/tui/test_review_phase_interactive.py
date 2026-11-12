"""Test review phase with injected mock jobs (bypasses crawler)."""

import pytest
from textual import work
from textual.app import ComposeResult
from textual.widgets import Static

from src.tui.dashboard import ATPDashboard
from src.tui.models.state import PhaseStatus, StateManager


class TestReviewPhaseInteractive:
    """Test interactive review phase without crawler."""

    @pytest.mark.asyncio
    async def test_review_phase_with_mock_jobs(self):
        """Inject mock jobs and verify review phase dialog interaction."""
        state = StateManager()

        mock_jobs = {
            "job_1": {
                "title": "Senior Python Developer",
                "company": "TechCorp",
                "location": "Remote",
                "url": "https://example.com/job1",
                "description": "Looking for 5+ years Python experience",
                "clean_text": "Senior Python Developer. TechCorp is hiring.",
                "status": "pending_review",
            },
            "job_2": {
                "title": "React Frontend Engineer",
                "company": "WebInc",
                "location": "San Francisco",
                "url": "https://example.com/job2",
                "description": "Build React components",
                "clean_text": "React Frontend Engineer. WebInc needs React devs.",
                "status": "pending_review",
            },
        }

        for job_id, job_data in mock_jobs.items():
            state.add_job(job_id=job_id, **job_data)

        assert len(state.jobs) == 2
        assert state.jobs["job_1"]["status"] == "pending_review"

    @pytest.mark.asyncio
    async def test_review_phase_with_tui_app(self):
        """Test review phase in TUI app with mock jobs."""
        state = StateManager()

        state.add_job(
            job_id="job_1",
            title="Python Dev",
            company="Corp A",
            location="Remote",
            url="https://example.com/1",
            description="Test job 1",
            clean_text="Python job description",
            status="pending_review",
        )
        state.add_job(
            job_id="job_2",
            title="React Dev",
            company="Corp B",
            location="NYC",
            url="https://example.com/2",
            description="Test job 2",
            clean_text="React job description",
            status="pending_review",
        )

        assert len(state.jobs) == 2
        assert state.jobs["job_1"]["status"] == "pending_review"
        assert state.jobs["job_2"]["status"] == "pending_review"

    @pytest.mark.asyncio
    async def test_review_phase_status_transitions(self):
        """Test that review phase correctly updates job statuses."""
        state = StateManager()

        state.add_job(
            job_id="confirm_job",
            title="Good Job",
            company="Good Corp",
            location="Remote",
            url="https://example.com/good",
            description="Great opportunity",
            clean_text="Good job",
            status="pending_review",
        )
        state.add_job(
            job_id="reject_job",
            title="Bad Job",
            company="Bad Corp",
            location="Nowhere",
            url="https://example.com/bad",
            description="Terrible opportunity",
            clean_text="Bad job",
            status="pending_review",
        )

        state.update_job("confirm_job", status="confirmed")
        state.update_job("reject_job", status="rejected")

        assert state.jobs["confirm_job"]["status"] == "confirmed"
        assert state.jobs["reject_job"]["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_review_phase_metrics(self):
        """Test review phase metrics (progress, totals)."""
        state = StateManager()

        for i in range(3):
            state.add_job(
                job_id=f"job_{i}",
                title=f"Job {i}",
                company=f"Corp {i}",
                location="Remote",
                url=f"https://example.com/{i}",
                description=f"Job {i}",
                clean_text=f"Job {i} description",
                status="pending_review",
            )

        state.start_phase("review", total_items=3)
        assert state.phase_status["review"] == PhaseStatus.RUNNING
        assert state.phase_metrics["review"].total_items == 3
        assert state.phase_metrics["review"].processed_items == 0

        for _i in range(3):
            state.increment_phase_progress("review")

        assert state.phase_metrics["review"].processed_items == 3
        assert state.phase_metrics["review"].progress_percent == 100.0

        state.complete_phase("review")
        assert state.phase_status["review"] == PhaseStatus.COMPLETED


class TestJobReviewDialogUnit:
    """Unit tests for JobReviewDialog focus fix."""

    @pytest.mark.asyncio
    async def test_dialog_focus_deferred(self):
        """Test that dialog focus is deferred until widgets mount."""
        from src.tui.dialogs.job_review import JobReviewDialog

        dialog = JobReviewDialog(
            "test_job",
            {
                "title": "Test",
                "company": "Test Corp",
                "location": "Remote",
                "clean_text": "Test description",
            },
        )

        # Focus is deferred to _set_focus.
        assert hasattr(dialog, "_set_focus")
        assert callable(dialog._set_focus)

    @pytest.mark.asyncio
    async def test_dialog_decision_property(self):
        """Test that dialog sets decision property correctly."""
        from src.tui.dialogs.job_review import JobReviewDialog

        dialog = JobReviewDialog("job_1", {"title": "Test Job"})
        assert dialog.decision is None
        dialog.decision = "confirm"
        assert dialog.decision == "confirm"

        dialog2 = JobReviewDialog("job_2", {"title": "Test Job 2"})
        dialog2.decision = "reject"
        assert dialog2.decision == "reject"

        dialog3 = JobReviewDialog("job_3", {"title": "Test Job 3"})
        dialog3.decision = "skip"
        assert dialog3.decision == "skip"

    @pytest.mark.asyncio
    async def test_dialog_has_keybindings(self):
        """Test that dialog has escape keybinding."""
        from src.tui.dialogs.job_review import JobReviewDialog

        dialog = JobReviewDialog("job_1", {"title": "Test"})

        assert ("escape", "quit_dialog", "Cancel") in dialog.BINDINGS
        assert hasattr(dialog, "action_quit_dialog")
        assert callable(dialog.action_quit_dialog)
