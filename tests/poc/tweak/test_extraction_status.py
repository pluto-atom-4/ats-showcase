"""Tests for extraction_status.py ExtractionOutcome and classify_extraction_outcome (Issue #737).

Regression numbers come from the reference 11-job sample in
docs/dev-note/jd-zero-extraction-fallback.md section 1.0:
- Blue Origin and Walmart shell rows: sections=4, stripped text ~460 chars, zero yield.
- UW jobs 1/2 and Walmart job 9: real content, zero skills/technology yield.
"""

import pytest

from src.poc.tweak.batch_processor import JobResult
from src.poc.tweak.extraction_status import (
    FALLBACK_MIN_SECTION_CONFIDENCE,
    MIN_DESCRIPTION_CHARS,
    MIN_SECTIONS_FOR_REAL_JD,
    ExtractionOutcome,
    classify_extraction_outcome,
)

SHELL_STRIPPED_CHARS = 460
REAL_CONTENT_CHARS = 2400


def make_job_result(
    sections_detected: int,
    *,
    requirements: int = 0,
    skills: int = 0,
    technologies: int = 0,
    errors: list[tuple[str, str]] | None = None,
) -> JobResult:
    """Build a JobResult with the given section count and extraction yield."""
    return JobResult(
        job_id="job-1",
        title="Software Engineer",
        company="Acme",
        sections_detected=sections_detected,
        keyword_matches=0,
        confidence_min=0.2,
        confidence_max=0.3,
        confidence_avg=0.25,
        requirements=[{"text": "r"} for _ in range(requirements)],
        skills=[{"text": "s"} for _ in range(skills)],
        technologies=[{"text": "t"} for _ in range(technologies)],
        errors=errors or [],
    )


class TestExtractionOutcomeEnum:
    """Tests for the ExtractionOutcome enum values."""

    def test_has_exactly_four_states(self):
        assert len(ExtractionOutcome) == 4

    @pytest.mark.parametrize(
        "member, value",
        [
            (ExtractionOutcome.COMPLETE, "complete"),
            (ExtractionOutcome.NEEDS_HUMAN_REVIEW, "needs_human_review"),
            (ExtractionOutcome.LIKELY_UNPARSEABLE_INPUT, "likely_unparseable_input"),
            (ExtractionOutcome.ERROR, "error"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value
        assert ExtractionOutcome(value) is member

    def test_is_str_subclass(self):
        assert isinstance(ExtractionOutcome.COMPLETE, str)


class TestDefaultConstants:
    """Tests for the hardcoded default thresholds."""

    def test_default_values(self):
        assert MIN_SECTIONS_FOR_REAL_JD == 5
        assert MIN_DESCRIPTION_CHARS == 800
        assert FALLBACK_MIN_SECTION_CONFIDENCE == 0.45


class TestClassifyError:
    """ERROR is returned whenever a pipeline stage recorded an error."""

    def test_error_with_no_yield_is_error(self):
        result = make_job_result(24, errors=[("converter", "boom")])
        assert classify_extraction_outcome(result, REAL_CONTENT_CHARS) is ExtractionOutcome.ERROR

    def test_error_takes_precedence_over_yield(self):
        result = make_job_result(24, skills=3, errors=[("skills", "boom")])
        assert classify_extraction_outcome(result, REAL_CONTENT_CHARS) is ExtractionOutcome.ERROR

    def test_error_takes_precedence_over_shell_input(self):
        result = make_job_result(4, errors=[("preprocessor", "boom")])
        assert classify_extraction_outcome(result, SHELL_STRIPPED_CHARS) is ExtractionOutcome.ERROR


class TestClassifyComplete:
    """COMPLETE requires no errors and nonzero yield in any category."""

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"requirements": 1},
            {"skills": 1},
            {"technologies": 1},
            {"requirements": 9, "skills": 2, "technologies": 4},
        ],
    )
    def test_any_nonzero_yield_is_complete(self, kwargs):
        result = make_job_result(24, **kwargs)
        assert classify_extraction_outcome(result, REAL_CONTENT_CHARS) is ExtractionOutcome.COMPLETE

    def test_partial_yield_on_shell_like_input_is_complete(self):
        # Yield wins: if anything was extracted, the input is not treated as unparseable.
        result = make_job_result(4, skills=2)
        assert classify_extraction_outcome(result, SHELL_STRIPPED_CHARS) is ExtractionOutcome.COMPLETE


