"""Top-level mirror of skill processor.

This is a convenience re-export of src.poc.tweak.spacy_pipeline.skill_processor,
providing easy top-level access without deep import paths.

The canonical location is: src.poc.tweak.spacy_pipeline.skill_processor

Issue #321: Implement skill processor for batch pipeline.
"""

# Re-export from canonical location
from src.poc.tweak.spacy_pipeline.skill_processor import SkillProcessor

__all__ = [
    "SkillProcessor",
]
