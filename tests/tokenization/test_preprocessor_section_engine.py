"""Model-free tests for Preprocessor.section_engine (Issue #281 S4).

Tests that section_engine parameter is properly stored and used in Preprocessor.
No spaCy model (en_core_web_md) required. Uses blank SectionDetector().
"""

from typing import Any, get_type_hints
from unittest.mock import patch

import pytest

from src.preprocessing.section_detector import SectionDetector
from src.preprocessing.section_extractor import SectionedResult
from src.preprocessing.section_patterns import SectionLabel
from src.tokenization.preprocessor import Preprocessor


class TestPreprocessorSectionEngineBasics:
    """Test basic section_engine parameter functionality."""

    def test_default_section_engine_is_none(self, monkeypatch: Any) -> None:
        """Default section_engine should be None (opt-in behavior)."""
        # Monkeypatch _load_model to skip spaCy initialization
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        preprocessor = Preprocessor()
        assert preprocessor.section_engine is None

    def test_section_engine_parameter_stored(self, monkeypatch: Any) -> None:
        """Passed section_engine should be stored in instance."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        assert preprocessor.section_engine is detector

    def test_extract_sectioned_requirements_returns_none_when_engine_is_none(self, monkeypatch: Any) -> None:
        """extract_sectioned_requirements should return None when section_engine is None."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        preprocessor = Preprocessor(section_engine=None)
        result = preprocessor.extract_sectioned_requirements("some text with requirements")

        assert result is None


class TestPreprocessorSectionEngineExecution:
    """Test extract_sectioned_requirements execution with real detector."""

    def test_extract_sectioned_requirements_with_real_detector(self, monkeypatch: Any) -> None:
        """With real SectionDetector, should return SectionedResult with actual data."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        # Real job description text with sections
        text = """## Requirements
- 5+ years of Python experience required
- Must have strong SQL skills
- Experience with distributed systems

## Benefits
- Health insurance
- 401k matching
"""

        result = preprocessor.extract_sectioned_requirements(text)

        # Should return SectionedResult, not None
        assert result is not None
        assert isinstance(result, SectionedResult)

        # Should have extracted exactly 3 requirements from Requirements section
        assert len(result.requirements) == 3

        # Verify first requirement text and source_section
        assert result.requirements[0].text == "5+ years of Python experience required"
        assert result.requirements[0].source_section == SectionLabel.REQUIREMENTS

        # Verify second requirement text and source_section
        assert result.requirements[1].text == "Experience with distributed systems"
        assert result.requirements[1].source_section == SectionLabel.REQUIREMENTS

        # Verify third requirement text and source_section
        assert result.requirements[2].text == "Must have strong SQL skills"
        assert result.requirements[2].source_section == SectionLabel.REQUIREMENTS

    def test_extract_sectioned_requirements_detects_sections(self, monkeypatch: Any) -> None:
        """Should populate sections_detected with detected section labels."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        text = """## Requirements
- 5+ years Python experience required
- Must know distributed systems

## Benefits
Health insurance"""

        result = preprocessor.extract_sectioned_requirements(text)

        assert result is not None
        # sections_detected should contain exactly SECTION_REQUIREMENTS
        # (Benefits section is present but its bullets don't match trigger patterns)
        assert result.sections_detected == ("SECTION_REQUIREMENTS",)

    def test_extract_sectioned_requirements_empty_text_returns_sectioned_result(self, monkeypatch: Any) -> None:
        """Empty text with engine should delegate to extract_sectioned, returning SectionedResult."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        # extract_sectioned returns SectionedResult even for empty text
        result = preprocessor.extract_sectioned_requirements("")
        assert result is not None
        assert isinstance(result, SectionedResult)
        assert len(result.requirements) == 0

        result = preprocessor.extract_sectioned_requirements("   ")
        assert result is not None
        assert isinstance(result, SectionedResult)
        assert len(result.requirements) == 0

    def test_extract_sectioned_requirements_text_without_sections(self, monkeypatch: Any) -> None:
        """Text without recognized sections should return result with empty requirements."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        # Plain text with no section headers
        text = "This is just some random text without any section headers."

        result = preprocessor.extract_sectioned_requirements(text)

        # Should return SectionedResult with empty requirements and no sections detected
        assert result is not None
        assert isinstance(result, SectionedResult)
        assert result.sections_detected == ()
        assert result.requirements == ()


class TestPreprocessorSectionEngineSignature:
    """Test that extract_entities signature remains unchanged."""

    def test_extract_entities_signature_unchanged(self, monkeypatch: Any) -> None:
        """extract_entities should have unchanged signature."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        # Get type hints using get_type_hints
        hints = get_type_hints(Preprocessor.extract_entities)
        return_type = hints.get("return")

        # Return type should be Tuple[List[str], List[str], List[str]]
        assert return_type is not None
        assert hasattr(return_type, "__origin__")
        assert return_type.__origin__ is tuple
        assert len(return_type.__args__) == 3


