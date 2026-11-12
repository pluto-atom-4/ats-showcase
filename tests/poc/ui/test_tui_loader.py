"""Tests for TUI loader module."""

import json
import tempfile
from pathlib import Path

import pytest

from src.poc.ui.loader import (
    Job,
    LoadResult,
    _load_single_file,
    _validate_job,
    discover_source_files,
    load_jobs,
)


class TestValidateJob:
    """Tests for _validate_job function."""

    def test_validate_job_with_all_fields(self) -> None:
        """Valid job with all fields should pass."""
        raw = {
            "id": "job-001",
            "title": "Engineer",
            "company": "TechCorp",
            "location": "Seattle",
            "status": "pending_review",
            "url": "https://example.com",
            "description": "A job",
            "salary_min": 100000,
            "salary_max": 150000,
            "posted_date": "2026-08-20",
            "crawled_at": "2026-08-25T10:00:00",
        }

        job, error = _validate_job(raw, "test.json", 0)

        assert error is None
        assert job is not None
        assert job["id"] == "job-001"
        assert job["title"] == "Engineer"
        assert job["company"] == "TechCorp"
        assert job["location"] == "Seattle"
        assert job["status"] == "pending_review"
        assert job.get("url") == "https://example.com"
        assert job.get("description") == "A job"
        assert job.get("salary_min") == 100000
        assert job.get("salary_max") == 150000
        assert job.get("posted_date") == "2026-08-20"
        assert job.get("crawled_at") == "2026-08-25T10:00:00"

    def test_validate_job_with_required_fields_only(self) -> None:
        """Job with only required fields should pass."""
        raw = {
            "id": "job-002",
            "title": "Manager",
            "company": "BigCorp",
            "location": "Remote",
            "status": "confirmed",
        }

        job, error = _validate_job(raw, "test.json", 0)

        assert error is None
        assert job is not None
        assert job["id"] == "job-002"
        assert "url" not in job or job.get("url") is None

    def test_validate_job_missing_required_field_id(self) -> None:
        """Job missing 'id' should fail."""
        raw = {
            "title": "Engineer",
            "company": "TechCorp",
            "location": "Seattle",
            "status": "pending_review",
        }

        job, error = _validate_job(raw, "test.json", 0)

        assert job is None
        assert error is not None
        assert "Missing required fields" in error
        assert "id" in error

    def test_validate_job_missing_multiple_required_fields(self) -> None:
        """Job missing multiple required fields should fail."""
        raw = {
            "id": "job-001",
            "title": "Engineer",
        }

        job, error = _validate_job(raw, "test.json", 0)

        assert job is None
        assert error is not None
        assert "company" in error
        assert "location" in error
        assert "status" in error

    def test_validate_job_with_none_optional_fields(self) -> None:
        """Job with None values in optional fields should skip them."""
        raw = {
            "id": "job-003",
            "title": "Dev",
            "company": "Corp",
            "location": "NYC",
            "status": "pending_review",
            "url": None,
            "description": None,
            "posted_date": None,
        }

        job, error = _validate_job(raw, "test.json", 0)

        assert error is None
        assert job is not None
        assert "url" not in job or job.get("url") is None
        assert "description" not in job or job.get("description") is None
        assert "posted_date" not in job or job.get("posted_date") is None


