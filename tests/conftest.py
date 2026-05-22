"""Pytest configuration and shared fixtures."""

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        yield db_path
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.fixture
def env_vars(monkeypatch):
    """Set up test environment variables."""
    test_env = {
        "ANTHROPIC_API_KEY": "test-key-12345",
        "DATABASE_PATH": "test.db",
        "SPACY_MODEL": "en_core_web_md",
        "LOG_LEVEL": "DEBUG",
        "PLAYWRIGHT_HEADLESS": "true",
    }
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)
    return test_env


@pytest.fixture
def sample_job_data():
    """Sample job posting data for testing."""
    return {
        "title": "Senior Python Developer",
        "company": "Tech Corp",
        "location": "San Francisco, CA",
        "description": """
        We are looking for a Senior Python Developer with 5+ years of experience.

        Requirements:
        - Python 3.11+
        - FastAPI/Django experience
        - PostgreSQL/MongoDB
        - Docker & Kubernetes
        - AWS knowledge preferred

        Responsibilities:
        - Design and implement backend systems
        - Collaborate with frontend team
        - Optimize database queries

        Benefits:
        - Competitive salary
        - Health insurance
        - 401(k) matching
        """,
        "salary_min": 150000,
        "salary_max": 200000,
        "posted_date": "2026-05-19",
    }


@pytest.fixture
def sample_cv_data():
    """Sample CV data for testing."""
    return {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1-555-0123",
        "skills": [
            "Python",
            "JavaScript",
            "React",
            "FastAPI",
            "PostgreSQL",
            "Docker",
            "AWS",
        ],
        "experience": [
            {
                "title": "Senior Developer",
                "company": "Tech Company",
                "duration": "2020-present",
                "description": "Led backend infrastructure redesign",
            },
        ],
        "education": [
            {
                "degree": "BS Computer Science",
                "school": "State University",
                "year": 2016,
            },
        ],
    }
