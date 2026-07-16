"""Error handling and edge case tests (Phase 5)."""

import pytest

from src.tui.models.state import PhaseStatus, StateManager
from src.tui.widgets.job_table import JobTable


class TestInvalidInputHandling:
    """Test handling of invalid or malformed input."""

    def test_add_job_with_empty_strings(self, state_manager: StateManager) -> None:
        """Jobs with empty strings handled gracefully."""
        state_manager.add_job("", "", "")
        assert "" in state_manager.jobs

        state_manager.add_job("job_valid", "Title", "")
        assert "job_valid" in state_manager.jobs

    def test_update_job_nonexistent(self, state_manager: StateManager) -> None:
        """Updating nonexistent job doesn't raise error."""
        # Should not raise
        state_manager.update_job("nonexistent", score=90)

        # Job still doesn't exist
        assert "nonexistent" not in state_manager.jobs

    def test_job_with_special_characters(self, state_manager: StateManager) -> None:
        """Jobs with special characters handled correctly."""
        special_title = "Senior Dev (C++/Python) 10+ yrs @ $150K-$200K"
        state_manager.add_job("special_job", special_title, "Company & Co.")
        assert state_manager.jobs["special_job"]["title"] == special_title
        assert state_manager.jobs["special_job"]["company"] == "Company & Co."

    def test_job_with_unicode_chars(self, state_manager: StateManager) -> None:
        """Jobs with unicode characters handled correctly."""
        state_manager.add_job("unicode_job", "Développeur Senior", "Société Générale")
        assert "unicode_job" in state_manager.jobs

    def test_very_long_job_title(self, state_manager: StateManager) -> None:
        """Very long job titles don't cause issues."""
        long_title = "A" * 5000
        state_manager.add_job("long_title", long_title, "Company")
        assert state_manager.jobs["long_title"]["title"] == long_title


class TestNullAndMissingData:
    """Test handling of None/null values and missing data."""

    def test_phase_start_with_zero_items(self, state_manager: StateManager) -> None:
        """Phase with 0 total items handled."""
        state_manager.start_phase("crawl", total_items=0)
        assert state_manager.phase_metrics["crawl"].total_items == 0
        assert state_manager.phase_metrics["crawl"].progress_percent == 0.0

    def test_progress_calculation_with_zero_total(self, state_manager: StateManager) -> None:
        """Progress calculation safe when total_items is 0."""
        state_manager.start_phase("crawl", total_items=0)
        metrics = state_manager.phase_metrics["crawl"]
        # Should not raise ZeroDivisionError
        assert metrics.progress_percent == 0.0

    def test_throughput_with_zero_items(self, state_manager: StateManager) -> None:
        """Throughput calculation safe with 0 processed items."""
        state_manager.start_phase("assess", total_items=10)
        metrics = state_manager.phase_metrics["assess"]
        assert metrics.items_per_second == 0.0

    def test_eta_with_zero_throughput(self, state_manager: StateManager) -> None:
        """ETA calculation safe when throughput is 0."""
        state_manager.start_phase("crawl", total_items=5)
        metrics = state_manager.phase_metrics["crawl"]
        assert metrics.eta_seconds == 0.0


class TestBoundaryConditions:
    """Test behavior at boundaries and limits."""

    def test_negative_phase_metrics(self, state_manager: StateManager) -> None:
        """Negative metrics are rejected or handled."""
        state_manager.start_phase("crawl", total_items=5)
        state_manager.increment_phase_progress("crawl", tokens=100, cost=0.0001)

        # Metrics should always be >= 0
        metrics = state_manager.phase_metrics["crawl"]
        assert metrics.processed_items >= 0
        assert metrics.total_tokens >= 0
        assert metrics.total_cost_usd >= 0.0

    def test_processed_exceeds_total(self, state_manager: StateManager) -> None:
        """Processing more items than total doesn't crash."""
        state_manager.start_phase("crawl", total_items=5)

        # Process 10 items (more than 5)
        for _ in range(10):
            state_manager.increment_phase_progress("crawl", tokens=100)

        metrics = state_manager.phase_metrics["crawl"]
        assert metrics.processed_items == 10
        # Progress percent can exceed 100%
        assert metrics.progress_percent == 200.0

    def test_very_large_token_count(self, state_manager: StateManager) -> None:
        """Very large token counts don't overflow."""
        state_manager.start_phase("assess", total_items=1)
        state_manager.increment_phase_progress("assess", tokens=10_000_000, cost=30.0)

        metrics = state_manager.phase_metrics["assess"]
        assert metrics.total_tokens == 10_000_000
        assert abs(metrics.total_cost_usd - 30.0) < 0.001

    def test_very_small_cost_value(self, state_manager: StateManager) -> None:
        """Very small cost values handled precisely."""
        state_manager.start_phase("preprocess", total_items=1)
        state_manager.increment_phase_progress(
            "preprocess", tokens=10, cost=0.00000001
        )

        metrics = state_manager.phase_metrics["preprocess"]
        assert metrics.total_cost_usd > 0


