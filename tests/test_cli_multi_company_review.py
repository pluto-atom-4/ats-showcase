"""Tests for multi-company review workflow with --merge-all flag."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.exceptions import Exit
from typer.testing import CliRunner

from src.verification.reviewer import JobReviewer, ReviewStats


class TestMultiCompanyReview:
    """Test JobReviewer with multiple extracted company files."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_extracted_files(self, temp_dir):
        """Create sample extracted job files from multiple companies."""
        companies = {
            "carbonrobotics_jobs.json": [
                {
                    "id": "carbonrobotics_1",
                    "title": "Deep Learning Engineer",
                    "company": "CarbonRobotics",
                    "location": "Seattle, WA",
                    "url": "https://carbonrobotics.com/jobs/1",
                    "description": "Looking for deep learning expert",
                },
                {
                    "id": "carbonrobotics_2",
                    "title": "Python Developer",
                    "company": "CarbonRobotics",
                    "location": "Seattle, WA",
                    "url": "https://carbonrobotics.com/jobs/2",
                    "description": "Senior Python developer needed",
                },
            ],
            "boeing_jobs.json": [
                {
                    "id": "boeing_1",
                    "title": "Systems Engineer",
                    "company": "Boeing",
                    "location": "Seattle, WA",
                    "url": "https://boeing.com/jobs/1",
                    "description": "Systems engineering role",
                },
            ],
            "blueorigin_jobs.json": [
                {
                    "id": "blueorigin_1",
                    "title": "Aerospace Engineer",
                    "company": "Blue Origin",
                    "location": "Kent, WA",
                    "url": "https://blueorigin.com/jobs/1",
                    "description": "Aerospace engineering position",
                },
            ],
        }

        files = {}
        for filename, jobs in companies.items():
            filepath = temp_dir / filename
            with open(filepath, "w") as f:
                json.dump(jobs, f)
            files[filename] = (filepath, jobs)

        return files

    @pytest.fixture
    def sample_preprocessed(self, temp_dir, sample_extracted_files):
        """Create preprocessed jobs matching all extracted companies."""
        preprocessed_jobs = []

        for filename, (_filepath, jobs) in sample_extracted_files.items():
            source_name = filename.replace("_jobs.json", "")
            for idx, job in enumerate(jobs):
                preprocessed_job = {
                    "job_id": f"{source_name}_{idx + 1}",
                    "title": job["title"],
                    "company": job["company"],
                    "location": job["location"],
                    "url": job["url"],
                    "clean_text": f"{job['title']}\n{job['location']}\n{job['description']}",
                    "chunks": [job["description"]],
                    "token_count": 150,
                    "estimated_cost": 0.00045,
                    "status": "pending_review",
                }
                preprocessed_jobs.append(preprocessed_job)

        preprocessed_path = temp_dir / "preprocessed_jobs.json"
        with open(preprocessed_path, "w") as f:
            json.dump(preprocessed_jobs, f)

        return preprocessed_path, preprocessed_jobs

    def test_review_batch_single_file_backward_compat(self, temp_dir, sample_extracted_files, sample_preprocessed):
        """Test backward compatibility: review_batch with single file path."""
        preprocessed_path, _ = sample_preprocessed
        extracted_path = sample_extracted_files["carbonrobotics_jobs.json"][0]

        db_path = temp_dir / "test.db"
        reviewer = JobReviewer(str(db_path))

        # Mock interactive review to auto-confirm all
        def mock_review_func(*args, **kwargs):
            stats = args[-1]
            stats.total += 1
            stats.add_confirmed(150, 0.00045)

        with patch.object(reviewer, "review_job_interactive", side_effect=mock_review_func):
            # Call with single Path (backward compat)
            stats = reviewer.review_batch(extracted_path, str(preprocessed_path))

        assert stats.confirmed == 2
        assert stats.total == 2
        reviewer._close_db()

    def test_review_batch_single_file_string(self, temp_dir, sample_extracted_files, sample_preprocessed):
        """Test backward compatibility: review_batch with string path."""
        preprocessed_path, _ = sample_preprocessed
        extracted_path = str(sample_extracted_files["carbonrobotics_jobs.json"][0])

        db_path = temp_dir / "test.db"
        reviewer = JobReviewer(str(db_path))

        def mock_review_func(*args, **kwargs):
            stats = args[-1]
            stats.total += 1
            stats.add_confirmed(150, 0.00045)

        with patch.object(reviewer, "review_job_interactive", side_effect=mock_review_func):
            # Call with string path (backward compat)
            stats = reviewer.review_batch(extracted_path, str(preprocessed_path))

        assert stats.confirmed == 2
        assert stats.total == 2
        reviewer._close_db()

    def test_review_batch_multiple_files(self, temp_dir, sample_extracted_files, sample_preprocessed):
        """Test review_batch with multiple extracted files (new functionality)."""
        preprocessed_path, preprocessed_jobs = sample_preprocessed
        extracted_files = [f[0] for f in sample_extracted_files.values()]

        db_path = temp_dir / "test.db"
        reviewer = JobReviewer(str(db_path))

        def mock_review_func(*args, **kwargs):
            stats = args[-1]
            stats.total += 1
            stats.add_confirmed(150, 0.00045)

        with patch.object(reviewer, "review_job_interactive", side_effect=mock_review_func):
            # Call with list of files
            stats = reviewer.review_batch(extracted_files, str(preprocessed_path))

        # Should process all jobs: 2 from carbonrobotics + 1 from boeing + 1 from blueorigin = 4 total
        assert stats.confirmed == 4
        assert stats.total == 4
        assert stats.total_tokens == 600  # 4 jobs * 150 tokens
        assert stats.total_cost == 0.0018  # 4 jobs * 0.00045 cost

        reviewer._close_db()

    def test_review_batch_multiple_files_mixed_results(self, temp_dir, sample_extracted_files, sample_preprocessed):
        """Test review_batch with multiple files and mixed confirm/reject results."""
        preprocessed_path, _ = sample_preprocessed
        extracted_files = [f[0] for f in sample_extracted_files.values()]

        db_path = temp_dir / "test.db"
        reviewer = JobReviewer(str(db_path))

        call_count = 0

        def side_effect_mixed(*args, **kwargs):
            nonlocal call_count
            stats = args[-1]
            stats.total += 1
            if call_count % 2 == 0:
                stats.add_confirmed(150, 0.00045)
            else:
                stats.add_rejected("location")
            call_count += 1

        with patch.object(reviewer, "review_job_interactive", side_effect=side_effect_mixed):
            stats = reviewer.review_batch(extracted_files, str(preprocessed_path))

        # 4 jobs: 2 confirmed, 2 rejected
        assert stats.confirmed == 2
        assert stats.rejected == 2
        assert stats.total == 4

        reviewer._close_db()

    def test_review_batch_missing_preprocessed_file(self, temp_dir, sample_extracted_files):
        """Test error handling when preprocessed file doesn't exist."""
        extracted_files = [f[0] for f in sample_extracted_files.values()]

        db_path = temp_dir / "test.db"
        reviewer = JobReviewer(str(db_path))

        with pytest.raises(Exit):
            reviewer.review_batch(extracted_files, str(temp_dir / "nonexistent.json"))

        reviewer._close_db()

    def test_review_batch_missing_extracted_file(self, temp_dir, sample_preprocessed):
        """Test error handling when extracted file doesn't exist."""
        preprocessed_path, _ = sample_preprocessed
        extracted_files = [temp_dir / "nonexistent_jobs.json"]

        db_path = temp_dir / "test.db"
        reviewer = JobReviewer(str(db_path))

        with pytest.raises(Exit):
            reviewer.review_batch(extracted_files, str(preprocessed_path))

        reviewer._close_db()

    def test_review_batch_loads_multiple_extracted_files(self, temp_dir, sample_extracted_files, sample_preprocessed):
        """Test that review_batch correctly loads multiple extracted files."""
        preprocessed_path, _ = sample_preprocessed
        extracted_files = [f[0] for f in sample_extracted_files.values()]

        db_path = temp_dir / "test.db"
        reviewer = JobReviewer(str(db_path))

        # Track job count
        job_count_processed = 0

        def counter_review(*args, **kwargs):
            nonlocal job_count_processed
            stats = args[-1]
            stats.total += 1
            stats.add_confirmed(150, 0.00045)
            job_count_processed += 1

        with patch.object(reviewer, "review_job_interactive", side_effect=counter_review):
            stats = reviewer.review_batch(extracted_files, str(preprocessed_path))

        # 4 files with 2, 1, 1 jobs respectively = 4 total jobs
        assert job_count_processed == 4
        assert stats.total == 4

        reviewer._close_db()
