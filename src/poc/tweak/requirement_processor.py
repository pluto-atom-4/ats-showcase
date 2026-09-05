"""Top-level mirror of requirement processor.

This is a convenience re-export of src.poc.tweak.spacy_pipeline.requirement_processor,
providing easy top-level access without deep import paths.

The canonical location is: src.poc.tweak.spacy_pipeline.requirement_processor

Issue #321: Implement requirement processor for batch pipeline.
"""

# Re-export from canonical location
from src.poc.tweak.spacy_pipeline.requirement_processor import RequirementProcessor

__all__ = [
    "RequirementProcessor",
]
