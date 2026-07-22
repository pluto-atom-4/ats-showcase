"""Minimal ModalScreen for job review (deferred focus management)."""

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ReviewDialog(ModalScreen):
    """Modal dialog for job review decision.

    Key pattern: Deferred focus via call_later in on_mount().
    Ensures buttons are mounted before focus() is called.
    """

    CSS = """
    ReviewDialog {
        align: center middle;
    }

    #dialog-box {
        width: 70;
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

    #description {
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
    """

    def __init__(self, job_id: str, title: str, company: str, description: str):
        super().__init__()
        self.job_id = job_id
        self.title = title
        self.company = company
        self.description = description
        self.decision: Optional[str] = None

    def on_mount(self) -> None:
        """Deferred focus: call_later ensures widgets are fully mounted."""
        self.call_later(self._set_focus)

    def _set_focus(self) -> None:
        """Set focus to confirm button (deferred until after compose)."""
        try:
            confirm_btn = self.query_one("#confirm", Button)
            confirm_btn.focus()
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        """Build dialog UI."""
        with Vertical(id="dialog-box"):
            with Static(id="job-info"):
                yield Static(
                    f"[b]Job Review[/b]\n"
                    f"Title: {self.title}\n"
                    f"Company: {self.company}"
                )

            yield Static(
                self.description[:300] + ("..." if len(self.description) > 300 else ""),
                id="description",
            )

            with Horizontal(id="buttons"):
                yield Button("Confirm", id="confirm", variant="primary")
                yield Button("Reject", id="reject", variant="error")
                yield Button("Skip", id="skip", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses (Tab + Enter workflow)."""
        if event.button.id == "confirm":
            self.decision = "confirm"
        elif event.button.id == "reject":
            self.decision = "reject"
        elif event.button.id == "skip":
            self.decision = "skip"

        self.dismiss(self.decision)

    def action_quit_dialog(self) -> None:
        """Escape key: dismiss without decision."""
        self.dismiss(None)

    BINDINGS = [
        ("escape", "quit_dialog", "Cancel"),
    ]
