"""Parity check script for v3 vs legacy preprocessing (Issue #281 S6).

Compares v3 section-based requirement extraction with legacy trigger-based extraction.
Produces markdown report with parity status for each fixture.

Exit codes:
  0 - Success (parity report generated, no schema violations)
  1 - Schema invariant violation detected (confidence out of range, count mismatch)
  2 - Fatal error (bad argument, missing fixture file)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import spacy
except ImportError:
    spacy = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Ensure src module is importable (for running as script)
_SCRIPT_DIR = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# Default fixture paths
_FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "preprocessing" / "fixtures"
DEFAULT_FIXTURES = [
    Path(__file__).parent.parent / "tests" / "poc" / "fixtures" / "raw_job_description.md",
    _FIXTURES_DIR / "parity_no_headers.md",
    _FIXTURES_DIR / "parity_benefits_heavy.md",
]


def _check_model_available(model_name: str) -> bool:
    """Check if spaCy model is available without loading it.

    Args:
        model_name: Model name (e.g., "en_core_web_md")

    Returns:
        True if model is installed, False otherwise
    """
    if spacy is None:
        return False
    try:
        return bool(spacy.util.is_package(model_name))
    except Exception:
        return False


def _load_fixture(fixture_path: Path) -> Optional[str]:
    """Load fixture markdown file.

    Args:
        fixture_path: Path to fixture file

    Returns:
        File contents or None if not found
    """
    if not fixture_path.exists():
        logger.error(f"Fixture not found: {fixture_path}")
        return None
    try:
        return fixture_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read fixture {fixture_path}: {e}")
        return None


def _extract_v3_metrics(text: str) -> tuple[int, list[str], dict[str, int], float, Any]:
    """Extract v3 metrics from text using SectionDetector (model-free).

    Uses extract_sectioned() directly, bypassing Preprocessor to avoid
    model loading. v3 extraction is model-free since it only uses the
    SectionDetector (spaCy blank pipeline with SpanRuler).

    Args:
        text: Job description text

    Returns:
        Tuple of (requirement_count, sections_detected, requirements_by_section,
                  avg_confidence, sectioned_result)

    Raises:
        ImportError if imports fail
        Exception if extraction fails (caught by caller)
    """
    from src.preprocessing.section_detector import SectionDetector
    from src.preprocessing.section_extractor import extract_sectioned

    detector = SectionDetector()
    result = extract_sectioned(text, detector=detector)

    if result is None or not result.requirements:
        return 0, [], {}, 0.0, result

    # Build metrics
    req_count = len(result.requirements)
    sections = list(result.sections_detected)
    req_by_section = result.requirements_by_section

    # Calculate average confidence
    avg_conf = sum(r.final_confidence for r in result.requirements) / req_count if req_count > 0 else 0.0

    return req_count, sections, req_by_section, avg_conf, result


def _extract_legacy_metrics(text: str, model_name: str = "en_core_web_md") -> tuple[int, list[str], Optional[str]]:
    """Extract legacy metrics using Preprocessor.extract_entities.

    Args:
        text: Job description text
        model_name: spaCy model to use

    Returns:
        Tuple of (requirement_count, requirement_texts, error_msg_or_none)
    """
    from src.tokenization.preprocessor import Preprocessor

    try:
        preprocessor = Preprocessor(model=model_name)
        skills, technologies, requirements = preprocessor.extract_entities(text)
        return len(requirements), list(requirements), None
    except Exception as e:
        return 0, [], str(e)


def _validate_schema_result(result: Any) -> bool:
    """Validate v3 schema invariants against real SectionedResult.

    Args:
        result: SectionedResult object from extract_sectioned

    Returns:
        True if schema is valid, False otherwise
    """
    if result is None:
        return True  # Empty result is valid

    # Check schema_version
    schema_version = getattr(result, "schema_version", None)
    if schema_version != "3.0":
        logger.error(f"Invalid schema_version: {schema_version}, expected '3.0'")
        return False

    # Check confidence values
    requirements = getattr(result, "requirements", [])
    for req in requirements:
        conf = getattr(req, "final_confidence", 0.0)
        if not isinstance(conf, (int, float)) or conf < 0.0 or conf > 1.0:
            logger.error(f"Confidence out of range [0.0, 1.0]: {conf} for requirement '{getattr(req, 'text', '?')}'")
            return False

    # Check requirements_by_section sum matches requirements count
    req_count = len(requirements)
    req_by_section = getattr(result, "requirements_by_section", {})
    section_sum = sum(req_by_section.values())
    if section_sum != req_count:
        logger.error(f"requirements_by_section sum ({section_sum}) != requirements count ({req_count})")
        return False

    return True


def _normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, whitespace collapse)."""
    return " ".join(text.lower().split())


def _compute_text_diff(v3_texts: list[str], legacy_texts: list[str]) -> tuple[int, int]:
    """Compute v3-only and legacy-only text counts.

    Args:
        v3_texts: List of v3 requirement texts
        legacy_texts: List of legacy requirement texts

    Returns:
        Tuple of (v3_only_count, legacy_only_count)
    """
    v3_norm = {_normalize_text(t) for t in v3_texts}
    legacy_norm = {_normalize_text(t) for t in legacy_texts}

    v3_only = len(v3_norm - legacy_norm)
    legacy_only = len(legacy_norm - v3_norm)

    return v3_only, legacy_only


