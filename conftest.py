"""Root-level pytest configuration - ensures sys.path is correct before ANY imports"""

import sys
from pathlib import Path

# CRITICAL: Root-level conftest.py is discovered and executed by pytest FIRST
# This runs at module level before pytest tries to import ANY test modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))
