"""Tests for database initialization helpers."""

import logging
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.storage._init_helpers import initialize_db_common


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield str(Path(tmpdir) / "test.db")


class TestInitializeDbCommon:
    """Tests for initialize_db_common function."""

    def test_successful_initialization(self, temp_db_path):
        """Test successful database initialization."""
        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)",
            "another_table": "CREATE TABLE IF NOT EXISTS another_table (id INTEGER PRIMARY KEY, value TEXT)",
        }

        conn = initialize_db_common(temp_db_path, tables)

        # Verify connection is created
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)

        # Verify row_factory is set
        assert conn.row_factory == sqlite3.Row

        # Verify tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        assert cursor.fetchone() is not None

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='another_table'")
        assert cursor.fetchone() is not None

        conn.close()

    def test_creates_parent_directory(self, temp_db_path):
        """Test that parent directory is created if it doesn't exist."""
        nested_path = str(Path(temp_db_path).parent / "nested" / "deep" / "test.db")

        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)",
        }

        conn = initialize_db_common(nested_path, tables)

        # Verify directory was created
        assert Path(nested_path).parent.exists()

        # Verify database file was created
        assert Path(nested_path).exists()

        conn.close()

    def test_row_factory_set_to_row(self, temp_db_path):
        """Test that row_factory is set to sqlite3.Row."""
        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)",
        }

        conn = initialize_db_common(temp_db_path, tables)

        assert conn.row_factory == sqlite3.Row

        # Verify we can access columns by name
        cursor = conn.cursor()
        cursor.execute("INSERT INTO test_table (name) VALUES (?)", ("test",))
        cursor.execute("SELECT * FROM test_table")
        row = cursor.fetchone()

        assert row["name"] == "test"

        conn.close()

    def test_multiple_tables_created(self, temp_db_path):
        """Test that all tables in the dictionary are created."""
        tables = {
            "table1": "CREATE TABLE IF NOT EXISTS table1 (id INTEGER PRIMARY KEY)",
            "table2": "CREATE TABLE IF NOT EXISTS table2 (id INTEGER PRIMARY KEY, data TEXT)",
            "table3": "CREATE TABLE IF NOT EXISTS table3 (id INTEGER PRIMARY KEY, value REAL)",
        }

        conn = initialize_db_common(temp_db_path, tables)

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM sqlite_master WHERE type='table'")
        count = cursor.fetchone()["count"]

        # Should have at least our 3 tables (SQLite may have internal tables)
        assert count >= 3

        conn.close()

    def test_empty_tables_dict(self, temp_db_path):
        """Test initialization with empty tables dictionary."""
        tables = {}

        conn = initialize_db_common(temp_db_path, tables)

        # Should still return a valid connection
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)

        conn.close()

    def test_table_creation_failure(self, temp_db_path):
        """Test that table creation failure raises an error."""
        # Invalid SQL will cause OperationalError
        tables = {
            "bad_table": "INVALID SQL STATEMENT",
        }

        with pytest.raises(sqlite3.OperationalError):
            initialize_db_common(temp_db_path, tables)

    def test_connection_committed(self, temp_db_path):
        """Test that connection is committed after table creation."""
        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)",
        }

        conn = initialize_db_common(temp_db_path, tables)
        conn.close()

        # Reopen connection and verify table persisted
        new_conn = sqlite3.connect(temp_db_path)
        cursor = new_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        assert cursor.fetchone() is not None
        new_conn.close()

    def test_handles_existing_tables(self, temp_db_path):
        """Test that CREATE TABLE IF NOT EXISTS doesn't fail for existing tables."""
        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)",
        }

        # Create tables first time
        conn1 = initialize_db_common(temp_db_path, tables)
        conn1.close()

        # Create again - should not fail
        conn2 = initialize_db_common(temp_db_path, tables)
        assert conn2 is not None

        cursor = conn2.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        assert cursor.fetchone() is not None

        conn2.close()

    def test_connection_failure(self, temp_db_path):
        """Test error handling when connection fails."""
        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)",
        }

        # Patch sqlite3.connect to raise an error
        with patch("sqlite3.connect") as mock_connect:
            mock_connect.side_effect = sqlite3.OperationalError("Cannot open database")

            with pytest.raises(sqlite3.OperationalError):
                initialize_db_common(temp_db_path, tables)

    @patch("src.storage._init_helpers.Path.mkdir")
    def test_mkdir_failure(self, mock_mkdir, temp_db_path):
        """Test error handling when directory creation fails."""
        mock_mkdir.side_effect = OSError("Permission denied")

        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)",
        }

        with pytest.raises(OSError):
            initialize_db_common(temp_db_path, tables)

    def test_returns_connection_object(self, temp_db_path):
        """Test that function returns a sqlite3.Connection object."""
        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)",
        }

        conn = initialize_db_common(temp_db_path, tables)

        assert isinstance(conn, sqlite3.Connection)

        conn.close()

    def test_database_file_created(self, temp_db_path):
        """Test that database file is created at specified path."""
        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)",
        }

        initialize_db_common(temp_db_path, tables)

        assert Path(temp_db_path).exists()

    def test_complex_schema(self, temp_db_path):
        """Test with a more complex schema including constraints and indices."""
        tables = {
            "jobs": """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT,
                    location TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "assessments": """
                CREATE TABLE IF NOT EXISTS assessments (
                    assessment_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    score REAL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
            """,
        }

        conn = initialize_db_common(temp_db_path, tables)

        cursor = conn.cursor()

        # Verify jobs table exists and has correct schema
        cursor.execute("PRAGMA table_info(jobs)")
        columns = cursor.fetchall()
        column_names = [row[1] for row in columns]
        assert "job_id" in column_names
        assert "title" in column_names

        # Verify assessments table exists
        cursor.execute("PRAGMA table_info(assessments)")
        columns = cursor.fetchall()
        column_names = [row[1] for row in columns]
        assert "assessment_id" in column_names
        assert "job_id" in column_names

        conn.close()

    def test_logging_success(self, temp_db_path, caplog):
        """Test that success is logged."""
        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY)",
        }

        # Capture log at INFO level
        with caplog.at_level(logging.INFO):
            conn = initialize_db_common(temp_db_path, tables)

            # Check that info log was created
            assert any(
                "Initialized database" in record.message for record in caplog.records if record.levelname == "INFO"
            )

            conn.close()

    def test_concurrent_access_safe(self, temp_db_path):
        """Test that multiple connections can access the same database."""
        tables = {
            "test_table": "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, value TEXT)",
        }

        conn1 = initialize_db_common(temp_db_path, tables)
        conn2 = initialize_db_common(temp_db_path, tables)

        # Insert via first connection
        cursor1 = conn1.cursor()
        cursor1.execute("INSERT INTO test_table (value) VALUES (?)", ("test1",))
        conn1.commit()

        # Read via second connection
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT COUNT(*) as count FROM test_table")
        count = cursor2.fetchone()["count"]

        assert count == 1

        conn1.close()
        conn2.close()
