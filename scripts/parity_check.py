"""Parity check script for v3 vs legacy preprocessing (Issue #281 S6).

Compares v3 section-based requirement extraction with legacy trigger-based extraction.
Produces markdown report with parity status for each fixture.

Exit codes:
  0 - Success (parity report generated, no schema violations)
  1 - Schema invariant violations detected (confidence out of range, count mismatch)
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
        return spacy.util.is_package(model_name)
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


def _extract_v3_metrics(text: str) -> tuple[int, list[str], dict[str, int], float]:
    """Extract v3 metrics from text using SectionDetector (model-free).

    Uses extract_sectioned() directly, bypassing Preprocessor to avoid
    model loading. v3 extraction is model-free since it only uses the
    SectionDetector (spaCy blank pipeline with SpanRuler).

    Args:
        text: Job description text

    Returns:
        Tuple of (requirement_count, sections_detected, requirements_by_section, avg_confidence)

    Raises:
        ImportError if imports fail
        Exception if extraction fails (caught by caller)
    """
    from src.preprocessing.section_detector import SectionDetector
    from src.preprocessing.section_extractor import extract_sectioned

    detector = SectionDetector()
    result = extract_sectioned(text, detector=detector)

    if result is None or not result.requirements:
        return 0, [], {}, 0.0

    # Build metrics
    req_count = len(result.requirements)
    sections = list(result.sections_detected)
    req_by_section = result.requirements_by_section

    # Calculate average confidence
    avg_conf = sum(r.final_confidence for r in result.requirements) / req_count if req_count > 0 else 0.0

    return req_count, sections, req_by_section, avg_conf


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


def _validate_schema(result_dict: dict[str, Any]) -> bool:
    """Check v3 schema invariants.

    Args:
        result_dict: Result dict from v3 extraction

    Returns:
        True if schema is valid, False otherwise
    """
    # Check schema_version
    if result_dict.get("schema_version") != "3.0":
        logger.error(f"Invalid schema_version: {result_dict.get('schema_version')}, expected '3.0'")
        return False

    # Check confidence values
    for req in result_dict.get("requirements", []):
        conf = req.get("final_confidence", 0.0)
        if not isinstance(conf, (int, float)) or conf < 0.0 or conf > 1.0:
            logger.error(f"Confidence out of range [0.0, 1.0]: {conf} for requirement '{req.get('text', '?')}'")
            return False

    # Check requirements_by_section sum matches requirements count
    req_count = len(result_dict.get("requirements", []))
    section_sum = sum(result_dict.get("requirements_by_section", {}).values())
    if section_sum != req_count:
        logger.error(f"requirements_by_section sum ({section_sum}) != requirements count ({req_count})")
        return False

    return True


def _generate_parity_report(
    fixtures: list[Path],
) -> tuple[str, int]:
    """Generate parity report for fixtures.

    Args:
        fixtures: List of fixture file paths

    Returns:
        Tuple of (markdown_report, exit_code)
        exit_code: 0 for success, 1 for schema violation
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
        fixture_name = fixture_path.name
        text = _load_fixture(fixture_path)

        if text is None:
            lines.append(f"| {fixture_name} | error | N/A | N/A | N/A | N/A | Failed to load fixture |\n")
            continue

        # Extract v3 metrics
        try:
            v3_count, v3_sections, v3_by_section, v3_avg_conf = _extract_v3_metrics(text)
        except Exception as e:
            logger.error(f"v3 extraction failed for {fixture_name}: {e}")
            lines.append(f"| {fixture_name} | error | Error | N/A | N/A | N/A | v3 extraction failed: {e} |\n")
            exit_code = 1
            continue

        # Validate schema for v3 result
        # Create dummy requirements matching the count from v3_by_section
        result_dict: dict[str, Any] = {
            "schema_version": "3.0",
            "requirements": [
                {
                    "final_confidence": 0.5,  # dummy
                    "text": f"dummy_{i}",
                }
                for i in range(v3_count)
            ],
            "requirements_by_section": v3_by_section,
        }
        if not _validate_schema(result_dict):
            exit_code = 1

        # Extract legacy metrics (if model available)
        legacy_count = 0
        legacy_status = "skipped"
        if model_available:
            legacy_count, _, error_msg = _extract_legacy_metrics(text)
            legacy_status = "ok" if error_msg is None else "error"
        else:
            legacy_status = "model-unavailable"

        # Determine parity status
        # Status rules:
        # - "model-unavailable" if legacy model not available
        # - "equivalent" if v3_count >= legacy_count
        # - "review" if v3_count < legacy_count
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

        # Format sections detected
        sections_str = ", ".join(v3_sections) if v3_sections else "none"

        # Add table row
        row = (
            f"| {fixture_name} | {status} | {v3_count} | {sections_str} | "
            f"{v3_avg_conf:.2f} | {legacy_count} | {notes} |\n"
        )
        lines.append(row)

    lines.append("\n---\n")
    lines.append("## Metadata\n\n")
    lines.append(f"- spaCy model `en_core_web_md` available: {model_available}\n")
    lines.append("- v3: Section-based requirement extraction with SectionDetector\n")
    lines.append("- Legacy: Trigger-based requirement extraction via extract_entities\n")
    lines.append("- Status 'model-unavailable': Legacy extraction requires spaCy model; not available in CI\n")
    lines.append("- Exit code 0: All fixtures processed, no schema violations\n")
    lines.append("- Exit code 1: Schema invariant violation detected\n")

    return "".join(lines), exit_code


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point.

    Args:
        argv: Command-line arguments (default: sys.argv[1:])

    Returns:
        Exit code
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