class TestClassifyLikelyUnparseable:
    """Zero yield with a shell-like input (few sections or short stripped text)."""

    def test_blue_origin_shell_row_is_unparseable(self):
        # Reference: sections=4, stripped ~460 chars, zero yield.
        result = make_job_result(4)
        outcome = classify_extraction_outcome(result, SHELL_STRIPPED_CHARS)
        assert outcome is ExtractionOutcome.LIKELY_UNPARSEABLE_INPUT

    def test_walmart_shell_row_is_unparseable(self):
        # Walmart rows 6,7,8,10,11 share the same shell capture: sections=4, zero yield.
        result = make_job_result(4)
        outcome = classify_extraction_outcome(result, 459)
        assert outcome is ExtractionOutcome.LIKELY_UNPARSEABLE_INPUT

    def test_short_stripped_text_alone_is_unparseable(self):
        result = make_job_result(10)
        outcome = classify_extraction_outcome(result, MIN_DESCRIPTION_CHARS - 1)
        assert outcome is ExtractionOutcome.LIKELY_UNPARSEABLE_INPUT

    def test_too_few_sections_alone_is_unparseable(self):
        result = make_job_result(MIN_SECTIONS_FOR_REAL_JD - 1)
        outcome = classify_extraction_outcome(result, REAL_CONTENT_CHARS)
        assert outcome is ExtractionOutcome.LIKELY_UNPARSEABLE_INPUT

    def test_zero_sections_is_unparseable(self):
        result = make_job_result(0)
        assert classify_extraction_outcome(result, 0) is ExtractionOutcome.LIKELY_UNPARSEABLE_INPUT


class TestClassifyNeedsHumanReview:
    """Zero yield with real content (enough sections and stripped text)."""

    def test_uw_job_zero_yield_needs_review(self):
        # Reference: UW jobs 1/2 have 24/20 sections and real content, zero skills/tech yield.
        result = make_job_result(24)
        outcome = classify_extraction_outcome(result, REAL_CONTENT_CHARS)
        assert outcome is ExtractionOutcome.NEEDS_HUMAN_REVIEW

    def test_uw_job_2_zero_yield_needs_review(self):
        result = make_job_result(20)
        outcome = classify_extraction_outcome(result, REAL_CONTENT_CHARS)
        assert outcome is ExtractionOutcome.NEEDS_HUMAN_REVIEW

    def test_walmart_job_9_zero_yield_needs_review(self):
        # Reference: Walmart job 9 has 7 sections, dense skill/tech text, zero yield.
        result = make_job_result(7)
        outcome = classify_extraction_outcome(result, REAL_CONTENT_CHARS)
        assert outcome is ExtractionOutcome.NEEDS_HUMAN_REVIEW

    def test_exact_thresholds_are_real_content(self):
        result = make_job_result(MIN_SECTIONS_FOR_REAL_JD)
        outcome = classify_extraction_outcome(result, MIN_DESCRIPTION_CHARS)
        assert outcome is ExtractionOutcome.NEEDS_HUMAN_REVIEW


class TestKeywordOverrides:
    """min_sections and min_description_chars are keyword-only overrides."""

    def test_min_sections_override_makes_shell_row_real(self):
        # With min_sections lowered to 4, a sections=4 row with long text is real content.
        result = make_job_result(4)
        outcome = classify_extraction_outcome(result, REAL_CONTENT_CHARS, min_sections=4)
        assert outcome is ExtractionOutcome.NEEDS_HUMAN_REVIEW

    def test_min_sections_override_makes_real_row_unparseable(self):
        result = make_job_result(24)
        outcome = classify_extraction_outcome(result, REAL_CONTENT_CHARS, min_sections=25)
        assert outcome is ExtractionOutcome.LIKELY_UNPARSEABLE_INPUT

    def test_min_description_chars_override_makes_shell_row_real(self):
        # Lowering the char threshold below 460 turns the shell row into real content.
        result = make_job_result(4)
        outcome = classify_extraction_outcome(result, SHELL_STRIPPED_CHARS, min_sections=4, min_description_chars=400)
        assert outcome is ExtractionOutcome.NEEDS_HUMAN_REVIEW

    def test_min_description_chars_override_makes_real_row_unparseable(self):
        result = make_job_result(24)
        outcome = classify_extraction_outcome(result, REAL_CONTENT_CHARS, min_description_chars=REAL_CONTENT_CHARS + 1)
        assert outcome is ExtractionOutcome.LIKELY_UNPARSEABLE_INPUT

    def test_overrides_do_not_affect_complete_or_error(self):
        complete = make_job_result(1, skills=1)
        error = make_job_result(24, errors=[("x", "y")])
        assert (
            classify_extraction_outcome(complete, 0, min_sections=99, min_description_chars=99999)
            is ExtractionOutcome.COMPLETE
        )
        assert (
            classify_extraction_outcome(error, REAL_CONTENT_CHARS, min_sections=0, min_description_chars=0)
            is ExtractionOutcome.ERROR
        )

    def test_thresholds_are_keyword_only(self):
        result = make_job_result(24)
        with pytest.raises(TypeError):
            classify_extraction_outcome(result, REAL_CONTENT_CHARS, 4)  # type: ignore[misc]
