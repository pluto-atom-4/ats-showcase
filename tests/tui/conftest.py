"""Fixtures for TUI tests."""

import pytest

from tui.models.state import StateManager


@pytest.fixture
def state_manager():
    """Provide a fresh StateManager for each test."""
    return StateManager()
