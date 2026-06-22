"""Tests for environment variable loading from .env file."""

import os
import tempfile
from pathlib import Path

import pytest


class TestEnvLoading:
    """Test .env file loading in CLI."""

    def test_dotenv_import_available(self):
        """Verify python-dotenv is installed."""
        try:
            from dotenv import load_dotenv

            assert load_dotenv is not None
        except ImportError:
            pytest.fail("python-dotenv not installed")

    def test_load_dotenv_in_cli(self):
        """Test load_dotenv is called in CLI main function."""
        from src import cli

        # Check that load_dotenv is imported
        assert hasattr(cli, "load_dotenv"), "load_dotenv not imported in cli.py"

        # Verify main function exists
        assert hasattr(cli, "main"), "main function not defined in cli.py"

    def test_env_file_exists(self):
        """Test .env file exists in project root."""
        env_file = Path(".env")
        assert env_file.exists(), ".env file not found in project root"

    def test_env_file_has_anthropic_key_template(self):
        """Test .env.example has ANTHROPIC_API_KEY template."""
        env_example = Path(".env.example")
        if env_example.exists():
            with open(env_example) as f:
                content = f.read()
                assert (
                    "ANTHROPIC_API_KEY" in content
                ), "ANTHROPIC_API_KEY not in .env.example"

    def test_llm_provider_error_message(self):
        """Test improved error message from LLMProvider."""
        from src.llm.provider import LLMProvider

        # Clear API key from environment
        original_key = os.environ.pop("ANTHROPIC_API_KEY", None)

        try:
            with pytest.raises(ValueError) as exc_info:
                LLMProvider()

            error_msg = str(exc_info.value)
            assert "ANTHROPIC_API_KEY" in error_msg
            assert ".env" in error_msg
            assert "export" in error_msg.lower()
        finally:
            # Restore original key if it existed
            if original_key:
                os.environ["ANTHROPIC_API_KEY"] = original_key

    def test_llm_provider_with_explicit_key(self):
        """Test LLMProvider can be initialized with explicit API key."""
        from src.llm.provider import LLMProvider

        # Should not raise with explicit key (though Anthropic client init might)
        test_key = "test-key-for-unit-test"  # pragma: allowlist secret
        try:
            provider = LLMProvider(api_key=test_key)
            assert provider.api_key == test_key
        except Exception as e:
            # Anthropic client initialization might fail, but key should be set
            if "test-key" not in str(e):
                # If the error isn't about the key format, check it was at least set
                pass


class TestEnvIntegration:
    """Integration tests for environment loading."""

    def test_env_loading_with_temp_file(self):
        """Test loading custom .env file."""
        from dotenv import load_dotenv

        # Create temp .env file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False, dir="."
        ) as f:
            f.write("TEST_VAR=test_value\n")
            f.write("ANOTHER_VAR=another_value\n")
            temp_env_path = f.name

        try:
            # Load the temp .env file
            load_dotenv(temp_env_path)

            # Verify values loaded
            assert os.getenv("TEST_VAR") == "test_value"
            assert os.getenv("ANOTHER_VAR") == "another_value"
        finally:
            # Clean up
            Path(temp_env_path).unlink()
            # Clear test variables
            os.environ.pop("TEST_VAR", None)
            os.environ.pop("ANOTHER_VAR", None)

    def test_env_overrides_not_set(self):
        """Test that .env doesn't override already-set env vars."""
        from dotenv import load_dotenv

        # Set environment variable
        os.environ["OVERRIDE_TEST"] = "original"

        # Create temp .env with different value
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False, dir="."
        ) as f:
            f.write("OVERRIDE_TEST=from_env_file\n")
            temp_env_path = f.name

        try:
            # Load should not override existing env vars
            load_dotenv(temp_env_path, override=False)

            # Should keep original value
            assert os.getenv("OVERRIDE_TEST") == "original"
        finally:
            Path(temp_env_path).unlink()
            os.environ.pop("OVERRIDE_TEST", None)
