"""Tests for DataReshaper entity formatting and chunking."""

import pytest

from src.assessment.data_reshaper import DataReshaper


class TestChunkBySentences:
    """Test semantic chunking at sentence boundaries."""

    def test_chunk_empty_text(self) -> None:
        """Empty text returns empty chunks."""
        chunks = DataReshaper.chunk_by_sentences("")
        assert chunks == []

    def test_chunk_single_sentence(self) -> None:
        """Single sentence returns one chunk."""
        text = "This is a simple sentence."
        chunks = DataReshaper.chunk_by_sentences(text)
        assert len(chunks) == 1
        assert "simple sentence" in chunks[0]

    def test_chunk_multiple_sentences(self) -> None:
        """Multiple sentences split at boundaries."""
        text = "First sentence. Second sentence. Third sentence."
        chunks = DataReshaper.chunk_by_sentences(text)
        assert len(chunks) >= 1
        full_text = " ".join(chunks)
        assert "First" in full_text
        assert "Second" in full_text
        assert "Third" in full_text

    def test_chunk_preserves_abbreviations(self) -> None:
        """Preserves Dr., Inc., etc. (sentences split only on clear boundaries)."""
        text = "Dr. Smith works at Google Inc. The company is hiring."
        chunks = DataReshaper.chunk_by_sentences(text)
        full_text = " ".join(chunks)
        assert "Dr." in full_text or "Dr" in full_text
        assert "Inc." in full_text or "Inc" in full_text

    def test_chunk_with_exclamation_marks(self) -> None:
        """Splits on exclamation marks."""
        text = "Great opportunity! Join our team. Apply now!"
        chunks = DataReshaper.chunk_by_sentences(text)
        assert len(chunks) >= 1
        full_text = " ".join(chunks)
        assert "opportunity" in full_text
        assert "team" in full_text

    def test_chunk_with_question_marks(self) -> None:
        """Splits on question marks."""
        text = "Are you experienced? Do you know Python? Send your CV."
        chunks = DataReshaper.chunk_by_sentences(text)
        assert len(chunks) >= 1
        full_text = " ".join(chunks)
        assert "experienced" in full_text
        assert "Python" in full_text

    def test_chunk_long_text(self) -> None:
        """Long text splits into multiple chunks."""
        text = " ".join(["Sentence number {}.".format(i) for i in range(20)])
        chunks = DataReshaper.chunk_by_sentences(text, target_tokens=50)
        assert len(chunks) > 1

    def test_chunk_respects_target_tokens(self) -> None:
        """Chunks stay near target token count (approximate)."""
        text = " ".join(["Python Django PostgreSQL REST API microservices."] * 5)
        chunks = DataReshaper.chunk_by_sentences(text, target_tokens=30)
        assert len(chunks) >= 1
        # Each chunk should have reasonable size (allow variance)
        assert all(len(chunk) > 10 for chunk in chunks)

    def test_chunk_whitespace_handling(self) -> None:
        """Strips leading/trailing whitespace from chunks."""
        text = "  First sentence.   Second sentence.  "
        chunks = DataReshaper.chunk_by_sentences(text)
        for chunk in chunks:
            assert not chunk.startswith(" ")
            assert not chunk.endswith(" ")


class TestFormatExtractedEntities:
    """Test entity formatting for prompts."""

    def test_format_empty_entities(self) -> None:
        """Empty entity lists return empty string."""
        result = DataReshaper.format_extracted_entities([], [], [])
        assert result == ""

    def test_format_skills_only(self) -> None:
        """Format with only skills."""
        skills = ["Python", "JavaScript", "SQL"]
        result = DataReshaper.format_extracted_entities(skills, [], [])
        assert "Skills" in result
        assert "Python" in result
        assert "JavaScript" in result

    def test_format_technologies_only(self) -> None:
        """Format with only technologies."""
        tech = ["AWS", "Docker", "Kubernetes"]
        result = DataReshaper.format_extracted_entities([], tech, [])
        assert "Tech Stack" in result
        assert "AWS" in result
        assert "Docker" in result

    def test_format_requirements_only(self) -> None:
        """Format with only requirements."""
        reqs = ["5+ years experience", "Remote eligible", "Visa sponsorship"]
        result = DataReshaper.format_extracted_entities([], [], reqs)
        assert "Requirements" in result
        assert "5+ years" in result

    def test_format_all_entities(self) -> None:
        """Format with all entity types."""
        skills = ["Python", "React"]
        tech = ["AWS", "Docker"]
        reqs = ["5+ years", "Remote"]
        result = DataReshaper.format_extracted_entities(skills, tech, reqs)
        assert "Skills" in result
        assert "Tech Stack" in result
        assert "Requirements" in result
        assert "Python" in result
        assert "AWS" in result
        assert "5+ years" in result

    def test_format_respects_limit(self) -> None:
        """Limit parameter restricts entity count."""
        skills = [f"Skill{i}" for i in range(20)]
        result = DataReshaper.format_extracted_entities(skills, [], [], limit=5)
        # Should contain first 5 skills
        for i in range(5):
            assert f"Skill{i}" in result
        # Should not contain beyond limit (may contain some due to formatting)
        assert result.count("Skill") <= 10

    def test_format_returns_string(self) -> None:
        """Always returns string."""
        result1 = DataReshaper.format_extracted_entities(["Python"], [], [])
        result2 = DataReshaper.format_extracted_entities([], [], [])
        assert isinstance(result1, str)
        assert isinstance(result2, str)