class TestPreprocessorSectionEngineCustomDetector:
    """Test that custom SectionDetector instances are properly used."""

    def test_custom_detector_passed_to_extract_sectioned(self, monkeypatch: Any) -> None:
        """Passed detector should be used in extract_sectioned_requirements."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        # Create a real detector
        real_detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=real_detector)

        # Track which detector was passed
        call_tracker: list[Any] = []

        def mock_extract_sectioned(text: str, *, detector: Any = None, **kwargs: Any) -> SectionedResult:
            call_tracker.append(detector)
            return SectionedResult(
                requirements=(),
                sections_detected=(),
                requirements_by_section={},
            )

        # Patch at module level where it's imported
        with patch("src.tokenization.preprocessor.extract_sectioned", mock_extract_sectioned):
            text = "## Requirements\nSome requirement"
            result = preprocessor.extract_sectioned_requirements(text)

            # Verify result is from our mock
            assert isinstance(result, SectionedResult)
            assert len(result.requirements) == 0
            # Verify detector was passed with identity check
            assert len(call_tracker) == 1
            assert call_tracker[0] is real_detector


class TestPreprocessorSectionEngineEdgeCases:
    """Test edge cases."""

    def test_extract_sectioned_propagates_errors(self, monkeypatch: Any) -> None:
        """If extract_sectioned fails, error should propagate (not be swallowed)."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        # Patch extract_sectioned to raise an error at module level
        with patch("src.tokenization.preprocessor.extract_sectioned", side_effect=RuntimeError("Test error")):
            with pytest.raises(RuntimeError, match="Test error"):
                preprocessor.extract_sectioned_requirements("test text")


class TestPreprocessorSectionEngineIntegration:
    """Integration tests with real components."""

    def test_section_engine_is_transient(self, monkeypatch: Any) -> None:
        """Output from extract_sectioned_requirements should not be persisted."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        text = "## Requirements\n- 5+ years Python experience required\n- Must know SQL"

        result1 = preprocessor.extract_sectioned_requirements(text)
        result2 = preprocessor.extract_sectioned_requirements(text)

        # Both should be SectionedResult and equal by value (frozen dataclass)
        assert result1 is not None
        assert result2 is not None
        assert isinstance(result1, SectionedResult)
        assert isinstance(result2, SectionedResult)
        assert result1 == result2

    def test_extract_entities_not_affected_by_section_engine(self, monkeypatch: Any) -> None:
        """extract_entities should work regardless of section_engine setting."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        preprocessor1 = Preprocessor(section_engine=None)
        preprocessor1.nlp = None

        preprocessor2 = Preprocessor(section_engine=SectionDetector())
        preprocessor2.nlp = None

        # Both should have the same extract_entities behavior (return empty with nlp=None)
        result1 = preprocessor1.extract_entities("test text")
        result2 = preprocessor2.extract_entities("test text")

        # Both should be ([], [], []) since nlp is None
        assert result1 == ([], [], [])
        assert result2 == ([], [], [])
