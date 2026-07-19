"""Tests for LLM model configuration."""

import pytest

from src.config.models import (
    DEFAULT_MODEL,
    SUPPORTED_MODELS,
    get_model_display_name,
    get_model_pricing,
    get_supported_models_list,
    validate_model,
)


class TestModelConfiguration:
    """Test model registry and validation."""

    def test_default_model(self):
        """Default model is Sonnet."""
        assert DEFAULT_MODEL == "claude-sonnet-5"

    def test_supported_models_exist(self):
        """Verify all required models are registered."""
        required = {"claude-haiku-4-5-20251001", "claude-sonnet-5", "claude-opus-4-8"}
        assert required.issubset(SUPPORTED_MODELS.keys())

    def test_validate_model_accepts_valid(self):
        """validate_model accepts supported model IDs."""
        validate_model("claude-sonnet-5")  # Should not raise
        validate_model("claude-haiku-4-5-20251001")
        validate_model("claude-opus-4-8")

    def test_validate_model_rejects_invalid(self):
        """validate_model raises ValueError for unsupported models."""
        with pytest.raises(ValueError, match="Invalid model"):
            validate_model("claude-invalid-1.0")

    def test_get_model_pricing_sonnet(self):
        """Sonnet pricing: $3/$15 per 1M."""
        input_price, output_price = get_model_pricing("claude-sonnet-5")
        assert input_price == 3.0
        assert output_price == 15.0

    def test_get_model_pricing_haiku(self):
        """Haiku pricing: $0.80/$4 per 1M."""
        input_price, output_price = get_model_pricing("claude-haiku-4-5-20251001")
        assert input_price == 0.80
        assert output_price == 4.0

    def test_get_model_pricing_opus(self):
        """Opus pricing: $15/$75 per 1M."""
        input_price, output_price = get_model_pricing("claude-opus-4-8")
        assert input_price == 15.0
        assert output_price == 75.0

    def test_get_model_pricing_invalid(self):
        """get_model_pricing raises ValueError for invalid model."""
        with pytest.raises(ValueError):
            get_model_pricing("claude-invalid-1.0")

    def test_get_model_display_name(self):
        """Display names are correct."""
        assert get_model_display_name("claude-haiku-4-5-20251001") == "Haiku"
        assert get_model_display_name("claude-sonnet-5") == "Sonnet"
        assert get_model_display_name("claude-opus-4-8") == "Opus"

    def test_get_supported_models_list(self):
        """Supported models list is formatted correctly."""
        models_list = get_supported_models_list()
        assert "claude-haiku-4-5-20251001" in models_list
        assert "claude-sonnet-5" in models_list
        assert "claude-opus-4-8" in models_list
        assert "," in models_list  # Comma-separated