class TestLoadSingleFile:
    """Tests for _load_single_file function."""

    def test_load_single_file_valid(self) -> None:
        """Load valid JSON file should succeed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "jobs.json"
            jobs_data = [
                {
                    "id": "job-001",
                    "title": "Engineer",
                    "company": "TechCorp",
                    "location": "Seattle",
                    "status": "pending_review",
                }
            ]
            file_path.write_text(json.dumps(jobs_data))

            jobs, warning = _load_single_file(file_path)

            assert len(jobs) == 1
            assert jobs[0]["id"] == "job-001"
            assert warning is None

    def test_load_single_file_malformed_json(self) -> None:
        """Load malformed JSON file should return error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "bad.json"
            file_path.write_text("{ invalid json }")

            jobs, warning = _load_single_file(file_path)

            assert jobs == []
            assert warning is not None
            assert "Invalid JSON" in warning

    def test_load_single_file_not_array(self) -> None:
        """Load JSON file with object instead of array should fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "object.json"
            file_path.write_text('{"id": "job-001"}')

            jobs, warning = _load_single_file(file_path)

            assert jobs == []
            assert warning is not None
            assert "Expected JSON array" in warning

    def test_load_single_file_partial_validation_errors(self) -> None:
        """Load file with some valid and some invalid entries should load valid ones."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "mixed.json"
            jobs_data = [
                {
                    "id": "job-001",
                    "title": "Engineer",
                    "company": "TechCorp",
                    "location": "Seattle",
                    "status": "pending_review",
                },
                {"id": "job-002", "title": "Manager"},
                {
                    "id": "job-003",
                    "title": "Dev",
                    "company": "Corp",
                    "location": "NYC",
                    "status": "confirmed",
                },
            ]
            file_path.write_text(json.dumps(jobs_data))

            jobs, warning = _load_single_file(file_path)

            assert len(jobs) == 2
            assert jobs[0]["id"] == "job-001"
            assert jobs[1]["id"] == "job-003"
            assert warning is not None
            assert "skipped" in warning.lower()

    def test_load_single_file_not_found(self) -> None:
        """Load non-existent file should return error."""
        file_path = Path("/tmp/nonexistent_xyz123456.json")

        jobs, warning = _load_single_file(file_path)

        assert jobs == []
        assert warning is not None
        assert "Cannot read file" in warning

    def test_load_single_file_empty_array(self) -> None:
        """Load empty JSON array should succeed with zero jobs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "empty.json"
            file_path.write_text("[]")

            jobs, warning = _load_single_file(file_path)

            assert jobs == []
            assert warning is None


class TestDiscoverSourceFiles:
    """Tests for discover_source_files function."""

    def test_discover_source_files_finds_jobs(self) -> None:
        """Discover should find *_jobs.json files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "company1_jobs.json").touch()
            (tmppath / "company2_jobs.json").touch()
            (tmppath / "other_file.json").touch()
            (tmppath / "preprocessed_jobs.json").touch()

            files = discover_source_files(tmppath)

            assert len(files) == 2
            assert all("_jobs.json" in f.name for f in files)
            assert not any("preprocessed_jobs.json" in f.name for f in files)

    def test_discover_source_files_sorted(self) -> None:
        """Discover should return sorted files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "zebra_jobs.json").touch()
            (tmppath / "apple_jobs.json").touch()
            (tmppath / "banana_jobs.json").touch()

            files = discover_source_files(tmppath)

            names = [f.name for f in files]
            assert names == sorted(names)

    def test_discover_source_files_nonexistent_dir(self) -> None:
        """Discover non-existent directory should return empty list."""
        files = discover_source_files(Path("/tmp/nonexistent_xyz123456"))

        assert files == []

    def test_discover_source_files_excludes_specified(self) -> None:
        """Discover should exclude files in exclude set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "regular_jobs.json").touch()
            (tmppath / "preprocessed_jobs.json").touch()
            (tmppath / "skip_me_jobs.json").touch()

            files = discover_source_files(
                tmppath,
                exclude=frozenset({"preprocessed_jobs.json", "skip_me_jobs.json"}),
            )

            assert len(files) == 1
            assert files[0].name == "regular_jobs.json"


