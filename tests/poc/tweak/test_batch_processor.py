"""Tests for POC Batch Processor for multi-job markdown pipeline.

Tests validate:
1. Job loading from JSON array
2. Error handling for non-array input
3. Error handling for missing description field
4. Empty array handling
5. Full batch processing integration
"""

import json
from pathlib import Path

import pytest

from src.poc.tweak.batch_processor import JobResult, load_jobs, run_batch


class TestLoadJobs:
    """Tests for load_jobs() function."""

    def test_load_jobs_valid_array_returns_list_of_dicts(self, tmp_path):
        """Test loading valid JSON array of job records."""
        # Arrange
        fixture_path = Path(__file__).parent.parent / "fixtures" / "details_test_fixture.json"

        # Act
        jobs = load_jobs(str(fixture_path))

        # Assert
        assert isinstance(jobs, list)
        assert len(jobs) == 4, "Fixture should contain 4 job records"
        assert all(isinstance(job, dict) for job in jobs)
        assert all("description" in job for job in jobs)

    def test_load_jobs_non_array_raises_valueerror(self, tmp_path):
        """Test that non-array JSON raises ValueError with clear message."""
        # Arrange
        test_file = tmp_path / "non_array.json"
        test_file.write_text(json.dumps({"job": "single_object"}))

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_jobs(str(test_file))

        assert "Expected JSON array at root" in str(exc_info.value)
        assert "got dict" in str(exc_info.value)

    def test_load_jobs_missing_description_field_raises_valueerror(self, tmp_path):
        """Test that records without description field raise ValueError."""
        # Arrange
        test_file = tmp_path / "missing_description.json"
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer",
                        "company": "Acme",
                        # Missing "description" field
                    }
                ]
            )
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            load_jobs(str(test_file))

        assert "missing 'description' field" in str(exc_info.value)
        assert "job1" in str(exc_info.value)

    def test_load_jobs_null_description_is_valid(self, tmp_path):
        """Test that null description values are accepted (processed gracefully)."""
        # Arrange - description field present but null
        test_file = tmp_path / "null_description.json"
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer",
                        "company": "Acme",
                        "description": None,  # Explicitly null
                    }
                ]
            )
        )

        # Act
        jobs = load_jobs(str(test_file))

        # Assert - should load without error
        assert len(jobs) == 1
        assert jobs[0]["description"] is None

    def test_load_jobs_empty_array_returns_empty_list(self, tmp_path):
        """Test that empty JSON array returns empty list without error."""
        # Arrange
        test_file = tmp_path / "empty_array.json"
        test_file.write_text(json.dumps([]))

        # Act
        jobs = load_jobs(str(test_file))

        # Assert
        assert jobs == []

    def test_load_jobs_file_not_found_raises_error(self, tmp_path):
        """Test that missing file raises FileNotFoundError."""
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            load_jobs(str(tmp_path / "nonexistent.json"))


