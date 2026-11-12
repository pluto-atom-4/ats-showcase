"""Pytest configuration and fixtures"""

import sys
import tempfile
from pathlib import Path

import pytest

# Must run at import time, before pytest imports tests; do not move into pytest_configure.
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

_src = _root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


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
    # delete=False: the path must outlive the handle; the OS cleans up after the test.
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        yield tmp.name
