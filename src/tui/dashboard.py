"""Main TUI Dashboard for ATS Playground workflow orchestration."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from .models.state import PhaseStatus, StateManager
from .panels.assess_panel import AssessPanel
from .panels.crawl_panel import CrawlPanel
from .panels.export_panel import ExportPanel
from .panels.preprocess_panel import PreprocessPanel
from .widgets.phase_indicator import PhaseIndicator


class HeaderPanel(Static):
    """Header showing overall workflow status and cost."""

    def __init__(self, state: StateManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = state

    def render(self) -> str:
        """Render header with workflow status and total cost."""
        from src.tui.utils.formatters import format_cost, format_tokens

        title = "🎯 ATS Playground - Workflow Dashboard"
        tokens = format_tokens(self.state.total_tokens_used)
        cost = format_cost(self.state.total_cost_usd)

        return f"{title}\nTokens: {tokens} | Total Cost: {cost}"


class ATPDashboard(Screen):
    """
    Main TUI Dashboard for ATS Playground workflow.

    Layout:
    ┌─────────────────────────────────────┐
    │  Header: Workflow Status, Total Cost │
    ├─────────────────────────────────────┤
    │  Phase Indicator (✓ ⏳ ⚪ ⚪)        │
    ├─────────────────────────────────────┤
    │                                       │
    │  Active Panel (Crawl/Prep/Assess/Exp)│
    │                                       │
    ├─────────────────────────────────────┤
    │ [p]ause [r]esume [q]uit               │
    └─────────────────────────────────────┘
    """

    CSS = """
    Screen {
        layout: vertical;
    }

    #header {
        height: 3;
        border: solid $primary;
    }

    #phase-indicator {
        height: 1;
        background: $boost;
    }

    #content {
        height: 1fr;
        border: solid $primary;
    }

    #footer {
        height: 1;
        background: $boost;
    }
    """

    BINDINGS = [
        ("p", "pause_resume", "Pause/Resume"),
        ("r", "resume_workflow", "Resume"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(self, state: StateManager):
        super().__init__()
        self.state = state
        self.title = "ATS Playground - TUI Dashboard"
        self.current_phase = "crawl"

    def compose(self) -> ComposeResult:
        """Render dashboard layout."""
        yield HeaderPanel(self.state, id="header")
        yield PhaseIndicator(self.state, id="phase-indicator")

        with Vertical(id="content"):
            yield CrawlPanel(self.state, id="crawl-panel")
            yield PreprocessPanel(self.state, id="preprocess-panel", visible=False)
            yield AssessPanel(self.state, id="assess-panel", visible=False)
            yield ExportPanel(self.state, id="export-panel", visible=False)

        yield Static("[p]ause [r]esume [q]uit", id="footer")

    def _show_panel(self, panel_id: str) -> None:
        """Show one panel, hide others."""
        for panel_name in [
            "crawl-panel",
            "preprocess-panel",
            "assess-panel",
            "export-panel",
        ]:
            panel = self.query_one(f"#{panel_name}")
            panel.visible = panel_name == panel_id

    def action_pause_resume(self) -> None:
        """Toggle pause on workflow."""
        self.state.paused = not self.state.paused
        verb = "Paused" if self.state.paused else "Resumed"
        self.notify(f"{verb} workflow")

    def action_resume_workflow(self) -> None:
        """Resume from pause."""
        if self.state.paused:
            self.state.paused = False
            self.notify("Resumed workflow")

    def action_quit_app(self) -> None:
        """Exit dashboard."""
        if any(
            s == PhaseStatus.RUNNING for s in self.state.phase_status.values()
        ):
            self.notify("Workflow still running. Press [p] to pause first.")
        else:
            self.app.exit()