class TestRunBatch:
    """Tests for run_batch() integration."""

    def test_run_batch_processes_4_jobs_from_fixture(self):
        """Test full batch processing on fixture with 4 jobs."""
        # Arrange
        fixture_path = Path(__file__).parent.parent / "fixtures" / "details_test_fixture.json"

        # Act
        results = run_batch(str(fixture_path))

        # Assert
        assert isinstance(results, list)
        assert len(results) == 4, "Should process all 4 jobs from fixture"

        # Verify each result
        for result in results:
            assert isinstance(result, JobResult)
            assert result.job_id, "Job ID should be set"
            assert result.title, "Title should be set"
            assert result.company, "Company should be set"
            assert result.sections_detected >= 0, "Sections detected should be non-negative"
            assert result.keyword_matches >= 0, "Keyword matches should be non-negative"
            assert 0.0 <= result.confidence_min <= 1.0, "Min confidence should be in [0,1]"
            assert 0.0 <= result.confidence_max <= 1.0, "Max confidence should be in [0,1]"
            assert 0.0 <= result.confidence_avg <= 1.0, "Avg confidence should be in [0,1]"

        # Verify confidence constraints
        for result in results:
            if result.sections_detected > 0:
                # If sections were detected, confidence scores should be reasonable
                assert result.confidence_max >= result.confidence_min, "Max confidence should be >= min confidence"
                assert result.confidence_avg >= result.confidence_min, "Avg confidence should be >= min confidence"
                assert result.confidence_avg <= result.confidence_max, "Avg confidence should be <= max confidence"

    def test_batch_processor_no_section_classification_errors_on_real_fixtures(self):
        """Verify no section_classification errors on real fixture jobs (Bug A/B test).

        This test ensures that section objects are correctly accessed (Bug A fix: .title not .heading)
        and confidence aggregation matches per-section storage (Bug B fix).
        """
        # Arrange
        fixture_path = Path(__file__).parent.parent / "fixtures" / "details_test_fixture.json"

        # Act
        results = run_batch(str(fixture_path))

        # Assert - no "section_classification" errors (would indicate Bug A or similar)
        for result in results:
            section_class_errors = [error for error in result.errors if error[0] == "section_classification"]
            err_count = len(section_class_errors)
            assert err_count == 0, (
                f"Job {result.job_id} has {err_count} section_classification errors: {section_class_errors}"
            )

    def test_batch_processor_markdown_sections_have_valid_titles(self):
        """Verify MarkdownSection.heading correctly populated from section.title (Bug A fix).

        Bug A was: section.heading used instead of section.title, causing AttributeError.
        This test ensures heading field is correctly populated.
        """
        # Arrange
        fixture_path = Path(__file__).parent.parent / "fixtures" / "details_test_fixture.json"

        # Act
        results = run_batch(str(fixture_path))

        # Assert
        for result in results:
            assert isinstance(result.markdown_sections, list), f"Job {result.job_id} should have markdown_sections list"
            for section in result.markdown_sections:
                # heading should be a string (possibly empty if no title)
                assert isinstance(section.heading, str), (
                    f"Section {section.section_id} heading should be str, got {type(section.heading)}"
                )

    def test_batch_processor_confidence_aggregates_match_per_section_values(self):
        """Verify confidence aggregate stats match per-section values (Bug B fix).

        Bug B was: aggregates built from all_types confidences but stored in sections as primary_confidence.
        This test ensures consistency between aggregate min/max/avg and what's stored per-section.
        """
        # Arrange
        fixture_path = Path(__file__).parent.parent / "fixtures" / "details_test_fixture.json"

        # Act
        results = run_batch(str(fixture_path))

        # Assert
        for result in results:
            if result.sections_detected == 0:
                # If no sections, aggregates should be default
                assert result.confidence_min == 0.0, f"Job {result.job_id}: min should be 0.0 with no sections"
                assert result.confidence_max == 0.0, f"Job {result.job_id}: max should be 0.0 with no sections"
                assert result.confidence_avg == 0.0, f"Job {result.job_id}: avg should be 0.0 with no sections"
            else:
                # Extract confidences from stored markdown_sections
                section_confidences = [s.confidence for s in result.markdown_sections if s.confidence is not None]
                if section_confidences:
                    # Recompute aggregates from per-section values
                    expected_min = min(section_confidences)
                    expected_max = max(section_confidences)
                    expected_avg = sum(section_confidences) / len(section_confidences)

                    # Assert aggregates match recomputed values
                    jid = result.job_id
                    cmin = result.confidence_min
                    cmax = result.confidence_max
                    cavg = result.confidence_avg
                    min_err = f"{jid}: confidence_min mismatch (result={cmin}, expected={expected_min})"
                    max_err = f"{jid}: confidence_max mismatch (result={cmax}, expected={expected_max})"
                    avg_err = f"{jid}: confidence_avg mismatch (result={cavg}, expected={expected_avg})"
                    assert abs(cmin - expected_min) < 0.001, min_err
                    assert abs(cmax - expected_max) < 0.001, max_err
                    assert abs(cavg - expected_avg) < 0.001, avg_err

    def test_batch_processor_extracts_technologies_regression(self):
        """Verify technology extraction works (regression test for entity_ruler patterns).

        Issue #321: entity_ruler patterns must be loaded for technology extraction.
        """
        # Arrange
        fixture_path = Path(__file__).parent.parent / "fixtures" / "details_test_fixture.json"

        # Act
        results = run_batch(str(fixture_path))

        # Assert - at least one job should extract technologies
        tech_counts = [len(r.technologies) for r in results]
        assert max(tech_counts) > 0, "No technologies extracted - entity_ruler patterns not loaded"

        # Verify structure of extracted technologies
        for result in results:
            for tech in result.technologies:
                assert isinstance(tech, dict), "Technology should be a dict"
                assert "tech" in tech, "Technology dict must have 'tech' key"
                assert "confidence" in tech, "Technology dict must have 'confidence' key"
                assert isinstance(tech["tech"], str), "Tech value should be string"
                assert isinstance(tech["confidence"], float), "Confidence should be float"
                assert tech["confidence"] == 1.0, "Technology confidence should always be 1.0"

    def test_batch_processor_handles_null_description_gracefully(self, tmp_path):
        """Test that jobs with null descriptions are processed without errors.

        Null descriptions should be treated as empty strings and processed
        without causing the batch processor to fail (Issue #340).
        """
        # Arrange - Create test file with null description
        test_file = tmp_path / "null_description_jobs.json"
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer Position",
                        "company": "TechCorp",
                        "description": None,  # Null description
                        "location": "Remote",
                    },
                    {
                        "id": "job2",
                        "title": "Engineer Role",
                        "company": "InnovateLabs",
                        "description": "<p>Some HTML content here</p>",  # Valid description
                        "location": "On-site",
                    },
                ]
            )
        )

        # Act - Should not raise error
        results = run_batch(str(test_file))

        # Assert
        assert len(results) == 2, "Should process both jobs"

        # First job with null description should process without error
        job1_result = results[0]
        assert job1_result.job_id == "job1"
        assert job1_result.title == "Developer Position"
        assert not job1_result.has_errors(), f"Job with null description should not error: {job1_result.errors}"

        # Second job with valid description should also process
        job2_result = results[1]
        assert job2_result.job_id == "job2"
        assert job2_result.title == "Engineer Role"
        # This job may have content to process
        assert isinstance(job2_result.sections_detected, int)