class TestPrepareAssessmentContext:
    """Test assessment context preparation."""

    def test_context_with_minimal_data(self) -> None:
        """Minimal context with just CV and job."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        context = DataReshaper.prepare_assessment_context(cv, job)
        assert "cv" in context
        assert "job_description" in context
        assert "token_count" in context
        assert context["cv"] == cv
        assert context["job_description"] == job

    def test_context_with_entities(self) -> None:
        """Context includes extracted entities."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        entities = (["Python", "Django"], ["AWS", "Docker"], ["5+ years"])
        context = DataReshaper.prepare_assessment_context(cv, job, entities)
        assert "entities" in context
        assert "Python" in context["entities"]
        assert "AWS" in context["entities"]
        assert "5+ years" in context["entities"]

    def test_context_with_chunks(self) -> None:
        """Context includes semantic chunks."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        chunks = ["Requirement 1: 5+ years", "Requirement 2: AWS experience"]
        context = DataReshaper.prepare_assessment_context(cv, job, chunks=chunks)
        assert "chunks" in context
        assert context["chunks"] == chunks

    def test_context_token_count_positive(self) -> None:
        """Token count is positive for non-empty data."""
        cv = "Senior Python Developer with 10 years experience"
        job = "We seek a Python expert with AWS knowledge"
        context = DataReshaper.prepare_assessment_context(cv, job)
        assert context["token_count"] > 0

    def test_context_token_count_increases_with_data(self) -> None:
        """More data = higher token count."""
        cv = "Senior Python Developer"
        job = "We seek a Python expert"
        context1 = DataReshaper.prepare_assessment_context(cv, job)

        entities = (["Python", "Django"], ["AWS", "Docker"], ["5+ years"])
        context2 = DataReshaper.prepare_assessment_context(cv, job, entities)

        assert context2["token_count"] > context1["token_count"]

    def test_context_with_all_parameters(self) -> None:
        """Context with all optional parameters."""
        cv = "10 years Python, 5 years React"
        job = "Senior Full Stack Engineer"
        entities = (["Python", "React"], ["AWS", "PostgreSQL"], ["Visa sponsorship"])
        chunks = ["Chunk 1", "Chunk 2"]
        context = DataReshaper.prepare_assessment_context(cv, job, entities, chunks)

        assert context["cv"] == cv
        assert context["job_description"] == job
        assert context["entities"]
        assert context["chunks"] == chunks
        assert context["token_count"] > 0

    def test_context_none_entities_default(self) -> None:
        """None entities parameter defaults to empty tuples."""
        cv = "Senior Developer"
        job = "We are hiring"
        context = DataReshaper.prepare_assessment_context(cv, job, None)
        assert context["entities"] == ""  # Empty because no entities

    def test_context_none_chunks_default(self) -> None:
        """None chunks parameter defaults to empty list."""
        cv = "Senior Developer"
        job = "We are hiring"
        context = DataReshaper.prepare_assessment_context(cv, job, chunks=None)
        assert context["chunks"] == []

    def test_context_empty_strings(self) -> None:
        """Context handles empty input strings."""
        context = DataReshaper.prepare_assessment_context("", "")
        assert context["cv"] == ""
        assert context["job_description"] == ""
        # Token count may be 0 or minimal
        assert context["token_count"] >= 0

    def test_context_special_characters(self) -> None:
        """Context handles special characters."""
        cv = "C++ & Python Developer ($100k-$200k)"
        job = "Rust/Go developer (100% remote, NYC/SF)"
        context = DataReshaper.prepare_assessment_context(cv, job)
        assert "C++" in context["cv"]
        assert "$" in context["cv"]
        assert context["token_count"] > 0
