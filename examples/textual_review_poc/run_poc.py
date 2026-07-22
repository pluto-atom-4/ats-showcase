#!/usr/bin/env python
"""Entry point for Textual review PoC."""

import sys
from pathlib import Path

# Add parent dir to path so we can import review modules
sys.path.insert(0, str(Path(__file__).parent))

from review_poc import main

if __name__ == "__main__":
    main()
