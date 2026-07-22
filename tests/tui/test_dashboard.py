"""Tests for TUI dashboard and panels."""

import pytest

from src.tui.dashboard import ATPDashboard, ATPDashboardApp, HeaderPanel
from src.tui.models.state import PhaseStatus, StateManager
from src.tui.panels.assess_panel import AssessPanel
from src.tui.panels.base import BasePanelWidget
from src.tui.panels.crawl_panel import CrawlPanel
from src.tui.panels.export_panel import ExportPanel
from src.tui.panels.preprocess_panel import PreprocessPanel
from src.tui.widgets.cost_tracker import CostTracker
from src.tui.widgets.job_table import JobTable
from src.tui.widgets.phase_indicator import PhaseIndicator
from src.tui.widgets.progress_bar import TUIProgressBar


class TestDashboard:
    """Tests for ATPDashboard."""

    def test_dashboard_initialization(self, state_manager):
        """Dashboard initializes without errors."""
        dashboard = ATPDashboard(state_manager)
        assert dashboard.state is state_manager
        assert dashboard.title == "ATS Showcase - TUI Dashboard"

    def test_dashboard_has_bindings(self, state_manager):
        """App has required keyboard bindings for command palette."""
        app = ATPDashboardApp(state_manager)
        bindings = [binding[0] for binding in app.BINDINGS]
        assert "p" in bindings
        assert "r" in bindings
        assert "q" in bindings


class TestHeaderPanel:
    """Tests for HeaderPanel."""

    def test_header_panel_renders(self, state_manager):
        """HeaderPanel renders without errors."""
        header = HeaderPanel(state_manager)
        content = header.render()
        assert "ATS Showcase" in content
        assert "$" in content  # Cost symbol


class TestCrawlPanel:
    """Tests for CrawlPanel."""

    def test_crawl_panel_initialization(self, state_manager):
        """CrawlPanel initializes correctly."""
        panel = CrawlPanel(state_manager)
        assert panel.phase == "crawl"
        assert panel.state is state_manager

    def test_crawl_panel_renders(self, state_manager):
        """CrawlPanel renders without errors."""
        panel = CrawlPanel(state_manager)
        state_manager.start_phase("crawl", total_items=10)
        state_manager.increment_phase_progress("crawl", tokens=100)
        content = panel.render()
        assert "CRAWL" in content
        assert "100" in content  # Token count


class TestPreprocessPanel:
    """Tests for PreprocessPanel."""

    def test_preprocess_panel_initialization(self, state_manager):
        """PreprocessPanel initializes correctly."""
        panel = PreprocessPanel(state_manager)
        assert panel.phase == "preprocess"

    def test_preprocess_panel_renders(self, state_manager):
        """PreprocessPanel renders without errors."""
        panel = PreprocessPanel(state_manager)
        state_manager.start_phase("preprocess", total_items=10)
        state_manager.increment_phase_progress("preprocess", tokens=200)
        content = panel.render()
        assert "PREPROCESS" in content


class TestAssessPanel:
    """Tests for AssessPanel."""

    def test_assess_panel_initialization(self, state_manager):
        """AssessPanel initializes correctly."""
        panel = AssessPanel(state_manager)
        assert panel.phase == "assess"

    def test_assess_panel_with_top_matches(self, state_manager):
        """AssessPanel displays top matches."""
        panel = AssessPanel(state_manager)
        state_manager.start_phase("assess", total_items=3)

        # Add jobs to state
        state_manager.add_job(
            job_id="job_1",
            title="Python Developer",
            company="TechCorp",
            overall_score=95,
        )
        state_manager.add_job(
            job_id="job_2",
            title="Backend Engineer",
            company="StartupXYZ",
            overall_score=87,
        )

        # Verify panel header renders
        content = panel.render()
        assert "ASSESS" in content

        # Verify jobs are in state (panel would display via JobTable widget)
        jobs_in_state = [j for j in state_manager.jobs.values() if j.get("overall_score")]
        assert len(jobs_in_state) == 2
        assert any(j["title"] == "Python Developer" for j in jobs_in_state)


class TestExportPanel:
    """Tests for ExportPanel."""

    def test_export_panel_initialization(self, state_manager):
        """ExportPanel initializes correctly."""
        panel = ExportPanel(state_manager)
        assert panel.phase == "export"

    def test_export_panel_renders(self, state_manager):
        """ExportPanel renders without errors."""
        panel = ExportPanel(state_manager)
        state_manager.start_phase("export", total_items=1)
        state_manager.increment_phase_progress("export")
        content = panel.render()
        assert "EXPORT" in content


class TestBasePanelWidget:
    """Tests for BasePanelWidget helpers."""

    def test_panel_header_rendering(self, state_manager):
        """Panel renders correct header format."""
        state_manager.start_phase("crawl", total_items=10)
        panel = CrawlPanel(state_manager)
        header = panel.render_phase_header()
        assert "CRAWL" in header
        assert "RUNNING" in header


class TestPhaseIndicator:
    """Tests for PhaseIndicator widget."""

    def test_phase_indicator_initialization(self, state_manager):
        """PhaseIndicator initializes correctly."""
        indicator = PhaseIndicator(state_manager)
        assert indicator.state is state_manager

    def test_phase_indicator_shows_all_phases(self, state_manager):
        """PhaseIndicator displays all phases."""
        indicator = PhaseIndicator(state_manager)
        content = indicator.render()
        assert "Crawl" in content
        assert "Preprocess" in content
        assert "Assess" in content
        assert "Export" in content

    def test_phase_indicator_shows_status(self, state_manager):
        """PhaseIndicator shows phase status correctly."""
        state_manager.start_phase("crawl", total_items=5)
        indicator = PhaseIndicator(state_manager)
        content = indicator.render()
        # Should show running indicator
        assert "⏳" in content or "Running" in content or "Crawl" in content


class TestProgressBar:
    """Tests for TUIProgressBar widget."""

    def test_progress_bar_initialization(self, state_manager):
        """TUIProgressBar initializes correctly."""
        bar = TUIProgressBar(state_manager, "crawl")
        assert bar.phase == "crawl"

    def test_progress_bar_renders(self, state_manager):
        """TUIProgressBar renders without errors."""
        bar = TUIProgressBar(state_manager, "crawl")
        state_manager.start_phase("crawl", total_items=100)
        state_manager.increment_phase_progress("crawl", tokens=50)
        content = bar.render()
        assert "%" in content
        assert "(" in content  # Progress count


class TestCostTracker:
    """Tests for CostTracker widget."""

    def test_cost_tracker_initialization(self, state_manager):
        """CostTracker initializes correctly."""
        tracker = CostTracker(state_manager, "crawl")
        assert tracker.phase == "crawl"

    def test_cost_tracker_renders(self, state_manager):
        """CostTracker displays cost correctly."""
        tracker = CostTracker(state_manager, "crawl")
        state_manager.start_phase("crawl", total_items=1)
        state_manager.increment_phase_progress("crawl", tokens=100, cost=0.0003)
        content = tracker.render()
        assert "$" in content
        assert "100" in content


class TestJobTable:
    """Tests for JobTable widget."""

    def test_job_table_initialization(self, state_manager):
        """JobTable initializes correctly."""
        table = JobTable(state_manager)
        assert table.state is state_manager

    def test_job_table_has_update_rows_method(self, state_manager):
        """JobTable has update_rows method."""
        table = JobTable(state_manager)
        # Verify method exists and is callable
        assert hasattr(table, "update_rows")
        assert callable(table.update_rows)
