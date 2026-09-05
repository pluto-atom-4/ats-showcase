"""Top-level mirror of technology processor.

This is a convenience re-export of src.poc.tweak.spacy_pipeline.technology_processor,
providing easy top-level access without deep import paths.

The canonical location is: src.poc.tweak.spacy_pipeline.technology_processor

Issue #321: Implement technology processor for batch pipeline.
"""

# Re-export from canonical location
from src.poc.tweak.spacy_pipeline.technology_processor import TechnologyProcessor

__all__ = [
    "TechnologyProcessor",
]
