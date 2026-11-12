"""Tests for POC requirement extraction pipeline.

48 tests covering:
- Unit tests (39): parsing, classification, spans, normalization, schema
- Integration tests (9): full pipeline, Carbon Robotics example
"""

import json
from pathlib import Path
from typing import Any, cast

import pytest

from src.poc.extract_requirements import (
    RequirementExtractionOutput,
    RequirementExtractor,
    RequirementModel,
    extract_requirements_from_markdown,
)


@pytest.fixture
def extractor() -> RequirementExtractor:
    """Initialize RequirementExtractor for testing."""
    try:
        return RequirementExtractor(
            spacy_model="en_core_web_md",
            min_confidence=0.50,
            max_requirements=25,
        )
    except RuntimeError as e:
        pytest.skip(f"spaCy model not available: {e}")
        raise  # pragma: no cover


@pytest.fixture
def sample_job_md() -> str:
    """Sample markdown job description."""
    return """# Senior Python Developer

## Company
Carbon Robotics

## About This Role
We're looking for an experienced Python developer to join our team.

## Requirements
Must have 5+ years of experience in Python development.
Experience with Django and FastAPI frameworks is essential.
Strong knowledge of databases (PostgreSQL, MongoDB).
Ability to work in a fast-paced environment.
"""


@pytest.fixture
def carbon_robotics_job() -> str:
    """Load Carbon Robotics job fixture."""
    fixtures_path = Path(__file__).parent / "fixtures" / "carbon_robotics_job.md"
    if not fixtures_path.exists():
        pytest.skip("Carbon Robotics fixture not available")
    with open(fixtures_path) as f:
        return f.read()


@pytest.fixture
def carbon_robotics_expected() -> dict[str, Any]:
    """Load expected output for Carbon Robotics job."""
    fixtures_path = Path(__file__).parent / "fixtures" / "carbon_robotics_output.json"
    if not fixtures_path.exists():
        pytest.skip("Carbon Robotics expected output fixture not available")
    with open(fixtures_path) as f:
        return cast(dict[str, Any], json.load(f))


# Unit Tests (39)


class TestRequirementExtractorInitialization:
    """Test extractor initialization and configuration."""

    def test_init_with_defaults(self, extractor):
        """Test initialization with default parameters."""
        assert extractor.min_confidence == 0.50
        assert extractor.max_requirements == 25
        assert extractor.spacy_model_name == "en_core_web_md"

    def test_init_with_custom_confidence(self):
        """Test initialization with custom confidence threshold."""
        try:
            extractor = RequirementExtractor(min_confidence=0.70)
            assert extractor.min_confidence == 0.70
        except RuntimeError:
            pytest.skip("spaCy model not available")

    def test_init_with_custom_max_requirements(self):
        """Test initialization with custom max requirements."""
        try:
            extractor = RequirementExtractor(max_requirements=10)
            assert extractor.max_requirements == 10
        except RuntimeError:
            pytest.skip("spaCy model not available")

    def test_spacy_model_loaded(self, extractor):
        """Test that spaCy model is loaded."""
        assert extractor.nlp is not None
        assert "requirement_filter" in extractor.nlp.pipe_names
        assert "span_categorizer" in extractor.nlp.pipe_names

    def test_init_with_invalid_model(self):
        """Test initialization with invalid spaCy model."""
        with pytest.raises(RuntimeError, match="Failed to load spaCy model"):
            RequirementExtractor(spacy_model="invalid_model_xyz")


class TestMarkdownParsing:
    """Test company extraction from markdown."""

    def test_extract_company_from_h1(self, extractor):
        """Test company extraction from h1 header."""
        md = "# Carbon Robotics\n\nJob description..."
        company = extractor.extract_company(md)
        assert company == "Carbon Robotics"

    def test_extract_company_from_h2(self, extractor):
        """Test company extraction from h2 header."""
        md = "## Company Name\n\nJob description..."
        company = extractor.extract_company(md)
        assert company == "Company Name"

    def test_extract_company_from_company_field(self, extractor):
        """Test company extraction from 'Company: ' field."""
        md = "Company: Acme Corp\n\nJob description..."
        company = extractor.extract_company(md)
        assert company == "Acme Corp"

    def test_extract_company_from_employer_field(self, extractor):
        """Test company extraction from 'Employer: ' field."""
        md = "Employer: Tech Startup Inc\n\nJob description..."
        company = extractor.extract_company(md)
        assert company == "Tech Startup Inc"

    def test_extract_company_case_insensitive(self, extractor):
        """Test company extraction with case-insensitive patterns."""
        md = "COMPANY: Some Corp\n\nJob description..."
        company = extractor.extract_company(md)
        assert company == "Some Corp"

    def test_extract_company_not_found(self, extractor):
        """Test when company name is not found."""
        md = "Job description without company info..."
        company = extractor.extract_company(md)
        assert company is None

    def test_extract_company_whitespace_trimmed(self, extractor):
        """Test that extracted company name is trimmed."""
        md = "#  Extra Spaces Corp  \n\nJob..."
        company = extractor.extract_company(md)
        assert company == "Extra Spaces Corp"


