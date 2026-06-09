"""Tests for CLI config loading with enabled flag support."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli import (
    filter_enabled_companies,
    load_companies_from_directory,
    load_companies_from_file,
)

runner = CliRunner()


class TestLoadCompaniesFromFile:
    """Test loading companies from a single config file."""

    def test_load_valid_config(self):
        """Test loading a valid config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config = {
                "companies": {
                    "Company1": {
                        "name": "Company One",
                        "url": "https://example.com",
                    }
                }
            }
            json.dump(config, f)
            f.flush()

            result = load_companies_from_file(Path(f.name))
            assert "Company1" in result
            assert result["Company1"]["name"] == "Company One"

            Path(f.name).unlink()

    def test_load_missing_file(self):
        """Test loading a non-existent file."""
        with pytest.raises(FileNotFoundError):
            load_companies_from_file(Path("nonexistent.json"))

    def test_load_invalid_json(self):
        """Test loading an invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            f.flush()

            with pytest.raises(ValueError, match="Invalid JSON"):
                load_companies_from_file(Path(f.name))

            Path(f.name).unlink()


class TestLoadCompaniesFromDirectory:
    """Test loading companies from a directory."""

    def test_load_from_directory(self):
        """Test loading all JSON files from a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create multiple config files
            config1 = {
                "companies": {
                    "Company1": {
                        "name": "Company One",
                        "url": "https://example1.com",
                    }
                }
            }
            config2 = {
                "companies": {
                    "Company2": {
                        "name": "Company Two",
                        "url": "https://example2.com",
                    }
                }
            }

            with open(tmppath / "config1.json", "w") as f:
                json.dump(config1, f)

            with open(tmppath / "config2.json", "w") as f:
                json.dump(config2, f)

            result = load_companies_from_directory(tmppath)
            assert len(result) == 2
            assert "Company1" in result
            assert "Company2" in result

    def test_load_from_empty_directory(self):
        """Test loading from a directory with no JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            with pytest.raises(FileNotFoundError, match="No JSON config files"):
                load_companies_from_directory(tmppath)

    def test_load_from_nonexistent_directory(self):
        """Test loading from a non-existent directory."""
        with pytest.raises(FileNotFoundError):
            load_companies_from_directory(Path("nonexistent_dir"))


class TestFilterEnabledCompanies:
    """Test filtering companies by enabled flag."""

    def test_filter_with_enabled_true(self):
        """Test filtering when enabled=true."""
        companies = {
            "Company1": {"enabled": True, "name": "Company One"},
            "Company2": {"enabled": False, "name": "Company Two"},
            "Company3": {"name": "Company Three"},  # No enabled flag (default to True)
        }

        enabled, disabled = filter_enabled_companies(companies)

        assert len(enabled) == 2
        assert len(disabled) == 1
        assert "Company1" in enabled
        assert "Company3" in enabled
        assert "Company2" in disabled

    def test_filter_all_enabled(self):
        """Test filtering when all companies are enabled."""
        companies = {
            "Company1": {"enabled": True, "name": "Company One"},
            "Company2": {"enabled": True, "name": "Company Two"},
        }

        enabled, disabled = filter_enabled_companies(companies)

        assert len(enabled) == 2
        assert len(disabled) == 0

    def test_filter_all_disabled(self):
        """Test filtering when all companies are disabled."""
        companies = {
            "Company1": {"enabled": False, "name": "Company One"},
            "Company2": {"enabled": False, "name": "Company Two"},
        }

        enabled, disabled = filter_enabled_companies(companies)

        assert len(enabled) == 0
        assert len(disabled) == 2

    def test_filter_missing_enabled_defaults_true(self):
        """Test that missing enabled flag defaults to True."""
        companies = {
            "Company1": {"name": "Company One"},
            "Company2": {"name": "Company Two"},
        }

        enabled, disabled = filter_enabled_companies(companies)

        assert len(enabled) == 2
        assert len(disabled) == 0

    def test_filter_preserves_company_data(self):
        """Test that filtering preserves all company data."""
        companies = {
            "Company1": {
                "enabled": True,
                "name": "Company One",
                "url": "https://example.com",
                "selectors": {"job": ".job"},
            }
        }

        enabled, disabled = filter_enabled_companies(companies)

        assert enabled["Company1"]["url"] == "https://example.com"
        assert enabled["Company1"]["selectors"]["job"] == ".job"
