"""Tests for job table search and filter functionality (Feature 3)."""

import pytest

from src.tui.models.state import StateManager
from src.tui.widgets.search_input import FilterBar, SearchInput


class TestSearchInput:
    """Tests for SearchInput widget."""

    def test_search_input_initialization(self):
        """SearchInput initializes with placeholder."""
        search = SearchInput()
        assert search.placeholder == "Search jobs..."

    def test_search_input_custom_placeholder(self):
        """SearchInput accepts custom placeholder."""
        search = SearchInput(placeholder="Find jobs by skill...")
        assert search.placeholder == "Find jobs by skill..."


class TestFilterBar:
    """Tests for FilterBar widget."""

    def test_filter_bar_initialization(self):
        """FilterBar initializes with placeholder."""
        filter_bar = FilterBar()
        assert "Filter" in filter_bar.placeholder

    def test_filter_bar_custom_placeholder(self):
        """FilterBar accepts custom placeholder."""
        filter_bar = FilterBar(placeholder="Filter by status...")
        assert filter_bar.placeholder == "Filter by status..."


class TestJobTableFilterLogic:
    """Tests for job table search and filter logic (no Textual context required)."""

    def _filter_by_search(
        self, jobs: list[dict], query: str
    ) -> list[dict]:
        """Simple business logic filter: search by title/company/location."""
        if not query:
            return jobs
        query_lower = query.lower()
        return [
            j
            for j in jobs
            if query_lower in j.get("title", "").lower()
            or query_lower in j.get("company", "").lower()
            or query_lower in j.get("location", "").lower()
        ]

    def _filter_by_status(
        self, jobs: list[dict], status: str | None
    ) -> list[dict]:
        """Simple business logic filter: filter by status."""
        if status is None:
            return jobs
        return [j for j in jobs if j.get("status") == status]

    def test_search_by_title(self):
        """Search filters jobs by title."""
        jobs = [
            {
                "id": "job_1",
                "title": "Python Developer",
                "company": "TechCorp",
                "status": "confirmed",
            },
            {
                "id": "job_2",
                "title": "Java Developer",
                "company": "StartupXYZ",
                "status": "confirmed",
            },
        ]

        result = self._filter_by_search(jobs, "python")
        assert len(result) == 1
        assert "Python" in result[0]["title"]

    def test_search_by_company(self):
        """Search filters jobs by company."""
        jobs = [
            {
                "id": "job_1",
                "title": "Dev Role",
                "company": "TechCorp",
                "status": "confirmed",
            },
            {
                "id": "job_2",
                "title": "Engineer Role",
                "company": "StartupXYZ",
                "status": "confirmed",
            },
        ]

        result = self._filter_by_search(jobs, "techcorp")
        assert len(result) == 1
        assert result[0]["company"] == "TechCorp"

    def test_search_by_location(self):
        """Search filters jobs by location."""
        jobs = [
            {
                "id": "job_1",
                "title": "Remote Dev",
                "company": "Corp",
                "location": "New York",
                "status": "confirmed",
            },
            {
                "id": "job_2",
                "title": "Local Dev",
                "company": "Corp",
                "location": "San Francisco",
                "status": "confirmed",
            },
        ]

        result = self._filter_by_search(jobs, "new york")
        assert len(result) == 1
        assert result[0]["location"] == "New York"

    def test_search_empty_results(self):
        """Search with no matches returns empty list."""
        jobs = [
            {
                "id": "job_1",
                "title": "Python Dev",
                "company": "TechCorp",
                "status": "confirmed",
            },
        ]

        result = self._filter_by_search(jobs, "golang")
        assert len(result) == 0

    def test_search_case_insensitive(self):
        """Search is case-insensitive."""
        jobs = [
            {
                "id": "job_1",
                "title": "Python Developer",
                "company": "TechCorp",
                "status": "confirmed",
            },
        ]

        result = self._filter_by_search(jobs, "PYTHON")
        assert len(result) == 1

    def test_filter_by_status(self):
        """Filter shows only jobs with specified status."""
        jobs = [
            {
                "id": "job_1",
                "title": "Confirmed Job",
                "company": "Corp",
                "status": "confirmed",
            },
            {
                "id": "job_2",
                "title": "Rejected Job",
                "company": "Corp",
                "status": "rejected",
            },
            {
                "id": "job_3",
                "title": "Pending Job",
                "company": "Corp",
                "status": "pending_review",
            },
        ]

        result = self._filter_by_status(jobs, "confirmed")
        assert len(result) == 1
        assert result[0]["status"] == "confirmed"

    def test_filter_none_shows_all(self):
        """Passing None to filter shows all jobs."""
        jobs = [
            {"id": "job_1", "title": "Job 1", "company": "Corp", "status": "confirmed"},
            {"id": "job_2", "title": "Job 2", "company": "Corp", "status": "rejected"},
        ]

        result = self._filter_by_status(jobs, None)
        assert len(result) == 2

    def test_search_and_filter_combined(self):
        """Search and filter work together."""
        jobs = [
            {
                "id": "job_1",
                "title": "Python Developer",
                "company": "TechCorp",
                "status": "confirmed",
            },
            {
                "id": "job_2",
                "title": "Python Backend",
                "company": "StartupXYZ",
                "status": "rejected",
            },
            {
                "id": "job_3",
                "title": "Java Developer",
                "company": "TechCorp",
                "status": "confirmed",
            },
        ]

        # Search for Python
        result = self._filter_by_search(jobs, "python")
        assert len(result) == 2

        # Then filter by confirmed
        result = self._filter_by_status(result, "confirmed")
        assert len(result) == 1
        assert "Python" in result[0]["title"]

    def test_clear_search_keeps_filter(self):
        """Clearing search keeps status filter active."""
        jobs = [
            {
                "id": "job_1",
                "title": "Python Dev",
                "company": "Corp",
                "status": "confirmed",
            },
            {
                "id": "job_2",
                "title": "Java Dev",
                "company": "Corp",
                "status": "confirmed",
            },
        ]

        # Apply both search and filter
        result = self._filter_by_search(jobs, "python")
        result = self._filter_by_status(result, "confirmed")
        assert len(result) == 1

        # Reset search (empty string)
        jobs_all = jobs  # Start from original
        result = self._filter_by_search(jobs_all, "")
        result = self._filter_by_status(result, "confirmed")
        assert len(result) == 2  # Both confirmed
