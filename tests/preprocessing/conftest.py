"""Conftest for preprocessing tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Setup sys.path for parity_check import (before any test file imports it)
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
