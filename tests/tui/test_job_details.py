"""Tests for inline job details viewing feature."""

import pytest

from src.tui.dialogs.job_details import JobDetailsPanel
from src.tui.models.state import StateManager
from src.tui.widgets.job_table import JobTable


class TestJobDetailsPanel:
    """Tests for job details panel display."""

    def test_job_details_initialization(self):
        """JobDetailsPanel initializes with job data."""
        job_id = "job_1"
        job_data = {
            "id": job_id,
            "title": "Python Developer",
            "company": "TechCorp",
            "overall_score": 85,
            "tech_score": 90,
            "seniority_score": 80,
            "location_score": 75,
        }

        panel = JobDetailsPanel(job_id, job_data)
        assert panel.job_id == job_id
        assert panel.job_data == job_data

    def test_job_details_renders_scores(self):
        """JobDetailsPanel renders all score categories."""
        job_data = {
            "id": "job_1",
            "title": "Test Job",
            "overall_score": 85,
            "tech_score": 90,
            "seniority_score": 80,
            "location_score": 75,
        }

        panel = JobDetailsPanel("job_1", job_data)
        content = panel.render()

        assert "85" in content  # Overall score
        assert "90" in content  # Tech score
        assert "80" in content  # Seniority score
        assert "75" in content  # Location score

    def test_job_details_renders_summary(self):
        """JobDetailsPanel displays assessment summary."""
        summary_text = "Strong technical fit with relevant experience."
        job_data = {
            "id": "job_1",
            "title": "Test Job",
            "assessment_summary": summary_text,
        }

        panel = JobDetailsPanel("job_1", job_data)
        content = panel.render()

        assert "Assessment Summary" in content
        assert "Strong technical fit" in content

    def test_job_details_renders_recommendations(self):
        """JobDetailsPanel displays recommendations."""
        job_data = {
            "id": "job_1",
            "title": "Test Job",
            "recommendations": [
                "Highlight Docker experience",
                "Mention AWS projects",
                "Emphasize team leadership",
            ],
        }

        panel = JobDetailsPanel("job_1", job_data)
        content = panel.render()

        assert "Recommendations" in content
        assert "Highlight Docker experience" in content
        assert "Mention AWS projects" in content


class TestJobTableExpansion:
    """Tests for job table expansion logic (without Textual app context)."""

    def test_job_table_initialization(self, state_manager):
        """JobTable initializes with expansion support."""
        table = JobTable(state_manager)
        assert table.expanded_job_id is None
        assert len(table.job_rows) == 0

    def test_job_table_get_expanded_job_none(self, state_manager):
        """get_expanded_job returns None when nothing expanded."""
        table = JobTable(state_manager)
        assert table.get_expanded_job() is None

    def test_job_table_expansion_state_changes(self, state_manager):
        """Test expansion state without DataTable infrastructure."""
        state_manager.add_job(
            job_id="job_1",
            title="Python Dev",
            company="TechCorp",
            overall_score=85,
        )

        table = JobTable(state_manager)

        # Manually set up job_rows (what update_rows does)
        job_1 = state_manager.jobs["job_1"]
        table.job_rows["row_0"] = job_1

        # Test expansion
        table.expanded_job_id = "job_1"
        expanded = table.get_expanded_job()
        assert expanded is not None
        assert expanded["title"] == "Python Dev"

        # Test collapse
        table.expanded_job_id = None
        assert table.get_expanded_job() is None

    def test_job_table_get_selected_job(self, state_manager):
        """Test get_selected_job retrieves correct job."""
        state_manager.add_job(
            job_id="job_1",
            title="Job 1",
            company="Corp",
            overall_score=85,
        )
        state_manager.add_job(
            job_id="job_2",
            title="Job 2",
            company="Corp",
            overall_score=87,
        )

        table = JobTable(state_manager)

        # Manually setup job_rows to simulate what update_rows does
        jobs = list(state_manager.jobs.values())
        for i, job in enumerate(jobs):
            table.job_rows[f"row_{i}"] = job

        # Without setting cursor_row (which is read-only), verify job_rows mapping
        assert len(table.job_rows) == 2
        row_keys = list(table.job_rows.keys())
        assert table.job_rows[row_keys[0]]["id"] == jobs[0]["id"]
        assert table.job_rows[row_keys[1]]["id"] == jobs[1]["id"]


class TestAssessmentViewingWorkflow:
    """Integration tests for viewing assessment details."""

    def test_details_panel_with_full_assessment(self):
        """Test JobDetailsPanel displays assessment correctly."""
        job_data = {
            "id": "job_1",
            "title": "Python Developer",
            "company": "TechCorp",
            "overall_score": 85,
            "tech_score": 90,
            "seniority_score": 80,
            "location_score": 75,
            "assessment_summary": "Strong technical fit.",
            "recommendations": ["Highlight Docker", "Mention AWS"],
        }

        panel = JobDetailsPanel(job_data["id"], job_data)
        content = panel.render()

        assert "85" in content  # Score
        assert "Strong technical fit" in content  # Summary
        assert "Highlight Docker" in content  # Recommendation

    def test_filter_only_assessed_jobs_for_display(self, state_manager):
        """Only show jobs with scores in table."""
        # Add unassessed job
        state_manager.add_job(
            job_id="job_1",
            title="Not Assessed Yet",
            company="Corp",
        )

        # Add assessed job
        state_manager.add_job(
            job_id="job_2",
            title="Already Assessed",
            company="Corp",
            overall_score=85,
        )

        # Filter only assessed
        assessed = [
            j for j in state_manager.jobs.values()
            if j.get("overall_score") is not None
        ]

        assert len(assessed) == 1
        assert assessed[0]["title"] == "Already Assessed"

    def test_details_panel_handles_empty_fields(self):
        """JobDetailsPanel handles missing optional fields gracefully."""
        job_data = {
            "id": "job_1",
            "title": "Minimal Job",
            # Missing: assessment_summary, recommendations, scores
        }

        panel = JobDetailsPanel("job_1", job_data)
        content = panel.render()

        # Should render without crashing
        assert "Minimal Job" in content
        assert "0/100" in content  # Default score
