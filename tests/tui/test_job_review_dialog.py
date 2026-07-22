"""Tests for JobReviewDialog entity extraction and display."""

from typing import Any, Dict

import pytest

from src.tui.dialogs.job_review import JobReviewDialog


@pytest.fixture
def basic_job_data() -> Dict[str, Any]:
    """Basic job data for review dialog."""
    return {
        "title": "Senior Python Developer",
        "company": "TechCorp",
        "location": "Remote",
        "clean_text": "We are looking for a Senior Python Developer with 5+ years experience.",
        "description": "Backend role using Python and PostgreSQL.",
    }


@pytest.fixture
def rich_job_data() -> Dict[str, Any]:
    """Job data with clean_text containing extractable entities."""
    return {
        "title": "Full Stack Engineer",
        "company": "StartupXYZ",
        "location": "San Francisco, CA",
        "clean_text": (
            "We seek a Full Stack Engineer proficient in Python, JavaScript, React, and "
            "PostgreSQL. Must have experience with AWS, Docker, and Kubernetes. "
            "Requirements: 3+ years backend development, 2+ years frontend experience. "
            "Strong knowledge of REST APIs and microservices architecture."
        ),
    }


@pytest.fixture
def minimal_job_data() -> Dict[str, Any]:
    """Minimal job data without clean_text."""
    return {
        "title": "Entry Level Developer",
        "company": "Company A",
        "location": "Austin, TX",
    }


class TestJobReviewDialogInit:
    """Test JobReviewDialog initialization."""

    def test_init_stores_job_data(self, basic_job_data: Dict[str, Any]) -> None:
        """Dialog stores job_id and job_data on init."""
        dialog = JobReviewDialog("job-123", basic_job_data)
        assert dialog.job_id == "job-123"
        assert dialog.job_data == basic_job_data
        assert dialog.decision is None

    def test_init_with_empty_job_data(self) -> None:
        """Dialog handles empty job_data dict."""
        dialog = JobReviewDialog("job-456", {})
        assert dialog.job_id == "job-456"
        assert dialog.job_data == {}


class TestEntityExtraction:
    """Test _extract_entities method."""

    def test_extract_entities_returns_tuple(
        self, basic_job_data: Dict[str, Any]
    ) -> None:
        """_extract_entities returns tuple of three lists."""
        dialog = JobReviewDialog("job-123", basic_job_data)
        result = dialog._extract_entities()
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert all(isinstance(r, list) for r in result)

    def test_extract_entities_with_clean_text(self, rich_job_data: Dict[str, Any]) -> None:
        """_extract_entities uses clean_text if available."""
        dialog = JobReviewDialog("job-123", rich_job_data)
        skills, technologies, requirements = dialog._extract_entities()
        assert isinstance(skills, list)
        assert isinstance(technologies, list)
        assert isinstance(requirements, list)

    def test_extract_entities_fallback_to_description(
        self, basic_job_data: Dict[str, Any]
    ) -> None:
        """_extract_entities falls back to 'description' if clean_text missing."""
        job_data = {**basic_job_data}
        del job_data["clean_text"]
        dialog = JobReviewDialog("job-123", job_data)
        skills, technologies, requirements = dialog._extract_entities()
        assert isinstance(skills, list)
        assert isinstance(technologies, list)
        assert isinstance(requirements, list)

    def test_extract_entities_empty_if_no_text(
        self, minimal_job_data: Dict[str, Any]
    ) -> None:
        """_extract_entities returns empty lists if no text available."""
        dialog = JobReviewDialog("job-123", minimal_job_data)
        skills, technologies, requirements = dialog._extract_entities()
        assert skills == []
        assert technologies == []
        assert requirements == []

    def test_extract_entities_handles_exceptions(
        self, basic_job_data: Dict[str, Any]
    ) -> None:
        """_extract_entities gracefully handles extraction failures."""
        dialog = JobReviewDialog("job-123", basic_job_data)
        result = dialog._extract_entities()
        assert len(result) == 3
        assert all(isinstance(r, list) for r in result)