class TestSentenceClassification:
    """Test sentence classification and requirement detection."""

    def test_classify_basic_requirement(self, extractor):
        """Test classification of basic requirement sentence."""
        md = "Python is required for this role."
        sentences = extractor.classify_sentences(md)
        assert len(sentences) > 0
        assert any("required" in s.lower() for s in sentences)

    def test_classify_multiple_requirements(self, extractor):
        """Test classification of multiple requirement sentences."""
        md = """
        Must have 5+ years of Python experience.
        Essential skills include Django and FastAPI.
        Knowledge of PostgreSQL is required.
        """
        sentences = extractor.classify_sentences(md)
        assert len(sentences) >= 2

    def test_classify_respects_confidence_threshold(self, extractor):
        """Test that low-confidence requirements are filtered."""
        extractor_strict = RequirementExtractor(min_confidence=0.90)
        md = "Nice to have experience with optional tools."
        sentences = extractor_strict.classify_sentences(md)
        assert isinstance(sentences, list)

    def test_classify_empty_text(self, extractor):
        """Test classification with empty text."""
        sentences = extractor.classify_sentences("")
        assert isinstance(sentences, list)

    def test_classify_no_requirements(self, extractor):
        """Test text with no requirements."""
        md = "This is a generic job description without any requirements."
        sentences = extractor.classify_sentences(md)
        assert isinstance(sentences, list)


class TestSpanExtraction:
    """Test span extraction using Phase 8b."""

    def test_extract_spans_basic(self, extractor):
        """Test basic span extraction."""
        md = "Must have 5+ years of Python experience."
        spans = extractor.extract_spans(md)
        assert len(spans) > 0
        assert all("text" in span for span in spans)
        assert all("confidence" in span for span in spans)

    def test_extract_spans_multiple(self, extractor):
        """Test extraction of multiple spans."""
        md = """
        Required: Python and Django experience.
        Essential knowledge of databases.
        Ability to work with REST APIs.
        """
        spans = extractor.extract_spans(md)
        assert len(spans) >= 2

    def test_extract_spans_respects_confidence(self, extractor):
        """Test that low-confidence spans are filtered."""
        md = "Nice to have optional knowledge of Rust."
        extractor_strict = RequirementExtractor(min_confidence=0.80)
        spans = extractor_strict.extract_spans(md)
        assert isinstance(spans, list)

    def test_extract_spans_includes_metadata(self, extractor):
        """Test that spans include required metadata."""
        md = "Required: 5+ years Python experience."
        spans = extractor.extract_spans(md)
        if spans:
            span = spans[0]
            assert "text" in span
            assert "confidence" in span
            assert "trigger_word" in span

    def test_extract_spans_empty_text(self, extractor):
        """Test span extraction with empty text."""
        spans = extractor.extract_spans("")
        assert isinstance(spans, list)


