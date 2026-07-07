"""Job verification and review module for ATS Playground.

This module provides interactive job review capabilities, allowing users to
confirm, reject, or skip jobs before expensive LLM API calls in Phase 4.
"""

from src.verification.reviewer import JobReviewer, ReviewStats

__all__ = ["JobReviewer", "ReviewStats"]
