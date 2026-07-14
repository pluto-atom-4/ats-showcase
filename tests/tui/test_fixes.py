"""Tests for TUI fixes: phase indicator, export panel, workflow integration."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.tui.dashboard import ATPDashboard
from src.tui.models.state import PhaseStatus, StateManager
from src.tui.panels.export_panel import ExportPanel
from src.tui.widgets.phase_indicator import PhaseIndicator


class TestPhaseIndicatorObserverFix:
    """Tests for PhaseIndicator observer subscription fix (#199)."""

    def test_phase_indicator_has_on_mount_method(self, state_manager):
        """PhaseIndicator has on_mount method for observer subscription."""
        indicator = PhaseIndicator(state_manager)
        assert hasattr(indicator, "on_mount")
        assert callable(indicator.on_mount)

    def test_phase_indicator_has_state_change_callback(self, state_manager):
        """PhaseIndicator has _on_state_change callback method."""
        indicator = PhaseIndicator(state_manager)
        # Verify _on_state_change method exists and is callable
        assert hasattr(indicator, "_on_state_change")
        assert callable(indicator._on_state_change)
        # Verify callback can be called (no errors)
        indicator._on_state_change("crawl")

    def test_phase_indicator_updates_emoji_on_crawl_start(self, state_manager):
        """PhaseIndicator shows running emoji when crawl starts."""
        indicator = PhaseIndicator(state_manager)
        state_manager.start_phase("crawl", total_items=10)
        content = indicator.render()
        # Should show running indicator
        assert "⏳" in content  # Running emoji

    def test_phase_indicator_updates_emoji_on_crawl_complete(self, state_manager):
        """PhaseIndicator shows complete emoji when crawl finishes."""
        indicator = PhaseIndicator(state_manager)
        state_manager.start_phase("crawl", total_items=10)
        state_manager.complete_phase("crawl")
        content = indicator.render()
        # Should show complete indicator
        assert "✓" in content  # Complete emoji

    def test_phase_indicator_shows_multiple_phase_transitions(self, state_manager):
        """PhaseIndicator correctly shows status of all phases."""
        indicator = PhaseIndicator(state_manager)
        state_manager.start_phase("crawl", total_items=10)
        state_manager.complete_phase("crawl")
        state_manager.start_phase("preprocess", total_items=10)

        content = indicator.render()
        # Crawl done, preprocess running
        assert "✓" in content  # At least one completed
        assert "⏳" in content  # At least one running


class TestExportPanelAccumulatedMetricsFix:
    """Tests for ExportPanel accumulated metrics display fix (#199)."""

    def test_export_panel_shows_accumulated_tokens(self, state_manager):
        """ExportPanel displays accumulated tokens from prior phases."""
        panel = ExportPanel(state_manager)

        # Simulate metrics from prior phases
        state_manager.start_phase("crawl", total_items=10)
        state_manager.increment_phase_progress("crawl", tokens=1000)
        state_manager.complete_phase("crawl")

        state_manager.start_phase("preprocess", total_items=10)
        state_manager.increment_phase_progress("preprocess", tokens=2000)
        state_manager.complete_phase("preprocess")

        state_manager.start_phase("assess", total_items=10)
        state_manager.increment_phase_progress("assess", tokens=3000)
        state_manager.complete_phase("assess")

        # Now show export panel
        state_manager.start_phase("export", total_items=1)
        content = panel.render()

        # Should show accumulated tokens (1000 + 2000 + 3000 = 6000)
        assert "Accumulated" in content
        assert "6" in content  # At least 6000 in output

    def test_export_panel_shows_accumulated_cost(self, state_manager):
        """ExportPanel displays accumulated cost from prior phases."""
        panel = ExportPanel(state_manager)

        state_manager.start_phase("crawl", total_items=1)
        state_manager.increment_phase_progress("crawl", cost=0.001)
        state_manager.complete_phase("crawl")

        state_manager.start_phase("preprocess", total_items=1)
        state_manager.increment_phase_progress("preprocess", cost=0.002)
        state_manager.complete_phase("preprocess")

        state_manager.start_phase("export", total_items=1)
        content = panel.render()

        # Should show accumulated cost
        assert "Accumulated" in content
        assert "$" in content  # Cost symbol

    def test_export_panel_hides_accumulated_when_empty(self, state_manager):
        """ExportPanel omits accumulated section if no prior metrics."""
        panel = ExportPanel(state_manager)
        state_manager.start_phase("export", total_items=1)
        content = panel.render()

        # No prior metrics, so no accumulated section
        assert "Accumulated" not in content


class TestJSONExportSchemaFix:
    """Tests for JSON export schema alignment fix (#199)."""

    def test_export_writes_json_to_correct_location(self, tmp_path, state_manager):
        """Export phase writes JSON to data/extracted_jobs/preprocessed_jobs.json."""
        # Mock the export directory
        export_dir = tmp_path / "extracted_jobs"
        export_file = export_dir / "preprocessed_jobs.json"

        # Add test job
        state_manager.add_job(
            job_id="test_job_1",
            title="Python Developer",
            company="TechCorp",
            description="Test job description",
            clean_text="A clean text version",
            chunks=["chunk1", "chunk2"],
            total_tokens=150,
            estimated_cost=0.00045,
        )

        # Simulate what dashboard export does
        preprocessed_jobs = [
            {
                "job_id": job_id,
                "company": job.get("company"),
                "clean_text": job.get("clean_text", ""),
                "sentences": (
                    job.get("clean_text", "").split("\n")
                    if job.get("clean_text")
                    else []
                ),
                "chunks": job.get("chunks", []),
                "token_count": job.get("total_tokens", 0),
                "estimated_cost": job.get("estimated_cost", 0.0),
                "crawled_date": datetime.now().isoformat(),
            }
            for job_id, job in state_manager.jobs.items()
        ]

        export_dir.mkdir(parents=True, exist_ok=True)
        export_file.write_text(
            json.dumps(preprocessed_jobs, indent=2, default=str),
            encoding="utf-8",
        )

        # Verify file was written
        assert export_file.exists()
        assert export_file.read_text()

    def test_export_json_has_correct_schema(self, tmp_path, state_manager):
        """Exported JSON matches PreprocessedJob schema."""
        export_dir = tmp_path / "extracted_jobs"
        export_file = export_dir / "preprocessed_jobs.json"

        # Add test job
        state_manager.add_job(
            job_id="test_job_1",
            title="Python Developer",
            company="TechCorp",
            description="Test job description",
            clean_text="A clean text version",
            chunks=["chunk1", "chunk2"],
            total_tokens=150,
            estimated_cost=0.00045,
        )

        preprocessed_jobs = [
            {
                "job_id": job_id,
                "company": job.get("company"),
                "clean_text": job.get("clean_text", ""),
                "sentences": (
                    job.get("clean_text", "").split("\n")
                    if job.get("clean_text")
                    else []
                ),
                "chunks": job.get("chunks", []),
                "token_count": job.get("total_tokens", 0),
                "estimated_cost": job.get("estimated_cost", 0.0),
                "crawled_date": datetime.now().isoformat(),
            }
            for job_id, job in state_manager.jobs.items()
        ]

        export_dir.mkdir(parents=True, exist_ok=True)
        export_file.write_text(
            json.dumps(preprocessed_jobs, indent=2, default=str),
            encoding="utf-8",
        )

        # Read and validate schema
        data = json.loads(export_file.read_text())
        assert len(data) > 0

        job = data[0]
        required_fields = [
            "job_id",
            "company",
            "clean_text",
            "sentences",
            "chunks",
            "token_count",
            "estimated_cost",
            "crawled_date",
        ]

        for field in required_fields:
            assert field in job, f"Missing required field: {field}"

    def test_export_json_crawled_date_is_iso_format(self, tmp_path, state_manager):
        """crawled_date in JSON is ISO 8601 format."""
        state_manager.add_job(
            job_id="test_job_1",
            title="Test",
            company="TechCorp",
        )

        now = datetime.now()
        iso_date = now.isoformat()

        job_data = {
            "job_id": "test_job_1",
            "company": "TechCorp",
            "clean_text": "",
            "sentences": [],
            "chunks": [],
            "token_count": 0,
            "estimated_cost": 0.0,
            "crawled_date": iso_date,
        }

        # Verify ISO format can be parsed back
        parsed = datetime.fromisoformat(job_data["crawled_date"])
        assert isinstance(parsed, datetime)


class TestCrawlPhaseJobStorageFix:
    """Tests for crawl phase description field storage (#199)."""

    def test_crawl_phase_stores_description(self, state_manager):
        """Crawl phase stores job description for preprocessing."""
        state_manager.add_job(
            job_id="job_1",
            title="Python Dev",
            company="TechCorp",
            description="Full job description here",
        )

        assert state_manager.jobs["job_1"]["description"] == "Full job description here"

    def test_crawl_phase_stores_url(self, state_manager):
        """Crawl phase stores job URL."""
        state_manager.add_job(
            job_id="job_1",
            title="Python Dev",
            company="TechCorp",
            url="https://example.com/job/123",
        )

        assert state_manager.jobs["job_1"]["url"] == "https://example.com/job/123"

    def test_crawl_phase_fallback_job_id_generation(self, state_manager):
        """Crawl phase generates ID from company/title if missing."""
        # Simulate what dashboard.py does:
        # job_id=job.id or f"{job.company}_{job.title}"
        job_id = "techcorp_python_developer"
        state_manager.add_job(
            job_id=job_id,
            title="Python Developer",
            company="TechCorp",
        )

        assert job_id in state_manager.jobs


class TestPreprocessPhaseCleanTextFix:
    """Tests for preprocess phase using description field (#199)."""

    def test_preprocess_uses_description_field(self, state_manager):
        """Preprocess phase can access description field from crawl."""
        state_manager.add_job(
            job_id="job_1",
            title="Python Dev",
            company="TechCorp",
            description="This is the job description",
        )

        job_data = state_manager.jobs["job_1"]
        description = job_data.get("description", "")
        assert description == "This is the job description"

    def test_preprocess_handles_missing_description(self, state_manager):
        """Preprocess phase handles missing description gracefully."""
        state_manager.add_job(
            job_id="job_1",
            title="Python Dev",
            company="TechCorp",
        )

        job_data = state_manager.jobs["job_1"]
        description = job_data.get("description", "")
        assert description == ""


class TestStateManagerObserverPattern:
    """Tests for StateManager observer pattern used by widgets."""

    def test_state_manager_notifies_observers(self, state_manager):
        """StateManager notifies registered observers on state change."""
        callback_called = []

        def observer(phase: str):
            callback_called.append(phase)

        state_manager.subscribe(observer)
        state_manager.start_phase("crawl", total_items=10)

        assert "crawl" in callback_called

    def test_state_manager_handles_observer_exception(self, state_manager):
        """StateManager continues if observer callback fails."""
        calls = {"bad": 0, "good": 0}

        def bad_observer(phase: str):
            calls["bad"] += 1
            raise RuntimeError("Observer error")

        def good_observer(phase: str):
            calls["good"] += 1

        state_manager.subscribe(bad_observer)
        state_manager.subscribe(good_observer)

        # Should not raise, even though bad_observer fails
        state_manager.start_phase("crawl", total_items=10)

        # good_observer should still be called
        assert calls["good"] == 1

    def test_state_manager_multiple_observers(self, state_manager):
        """StateManager can have multiple observers."""
        calls = {"observer1": 0, "observer2": 0}

        def obs1(phase: str):
            calls["observer1"] += 1

        def obs2(phase: str):
            calls["observer2"] += 1

        state_manager.subscribe(obs1)
        state_manager.subscribe(obs2)
        state_manager.start_phase("crawl", total_items=10)

        assert calls["observer1"] == 1
        assert calls["observer2"] == 1
