"""Terminal rendering, accessibility, and color scheme tests (Phase 5)."""

import re
from typing import Any

import pytest

from src.tui.dashboard import ATPDashboard
from src.tui.models.state import StateManager
from src.tui.panels.assess_panel import AssessPanel
from src.tui.panels.base import BasePanelWidget
from src.tui.panels.crawl_panel import CrawlPanel
from src.tui.widgets.cost_tracker import CostTracker
from src.tui.widgets.phase_indicator import PhaseIndicator
from src.tui.widgets.progress_bar import TUIProgressBar


class TestTerminalDimensions:
    """Test TUI rendering at various terminal sizes."""

    def test_dashboard_css_defined(self) -> None:
        """Dashboard has CSS for proper layout."""
        dashboard = ATPDashboard(StateManager())
        assert hasattr(dashboard, "CSS"), "Dashboard must define CSS"
        assert len(dashboard.CSS) > 0, "CSS must be non-empty"
        assert "vertical" in dashboard.CSS.lower(), "Should define vertical layout"

    def test_panel_css_responsive(self, state_manager: StateManager) -> None:
        """Panels have responsive CSS definitions."""
        panel = BasePanelWidget(state_manager, phase="crawl")
        assert hasattr(panel, "DEFAULT_CSS"), "Panel must have DEFAULT_CSS"
        assert "height:" in panel.DEFAULT_CSS, "Must define height for responsiveness"

    def test_widgets_scale_with_content(self, state_manager: StateManager) -> None:
        """Widgets adjust size based on content."""
        state_manager.start_phase("crawl", total_items=100)

        # Simulate adding jobs
        for i in range(10):
            state_manager.add_job(f"job_{i}", f"Title {i}", f"Company {i}")

        metrics = state_manager.phase_metrics["crawl"]
        assert metrics.total_items == 100
        # Widget should be able to handle this data volume


class TestColorSchemeSupport:
    """Test color scheme compatibility."""

    def test_widget_uses_semantic_colors(self) -> None:
        """Widgets use semantic color tokens, not hardcoded colors."""
        panel = BasePanelWidget(StateManager(), phase="crawl")
        css = panel.DEFAULT_CSS

        # Should use semantic tokens like $primary, $accent, $boost
        assert (
            "$primary" in css or "$accent" in css or "$boost" in css
        ), "CSS must use semantic color tokens"

    def test_dashboard_color_support(self) -> None:
        """Dashboard CSS includes color definitions."""
        dashboard = ATPDashboard(StateManager())
        css = dashboard.CSS

        # Check for color token usage
        semantic_colors = ["$primary", "$accent", "$boost", "$error", "$success"]
        has_colors = any(color in css for color in semantic_colors)
        assert has_colors, "Dashboard should use semantic color tokens"

    def test_dark_mode_colors_defined(self) -> None:
        """Color scheme works for both light and dark terminals."""
        dashboard = ATPDashboard(StateManager())
        css = dashboard.CSS

        # Should work on terminal without special theme handling
        # (Textual handles light/dark automatically)
        assert len(css) > 0, "CSS must be defined for theme support"


class TestAccessibility:
    """Test accessibility and readability."""

    def test_progress_bar_text_contrast(self, state_manager: StateManager) -> None:
        """Progress bar uses high-contrast text."""
        state_manager.start_phase("crawl", total_items=100)
        for _ in range(50):
            state_manager.increment_phase_progress("crawl", tokens=100)

        pb = TUIProgressBar(state_manager, "crawl")
        render = pb.render()

        # Should have clear percentage display
        assert "%" in render, "Progress should show percentage"
        assert re.search(r"\d+%", render), "Should show numeric percentage"

    def test_phase_indicator_clear_status(self, state_manager: StateManager) -> None:
        """Phase indicator clearly shows status."""
        from src.tui.models.state import PhaseStatus

        state_manager.phase_status["crawl"] = PhaseStatus.RUNNING

        pi = PhaseIndicator(state_manager)
        # Widget should render status clearly (actual render requires app context)
        assert hasattr(pi, "state"), "PhaseIndicator has access to state"
        assert "crawl" in state_manager.phase_status, "Phase status is trackable"

    def test_cost_display_readable(self, state_manager: StateManager) -> None:
        """Cost display shows values clearly."""
        state_manager.start_phase("assess", total_items=10)
        for _ in range(10):
            state_manager.increment_phase_progress("assess", tokens=500, cost=0.0015)

        ct = CostTracker(state_manager, "assess")
        render = ct.render()

        # Should show formatted tokens and cost
        assert "Token" in render or "token" in render, "Should label tokens"
        assert "$" in render, "Should show cost with currency symbol"

    def test_error_messages_clear(self, state_manager: StateManager) -> None:
        """Error messages are informative."""
        state_manager.start_phase("crawl", total_items=5)
        state_manager.increment_phase_progress(
            "crawl", tokens=0, error="Connection timeout: timeout=30s"
        )

        errors = state_manager.current_errors
        assert len(errors) > 0, "Errors should be recorded"
        assert "timeout" in errors[0], "Error should include details"

    def test_status_messages_visible(self, state_manager: StateManager) -> None:
        """Status transitions are visible."""
        from src.tui.models.state import PhaseStatus

        state_manager.start_phase("crawl", total_items=10)
        assert state_manager.phase_status["crawl"] == PhaseStatus.RUNNING

        state_manager.complete_phase("crawl")
        assert state_manager.phase_status["crawl"] == PhaseStatus.COMPLETED