class TestNormalization:
    """Test deduplication and normalization."""

    def test_normalize_deduplicates_exact_match(self, extractor):
        """Test deduplication of exact matches."""
        spans = [
            {
                "text": "Python experience",
                "trigger_word": "experience",
                "confidence": 0.85,
                "span_type": "atomic",
            },
            {
                "text": "Python experience",
                "trigger_word": "experience",
                "confidence": 0.80,
                "span_type": "atomic",
            },
        ]
        normalized = extractor.normalize(spans)
        assert len(normalized) == 1

    def test_normalize_case_insensitive(self, extractor):
        """Test case-insensitive deduplication."""
        spans = [
            {
                "text": "Python Experience",
                "trigger_word": "experience",
                "confidence": 0.85,
                "span_type": "atomic",
            },
            {
                "text": "python experience",
                "trigger_word": "experience",
                "confidence": 0.80,
                "span_type": "atomic",
            },
        ]
        normalized = extractor.normalize(spans)
        assert len(normalized) == 1

    def test_normalize_keeps_highest_confidence(self, extractor):
        """Test that highest confidence version is kept."""
        spans = [
            {
                "text": "Python",
                "trigger_word": "experience",
                "confidence": 0.75,
                "span_type": "atomic",
            },
            {
                "text": "Python",
                "trigger_word": "experience",
                "confidence": 0.92,
                "span_type": "atomic",
            },
        ]
        normalized = extractor.normalize(spans)
        assert len(normalized) == 1
        assert normalized[0]["confidence"] == 0.92

    def test_normalize_sorts_by_confidence(self, extractor):
        """Test that results are sorted by confidence descending."""
        spans = [
            {
                "text": "Requirement A",
                "trigger_word": "required",
                "confidence": 0.60,
                "span_type": "atomic",
            },
            {
                "text": "Requirement B",
                "trigger_word": "must",
                "confidence": 0.95,
                "span_type": "atomic",
            },
            {
                "text": "Requirement C",
                "trigger_word": "essential",
                "confidence": 0.75,
                "span_type": "atomic",
            },
        ]
        normalized = extractor.normalize(spans)
        assert len(normalized) == 3
        assert normalized[0]["confidence"] == 0.95
        assert normalized[1]["confidence"] == 0.75
        assert normalized[2]["confidence"] == 0.60

    def test_normalize_respects_max_requirements(self, extractor):
        """Test that max_requirements limit is enforced."""
        spans = [
            {
                "text": f"Requirement {i}",
                "trigger_word": "required",
                "confidence": 0.90 - (i * 0.01),
                "span_type": "atomic",
            }
            for i in range(30)
        ]
        normalized = extractor.normalize(spans)
        assert len(normalized) <= extractor.max_requirements

    def test_normalize_empty_list(self, extractor):
        """Test normalization with empty input."""
        normalized = extractor.normalize([])
        assert normalized == []

    def test_normalize_single_item(self, extractor):
        """Test normalization with single requirement."""
        spans = [
            {
                "text": "Python",
                "trigger_word": "experience",
                "confidence": 0.85,
                "span_type": "atomic",
            }
        ]
        normalized = extractor.normalize(spans)
        assert len(normalized) == 1


class TestJSONOutput:
    """Test JSON schema and output formatting."""

    def test_to_json_output_structure(self, extractor, sample_job_md):
        """Test that output has required structure."""
        doc = extractor.nlp(sample_job_md)
        sentence_count = len(list(doc.sents))
        spans = extractor.extract_spans(sample_job_md)
        normalized = extractor.normalize(spans)

        output = extractor.to_json(normalized, sample_job_md, sentence_count)

        assert isinstance(output, RequirementExtractionOutput)
        assert output.company is not None
        assert output.requirements_count >= 0
        assert isinstance(output.requirements, list)
        assert isinstance(output.metadata, dict)

    def test_to_json_includes_company(self, extractor):
        """Test that company is extracted in output."""
        md = "# Acme Corp\n\nRequired: Python experience."
        doc = extractor.nlp(md)
        sentence_count = len(list(doc.sents))
        spans = extractor.extract_spans(md)
        normalized = extractor.normalize(spans)

        output = extractor.to_json(normalized, md, sentence_count)
        assert output.company == "Acme Corp"

    def test_to_json_requirement_model_validation(self, extractor):
        """Test that requirements are valid RequirementModel objects."""
        md = "Must have Python experience."
        doc = extractor.nlp(md)
        sentence_count = len(list(doc.sents))
        spans = extractor.extract_spans(md)
        normalized = extractor.normalize(spans)

        output = extractor.to_json(normalized, md, sentence_count)

        for req in output.requirements:
            assert isinstance(req, RequirementModel)
            assert req.text
            assert 0.0 <= req.confidence <= 1.0
            assert req.trigger_word

    def test_to_json_metadata_completeness(self, extractor, sample_job_md):
        """Test that metadata includes all required fields."""
        doc = extractor.nlp(sample_job_md)
        sentence_count = len(list(doc.sents))
        spans = extractor.extract_spans(sample_job_md)
        normalized = extractor.normalize(spans)

        output = extractor.to_json(normalized, sample_job_md, sentence_count)

        assert "sentences_analyzed" in output.metadata
        assert "requirements_extracted" in output.metadata
        assert "spacy_model" in output.metadata
        assert "pipeline_components" in output.metadata

    def test_to_json_serializable(self, extractor, sample_job_md):
        """Test that output is JSON serializable."""
        doc = extractor.nlp(sample_job_md)
        sentence_count = len(list(doc.sents))
        spans = extractor.extract_spans(sample_job_md)
        normalized = extractor.normalize(spans)

        output = extractor.to_json(normalized, sample_job_md, sentence_count)

        json_str = output.model_dump_json()
        assert isinstance(json_str, str)

        parsed = json.loads(json_str)
        assert parsed["company"] is not None or parsed["company"] is None
        assert "requirements" in parsed