def _process_fixture_row(fixture_path: Path, model_available: bool) -> tuple[str, int]:
    """Process single fixture and return table row + exit code delta.

    Args:
        fixture_path: Path to fixture file
        model_available: Whether spaCy model is available

    Returns:
        Tuple of (table_row_string, exit_code_delta)
    """
    fixture_name = fixture_path.name
    text = _load_fixture(fixture_path)

    if text is None:
        row = f"| {fixture_name} | error | N/A | N/A | N/A | N/A | Failed to load fixture |\n"
        return row, 0

    # Extract v3 metrics with real result
    try:
        (v3_count, v3_sections, v3_by_section, v3_avg_conf, v3_result) = _extract_v3_metrics(text)
    except Exception as e:
        logger.error(f"v3 extraction failed for {fixture_name}: {e}")
        row = f"| {fixture_name} | error | Error | N/A | N/A | N/A | v3 extraction failed: {e} |\n"
        return row, 0

    # Validate schema against REAL v3 result
    schema_valid = _validate_schema_result(v3_result)
    exit_delta = 0 if schema_valid else 1

    # Extract legacy metrics (if model available)
    legacy_count = 0
    legacy_texts: list[str] = []
    legacy_status = "skipped"
    if model_available:
        legacy_count, legacy_texts, error_msg = _extract_legacy_metrics(text)
        legacy_status = "ok" if error_msg is None else "error"
    else:
        legacy_status = "model-unavailable"

    # Get v3 requirement texts for comparison
    v3_texts: list[str] = []
    if v3_result is not None:
        requirements = getattr(v3_result, "requirements", [])
        v3_texts = [getattr(r, "text", "") for r in requirements]

    # Determine parity status and notes
    if legacy_status == "model-unavailable":
        status = "model-unavailable"
        notes = "spaCy model not available; legacy extraction skipped"
    elif legacy_status == "error":
        status = "review"
        notes = "Legacy extraction error"
    elif v3_count < legacy_count:
        status = "review"
        notes = f"v3 count ({v3_count}) < legacy count ({legacy_count})"
    else:  # v3_count >= legacy_count
        status = "equivalent"
        notes = f"v3 count ({v3_count}) >= legacy count ({legacy_count})"

        # Add text diff if legacy ran
        if legacy_status == "ok" and (v3_texts or legacy_texts):
            v3_only, legacy_only = _compute_text_diff(v3_texts, legacy_texts)
            if v3_only > 0 or legacy_only > 0:
                notes += f"; v3-only: {v3_only}, legacy-only: {legacy_only}"

    # Format sections detected
    sections_str = ", ".join(v3_sections) if v3_sections else "none"

    # Add table row
    row = (
        f"| {fixture_name} | {status} | {v3_count} | {sections_str} | {v3_avg_conf:.2f} | {legacy_count} | {notes} |\n"
    )
    return row, exit_delta


def _generate_parity_report(
    fixtures: list[Path],
) -> tuple[str, int]:
    """Generate parity report for fixtures.

    Args:
        fixtures: List of fixture file paths

    Returns:
        Tuple of (markdown_report, exit_code)
        exit_code: 0 for success, 1 for schema invariant violation, 2 for fatal
    """
    lines: list[str] = [
        "# Parity Report: v3 vs Legacy Preprocessing\n",
        f"Generated for {len(fixtures)} fixture(s)\n",
        "---\n",
    ]

    # Table header
    lines.append("| Fixture | Status | v3 Count | v3 Sections | Avg Confidence | Legacy Count | Notes |\n")
    lines.append("|---------|--------|----------|-------------|----------------|--------------|-------|\n")

    exit_code = 0
    model_available = _check_model_available("en_core_web_md")

    for fixture_path in fixtures:
        row, exit_delta = _process_fixture_row(fixture_path, model_available)
        lines.append(row)
        if exit_delta != 0:
            exit_code = exit_delta

    lines.append("\n---\n")
    lines.append("## Metadata\n\n")
    lines.append(f"- spaCy model `en_core_web_md` available: {model_available}\n")
    lines.append("- v3: Section-based requirement extraction with SectionDetector\n")
    lines.append("- Legacy: Trigger-based requirement extraction via extract_entities\n")
    lines.append("- Status 'equivalent': v3 count >= legacy count (good parity)\n")
    lines.append("- Status 'review': v3 < legacy or legacy error (investigate)\n")
    lines.append("- Status 'model-unavailable': spaCy model not installed (expected in CI)\n")
    lines.append("- Exit code 0: All fixtures processed, no schema violations\n")
    lines.append("- Exit code 1: Schema invariant violation detected\n")
    lines.append("- Exit code 2: Fatal error (bad argument, missing fixture)\n")

    return "".join(lines), exit_code


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point.

    Args:
        argv: Command-line arguments (default: sys.argv[1:])

    Returns:
        Exit code: 0 (success), 1 (schema violation), 2 (fatal error)
    """
    parser = argparse.ArgumentParser(description="Generate parity report comparing v3 vs legacy preprocessing")
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--fixtures",
        type=str,
        nargs="+",
        default=[str(p) for p in DEFAULT_FIXTURES],
        help="Fixture file paths (default: standard fixtures)",
    )

    args = parser.parse_args(argv)

    # Convert fixture paths
    fixture_paths: list[Path] = []
    for fixture_str in args.fixtures:
        fixture_path = Path(fixture_str)
        if not fixture_path.exists():
            print(f"Fixture not found: {fixture_path}", file=sys.stderr)
            return 2
        fixture_paths.append(fixture_path)

    # Generate report
    report, exit_code = _generate_parity_report(fixture_paths)

    # Output report
    if args.output:
        try:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report, encoding="utf-8")
            print(f"Report written to {output_path}", file=sys.stderr)
        except Exception as e:
            print(f"Failed to write output file: {e}", file=sys.stderr)
            return 2
    else:
        print(report, end="")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
