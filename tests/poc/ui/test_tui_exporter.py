"""Tests for TUI exporter module."""

import json
import tempfile
from pathlib import Path

import pytest

from src.poc.ui.exporter import ensure_work_dir, export_jobs
from src.poc.ui.loader import Job


class TestEnsureWorkDir:
    """Tests for ensure_work_dir function."""

    def test_ensure_work_dir_creates_missing_directory(self) -> None:
        """ensure_work_dir should create missing parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "work" / "subdir" / "selected.json"

            ensure_work_dir(output_path)

            assert output_path.parent.exists()

    def test_ensure_work_dir_noop_if_exists(self) -> None:
        """ensure_work_dir should be a no-op if directory exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "selected.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            ensure_work_dir(output_path)

            assert output_path.parent.exists()

    def test_ensure_work_dir_handles_nested_paths(self) -> None:
        """ensure_work_dir should handle deeply nested paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "a" / "b" / "c" / "d" / "e" / "selected.json"

            ensure_work_dir(output_path)

            assert output_path.parent.exists()


class TestExportJobs:
    """Tests for export_jobs function."""

    def test_export_jobs_creates_file(self) -> None:
        """export_jobs should create a JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "work" / "selected.json"

            jobs: list[Job] = [
                {
                    "id": "j1",
                    "title": "Engineer",
                    "company": "Corp",
                    "location": "Seattle",
                    "status": "pending_review",
                }
            ]

            result = export_jobs(jobs, output_path)

            assert result == output_path
            assert output_path.exists()

    def test_export_jobs_writes_valid_json(self) -> None:
        """Exported file should contain valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "selected.json"

            jobs: list[Job] = [
                {
                    "id": "j1",
                    "title": "Engineer",
                    "company": "Corp",
                    "location": "Seattle",
                    "status": "pending_review",
                    "url": "https://example.com",
                }
            ]

            export_jobs(jobs, output_path)

            with open(output_path) as f:
                loaded = json.load(f)

            assert isinstance(loaded, list)
            assert len(loaded) == 1
            assert loaded[0]["id"] == "j1"
            assert loaded[0]["title"] == "Engineer"

    def test_export_jobs_multiple_jobs(self) -> None:
        """Export should handle multiple jobs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "selected.json"

            jobs: list[Job] = [
                {
                    "id": f"j{i}",
                    "title": f"Role {i}",
                    "company": "Corp",
                    "location": "Place",
                    "status": "pending_review",
                }
                for i in range(5)
            ]

            export_jobs(jobs, output_path)

            with open(output_path) as f:
                loaded = json.load(f)

            assert len(loaded) == 5
            assert all(job["id"] == f"j{i}" for i, job in enumerate(loaded))

    def test_export_jobs_empty_list(self) -> None:
        """Export should handle empty job list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "selected.json"

            export_jobs([], output_path)

            with open(output_path) as f:
                loaded = json.load(f)

            assert loaded == []

    def test_export_jobs_overwrites_existing(self) -> None:
        """Export should overwrite existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "selected.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            initial_job: Job = {
                "id": "old",
                "title": "Old",
                "company": "Corp",
                "location": "Place",
                "status": "pending_review",
            }
            with open(output_path, "w") as f:
                json.dump([initial_job], f)

            new_jobs: list[Job] = [
                {
                    "id": "new",
                    "title": "New",
                    "company": "Corp",
                    "location": "Place",
                    "status": "pending_review",
                }
            ]
            export_jobs(new_jobs, output_path)

            with open(output_path) as f:
                loaded = json.load(f)

            assert len(loaded) == 1
            assert loaded[0]["id"] == "new"

    def test_export_jobs_with_all_optional_fields(self) -> None:
        """Export should preserve all optional fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "selected.json"

            jobs: list[Job] = [
                {
                    "id": "j1",
                    "title": "Engineer",
                    "company": "Corp",
                    "location": "Seattle",
                    "status": "pending_review",
                    "description": "A great role",
                    "url": "https://example.com",
                    "salary_min": 120000,
                    "salary_max": 160000,
                    "posted_date": "2026-08-20",
                    "crawled_at": "2026-08-25T10:00:00",
                }
            ]

            export_jobs(jobs, output_path)

            with open(output_path) as f:
                loaded = json.load(f)

            assert loaded[0]["description"] == "A great role"
            assert loaded[0]["salary_min"] == 120000
            assert loaded[0]["posted_date"] == "2026-08-20"

    def test_export_jobs_creates_parent_dirs(self) -> None:
        """Export should create parent directories if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "deep" / "nested" / "path" / "selected.json"

            jobs: list[Job] = [
                {
                    "id": "j1",
                    "title": "Role",
                    "company": "Corp",
                    "location": "Place",
                    "status": "pending_review",
                }
            ]

            export_jobs(jobs, output_path)

            assert output_path.exists()
            assert output_path.parent.exists()

    def test_export_jobs_returns_path(self) -> None:
        """export_jobs should return the output path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "selected.json"

            jobs: list[Job] = []

            result = export_jobs(jobs, output_path)

            assert result == output_path

    def test_export_jobs_uses_proper_encoding(self) -> None:
        """Export should use UTF-8 encoding for non-ASCII characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "selected.json"

            jobs: list[Job] = [
                {
                    "id": "j1",
                    "title": "Ingenieur (French)",
                    "company": "Société Générale",
                    "location": "Paris, France",
                    "status": "confirmed",
                }
            ]

            export_jobs(jobs, output_path)

            with open(output_path, encoding="utf-8") as f:
                loaded = json.load(f)

            assert loaded[0]["company"] == "Société Générale"
            assert "Ingenieur" in loaded[0]["title"]

    def test_export_jobs_pretty_prints_json(self) -> None:
        """Exported JSON should be pretty-printed with indentation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output_path = tmppath / "selected.json"

            jobs: list[Job] = [
                {
                    "id": "j1",
                    "title": "Role",
                    "company": "Corp",
                    "location": "Place",
                    "status": "pending_review",
                }
            ]

            export_jobs(jobs, output_path)

            content = output_path.read_text()

            assert "\n" in content
            assert "  " in content
