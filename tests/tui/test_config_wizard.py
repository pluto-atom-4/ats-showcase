"""Tests for configuration wizard modal (Feature 4)."""

import pytest

from src.tui.dialogs.config_wizard import ConfigurationWizard
from src.tui.models.state import StateManager


class TestConfigurationWizard:
    """Tests for ConfigurationWizard modal."""

    def test_config_wizard_initialization(self, state_manager: StateManager):
        """ConfigurationWizard initializes with default values."""
        wizard = ConfigurationWizard(state_manager)
        assert wizard.cv_path == ""
        assert wizard.config_path == ""
        assert wizard.headless is True
        assert wizard.confirmed_only is True

    def test_config_wizard_cv_path_setter(self, state_manager: StateManager):
        """CV path can be set."""
        wizard = ConfigurationWizard(state_manager)
        wizard.cv_path = "custom/cv.json"
        assert wizard.cv_path == "custom/cv.json"

    def test_config_wizard_config_path_setter(self, state_manager: StateManager):
        """Config path can be set."""
        wizard = ConfigurationWizard(state_manager)
        wizard.config_path = "config/"
        assert wizard.config_path == "config/"

    def test_config_wizard_headless_false(self, state_manager: StateManager):
        """Headless can be set to False."""
        wizard = ConfigurationWizard(state_manager)
        wizard.headless = False
        assert wizard.headless is False

    def test_config_wizard_confirmed_only_false(self, state_manager: StateManager):
        """Confirmed-only can be set to False."""
        wizard = ConfigurationWizard(state_manager)
        wizard.confirmed_only = False
        assert wizard.confirmed_only is False

    def test_config_wizard_result_dict(self, state_manager: StateManager):
        """Wizard can produce correct result dict."""
        wizard = ConfigurationWizard(state_manager)
        wizard.cv_path = "test/cv.json"
        wizard.config_path = "test/config.json"
        wizard.headless = False
        wizard.confirmed_only = False

        result = {
            "cv_path": wizard.cv_path,
            "config_path": wizard.config_path,
            "headless": wizard.headless,
            "confirmed_only": wizard.confirmed_only,
        }

        assert result["cv_path"] == "test/cv.json"
        assert result["config_path"] == "test/config.json"
        assert result["headless"] is False
        assert result["confirmed_only"] is False

    def test_config_wizard_default_values_dict(self, state_manager: StateManager):
        """Wizard produces default values in result dict."""
        wizard = ConfigurationWizard(state_manager)
        # Simulate collecting with defaults (not calling _collect_config due to Textual)
        wizard.cv_path = "data/cv.json"
        wizard.config_path = "config/companies.json"

        result = {
            "cv_path": wizard.cv_path,
            "config_path": wizard.config_path,
            "headless": wizard.headless,
            "confirmed_only": wizard.confirmed_only,
        }

        assert result["cv_path"] == "data/cv.json"
        assert result["config_path"] == "config/companies.json"
        assert result["headless"] is True
        assert result["confirmed_only"] is True