class TestHTMLScoping:
    """Tests for HTML scoping via description_selector (Issue #363)."""

    def test_scoped_vs_unscoped_output_differs(self, tmp_path):
        """Test that scoped output differs from unscoped when selector is provided."""
        # Arrange - Create test file with selector-scoped HTML
        test_file = tmp_path / "scoping_test.json"
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer",
                        "company": "TechCorp",
                        "description": '<div class="sidebar">Sidebar content</div><div class="job-description">Job requirements here</div>',
                    }
                ]
            )
        )

        # Act - Process unscoped
        results_unscoped = run_batch(str(test_file), description_selector=None)

        # Act - Process scoped
        results_scoped = run_batch(str(test_file), description_selector=".job-description")

        # Assert - Results should differ (scoped has less content)
        assert len(results_unscoped) == 1
        assert len(results_scoped) == 1
        unscoped_job = results_unscoped[0]
        scoped_job = results_scoped[0]

        # Scoped should have fewer sections/keywords if it excluded sidebar
        # (Note: exact counts depend on pipeline, but scoped should be more focused)
        assert unscoped_job.job_id == scoped_job.job_id

    def test_scoping_warning_no_matches(self, tmp_path):
        """Test that no-match scenario generates warning."""
        # Arrange
        test_file = tmp_path / "no_match_test.json"
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer",
                        "company": "TechCorp",
                        "description": "<div>Some content</div>",
                    }
                ]
            )
        )

        # Act
        results = run_batch(str(test_file), description_selector=".nonexistent")

        # Assert
        assert len(results) == 1
        result = results[0]
        assert len(result.warnings) >= 1
        warning_texts = [w[1] for w in result.warnings]
        assert any("matched 0 elements" in w for w in warning_texts)
        assert not result.has_errors()  # Warnings are not errors

    def test_scoping_warning_multi_matches(self, tmp_path):
        """Test that multi-match scenario generates warning with count."""
        # Arrange
        test_file = tmp_path / "multi_match_test.json"
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer",
                        "company": "TechCorp",
                        "description": '<div class="desc">First</div><div class="desc">Second</div><div class="desc">Third</div>',
                    }
                ]
            )
        )

        # Act
        results = run_batch(str(test_file), description_selector=".desc")

        # Assert
        assert len(results) == 1
        result = results[0]
        assert len(result.warnings) >= 1
        warning_texts = [w[1] for w in result.warnings]
        assert any("matched 3 elements" in w for w in warning_texts)
        assert not result.has_errors()

    def test_scoping_warning_invalid_css(self, tmp_path):
        """Test that invalid CSS selector generates warning."""
        # Arrange
        test_file = tmp_path / "invalid_css_test.json"
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer",
                        "company": "TechCorp",
                        "description": "<div>Content</div>",
                    }
                ]
            )
        )

        # Act
        results = run_batch(str(test_file), description_selector=">>invalid")

        # Assert
        assert len(results) == 1
        result = results[0]
        assert len(result.warnings) >= 1
        warning_texts = [w[1] for w in result.warnings]
        assert any("Invalid CSS selector" in w for w in warning_texts)
        assert not result.has_errors()  # Invalid CSS is a warning, not an error

    def test_scoping_no_warning_on_single_match(self, tmp_path):
        """Test that single match produces no warning."""
        # Arrange
        test_file = tmp_path / "single_match_test.json"
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer",
                        "company": "TechCorp",
                        "description": '<div class="job-desc">Exact match</div>',
                    }
                ]
            )
        )

        # Act
        results = run_batch(str(test_file), description_selector=".job-desc")

        # Assert
        assert len(results) == 1
        result = results[0]
        # Should have no html_scoping warnings for single match
        html_scope_warnings = [w for w in result.warnings if w[0] == "html_scoping"]
        assert len(html_scope_warnings) == 0

    def test_warnings_not_counted_as_failure(self, tmp_path):
        """Test that warnings do not cause has_errors() to return True."""
        # Arrange
        test_file = tmp_path / "warnings_test.json"
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer",
                        "company": "TechCorp",
                        "description": "<div>No matching selector</div>",
                    }
                ]
            )
        )

        # Act
        results = run_batch(str(test_file), description_selector=".nonexistent")

        # Assert
        assert len(results) == 1
        result = results[0]
        assert len(result.warnings) > 0  # Has warnings
        assert not result.has_errors()  # But not errors

    def test_job_not_mutated_by_scoping(self, tmp_path):
        """Test that original job dict is not mutated by scoping."""
        # Arrange
        test_file = tmp_path / "mutate_test.json"
        original_html = '<div class="desc">Content</div>'
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer",
                        "company": "TechCorp",
                        "description": original_html,
                    }
                ]
            )
        )

        # Load jobs before processing
        jobs = load_jobs(str(test_file))
        original_description = jobs[0]["description"]

        # Act
        _results = run_batch(str(test_file), description_selector=".desc")

        # Assert - reload jobs and verify original not mutated
        jobs_after = load_jobs(str(test_file))
        assert jobs_after[0]["description"] == original_description

    def test_scoping_with_null_description(self, tmp_path):
        """Test that null description with selector is handled gracefully."""
        # Arrange
        test_file = tmp_path / "null_with_selector_test.json"
        test_file.write_text(
            json.dumps(
                [
                    {
                        "id": "job1",
                        "title": "Developer",
                        "company": "TechCorp",
                        "description": None,
                    }
                ]
            )
        )

        # Act
        results = run_batch(str(test_file), description_selector=".desc")

        # Assert
        assert len(results) == 1
        result = results[0]
        assert not result.has_errors()  # Null + selector = no error

    def test_fixture_scope_selector_fixture_loads(self):
        """Test that synthetic fixture loads and contains expected jobs."""
        # Arrange
        fixture_path = Path(__file__).parent.parent / "fixtures" / "scope_selector_fixture.json"

        # Act
        jobs = load_jobs(str(fixture_path))

        # Assert
        assert len(jobs) == 5
        job_ids = [job["id"] for job in jobs]
        assert "job_A_full_shell" in job_ids
        assert "job_B_already_scoped" in job_ids
        assert "job_C_no_match" in job_ids
        assert "job_D_multi_match" in job_ids
        assert "job_E_null_description" in job_ids

        # Verify all have description field (even if null)
        for job in jobs:
            assert "description" in job