class TestJobReviewDialogButtonHandling:
    """Test button press handling."""

    def test_confirm_button_sets_decision(self, basic_job_data: Dict[str, Any]) -> None:
        """Confirm button sets decision to 'confirm'."""
        dialog = JobReviewDialog("job-123", basic_job_data)
        assert dialog.decision is None
        dialog.decision = "confirm"
        assert dialog.decision == "confirm"

    def test_reject_button_sets_decision(self, basic_job_data: Dict[str, Any]) -> None:
        """Reject button sets decision to 'reject'."""
        dialog = JobReviewDialog("job-123", basic_job_data)
        dialog.decision = "reject"
        assert dialog.decision == "reject"

    def test_skip_button_sets_decision(self, basic_job_data: Dict[str, Any]) -> None:
        """Skip button sets decision to 'skip'."""
        dialog = JobReviewDialog("job-123", basic_job_data)
        dialog.decision = "skip"
        assert dialog.decision == "skip"


class TestJobReviewDialogIntegration:
    """Integration tests for full dialog workflow."""

    def test_dialog_handles_complete_job_data(self, rich_job_data: Dict[str, Any]) -> None:
        """Dialog properly handles fully populated job_data."""
        dialog = JobReviewDialog("job-789", rich_job_data)
        assert dialog.job_id == "job-789"
        assert dialog.job_data["title"] == "Full Stack Engineer"
        assert dialog.job_data["company"] == "StartupXYZ"

    def test_dialog_handles_minimal_job_data(self, minimal_job_data: Dict[str, Any]) -> None:
        """Dialog gracefully handles minimal job_data."""
        dialog = JobReviewDialog("job-001", minimal_job_data)
        assert dialog.job_id == "job-001"
        entities = dialog._extract_entities()
        assert len(entities) == 3

    def test_dialog_decision_flow(self, basic_job_data: Dict[str, Any]) -> None:
        """Dialog supports complete confirm/reject/skip flow."""
        dialog = JobReviewDialog("job-123", basic_job_data)
        assert dialog.decision is None
        dialog.decision = "confirm"
        assert dialog.decision == "confirm"
        dialog.decision = "reject"
        assert dialog.decision == "reject"
        dialog.decision = "skip"
        assert dialog.decision == "skip"


class TestJobReviewDialogEdgeCases:
    """Test edge cases and error scenarios."""

    def test_dialog_with_unicode_characters(self) -> None:
        """Dialog handles unicode in job data."""
        job_data = {
            "title": "Developer 中文 Über",
            "company": "TechCorp émoji 🚀",
            "location": "Zürich, Switzerland",
            "clean_text": "Požadavky: Python, PostgreSQL, Docker",
        }
        dialog = JobReviewDialog("job-123", job_data)
        assert "中文" in dialog.job_data["title"]

    def test_dialog_with_very_long_title(self) -> None:
        """Dialog handles very long job title."""
        long_title = "x" * 500
        job_data = {
            "title": long_title,
            "company": "Test",
            "location": "Remote",
        }
        dialog = JobReviewDialog("job-123", job_data)
        assert dialog.job_data["title"] == long_title

    def test_dialog_with_special_characters(self) -> None:
        """Dialog handles special characters in text."""
        job_data = {
            "title": "C++ & Rust Developer (Senior)",
            "company": "Test/Corp",
            "location": "NYC, NY; Remote",
            "clean_text": "Skills: Python, C++, Rust. Benefits: $100k-$200k, 401k.",
        }
        dialog = JobReviewDialog("job-123", job_data)
        assert "C++" in dialog.job_data["title"]
        assert "$" in dialog.job_data["clean_text"]

    def test_dialog_with_empty_strings(self) -> None:
        """Dialog handles empty string values."""
        job_data = {
            "title": "",
            "company": "",
            "location": "",
            "clean_text": "",
            "description": "",
        }
        dialog = JobReviewDialog("job-123", job_data)
        entities = dialog._extract_entities()
        assert entities == ([], [], [])

    def test_dialog_with_none_values(self) -> None:
        """Dialog handles missing optional fields."""
        job_data = {"title": "Test Job", "company": "Test", "location": "Remote"}
        dialog = JobReviewDialog("job-123", job_data)
        entities = dialog._extract_entities()
        assert len(entities) == 3