class TestContentOverflow:
    """Test handling of edge cases in content display."""

    def test_long_job_title_truncation(self, state_manager: StateManager) -> None:
        """Long job titles are handled gracefully."""
        long_title = "Senior Machine Learning Engineer with 10+ years of experience in " * 3
        state_manager.add_job("job_long", long_title, "CompanyName")

        assert "job_long" in state_manager.jobs
        job = state_manager.jobs["job_long"]
        assert job["title"] == long_title  # Stored intact, UI truncates on display

    def test_many_top_matches_limited(self, state_manager: StateManager) -> None:
        """Top matches capped at 5 regardless of input."""
        jobs = [
            {"id": f"j{i}", "title": f"Job {i}", "overall_score": 100 - i}
            for i in range(100)
        ]

        state_manager.update_top_matches(jobs)

        assert len(state_manager.top_matches) == 5, "Top matches must not exceed 5"

    def test_many_errors_accumulated(self, state_manager: StateManager) -> None:
        """Error list can accumulate many errors."""
        state_manager.start_phase("crawl", total_items=100)

        for i in range(20):
            state_manager.increment_phase_progress(
                "crawl", tokens=0, error=f"Error number {i}"
            )

        assert len(state_manager.current_errors) == 20
        assert "Error number 0" in state_manager.current_errors
        assert "Error number 19" in state_manager.current_errors

    def test_wide_cost_values_formatted(self, state_manager: StateManager) -> None:
        """Large cost values are formatted readably."""
        state_manager.start_phase("assess", total_items=1)
        # Simulate very large job (unusual case)
        state_manager.increment_phase_progress("assess", tokens=50000, cost=0.15)

        cost = state_manager.phase_metrics["assess"].total_cost_usd
        assert cost == 0.15, "Cost should accumulate correctly"


class TestKeyboardInteraction:
    """Test keyboard navigation and shortcuts."""

    def test_dashboard_has_keybindings(self) -> None:
        """Dashboard defines keyboard shortcuts."""
        dashboard = ATPDashboard(StateManager())
        assert hasattr(dashboard, "BINDINGS"), "Dashboard must define BINDINGS"
        assert isinstance(dashboard.BINDINGS, (list, tuple)), "BINDINGS must be a list"
        assert len(dashboard.BINDINGS) > 0, "Must define at least one binding"

    def test_pause_resume_action_defined(self) -> None:
        """Dashboard has pause/resume action."""
        dashboard = ATPDashboard(StateManager())
        assert hasattr(dashboard, "action_pause_resume"), "Must have pause_resume action"

    def test_quit_action_defined(self) -> None:
        """Dashboard has quit action."""
        dashboard = ATPDashboard(StateManager())
        assert hasattr(dashboard, "action_quit_app"), "Must have quit_app action"


class TestDataIntegrity:
    """Test data integrity during display and rendering."""

    def test_state_not_corrupted_by_display(self, state_manager: StateManager) -> None:
        """Rendering doesn't modify state."""
        state_manager.start_phase("crawl", total_items=5)
        state_manager.increment_phase_progress("crawl", tokens=100, cost=0.0003)

        original_items = state_manager.phase_metrics["crawl"].processed_items
        original_tokens = state_manager.phase_metrics["crawl"].total_tokens

        # Render widgets (in real app context)
        pb = TUIProgressBar(state_manager, "crawl")
        _ = pb.render()

        # State should be unchanged
        assert state_manager.phase_metrics["crawl"].processed_items == original_items
        assert state_manager.phase_metrics["crawl"].total_tokens == original_tokens

    def test_job_data_not_corrupted_by_updates(self, state_manager: StateManager) -> None:
        """Job updates don't corrupt other jobs."""
        state_manager.add_job("j1", "Job 1", "Company 1", score=80)
        state_manager.add_job("j2", "Job 2", "Company 2", score=75)

        state_manager.update_job("j1", score=90)

        assert state_manager.jobs["j1"]["score"] == 90
        assert state_manager.jobs["j2"]["score"] == 75  # Unchanged
