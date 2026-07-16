"""Configuration wizard modal for setting up workflow parameters."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from src.tui.models.state import StateManager


class ConfigurationWizard(ModalScreen[dict[str, Any]]):
    """Interactive configuration wizard for workflow setup.

    Allows users to input:
    - CV file path
    - Config file or config directory
    - Headless mode toggle
    - Confirmed-only toggle
    """

    CSS = """
    ConfigurationWizard {
        align: center middle;
    }

    ConfigurationWizard > Vertical {
        width: 60;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    ConfigurationWizard Label {
        margin: 1 0 0 0;
    }

    ConfigurationWizard Input {
        margin: 0 0 1 0;
    }

    ConfigurationWizard #buttons {
        margin: 1 0 0 0;
        height: auto;
    }

    ConfigurationWizard Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(self, state: StateManager):
        super().__init__()
        self.state = state
        self.cv_path: str = ""
        self.config_path: str = ""
        self.headless: bool = True
        self.confirmed_only: bool = True

    def compose(self) -> ComposeResult:
        """Render configuration wizard form."""
        with Vertical():
            yield Label("[bold]Workflow Configuration[/bold]")

            yield Label("CV File Path:")
            yield Input(
                placeholder="data/cv.json",
                id="cv-input",
            )

            yield Label("Config File:")
            yield Input(
                placeholder="config/companies.json or config/",
                id="config-input",
            )

            yield Label("Run in headless mode? (y/n):")
            yield Input(
                placeholder="y (default)",
                id="headless-input",
            )

            yield Label("Only assess confirmed jobs? (y/n):")
            yield Input(
                placeholder="y (default)",
                id="confirmed-only-input",
            )

            with Horizontal(id="buttons"):
                yield Button("Start Workflow", id="start-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "start-btn":
            self._collect_config()
            self.dismiss(
                {
                    "cv_path": self.cv_path,
                    "config_path": self.config_path,
                    "headless": self.headless,
                    "confirmed_only": self.confirmed_only,
                }
            )
        elif event.button.id == "cancel-btn":
            self.dismiss(None)

    def _collect_config(self) -> None:
        """Collect configuration from input fields."""
        cv_input = self.query_one("#cv-input", Input)
        config_input = self.query_one("#config-input", Input)
        headless_input = self.query_one("#headless-input", Input)
        confirmed_only_input = self.query_one("#confirmed-only-input", Input)

        self.cv_path = cv_input.value or "data/cv.json"
        self.config_path = config_input.value or "config/companies.json"
        self.headless = headless_input.value.lower() != "n"
        self.confirmed_only = confirmed_only_input.value.lower() != "n"
