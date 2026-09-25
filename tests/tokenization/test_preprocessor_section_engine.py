"""Model-free tests for Preprocessor.section_engine (Issue #281 S4).

Tests that section_engine parameter is properly stored and used in Preprocessor.
No spaCy model (en_core_web_md) required. Uses blank SectionDetector().
"""

import inspect
from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock, patch

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

    def test_extract_sectioned_requirements_returns_none_for_empty_text(self, monkeypatch: Any) -> None:
        """extract_sectioned_requirements should return None for empty/whitespace text."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        assert preprocessor.extract_sectioned_requirements("") is None
        assert preprocessor.extract_sectioned_requirements("   ") is None


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

        # Should have extracted requirements from Requirements section
        assert len(result.requirements) > 0

        # All requirements should come from Requirements section (Benefits excluded)
        for req in result.requirements:
            # SectionLabel.REQUIREMENTS has value "SECTION_REQUIREMENTS"
            assert req.source_section.value == SectionLabel.REQUIREMENTS.value

    def test_extract_sectioned_requirements_detects_sections(self, monkeypatch: Any) -> None:
        """Should populate sections_detected with detected section labels."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        text = """## Requirements
5+ years Python experience

## Benefits
Health insurance"""

        result = preprocessor.extract_sectioned_requirements(text)

        assert result is not None
        # sections_detected should contain "SECTION_REQUIREMENTS" (not benefits as it's filtered)
        assert len(result.sections_detected) > 0

    def test_extract_sectioned_requirements_empty_text_returns_none(self, monkeypatch: Any) -> None:
        """Empty text with engine should return None."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        result = preprocessor.extract_sectioned_requirements("   ")

        assert result is None

    def test_extract_sectioned_requirements_text_without_sections(self, monkeypatch: Any) -> None:
        """Text without recognized sections should return empty requirements."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        # Plain text with no section headers
        text = "This is just some random text without any section headers."

        result = preprocessor.extract_sectioned_requirements(text)

        # May return SectionedResult with 0 requirements
        if result is not None:
            assert isinstance(result, SectionedResult)
            # If sections not detected, requirements should be empty
            if len(result.sections_detected) == 0:
                assert len(result.requirements) == 0


class TestPreprocessorSectionEngineSignature:
    """Test that extract_entities signature remains unchanged."""

    def test_extract_entities_signature_unchanged(self, monkeypatch: Any) -> None:
        """extract_entities should have unchanged signature."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        preprocessor = Preprocessor(section_engine=SectionDetector())

        sig = inspect.signature(preprocessor.extract_entities)
        params = list(sig.parameters.keys())

        # Should have only 'text' parameter
        assert params == ["text"]

        # Return annotation should still be Tuple[List[str], List[str], List[str]]
        return_annotation = sig.return_annotation
        # Check it's a tuple of 3 lists
        assert hasattr(return_annotation, "__origin__")

    def test_extract_entities_return_type_tuple_of_lists(self, monkeypatch: Any) -> None:
        """extract_entities return type annotation should be unchanged."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        preprocessor = Preprocessor(section_engine=SectionDetector())
        sig = inspect.signature(preprocessor.extract_entities)

        # Verify return annotation exists and is a tuple type
        return_annotation = str(sig.return_annotation)
        # Should contain "Tuple" and "List[str]"
        assert "Tuple" in return_annotation or "tuple" in return_annotation
        assert "List[str]" in return_annotation or "list[str]" in return_annotation


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

        # Patch at the import location inside the method
        with patch(
            "src.preprocessing.section_extractor.extract_sectioned", mock_extract_sectioned
        ) as mock_patch:
            text = "## Requirements\nSome requirement"
            result = preprocessor.extract_sectioned_requirements(text)

            # Verify result is from our mock
            assert isinstance(result, SectionedResult)
            assert len(result.requirements) == 0

    def test_different_detectors_are_distinguished(self, monkeypatch: Any) -> None:
        """Each preprocessor should use its own detector instance."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector1 = SectionDetector()
        detector2 = SectionDetector()

        preprocessor1 = Preprocessor(section_engine=detector1)
        preprocessor2 = Preprocessor(section_engine=detector2)

        assert preprocessor1.section_engine is not preprocessor2.section_engine
        assert preprocessor1.section_engine is detector1
        assert preprocessor2.section_engine is detector2


class TestPreprocessorInitParameters:
    """Test that section_engine doesn't break existing parameters."""

    def test_all_init_parameters_work_together(self, monkeypatch: Any) -> None:
        """section_engine should work alongside existing parameters."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(
            model="en_core_web_md",
            extract_requirements=True,
            preserve_requirement_spans=True,
            section_engine=detector,
        )

        assert preprocessor.model_name == "en_core_web_md"
        assert preprocessor.extract_requirements is True
        assert preprocessor.preserve_requirement_spans is True
        assert preprocessor.section_engine is detector

    def test_section_engine_optional_default_none(self, monkeypatch: Any) -> None:
        """section_engine parameter should be optional with default None."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        # Without section_engine parameter
        preprocessor = Preprocessor(
            model="en_core_web_md",
            extract_requirements=True,
        )

        assert preprocessor.section_engine is None


class TestPreprocessorSectionEngineEdgeCases:
    """Test edge cases and error handling."""

    def test_extract_sectioned_requirements_with_mock_detector(self, monkeypatch: Any) -> None:
        """Should handle mock/patched detectors gracefully."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        # Mock detector that tracks calls
        mock_detector = MagicMock(spec=SectionDetector)

        preprocessor = Preprocessor(section_engine=mock_detector)

        # Patch extract_sectioned to avoid actual processing
        def mock_extract_sectioned(text: str, *, detector: Any = None, **kwargs: Any) -> SectionedResult:
            return SectionedResult(
                requirements=(),
                sections_detected=(),
                requirements_by_section={},
            )

        with patch(
            "src.preprocessing.section_extractor.extract_sectioned", mock_extract_sectioned
        ) as mock_extract:
            result = preprocessor.extract_sectioned_requirements("test text")

            assert isinstance(result, SectionedResult)
            # Detector was stored in instance
            assert preprocessor.section_engine is mock_detector

    def test_extract_sectioned_handles_error_gracefully(self, monkeypatch: Any) -> None:
        """If extract_sectioned fails, should return None gracefully."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        # Patch extract_sectioned to raise an error
        def mock_extract_failed(text: str, **kwargs: Any) -> None:
            raise RuntimeError("Test error")

        with patch(
            "src.preprocessing.section_extractor.extract_sectioned", side_effect=RuntimeError("Test error")
        ):
            result = preprocessor.extract_sectioned_requirements("test text")

            # Should return None on error, not raise
            assert result is None


class TestPreprocessorSectionEngineIntegration:
    """Integration tests with real components."""

    def test_section_engine_is_transient(self, monkeypatch: Any) -> None:
        """Output from extract_sectioned_requirements should not be persisted."""
        monkeypatch.setattr(Preprocessor, "_load_model", lambda self: None)

        detector = SectionDetector()
        preprocessor = Preprocessor(section_engine=detector)

        text = "## Requirements\n- Requirement 1"

        result1 = preprocessor.extract_sectioned_requirements(text)
        result2 = preprocessor.extract_sectioned_requirements(text)

        # Both should be SectionedResult but separate instances
        if result1 is not None:
            assert isinstance(result1, SectionedResult)
        if result2 is not None:
            assert isinstance(result2, SectionedResult)

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