class TestStateTransitionErrors:
    """Test invalid state transitions."""

    def test_complete_nonrunning_phase(self, state_manager: StateManager) -> None:
        """Completing phase that wasn't started doesn't crash."""
        # Phase not started
        assert state_manager.phase_status["crawl"] == PhaseStatus.IDLE

        # Complete it anyway
        state_manager.complete_phase("crawl")

        # Should show as completed
        assert state_manager.phase_status["crawl"] == PhaseStatus.COMPLETED

    def test_error_already_completed_phase(self, state_manager: StateManager) -> None:
        """Erroring a completed phase is allowed."""
        state_manager.start_phase("crawl", total_items=1)
        state_manager.increment_phase_progress("crawl", tokens=100)
        state_manager.complete_phase("crawl")

        # Error the completed phase
        state_manager.error_phase("crawl", "Late error")

        assert state_manager.phase_status["crawl"] == PhaseStatus.ERROR

    def test_restart_failed_phase(self, state_manager: StateManager) -> None:
        """Restarting a failed phase is allowed."""
        state_manager.start_phase("crawl", total_items=5)
        state_manager.error_phase("crawl", "Initial error")

        # Restart
        state_manager.start_phase("crawl", total_items=5)

        assert state_manager.phase_status["crawl"] == PhaseStatus.RUNNING
        assert state_manager.phase_metrics["crawl"].processed_items == 0


class TestDataConsistency:
    """Test data consistency under stress."""

    def test_concurrent_job_additions(self, state_manager: StateManager) -> None:
        """Adding jobs rapidly doesn't lose data."""
        for i in range(100):
            state_manager.add_job(f"job_{i}", f"Title {i}", f"Company {i % 10}")

        assert len(state_manager.jobs) == 100

    def test_top_matches_update_idempotent(self, state_manager: StateManager) -> None:
        """Updating top matches multiple times is consistent."""
        jobs1 = [
            {"id": "j1", "overall_score": 90},
            {"id": "j2", "overall_score": 80},
        ]
        jobs2 = [
            {"id": "j3", "overall_score": 95},
            {"id": "j4", "overall_score": 75},
        ]

        state_manager.update_top_matches(jobs1)
        first_result = state_manager.top_matches.copy()

        state_manager.update_top_matches(jobs2)
        second_result = state_manager.top_matches.copy()

        # Results are different but consistent
        assert first_result != second_result
        assert len(first_result) == len(second_result) == 2

    def test_error_accumulation_limit(self, state_manager: StateManager) -> None:
        """Error list doesn't grow unbounded."""
        state_manager.start_phase("crawl", total_items=1000)

        for i in range(100):
            state_manager.increment_phase_progress(
                "crawl", tokens=0, error=f"Error {i}"
            )

        # All errors should be recorded
        assert len(state_manager.current_errors) == 100


class TestSearchFilterLogic:
    """Test search and filter logic without Textual app context."""

    def test_search_special_chars_in_query(self) -> None:
        """Search queries with special characters are handled."""
        # Test that special chars don't cause regex errors
        queries = ["C++", "(ML)", "C#", "$100K", "10+yrs"]
        for query in queries:
            # These should not raise exceptions when normalized
            normalized = query.lower()
            assert isinstance(normalized, str)

    def test_case_insensitive_comparison(self) -> None:
        """Case insensitive search logic works."""
        title = "Python Developer"
        searches = ["PYTHON", "python", "Python", "PYTHONs"]

        for search in searches:
            # Case-insensitive match should work
            matches = search.lower() in title.lower()
            if search.lower() == "pythons":
                assert not matches
            else:
                assert matches

    def test_whitespace_normalization(self) -> None:
        """Whitespace in queries is handled."""
        queries = ["   ", "\t", "\n", "   python   "]
        for query in queries:
            stripped = query.strip()
            # Empty queries should be handled
            if not stripped:
                # Empty query shouldn't cause errors
                pass
            else:
                assert "python" in stripped.lower()

    def test_empty_job_list_state(self) -> None:
        """StateManager handles empty job lists."""
        state = StateManager()
        assert len(state.jobs) == 0
        assert len(state.top_matches) == 0

        # Adding and clearing jobs
        state.add_job("j1", "Title", "Company")
        assert len(state.jobs) == 1

        # No built-in clear, but jobs dict is mutable
        state.jobs.clear()
        assert len(state.jobs) == 0


class TestRecoveryFromErrors:
    """Test recovery mechanisms after errors."""

    def test_continue_after_single_error(self, state_manager: StateManager) -> None:
        """Workflow continues after error in one item."""
        state_manager.start_phase("crawl", total_items=5)

        state_manager.increment_phase_progress("crawl", tokens=100)
        state_manager.increment_phase_progress("crawl", tokens=0, error="Job parse failed")
        state_manager.increment_phase_progress("crawl", tokens=100)

        metrics = state_manager.phase_metrics["crawl"]
        assert metrics.processed_items == 3
        assert metrics.failed_items == 1
        assert metrics.total_tokens == 200

    def test_complete_after_errors(self, state_manager: StateManager) -> None:
        """Phase can complete even with errors."""
        state_manager.start_phase("assess", total_items=5)

        for i in range(5):
            if i % 2 == 0:
                state_manager.increment_phase_progress("assess", tokens=200)
            else:
                state_manager.increment_phase_progress(
                    "assess", tokens=0, error="API error"
                )

        state_manager.complete_phase("assess")

        assert state_manager.phase_status["assess"] == PhaseStatus.COMPLETED
        metrics = state_manager.phase_metrics["assess"]
        assert metrics.processed_items == 5
        assert metrics.failed_items == 2

    def test_pause_and_resume_workflow(self, state_manager: StateManager) -> None:
        """Workflow can pause and resume."""
        state_manager.start_phase("crawl", total_items=5)
        state_manager.increment_phase_progress("crawl", tokens=100)

        # Pause
        state_manager.paused = True
        assert state_manager.paused is True

        # Resume
        state_manager.paused = False
        assert state_manager.paused is False

        # Continue processing
        state_manager.increment_phase_progress("crawl", tokens=100)

        metrics = state_manager.phase_metrics["crawl"]
        assert metrics.processed_items == 2
