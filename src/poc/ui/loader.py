"""Load job listings from extracted_jobs/*.json files with graceful error handling."""

import json
from pathlib import Path
from typing import NamedTuple, NotRequired, TypedDict


class Job(TypedDict):
    """Job listing with required and optional fields."""

    id: str
    title: str
    company: str
    location: str
    status: str
    description: NotRequired[str | None]
    url: NotRequired[str]
    salary_min: NotRequired[float | None]
    salary_max: NotRequired[float | None]
    posted_date: NotRequired[str | None]
    crawled_at: NotRequired[str | None]


class LoadResult(NamedTuple):
    """Result from loading jobs, including warnings for failed files."""

    jobs: list[Job]
    warnings: list[str]


def discover_source_files(
    base_dir: Path = Path("data/extracted_jobs"),
    pattern: str = "*_jobs.json",
    exclude: frozenset[str] = frozenset({"preprocessed_jobs.json"}),
) -> list[Path]:
    """Discover source JSON files matching pattern, excluding specified files.

    Args:
        base_dir: Directory to search for job files.
        pattern: Glob pattern for filenames.
        exclude: Filenames to skip.

    Returns:
        Sorted list of Path objects matching the pattern and not in exclude.
    """
    if not base_dir.exists():
        return []

    files = [f for f in base_dir.glob(pattern) if f.name not in exclude]
    return sorted(files)


def _validate_job(raw: dict, source_file: str, index: int) -> tuple[Job | None, str | None]:
    """Validate a raw job dict has required fields. Return (job, error_msg) tuple.

    Args:
        raw: Raw dictionary from JSON.
        source_file: Filename for error messages.
        index: Job index in file for error messages.

    Returns:
        (Job dict, None) on success or (None, error_msg) on validation failure.
    """
    required_fields = {"id", "title", "company", "location", "status"}

    missing = required_fields - set(raw.keys())
    if missing:
        return None, (f"{source_file}[{index}]: Missing required fields: {', '.join(sorted(missing))}")

    # Build job with required fields + optional fields with safe defaults
    job: Job = {
        "id": raw["id"],
        "title": raw["title"],
        "company": raw["company"],
        "location": raw["location"],
        "status": raw["status"],
    }

    # Add optional fields if present
    if "description" in raw and raw["description"] is not None:
        job["description"] = raw["description"]
    if "url" in raw and raw["url"] is not None:
        job["url"] = raw["url"]
    if "salary_min" in raw:
        job["salary_min"] = raw["salary_min"]
    if "salary_max" in raw:
        job["salary_max"] = raw["salary_max"]
    if "posted_date" in raw and raw["posted_date"] is not None:
        job["posted_date"] = raw["posted_date"]
    if "crawled_at" in raw and raw["crawled_at"] is not None:
        job["crawled_at"] = raw["crawled_at"]

    return job, None


def _load_single_file(path: Path) -> tuple[list[Job], str | None]:
    """Load jobs from a single JSON file. Return (jobs, error_msg) tuple.

    Args:
        path: Path to JSON file.

    Returns:
        (jobs list, None) on success or ([], error_msg) on failure.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [], f"{path.name}: Invalid JSON: {e}"
    except OSError as e:
        return [], f"{path.name}: Cannot read file: {e}"

    if not isinstance(data, list):
        return [], f"{path.name}: Expected JSON array at top level, got {type(data).__name__}"

    jobs: list[Job] = []
    validation_errors = []

    for i, raw in enumerate(data):
        if not isinstance(raw, dict):
            validation_errors.append(f"{path.name}[{i}]: Expected object, got {type(raw).__name__}")
            continue

        job, error = _validate_job(raw, path.name, i)
        if error:
            validation_errors.append(error)
            continue

        assert job is not None  # error is None only when job is not None
        jobs.append(job)

    # If all entries failed validation, return error
    if validation_errors and not jobs:
        return [], f"{path.name}: All entries failed validation ({len(validation_errors)} errors)"

    # If some entries failed, log those but continue with successful ones
    warning = None
    if validation_errors:
        warning = f"{path.name}: {len(validation_errors)} entries skipped (validation errors)"

    return jobs, warning


def load_jobs(base_dir: Path = Path("data/extracted_jobs")) -> LoadResult:
    """Load jobs from all source files in base_dir.

    Gracefully handles missing files, malformed JSON, and validation errors.
    Continues loading other files even if some fail.

    Warnings are generated for:
    - Missing directory
    - Path is not a directory (but file exists)

    Note: Empty directories do NOT generate warnings (normal state).

    Args:
        base_dir: Directory containing job JSON files.

    Returns:
        LoadResult with all successfully loaded jobs and list of warnings.
    """
    all_jobs: list[Job] = []
    warnings: list[str] = []

    # Check if base_dir exists
    if not base_dir.exists():
        warnings.append(f"{base_dir}: Directory not found")
        return LoadResult(all_jobs, warnings)

    # Check if base_dir is a directory
    if not base_dir.is_dir():
        warnings.append(f"{base_dir}: Not a directory")
        return LoadResult(all_jobs, warnings)

    # Directory exists and is valid, discover and load files
    files = discover_source_files(base_dir)

    for file_path in files:
        jobs, warning = _load_single_file(file_path)
        all_jobs.extend(jobs)

        if warning:
            warnings.append(warning)

    return LoadResult(all_jobs, warnings)
