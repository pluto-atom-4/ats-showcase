"""Tests for storage and database functionality."""

import pytest

from storage.db import Database


@pytest.mark.unit
def test_database_initialization(temp_db):
    """Test database initialization."""
    db = Database(db_path=temp_db)
    assert db.db_path == temp_db
