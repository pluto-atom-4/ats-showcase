"""POC Batch Processor for multi-job markdown pipeline.

This module runs multiple job descriptions through the 4-stage spaCy markdown
pipeline to validate and test the processing workflow.

Stages:
1. HTMLPreprocessor: Clean HTML, normalize structure
2. HTMLMarkdownConverter: Convert HTML to Markdown using MarkItDown
3. MarkdownPolisher: Apply formatting rules for polished output
4. MarkdownSpanRuler: Parse sections from markdown content
5. SectionClassifier: Classify parsed sections into semantic types
6. RequirementProcessor: Extract requirements from sections (Issue #321)
7. SkillProcessor: Extract skills from sections (Issue #321)
8. TechnologyProcessor: Extract technologies from sections (Issue #321)

Components are instantiated once and reused across all jobs for efficiency.
Per-job errors are captured without aborting the batch.

Usage:
    >>> from src.poc.tweak.batch_processor import run_batch, print_summary
    >>>
    >>> results = run_batch("data/work/details_test.json")
    >>> summary = print_summary(results)
    >>> print(summary)

CLI:
    python -m src.poc.tweak.batch_processor --input-path data/work/details_test.json
    python -m src.poc.tweak.batch_processor --input-path data/work/details_test.json --output-json results.json
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import spacy

from src.poc.tweak.markdown_section_classifier import SectionClassifier
from src.poc.tweak.multi_line_paragraph import MarkdownSpanRuler
from src.poc.tweak.spacy_pipeline import (
    HTMLMarkdownConverter,
    HTMLPreprocessor,
    MarkdownPolisher,
    RequirementProcessor,
    SkillProcessor,
    TechnologyProcessor,
)


@dataclass
class JobResult:
    """Result of processing a single job through the markdown pipeline.

    Attributes:
        job_id: Unique identifier for the job
        title: Job title
        company: Company name
        sections_detected: Number of markdown sections detected
        keyword_matches: Total number of keyword matches in classifications
        confidence_min: Minimum confidence score across classifications
        confidence_max: Maximum confidence score across classifications
        confidence_avg: Average confidence score across classifications
        requirements: List of extracted requirements (Issue #321)
        skills: List of extracted skills (Issue #321)
        technologies: List of extracted technologies (Issue #321)
        errors: List of (stage_name, error_message) tuples for per-stage errors
    """

    job_id: str
    title: str
    company: str
    sections_detected: int
    keyword_matches: int
    confidence_min: float
    confidence_max: float
    confidence_avg: float
    requirements: List[Dict[str, Any]] = field(default_factory=list)
    skills: List[Dict[str, Any]] = field(default_factory=list)
    technologies: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[tuple] = field(default_factory=list)

    def add_error(self, stage: str, error: str) -> None:
        """Add a per-stage error to the result.

        Args:
            stage: Pipeline stage name (e.g., 'preprocessor', 'converter')
            error: Error message
        """
        self.errors.append((stage, error))

    def has_errors(self) -> bool:
        """Check if this job had any processing errors."""
        return len(self.errors) > 0


def load_jobs(path: str) -> List[Dict[str, Any]]:
    """Load and validate jobs from JSON file.

    Validates that:
    - Input is a JSON array
    - Each record contains a 'description' field
    - description field is non-empty

    Args:
        path: Path to JSON file containing job records

    Returns:
        List of job record dicts

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON is not an array or records lack description field
        json.JSONDecodeError: If JSON is malformed
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Job file not found: {path}")

    with open(file_path) as f:
        data = json.load(f)

    # Validate input is array
    if not isinstance(data, list):
        raise ValueError(
            f"Expected JSON array at root, got {type(data).__name__}. Input must be an array of job records."
        )

    # Validate each record has description field
    for i, job in enumerate(data):
        if not isinstance(job, dict):
            raise ValueError(f"Record {i} is not a dict (type: {type(job).__name__}). Each job must be an object.")
        if "description" not in job:
            raise ValueError(
                f"Record {i} (ID: {job.get('id', 'unknown')}) missing 'description' field. "
                "Each job must have a description."
            )
        if not job["description"]:
            raise ValueError(
                f"Record {i} (ID: {job.get('id', 'unknown')}) has empty description. Description cannot be empty."
            )

    return data


def process_job(
    job: Dict[str, Any],
    *,
    preprocessor: HTMLPreprocessor,
    converter: HTMLMarkdownConverter,
    polisher: MarkdownPolisher,
    classifier: SectionClassifier,
    ruler: MarkdownSpanRuler,
    req_processor: RequirementProcessor,
    skill_processor: SkillProcessor,
    tech_processor: TechnologyProcessor,
) -> JobResult:
    """Process a single job through the markdown pipeline.

    Runs job through 8 stages with per-stage error handling. Errors are captured
    in JobResult.errors and do not abort processing.

    Stages:
    1. HTMLPreprocessor: Clean raw HTML
    2. HTMLMarkdownConverter: Convert HTML to Markdown
    3. MarkdownPolisher: Polish Markdown formatting
    4. MarkdownSpanRuler: Parse sections from markdown
    5. SectionClassifier: Classify sections via keyword-based matching
    6. RequirementProcessor: Extract requirements (Issue #321)
    7. SkillProcessor: Extract skills (Issue #321)
    8. TechnologyProcessor: Extract technologies (Issue #321)

    Args:
        job: Job record dict (must have 'id', 'title', 'company', 'description')
        preprocessor: HTMLPreprocessor instance
        converter: HTMLMarkdownConverter instance
        polisher: MarkdownPolisher instance
        classifier: SectionClassifier instance
        ruler: MarkdownSpanRuler instance for parsing sections
        req_processor: RequirementProcessor instance
        skill_processor: SkillProcessor instance
        tech_processor: TechnologyProcessor instance

    Returns:
        JobResult with processing stats and any errors encountered

    Note:
        This function NEVER raises. All errors are captured in JobResult.errors.
    """
    job_id = job.get("id", "unknown")
    title = job.get("title", "Unknown")
    company = job.get("company", "Unknown")

    # Initialize result
    result = JobResult(
        job_id=job_id,
        title=title,
        company=company,
        sections_detected=0,
        keyword_matches=0,
        confidence_min=1.0,
        confidence_max=0.0,
        confidence_avg=0.0,
    )

    raw_html = job.get("description", "")

    # Stage 1: Preprocess
    try:
        clean_html = preprocessor.process(raw_html)
    except Exception as e:
        result.add_error("preprocessor", str(e))
        return result

    # Stage 2: Convert to Markdown
    try:
        markdown = converter.process(clean_html)
    except Exception as e:
        result.add_error("converter", str(e))
        return result

    # Stage 3: Polish Markdown
    try:
        polished_markdown = polisher.process(markdown)
    except Exception as e:
        result.add_error("polisher", str(e))
        return result

    # Stage 4: Parse sections using MarkdownSpanRuler
    try:
        sections = ruler.parse(polished_markdown)
        result.sections_detected = len(sections)

        # Stage 5: Classify each section and aggregate confidence stats
        if sections:
            confidences = []
            for section in sections:
                try:
                    classification = classifier.classify(section)

                    # Extract confidence stats from classification
                    if classification.all_types:
                        for tc in classification.all_types:
                            confidences.append(tc.confidence)

                        # Count total keyword matches
                        for type_class in classification.all_types:
                            result.keyword_matches += len(type_class.matched_keywords)
                except Exception as sec_err:
                    result.add_error("section_classification", str(sec_err))
                    # Continue processing other sections

            # Aggregate confidence stats across all sections
            if confidences:
                result.confidence_min = min(confidences)
                result.confidence_max = max(confidences)
                result.confidence_avg = sum(confidences) / len(confidences)
            else:
                # If all section classifications failed, reset to valid defaults
                result.confidence_min = 0.0
                result.confidence_max = 0.0
                result.confidence_avg = 0.0

    except Exception as e:
        result.add_error("section_parsing", str(e))
        # Errors in section parsing/classification do not halt further processing;
        # we report sections detected and partial confidence stats if any

    # Stages 6-8: Extract requirements, skills, technologies from doc (per-stage error handling)
    try:
        # Create a spaCy Doc for extraction
        # We process polished markdown through the full pipeline again
        # to populate doc._.classified_sections and other extensions
        import spacy

        nlp = spacy.blank("en")  # Minimal NLP for doc creation

        # Create synthetic doc with sections pre-populated
        doc = nlp("")  # Create empty doc
        doc._.sections = sections  # Pre-populate sections from ruler output

        # Apply classifiers and extract data
        from src.poc.tweak.spacy_pipeline import SectionClassifierComponent

        section_classifier = SectionClassifierComponent(nlp, "section_classifier")
        doc = section_classifier(doc)

        # Extract requirements
        try:
            doc = req_processor(doc)
            result.requirements = doc._.requirements if doc._.requirements else []
        except Exception as e:
            result.add_error("requirement_extraction", str(e))

        # Extract skills
        try:
            doc = skill_processor(doc)
            result.skills = doc._.skills if doc._.skills else []
        except Exception as e:
            result.add_error("skill_extraction", str(e))

        # Extract technologies
        try:
            doc = tech_processor(doc)
            result.technologies = doc._.technologies if doc._.technologies else []
        except Exception as e:
            result.add_error("technology_extraction", str(e))

    except Exception as e:
        result.add_error("extraction_pipeline", str(e))

    return result


def run_batch(input_path: str) -> List[JobResult]:
    """Run batch processing on all jobs in input file.

    Loads spaCy model, instantiates pipeline components once, then processes
    all jobs sequentially through the pipeline.

    Args:
        input_path: Path to JSON file with job records

    Returns:
        List of JobResult objects (one per job)

    Raises:
        FileNotFoundError: If input file not found
        ValueError: If input file is not valid JSON array
        OSError: If spaCy model cannot be loaded
    """
    # Load jobs
    jobs = load_jobs(input_path)

    # Load spaCy model once
    try:
        nlp = spacy.load("en_core_web_md")
    except OSError as e:
        raise OSError(
            f"Failed to load spaCy model 'en_core_web_md': {e}. Run: uv run python -m spacy download en_core_web_md"
        ) from e

    # Explicit entity_ruler registration (required by TechnologyProcessor, D5 decision)
    if "entity_ruler" not in nlp.pipe_names:
        nlp.add_pipe("entity_ruler", before="ner")

    # Instantiate components once
    preprocessor = HTMLPreprocessor()
    converter = HTMLMarkdownConverter()
    polisher = MarkdownPolisher()
    ruler = MarkdownSpanRuler(nlp)
    classifier = SectionClassifier()

    # Add pipeline components (all use last=True, D3 decision)
    req_processor = RequirementProcessor(nlp, "requirement_processor")
    skill_processor = SkillProcessor(nlp, "skill_processor")
    tech_processor = TechnologyProcessor(nlp, "technology_processor")

    # Process all jobs
    results = []
    for job in jobs:
        result = process_job(
            job,
            preprocessor=preprocessor,
            converter=converter,
            polisher=polisher,
            classifier=classifier,
            ruler=ruler,
            req_processor=req_processor,
            skill_processor=skill_processor,
            tech_processor=tech_processor,
        )
        results.append(result)

    return results


def print_summary(results: List[JobResult]) -> str:
    """Generate and print summary of batch processing results.

    Outputs per-job statistics and aggregate stats.

    Args:
        results: List of JobResult objects from run_batch()

    Returns:
        Formatted summary string (also prints to stdout)
    """
    lines = []

    # Header
    lines.append("=" * 80)
    lines.append("BATCH PROCESSING SUMMARY")
    lines.append("=" * 80)
    lines.append("")

    # Per-job results
    lines.append("PER-JOB RESULTS:")
    lines.append("-" * 80)

    for i, result in enumerate(results, 1):
        lines.append(f"\n[Job {i}] {result.title}")
        lines.append(f"  Job ID: {result.job_id}")
        lines.append(f"  Company: {result.company}")
        lines.append(f"  Sections Detected: {result.sections_detected}")
        lines.append(f"  Keyword Matches: {result.keyword_matches}")
        if result.sections_detected > 0:
            lines.append(
                f"  Confidence Scores: min={result.confidence_min:.3f}, "
                f"max={result.confidence_max:.3f}, avg={result.confidence_avg:.3f}"
            )
        else:
            lines.append("  Confidence Scores: N/A (no sections detected)")

        # Extraction stats (Issue #321)
        lines.append("  Extracted:")
        lines.append(f"    - Requirements: {len(result.requirements)}")
        lines.append(f"    - Skills: {len(result.skills)}")
        lines.append(f"    - Technologies: {len(result.technologies)}")

        if result.has_errors():
            lines.append(f"  Errors ({len(result.errors)}):")
            for stage, error in result.errors:
                lines.append(f"    - {stage}: {error}")
        else:
            lines.append("  Status: SUCCESS")

    # Aggregate statistics
    lines.append("")
    lines.append("-" * 80)
    lines.append("AGGREGATE STATISTICS:")
    lines.append("-" * 80)

    total_jobs = len(results)
    successful = sum(1 for r in results if not r.has_errors())
    failed = total_jobs - successful
    total_sections = sum(r.sections_detected for r in results)
    total_keywords = sum(r.keyword_matches for r in results)
    total_requirements = sum(len(r.requirements) for r in results)
    total_skills = sum(len(r.skills) for r in results)
    total_technologies = sum(len(r.technologies) for r in results)

    lines.append(f"Total Jobs Processed: {total_jobs}")
    lines.append(f"Successful: {successful}")
    lines.append(f"Failed: {failed}")
    lines.append(f"Success Rate: {successful / total_jobs * 100:.1f}%")
    lines.append(f"Total Sections Detected: {total_sections}")
    lines.append(f"Total Keyword Matches: {total_keywords}")
    lines.append(f"Total Requirements Extracted: {total_requirements}")
    lines.append(f"Total Skills Extracted: {total_skills}")
    lines.append(f"Total Technologies Extracted: {total_technologies}")

    # Confidence stats
    confidences_with_values = [r.confidence_avg for r in results if r.sections_detected > 0 and r.confidence_avg > 0]
    if confidences_with_values:
        avg_confidence = sum(confidences_with_values) / len(confidences_with_values)
        lines.append(f"Average Confidence (across all jobs): {avg_confidence:.3f}")

    lines.append("")
    lines.append("=" * 80)

    summary = "\n".join(lines)
    print(summary)
    return summary


def main() -> int:
    """CLI entry point for batch processor.

    Parses arguments, runs batch processing, prints summary, and optionally
    exports results to JSON.

    Returns:
        Exit code (0 on success, 1 on error)
    """
    parser = argparse.ArgumentParser(description="POC Batch Processor for multi-job markdown pipeline")
    parser.add_argument(
        "--input-path",
        type=str,
        default="data/work/details_test.json",
        help="Path to JSON file with job records (default: data/work/details_test.json)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Output path for JSON results (optional)",
    )

    args = parser.parse_args()

    try:
        results = run_batch(args.input_path)
        print_summary(results)

        # Export to JSON if requested
        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump([asdict(r) for r in results], f, indent=2)
            print(f"\nResults saved to {args.output_json}")

        return 0
    except (FileNotFoundError, ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
