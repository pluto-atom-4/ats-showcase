"""Top-level mirror of consolidated extraction patterns.

This is a convenience re-export of src.poc.tweak.spacy_pipeline.patterns,
providing easy top-level access without deep import paths.

The canonical location is: src.poc.tweak.spacy_pipeline.patterns

Issue #321: Consolidate patterns for batch processing pipeline.
"""

# Re-export from canonical location
from src.poc.tweak.spacy_pipeline.patterns import REQUIREMENT_PATTERNS, SKILL_VERBS, TECH_TERMS

__all__ = [
    "REQUIREMENT_PATTERNS",
    "SKILL_VERBS",
    "TECH_TERMS",
]
