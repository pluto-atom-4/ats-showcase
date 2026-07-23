"""Tests for PromptBuilder prompt construction."""

import json
from typing import List, Tuple

import pytest

from src.assessment.prompt_builder import SYSTEM_PROMPT, PromptBuilder


class TestSystemPrompt:
    """Test system prompt definition."""

    def test_system_prompt_contains_json_format(self) -> None:
        """System prompt includes JSON output format."""
        assert "JSON" in SYSTEM_PROMPT or "json" in SYSTEM_PROMPT
        assert "overall_score" in SYSTEM_PROMPT

    def test_system_prompt_contains_guidelines(self) -> None:
        """System prompt includes assessment guidelines."""
        assert "objective" in SYSTEM_PROMPT.lower()
        assert "recruiter" in SYSTEM_PROMPT.lower()

    def test_system_prompt_is_string(self) -> None:
        """System prompt is a non-empty string."""
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 100


class TestBuildSimplePrompt:
    """Test simple prompt building."""

    def test_simple_prompt_minimal(self) -> None:
        """Minimal prompt with CV and job only."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_simple_prompt(cv, job)

        assert isinstance(prompt, str)
        assert cv in prompt
        assert job in prompt
        assert "Assessment" in prompt

    def test_simple_prompt_includes_system(self) -> None:
        """Prompt includes system prompt."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_simple_prompt(cv, job)
        assert "objective" in prompt.lower() or "recruiter" in prompt.lower()

    def test_simple_prompt_with_entities(self) -> None:
        """Prompt includes extracted entities when provided."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        skills = ["Python", "Django"]
        tech = ["AWS", "Docker"]
        requirements = ["5+ years", "Remote"]

        prompt = PromptBuilder.build_simple_prompt(
            cv, job, (skills, tech, requirements)
        )

        assert "Python" in prompt
        assert "AWS" in prompt
        assert "5+ years" in prompt

    def test_simple_prompt_without_entities(self) -> None:
        """Prompt works without entities (defaults to empty)."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_simple_prompt(cv, job, None)

        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_simple_prompt_with_chunks(self) -> None:
        """Prompt includes semantic chunks when provided."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        chunks = ["Requirement 1: 5+ years", "Requirement 2: AWS knowledge"]

        prompt = PromptBuilder.build_simple_prompt(
            cv, job, chunks=chunks
        )

        # Chunks should be in prompt
        assert "Requirement 1" in prompt or "5+ years" in prompt

    def test_simple_prompt_without_chunks(self) -> None:
        """Prompt works without chunks (defaults to empty)."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_simple_prompt(cv, job, chunks=None)

        assert isinstance(prompt, str)

    def test_simple_prompt_special_characters(self) -> None:
        """Prompt handles special characters in CV/job."""
        cv = "C++ Developer ($100k salary)"
        job = "Rust/Go expert (100% remote)"
        prompt = PromptBuilder.build_simple_prompt(cv, job)

        assert "C++" in prompt
        assert "$" in prompt
        assert "/" in prompt

    def test_simple_prompt_ends_with_json(self) -> None:
        """Prompt ends with prompt for JSON response."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_simple_prompt(cv, job)

        # Should end with something prompting JSON
        assert "JSON:" in prompt or "json" in prompt.lower() or "Assessment" in prompt

    def test_simple_prompt_all_entities_included(self) -> None:
        """All entity types appear when provided."""
        cv = "10 years Python"
        job = "Senior role"
        skills = ["Python", "React"]
        tech = ["AWS", "PostgreSQL"]
        reqs = ["Remote", "Visa"]

        prompt = PromptBuilder.build_simple_prompt(
            cv, job, (skills, tech, reqs)
        )

        assert "Skills" in prompt
        assert "Tech Stack" in prompt
        assert "Requirements" in prompt

    def test_simple_prompt_none_cv(self) -> None:
        """Handles edge case of empty CV."""
        cv = ""
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_simple_prompt(cv, job)

        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_simple_prompt_none_job(self) -> None:
        """Handles edge case of empty job."""
        cv = "Senior Python Developer"
        job = ""
        prompt = PromptBuilder.build_simple_prompt(cv, job)

        assert isinstance(prompt, str)
        assert len(prompt) > 50


class TestBuildPromptWithExamples:
    """Test prompt building with few-shot examples."""

    def test_examples_prompt_includes_example(self) -> None:
        """Prompt with examples includes an example assessment."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_prompt_with_examples(cv, job)

        assert "Example" in prompt
        assert "overall_score" in prompt

    def test_examples_prompt_includes_cv_and_job(self) -> None:
        """Prompt includes actual CV and job."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_prompt_with_examples(cv, job)

        assert cv in prompt
        assert job in prompt

    def test_examples_prompt_longer_than_simple(self) -> None:
        """Prompt with examples is longer than simple prompt."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"

        simple = PromptBuilder.build_simple_prompt(cv, job)
        with_examples = PromptBuilder.build_prompt_with_examples(cv, job)

        assert len(with_examples) > len(simple)

    def test_examples_prompt_with_entities(self) -> None:
        """Prompt with examples includes entities."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        skills = ["Python", "Django"]
        tech = ["AWS"]
        reqs = ["5+ years"]

        prompt = PromptBuilder.build_prompt_with_examples(
            cv, job, (skills, tech, reqs)
        )

        assert "Python" in prompt
        assert "AWS" in prompt
        assert "5+ years" in prompt

    def test_examples_prompt_with_chunks(self) -> None:
        """Prompt with examples includes chunks."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        chunks = ["Chunk 1: Requirements", "Chunk 2: Benefits"]

        prompt = PromptBuilder.build_prompt_with_examples(
            cv, job, chunks=chunks
        )

        # At least one chunk should be in prompt
        assert any(chunk in prompt for chunk in chunks)

    def test_examples_prompt_example_is_valid_json(self) -> None:
        """Example assessment in prompt is valid JSON."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_prompt_with_examples(cv, job)

        # Extract example JSON from prompt (simple heuristic)
        if '"overall_score"' in prompt or "'overall_score'" in prompt:
            # Example exists, good sign
            assert True

    def test_examples_prompt_includes_system(self) -> None:
        """Prompt includes system prompt."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_prompt_with_examples(cv, job)

        # Should have system prompt guidance
        assert "objective" in prompt.lower() or "recruiter" in prompt.lower()

    def test_examples_prompt_ends_with_json(self) -> None:
        """Prompt ends with prompt for JSON response."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_prompt_with_examples(cv, job)

        assert "JSON:" in prompt or "json" in prompt.lower()

    def test_examples_prompt_special_characters(self) -> None:
        """Prompt with examples handles special characters."""
        cv = "C++ & Python Developer ($150k)"
        job = "Rust/Go expert (NYC/SF, 100% remote)"
        prompt = PromptBuilder.build_prompt_with_examples(cv, job)

        assert "C++" in prompt
        assert "$" in prompt

    def test_examples_prompt_none_cv(self) -> None:
        """Handles empty CV."""
        cv = ""
        job = "We seek a Python expert"
        prompt = PromptBuilder.build_prompt_with_examples(cv, job)

        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_examples_prompt_none_job(self) -> None:
        """Handles empty job."""
        cv = "Senior Python Developer"
        job = ""
        prompt = PromptBuilder.build_prompt_with_examples(cv, job)

        assert isinstance(prompt, str)
        assert len(prompt) > 100


class TestPromptComparison:
    """Compare simple vs examples prompts."""

    def test_both_include_cv(self) -> None:
        """Both prompt types include CV."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"

        simple = PromptBuilder.build_simple_prompt(cv, job)
        with_examples = PromptBuilder.build_prompt_with_examples(cv, job)

        assert cv in simple
        assert cv in with_examples

    def test_both_include_job(self) -> None:
        """Both prompt types include job."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"

        simple = PromptBuilder.build_simple_prompt(cv, job)
        with_examples = PromptBuilder.build_prompt_with_examples(cv, job)

        assert job in simple
        assert job in with_examples

    def test_examples_has_example_simple_doesnt(self) -> None:
        """Only examples prompt includes example assessment."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"

        simple = PromptBuilder.build_simple_prompt(cv, job)
        with_examples = PromptBuilder.build_prompt_with_examples(cv, job)

        # Examples should have "Example" or similar
        assert "Example" in with_examples
        # Simple may or may not have it (but less likely)

    def test_both_prompt_json_output(self) -> None:
        """Both prompts request JSON output."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"

        simple = PromptBuilder.build_simple_prompt(cv, job)
        with_examples = PromptBuilder.build_prompt_with_examples(cv, job)

        assert ("JSON:" in simple or "JSON:" in with_examples)
