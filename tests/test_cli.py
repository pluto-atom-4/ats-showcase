"""Tests for src.cli helper functions.

Focused on `_preprocess_single_job`, which maps a raw crawled job dict into
a `PreprocessedJob`. Issue #195 / Phase 8 added `title` and
`markdown_description` field mapping so downstream consumers (export,
query, TUI job table) don't have to re-parse them out of `clean_text`.
"""

from src.cli import _preprocess_single_job
from src.tokenization.chunker import SemanticChunker
from src.tokenization.counter import TokenCounter
from src.tokenization.preprocessor import Preprocessor


class TestPreprocessSingleJobFieldMapping:
    """Verify title / markdown_description are correctly mapped onto PreprocessedJob."""

    def test_title_and_markdown_description_mapped(self) -> None:
        job_dict = {
            "title": "Senior Python Developer",
            "company": "Acme Corp",
            "location": "Remote",
            "description": (
                "# Senior Python Developer\n\nWe need a strong backend engineer with Python and FastAPI experience."
            ),
            "requirements": ["Python", "FastAPI"],
        }

        chunker = SemanticChunker()
        counter = TokenCounter()
        preprocessor = Preprocessor()

        result = _preprocess_single_job(
            job_dict=job_dict,
            chunker=chunker,
            counter=counter,
            preprocessor=preprocessor,
            pricing_date="2026-07-18",
            show_estimates=False,
            job_index=1,
        )

        assert result is not None
        preprocessed, token_count, estimated_cost, trigger_requirements = result

        assert preprocessed.title == job_dict["title"]
        assert job_dict["title"] in preprocessed.markdown_description
        assert job_dict["location"] in preprocessed.markdown_description
        assert token_count > 0
        assert estimated_cost >= 0

    def test_returns_none_on_missing_required_field(self) -> None:
        """Invalid job dict (missing required JobPosting fields) fails gracefully."""
        job_dict = {"title": "Incomplete Job"}

        chunker = SemanticChunker()
        counter = TokenCounter()
        preprocessor = Preprocessor()

        result = _preprocess_single_job(
            job_dict=job_dict,
            chunker=chunker,
            counter=counter,
            preprocessor=preprocessor,
            pricing_date="2026-07-18",
            show_estimates=False,
            job_index=1,
        )

        assert result is None
