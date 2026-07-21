"""Interactive job review dialog for approval/rejection during crawl phase."""

from typing import Any, Dict, Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from src.tui.utils.formatters import truncate


class JobReviewDialog(ModalScreen):
    """Modal dialog for user to approve/reject/skip extracted job.

    Shows:
    - Job title, company, location
    - Clean text preview (first 500 chars)
    - Buttons: Confirm, Reject, Skip

    User decision saved to StateManager.jobs[job_id]["status"].
    """

    CSS = """
    JobReviewDialog {
        align: center middle;
    }

    #job-review-box {
        width: 80;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #job-info {
        width: 1fr;
        height: auto;
        padding: 0 0 1 0;
    }

    #preview {
        width: 1fr;
        height: auto;
        border-top: solid $accent;
        padding: 1 0;
        margin: 1 0;
    }

    #buttons {
        width: 1fr;
        height: auto;
        border-top: solid $accent;
        padding: 1 0 0 0;
        layout: horizontal;
    }

    Button {
        margin: 0 1;
    }

    #footer-help {
        width: 1fr;
        height: auto;
        border-top: solid $accent;
        padding: 1 0;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, job_id: str, job_data: Dict[str, Any]):
        super().__init__()
        self.job_id = job_id
        self.job_data = job_data
        self.decision: Optional[str] = None  # "confirm" | "reject" | "skip"

    def on_mount(self) -> None:
        """Set focus to first button after compose completes."""
        self.call_later(self._set_focus)

    def _set_focus(self) -> None:
        """Set focus to confirm button (called after compose)."""
        try:
            confirm_btn = self.query_one("#confirm", Button)
            confirm_btn.focus()
        except Exception:
            # If focus fails, let Textual handle default focus
            pass

    def compose(self) -> ComposeResult:
        """Render job review dialog."""
        with Container(id="job-review-box"):
            with Static(id="job-info"):
                yield Static(
                    f"[b]Job Review[/b]\n"
                    f"Title: {self.job_data.get('title', 'Unknown')}\n"
                    f"Company: {self.job_data.get('company', 'Unknown')}\n"
                    f"Location: {self.job_data.get('location', 'Unknown')}"
                )

            preview_text = self.job_data.get("clean_text", "")
            if not preview_text:
                preview_text = self.job_data.get("description", "")
            preview = truncate(preview_text, max_len=500)

            yield Static(preview, id="preview")

            with Horizontal(id="buttons"):
                yield Button("Confirm", id="confirm", variant="primary")
                yield Button("Reject", id="reject", variant="error")
                yield Button("Skip", id="skip", variant="warning")

            yield Static("esc=Cancel", id="footer-help")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "confirm":
            self.decision = "confirm"
        elif event.button.id == "reject":
            self.decision = "reject"
        elif event.button.id == "skip":
            self.decision = "skip"

        self.dismiss(self.decision)

    def action_quit_dialog(self) -> None:
        """Close dialog without decision (escape key)."""
        self.dismiss(None)

    BINDINGS = [
        ("escape", "quit_dialog", "Cancel"),
    ]
