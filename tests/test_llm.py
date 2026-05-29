"""Tests for LLM client and prompts."""

import pytest

from llm.prompts import get_assessment_prompt, get_prompt


@pytest.mark.unit
def test_assessment_prompt():
    """Test assessment prompt generation."""
    prompt = get_assessment_prompt()
    assert "expert" in prompt.lower()
    assert "score" in prompt.lower()


@pytest.mark.unit
def test_personalized_assessment_prompt():
    """Test assessment prompt with CV summary."""
    cv_summary = "Python developer with 5 years experience"
    prompt = get_assessment_prompt(cv_summary=cv_summary)
    assert cv_summary in prompt


@pytest.mark.unit
def test_get_prompt():
    """Test prompt retrieval."""
    assessment = get_prompt("assessment")
    extraction = get_prompt("extraction")
    summary = get_prompt("summary")

    assert len(assessment) > 0
    assert len(extraction) > 0
    assert len(summary) > 0


@pytest.mark.unit
def test_invalid_prompt_type():
    """Test error handling for invalid prompt type."""
    with pytest.raises(ValueError):
        get_prompt("invalid_prompt_type")