class TestLoadJobs:
    """Tests for load_jobs function."""

    def test_load_jobs_from_fixtures(self) -> None:
        """Load jobs from fixture directory."""
        fixture_dir = Path(__file__).parent / "fixtures"

        result = load_jobs(fixture_dir)

        assert isinstance(result, LoadResult)
        assert len(result.jobs) > 0
        assert all(isinstance(job, dict) for job in result.jobs)
        assert len(result.jobs) >= 3

    def test_load_jobs_includes_all_required_fields(self) -> None:
        """Loaded jobs should have all required fields."""
        fixture_dir = Path(__file__).parent / "fixtures"

        result = load_jobs(fixture_dir)

        required_fields = {"id", "title", "company", "location", "status"}
        for job in result.jobs:
            assert required_fields.issubset(job.keys())

    def test_load_jobs_with_warnings(self) -> None:
        """Load jobs should include warnings for problematic files."""
        fixture_dir = Path(__file__).parent / "fixtures"

        result = load_jobs(fixture_dir)

        assert len(result.warnings) > 0

    def test_load_jobs_nonexistent_dir(self) -> None:
        """Load from non-existent directory should return warning and empty result."""
        result = load_jobs(Path("/tmp/nonexistent_xyz123456"))

        assert result.jobs == []
        assert len(result.warnings) > 0
        assert any("Directory not found" in w for w in result.warnings)

    def test_load_jobs_nonexistent_dir_emits_warning(self) -> None:
        """Load from non-existent directory should emit directory not found warning."""
        result = load_jobs(Path("/tmp/nonexistent_xyz_1234567"))

        assert len(result.warnings) > 0
        warning = result.warnings[0]
        assert "Directory not found" in warning

    def test_load_jobs_not_a_directory(self) -> None:
        """Load from file path (not directory) should return warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            file_path = tmppath / "file.txt"
            file_path.write_text("not a directory")

            result = load_jobs(file_path)

            assert result.jobs == []
            assert len(result.warnings) > 0
            assert any("Not a directory" in w for w in result.warnings)

    def test_load_jobs_graceful_failure(self) -> None:
        """Load should gracefully handle a mix of valid and invalid files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            valid_file = tmppath / "valid_jobs.json"
            valid_file.write_text(
                json.dumps(
                    [
                        {
                            "id": "j1",
                            "title": "Role",
                            "company": "Corp",
                            "location": "Place",
                            "status": "pending_review",
                        }
                    ]
                )
            )

            bad_file = tmppath / "bad_jobs.json"
            bad_file.write_text("{ invalid }")

            result = load_jobs(tmppath)

            assert len(result.jobs) == 1
            assert len(result.warnings) > 0

    def test_load_jobs_with_fixture_files(self) -> None:
        """Load jobs from fixture files in temp directory (no git dependency)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            fixture_file = tmppath / "test_jobs.json"
            fixture_file.write_text(
                json.dumps(
                    [
                        {
                            "id": "fixture_1",
                            "title": "Senior Python Developer",
                            "company": "TechCorp",
                            "location": "Remote",
                            "status": "confirmed",
                            "description": "Seeking experienced Python developer",
                        },
                        {
                            "id": "fixture_2",
                            "title": "Java Engineer",
                            "company": "DataCorp",
                            "location": "New York",
                            "status": "pending_review",
                        },
                    ]
                )
            )

            result = load_jobs(base_dir=tmppath)

            assert len(result.jobs) == 2
            assert result.jobs[0]["id"] == "fixture_1"
            assert result.jobs[1]["id"] == "fixture_2"
            assert len(result.warnings) == 0

            for job in result.jobs:
                assert "id" in job
                assert "title" in job
                assert "company" in job
                assert "location" in job
                assert "status" in job


class TestJobTypeHint:
    """Tests to verify Job TypedDict structure."""

    def test_job_type_structure(self) -> None:
        """Verify Job type can hold all documented fields."""
        job: Job = {
            "id": "j1",
            "title": "Engineer",
            "company": "Corp",
            "location": "Remote",
            "status": "pending_review",
            "description": "A role",
            "url": "https://example.com",
            "salary_min": 100000,
            "salary_max": 150000,
            "posted_date": "2026-08-20",
            "crawled_at": "2026-08-25T10:00:00",
        }

        assert job["id"] == "j1"
        assert job["title"] == "Engineer"
        assert job.get("salary_min") == 100000
