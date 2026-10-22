"""Extraction outcome classification for processed jobs (Issue #737, Part of #735).

Replaces the misleading binary ``Status: SUCCESS`` in ``batch_processor.print_summary()``,
which only reflects the absence of pipeline-stage exceptions. This module classifies a
job by whether extraction actually produced output and whether the input looks like a
real job description.

Thresholds are hardcoded defaults. They are overridable only through keyword arguments
(which Spec 3 wires to CLI flags); there is no environment-variable override.
"""

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.poc.tweak.batch_processor import JobResult


class ExtractionOutcome(str, Enum):
    """Outcome status for a single job's extraction run.

    Values:
        COMPLETE: No stage errors and at least one of requirements/skills/technologies extracted.
        NEEDS_HUMAN_REVIEW: No stage errors, zero extraction yield, but the input has real
            content (enough sections and stripped text length). The pipeline could not parse it.
        LIKELY_UNPARSEABLE_INPUT: Zero extraction yield and the input looks like a shell or
            boilerplate page (too few sections or too little stripped text). Points at the crawler.
        ERROR: A pipeline stage raised an error.
    """

    COMPLETE = "complete"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    LIKELY_UNPARSEABLE_INPUT = "likely_unparseable_input"
    ERROR = "error"


# Hardcoded defaults. Tunable via keyword-only arguments of classify_extraction_outcome().
MIN_SECTIONS_FOR_REAL_JD = 5
MIN_DESCRIPTION_CHARS = 800
# Consumed by the fallback extraction spec (Spec 4), not by classify_extraction_outcome().
FALLBACK_MIN_SECTION_CONFIDENCE = 0.45


def classify_extraction_outcome(
    job_result: "JobResult",
    stripped_text_len: int,
    *,
    min_sections: int = MIN_SECTIONS_FOR_REAL_JD,
    min_description_chars: int = MIN_DESCRIPTION_CHARS,
) -> ExtractionOutcome:
    """Classify the extraction outcome of a processed job.

    Evaluation order (first match wins):
        1. Any pipeline-stage error -> ERROR.
        2. Any requirements/skills/technologies extracted -> COMPLETE.
        3. Too few sections or too little stripped text -> LIKELY_UNPARSEABLE_INPUT.
        4. Otherwise -> NEEDS_HUMAN_REVIEW.

    Args:
        job_result: Result of processing a single job.
        stripped_text_len: Length of the job's text after HTML/markdown stripping.
        min_sections: Minimum detected sections for the input to count as a real JD.
        min_description_chars: Minimum stripped text length for the input to count as a real JD.

    Returns:
        The ExtractionOutcome for this job.
    """
    if job_result.errors:
        return ExtractionOutcome.ERROR

    yield_count = len(job_result.requirements) + len(job_result.skills) + len(job_result.technologies)
    if yield_count > 0:
        return ExtractionOutcome.COMPLETE

    if job_result.sections_detected < min_sections or stripped_text_len < min_description_chars:
        return ExtractionOutcome.LIKELY_UNPARSEABLE_INPUT

    return ExtractionOutcome.NEEDS_HUMAN_REVIEW
