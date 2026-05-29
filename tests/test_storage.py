"""Tests for storage and database functionality."""

import pytest

from storage.db import Database
from storage.queries import CostQueries, JobQueries


@pytest.mark.unit
def test_database_initialization(temp_db):
    """Test database initialization."""
    db = Database(db_path=temp_db)
    assert db.db_path == temp_db


@pytest.mark.unit
def test_job_queries():
    """Test SQL query generation."""
    # Test get_all_jobs
    query = JobQueries.get_all_jobs(status="confirmed", company="TechCorp")
    assert "confirmed" in query
    assert "TechCorp" in query

    # Test search_jobs
    search_query = JobQueries.search_jobs(keyword="Python", min_score=75)
    assert "Python" in search_query
    assert "75" in search_query


@pytest.mark.unit
def test_cost_queries():
    """Test cost tracking queries."""
    total_query = CostQueries.get_total_cost()
    assert "SUM(cost)" in total_query

    phase_query = CostQueries.get_cost_by_phase()
    assert "phase" in phase_query
