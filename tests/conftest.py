"""Pytest configuration and fixtures"""

import sys
import tempfile
from pathlib import Path

import pytest

# CRITICAL: Add paths at import time (module level) before pytest imports tests
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

_src = _root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


# Also register with pytest's session configure hook as backup
def pytest_configure(config):
    """Pytest hook: runs before test collection"""
    root = Path(__file__).parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


@pytest.fixture
def temp_db():
    """Fixture providing a temporary database path for tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        yield tmp.name
    # Cleanup is handled by OS after test completes