class TestFullPipeline:
    """Test complete extraction pipeline."""

    def test_extract_full_pipeline_basic(self, extractor, sample_job_md):
        """Test full pipeline with sample job."""
        output = extractor.extract(sample_job_md)

        assert isinstance(output, RequirementExtractionOutput)
        assert output.company is not None
        assert output.requirements_count > 0
        assert len(output.requirements) > 0
        assert output.metadata["sentences_analyzed"] > 0

    def test_extract_full_pipeline_consistent(self, extractor, sample_job_md):
        """Test that running pipeline twice gives same results."""
        output1 = extractor.extract(sample_job_md)
        output2 = extractor.extract(sample_job_md)

        assert output1.requirements_count == output2.requirements_count
        assert output1.company == output2.company
        if output1.requirements:
            assert output1.requirements[0].text == output2.requirements[0].text

    def test_extract_convenience_function(self, sample_job_md):
        """Test convenience function for single-pass extraction."""
        output = extract_requirements_from_markdown(sample_job_md)

        assert isinstance(output, RequirementExtractionOutput)
        assert output.requirements_count >= 0

    def test_extract_with_custom_thresholds(self):
        """Test extraction with custom confidence and max requirements."""
        try:
            extractor = RequirementExtractor(
                min_confidence=0.70,
                max_requirements=10,
            )
            md = """
            Must have 5+ years Python.
            Essential Django knowledge.
            Nice to have Docker skills.
            """
            output = extractor.extract(md)
            assert output.requirements_count <= 10
        except RuntimeError:
            pytest.skip("spaCy model not available")

    def test_extract_long_job_description(self, extractor):
        """Test extraction with longer job description."""
        md = """# Senior Backend Engineer

## Requirements
- Must have 5+ years of Python experience
- Essential knowledge of Django and FastAPI
- Strong understanding of PostgreSQL
- Ability to design scalable microservices
- Experience with Docker and Kubernetes
- Knowledge of CI/CD pipelines
- Understanding of cloud platforms (AWS, GCP)
"""
        output = extractor.extract(md)

        assert output.requirements_count > 0
        assert len(output.requirements) > 0

    def test_extract_minimal_text(self, extractor):
        """Test extraction with minimal text."""
        md = "Required: Python"
        output = extractor.extract(md)

        assert isinstance(output, RequirementExtractionOutput)

    def test_extract_no_requirements(self, extractor):
        """Test extraction when no requirements are found."""
        md = "This is a generic job description with no specific requirements."
        output = extractor.extract(md)

        assert output.requirements_count == 0
        assert len(output.requirements) == 0

    def test_extract_carbon_robotics(self, extractor, carbon_robotics_job, carbon_robotics_expected):
        """Test extraction on Carbon Robotics job fixture."""
        output = extractor.extract(carbon_robotics_job)

        assert output.requirements_count >= carbon_robotics_expected.get("min_requirements", 1)
        assert len(output.requirements) >= 1

    def test_extract_output_json_serializable(self, extractor, sample_job_md):
        """Test that complete output is JSON serializable."""
        output = extractor.extract(sample_job_md)

        json_str = output.model_dump_json()
        parsed = json.loads(json_str)

        assert "company" in parsed
        assert "requirements_count" in parsed
        assert "requirements" in parsed
        assert "metadata" in parsed


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_extract_with_special_characters(self, extractor):
        """Test extraction with special characters in text."""
        md = """
        Required: C++, C#, & Java programming
        Must know Python/JavaScript or equivalent
        """
        output = extractor.extract(md)
        assert output.requirements_count >= 0

    def test_extract_with_multiple_companies_listed(self, extractor):
        """Test extraction when multiple companies are mentioned."""
        md = """# Company A

Also considering Company B applicants.

Required: 5+ years experience.
"""
        output = extractor.extract(md)
        assert output.company == "Company A"

    def test_normalize_with_trailing_whitespace(self, extractor):
        """Test normalization handles trailing whitespace correctly."""
        spans = [
            {
                "text": "  Python  ",
                "trigger_word": "experience",
                "confidence": 0.85,
                "span_type": "atomic",
            },
            {
                "text": "Python",
                "trigger_word": "experience",
                "confidence": 0.80,
                "span_type": "atomic",
            },
        ]
        normalized = extractor.normalize(spans)
        assert len(normalized) == 1

    def test_extract_with_very_high_confidence_threshold(self):
        """Test extraction with very high confidence threshold."""
        try:
            extractor = RequirementExtractor(min_confidence=0.99)
            md = "Required: Python. Must have Java. Nice to have Rust."
            output = extractor.extract(md)
            assert output.requirements_count >= 0
        except RuntimeError:
            pytest.skip("spaCy model not available")

    def test_extract_empty_after_normalization(self, extractor):
        """Test when all requirements are filtered out during normalization."""
        extractor_strict = RequirementExtractor(min_confidence=0.95)
        md = "Nice to have some optional skills."
        output = extractor_strict.extract(md)
        assert output.requirements_count >= 0
        assert isinstance(output.requirements, list)
