"""Measure false positives of the SECTION_HEADER_KEYWORDS_ONLY heading phrases (Issue #747, Refs #734).

For each job in the local input data, the markdown pipeline is run twice:
once with the pre-#731 heading vocabulary (KNOWN_PLAIN_HEADINGS minus
SECTION_HEADER_KEYWORDS_ONLY) and once with the current vocabulary
(KNOWN_PLAIN_HEADINGS). A "hit" is a section in the current run whose heading is one
of the 16 SECTION_HEADER_KEYWORDS_ONLY phrases and which does not start at the same
line as any section in the pre-#731 run (so genuine pre-existing headings are not
counted).

The script is measurement only: it does not change any vocabulary, and it fills in
neither the manual-review verdicts nor the per-phrase recommendations. Those are
left as placeholders in the report for a human reviewer.

Exit codes:
  0 - Report written
  2 - An --input path does not exist

Usage:
  uv run python scripts/measure_heading_promoter_fp.py
  uv run python scripts/measure_heading_promoter_fp.py --input data/work/my_details.json --output out/report.md
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ensure src module is importable when run as a script (matches scripts/parity_check.py)
_SCRIPT_DIR = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import spacy  # noqa: E402

import src.poc.sentence_splitter  # noqa: E402,F401  (registers poc_sentence_splitter factory)
from src.poc.tweak.batch_processor import load_jobs, process_job  # noqa: E402
from src.poc.tweak.markdown_section_classifier import SectionClassifier  # noqa: E402
from src.poc.tweak.multi_line_paragraph import MarkdownSpanRuler  # noqa: E402
from src.poc.tweak.spacy_pipeline import (  # noqa: E402
    HTMLMarkdownConverter,
    HTMLPreprocessor,
    MarkdownPolisher,
    RequirementProcessor,
    SkillProcessor,
    TechnologyProcessor,
)
from src.poc.tweak.spacy_pipeline.heading_promoter import (  # noqa: E402
    KNOWN_PLAIN_HEADINGS,
    HeadingPromoter,
)
from src.poc.tweak.spacy_pipeline.section_header_keywords import (  # noqa: E402
    SECTION_HEADER_KEYWORDS_ONLY,
)

logger = logging.getLogger(__name__)

DEFAULT_INPUTS: list[Path] = [_PROJECT_ROOT / "data/work/my_details.json"]
# Under data/, which .gitignore covers (`data/`), so the generated report is never committed.
DEFAULT_OUTPUT: Path = _PROJECT_ROOT / "data/work/heading_promoter_fp_report.md"
MISMATCH_WORD_COUNT_THRESHOLD: int = 8
PREVIEW_CHARS: int = 120
SMALL_SAMPLE_WARNING_THRESHOLD: int = 30


def load_and_dedupe_jobs(input_paths: list[Path]) -> list[dict[str, Any]]:
    """load_jobs() each path, concatenate, drop records whose 'description' is
    byte-identical to an earlier record's (keep first occurrence). Log count of
    dropped duplicates.

    Records with a null description are never treated as duplicates of each other.
    """
    jobs: list[dict[str, Any]] = []
    for path in input_paths:
        jobs.extend(load_jobs(str(path)))

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    dropped = 0
    for job in jobs:
        description = job.get("description")
        if isinstance(description, str):
            if description in seen:
                dropped += 1
                continue
            seen.add(description)
        unique.append(job)

    logger.info("Dropped %d duplicate job record(s) by identical description", dropped)
    return unique


def normalize_heading(text: str) -> str:
    """Normalize a heading for comparison against SECTION_HEADER_KEYWORDS_ONLY.

    Mirrors ``HeadingPromoter._normalize`` in
    ``src/poc/tweak/spacy_pipeline/heading_promoter.py`` step for step (casefold;
    fold U+2019 and U+2018 to "'"; collapse whitespace; strip all trailing ':' and
    surrounding whitespace). That method is private and has no public equivalent,
    so it is mirrored here; ``run_self_test`` asserts the two agree.
    """
    text = text.casefold()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = " ".join(text.split())
    return text.rstrip(":").strip()


@dataclass
class Hit:
    record_index: int  # 1-based position in the de-duplicated job list
    job_id: str
    company: str
    title: str
    phrase: str
    heading_text: str
    section_type: str
    confidence: float
    content_preview: str  # section.content[:120]
    mismatch_flag: bool  # section_type == "other" and word_count < MISMATCH_WORD_COUNT_THRESHOLD


@dataclass
class JobDelta:
    record_index: int  # 1-based position in the de-duplicated job list
    job_id: str
    requirements_before: int
    requirements_after: int
    skills_before: int
    skills_after: int
    technologies_before: int
    technologies_after: int


def build_components(nlp: Any) -> dict[str, Any]:
    """Build and return the shared preprocessor/converter/polisher/classifier/ruler/
    req_processor/skill_processor/tech_processor objects exactly as
    batch_processor.run_batch() does (copy that block). heading_promoter is excluded
    here: it is built separately per before/after call in run_before_after().

    Expects ``nlp`` to be the loaded spaCy model (``en_core_web_md``).
    """
    # Explicit entity_ruler registration (required by TechnologyProcessor, D5 decision)
    if "entity_ruler" not in nlp.pipe_names:
        nlp.add_pipe("entity_ruler", before="ner")

    # Sentence splitter (Issue #643); default-on in run_batch
    if "poc_sentence_splitter" not in nlp.pipe_names:
        nlp.add_pipe("poc_sentence_splitter")

    # Load technology patterns into entity_ruler (Issue #321 fix)
    ruler = nlp.get_pipe("entity_ruler")
    tech_patterns = TechnologyProcessor.generate_tech_patterns()
    ruler.add_patterns(tech_patterns)  # type: ignore

    # Instantiate components once
    preprocessor = HTMLPreprocessor()
    converter = HTMLMarkdownConverter()
    polisher = MarkdownPolisher()
    markdown_ruler = MarkdownSpanRuler(nlp)
    classifier = SectionClassifier()

    # Add pipeline components (all use last=True, D3 decision)
    req_processor = RequirementProcessor(nlp, "requirement_processor")
    skill_processor = SkillProcessor(nlp, "skill_processor")
    tech_processor = TechnologyProcessor(nlp, "technology_processor")

    return {
        "preprocessor": preprocessor,
        "converter": converter,
        "polisher": polisher,
        "classifier": classifier,
        "ruler": markdown_ruler,
        "req_processor": req_processor,
        "skill_processor": skill_processor,
        "tech_processor": tech_processor,
    }


def run_before_after(job: dict[str, Any], nlp: Any, components: dict[str, Any]) -> tuple[Any, Any]:
    """Call process_job() twice on the same job dict: once with
    heading_promoter=HeadingPromoter(headings=KNOWN_PLAIN_HEADINGS - SECTION_HEADER_KEYWORDS_ONLY),
    once with heading_promoter=HeadingPromoter(headings=KNOWN_PLAIN_HEADINGS). Returns
    (result_before, result_after).
    """
    before_promoter = HeadingPromoter(headings=KNOWN_PLAIN_HEADINGS - SECTION_HEADER_KEYWORDS_ONLY)
    after_promoter = HeadingPromoter(headings=KNOWN_PLAIN_HEADINGS)

    result_before = process_job(
        job,
        nlp=nlp,
        preprocessor=components["preprocessor"],
        converter=components["converter"],
        polisher=components["polisher"],
        classifier=components["classifier"],
        ruler=components["ruler"],
        req_processor=components["req_processor"],
        skill_processor=components["skill_processor"],
        tech_processor=components["tech_processor"],
        heading_promoter=before_promoter,
    )
    result_after = process_job(
        job,
        nlp=nlp,
        preprocessor=components["preprocessor"],
        converter=components["converter"],
        polisher=components["polisher"],
        classifier=components["classifier"],
        ruler=components["ruler"],
        req_processor=components["req_processor"],
        skill_processor=components["skill_processor"],
        tech_processor=components["tech_processor"],
        heading_promoter=after_promoter,
    )
    return result_before, result_after


def find_hits_and_deltas(jobs: list[dict[str, Any]]) -> tuple[list[Hit], list[JobDelta]]:
    """Load spaCy model + components once (not per job). For each job call
    run_before_after(); for each section in result_after.markdown_sections, if
    normalize_heading(section.heading) is in SECTION_HEADER_KEYWORDS_ONLY AND no
    section in result_before.markdown_sections shares its line_start, append a Hit.
    Always append one JobDelta per job regardless of whether it produced any hits.
    """
    nlp = spacy.load("en_core_web_md")
    components = build_components(nlp)

    hits: list[Hit] = []
    deltas: list[JobDelta] = []
    for record_index, job in enumerate(jobs, start=1):
        result_before, result_after = run_before_after(job, nlp, components)

        before_starts = {section.line_start for section in result_before.markdown_sections}
        for section in result_after.markdown_sections:
            phrase = normalize_heading(section.heading)
            if phrase not in SECTION_HEADER_KEYWORDS_ONLY or section.line_start in before_starts:
                continue
            word_count = len(section.content.split())
            hits.append(
                Hit(
                    record_index=record_index,
                    job_id=str(result_after.job_id),
                    company=str(result_after.company),
                    title=str(result_after.title),
                    phrase=phrase,
                    heading_text=section.heading,
                    section_type=str(section.section_type),
                    confidence=float(section.confidence),
                    content_preview=section.content[:PREVIEW_CHARS],
                    mismatch_flag=(str(section.section_type) == "other" and word_count < MISMATCH_WORD_COUNT_THRESHOLD),
                )
            )

        deltas.append(
            JobDelta(
                record_index=record_index,
                job_id=str(result_after.job_id),
                requirements_before=len(result_before.requirements),
                requirements_after=len(result_after.requirements),
                skills_before=len(result_before.skills),
                skills_after=len(result_after.skills),
                technologies_before=len(result_before.technologies),
                technologies_after=len(result_after.technologies),
            )
        )

    return hits, deltas


def _md_cell(value: object) -> str:
    """Render a value safely inside a markdown table cell."""
    text = str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    return text


def _render_phrase_table(hits: list[Hit]) -> list[str]:
    lines = [
        "## Per-phrase hit counts",
        "",
        "| phrase | hit count | section types seen | mismatch_flag count |",
        "|---|---|---|---|",
    ]
    for phrase in sorted(SECTION_HEADER_KEYWORDS_ONLY):
        phrase_hits = [h for h in hits if h.phrase == phrase]
        types_seen = sorted({h.section_type for h in phrase_hits})
        mismatch_count = sum(1 for h in phrase_hits if h.mismatch_flag)
        lines.append(
            f"| {_md_cell(phrase)} | {len(phrase_hits)} | {_md_cell(', '.join(types_seen) or '-')} | {mismatch_count} |"
        )
    lines.append("")
    return lines


def _render_delta_table(deltas: list[JobDelta]) -> list[str]:
    lines = [
        "## Per-job requirements / skills / technologies (before vs after)",
        "",
        "| # | job_id | requirements before | requirements after | skills before | skills after "
        "| technologies before | technologies after |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in deltas:
        lines.append(
            f"| {d.record_index} | {_md_cell(d.job_id)} | {d.requirements_before} | {d.requirements_after} "
            f"| {d.skills_before} | {d.skills_after} | {d.technologies_before} | {d.technologies_after} |"
        )
    lines.append("")
    return lines


def _render_hit_details(hits: list[Hit]) -> list[str]:
    lines = [
        "## Hit details",
        "",
        "| # | job_id | company | title | phrase | heading_text | section_type | confidence "
        "| content_preview | mismatch_flag |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for h in hits:
        lines.append(
            f"| {h.record_index} | {_md_cell(h.job_id)} | {_md_cell(h.company)} | {_md_cell(h.title)} "
            f"| {_md_cell(h.phrase)} "
            f"| {_md_cell(h.heading_text)} | {_md_cell(h.section_type)} | {h.confidence:.2f} "
            f"| {_md_cell(h.content_preview)} | {h.mismatch_flag} |"
        )
    lines.append("")
    return lines


def _render_manual_review(hits: list[Hit]) -> list[str]:
    lines = [
        "## Manual review",
        "",
        "Placeholder: verdicts are filled in by a human reviewer, not by this script.",
        "",
        "| # | job_id | title | phrase | heading_text | section_type | Verdict (true heading / false positive) |",
        "|---|---|---|---|---|---|---|",
    ]
    for h in hits:
        lines.append(
            f"| {h.record_index} | {_md_cell(h.job_id)} | {_md_cell(h.title)} | {_md_cell(h.phrase)} "
            f"| {_md_cell(h.heading_text)} | {_md_cell(h.section_type)} | |"
        )
    lines.append("")
    return lines


def _render_recommendations() -> list[str]:
    lines = ["## Recommendation per phrase", ""]
    for phrase in sorted(SECTION_HEADER_KEYWORDS_ONLY):
        lines.append(f"- {phrase}: (TBD by human reviewer)")
    lines.append("")
    return lines


def _data_loss_line(deltas: list[JobDelta]) -> str:
    decreased: list[str] = []
    for d in deltas:
        drops = []
        if d.requirements_after < d.requirements_before:
            drops.append(f"requirements {d.requirements_before}->{d.requirements_after}")
        if d.skills_after < d.skills_before:
            drops.append(f"skills {d.skills_before}->{d.skills_after}")
        if d.technologies_after < d.technologies_before:
            drops.append(f"technologies {d.technologies_before}->{d.technologies_after}")
        if drops:
            decreased.append(f"#{d.record_index} {d.job_id} ({', '.join(drops)})")
    if decreased:
        return (
            "Decrease found in after-count vs before-count for requirements/skills/technologies in "
            f"{len(decreased)} job(s): " + "; ".join(decreased) + "."
        )
    return (
        "No decrease found: for every job, the after-count is not lower than the before-count "
        "for requirements, skills, and technologies."
    )


def render_report(jobs: list[dict[str, Any]], hits: list[Hit], deltas: list[JobDelta], output_path: Path) -> None:
    """Write markdown to output_path (create parent dirs if needed), in order:
    1. Coverage-limit statement with ACTUAL post-dedupe job/company counts (never
       hardcode).
    2. Per-phrase hit-count table: phrase | hit count | section types seen |
       mismatch_flag count.
    3. Per-job requirements/skills/technologies before-vs-after table (from `deltas`).
    4. Per-hit detail table: job_id, company, title, phrase, heading_text,
       section_type, confidence, content_preview, mismatch_flag.
    5. '## Manual review' - one row per hit, explicit empty 'Verdict (true heading /
       false positive)' column (placeholder; this script does not fill it).
    6. '## Recommendation per phrase' - one empty bullet per of the 16 phrases
       (sorted), each '(TBD by human reviewer)' (placeholder; not filled here).
    7. '## Data-loss check (Section 3)' - states, using actual `deltas` values,
       whether any job's after-count is lower than its before-count for
       requirements/skills/technologies, naming job id(s) if so, else states plainly
       no decrease was found.
    """
    companies = {str(job.get("company", "")) for job in jobs}
    lines: list[str] = [
        "# Issue #747: HeadingPromoter false-positive measurement (Refs #734)",
        "",
        "## Coverage limit",
        "",
        f"This sample covers **{len(jobs)} distinct job postings** from **{len(companies)} companies** "
        "(after de-duplicating byte-identical descriptions). It is a small-sample point estimate, "
        "not a statistically reliable false-positive rate.",
        "",
        f"Companies: {', '.join(sorted(companies)) if companies else '(none)'}",
        "",
    ]
    lines += _render_phrase_table(hits)
    lines += _render_delta_table(deltas)
    lines += _render_hit_details(hits)
    lines += _render_manual_review(hits)
    lines += _render_recommendations()
    lines += ["## Data-loss check (Section 3)", "", _data_loss_line(deltas), ""]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


# (raw, expected normalized value); expected must be one of the 16 phrases
SELF_TEST_CASES: list[tuple[str, str]] = [
    ("Nice to Have", "nice to have"),
    ("Background:", "background"),
    ("Needed::", "needed"),
    ("What you\u2018ll do", "what you'll do"),
    ("What you\u2019ll do:", "what you'll do"),
    ("  What   We\u2019re  Looking   For: ", "what we're looking for"),
]


# Raw strings that must match HeadingPromoter._normalize exactly (not necessarily phrases)
SELF_TEST_PARITY_ONLY: list[str] = [
    "Needed: :",
    "Needed\u00a0:",
    "Nice\tto\tHave",
    "Nice\u00a0to\u00a0Have",
    "Nice\u2013to\u2014have",
    "Background.",
    "Background!?",
    "",
    ":",
    "   ",
]


def run_self_test() -> int:
    """Check normalize_heading() against HeadingPromoter._normalize and the phrase set.

    Returns 0 when every case passes, 1 otherwise.
    """
    promoter = HeadingPromoter()
    failures = 0
    for raw, expected in SELF_TEST_CASES:
        got = normalize_heading(raw)
        if got != expected or got != promoter._normalize(raw) or got not in SECTION_HEADER_KEYWORDS_ONLY:
            failures += 1
            print(f"FAIL: {raw!r} -> {got!r} (expected {expected!r}, promoter {promoter._normalize(raw)!r})")
    for raw in SELF_TEST_PARITY_ONLY:
        if normalize_heading(raw) != promoter._normalize(raw):
            failures += 1
            print(f"FAIL: parity {raw!r} -> {normalize_heading(raw)!r} vs promoter {promoter._normalize(raw)!r}")
    for phrase in sorted(SECTION_HEADER_KEYWORDS_ONLY):
        if normalize_heading(phrase) != phrase or promoter._normalize(phrase) != phrase:
            failures += 1
            print(f"FAIL: phrase {phrase!r} does not round-trip through normalization")
    print(
        f"self-test: {len(SELF_TEST_CASES)} cases + {len(SELF_TEST_PARITY_ONLY)} parity-only strings "
        f"+ {len(SECTION_HEADER_KEYWORDS_ONLY)} phrases, {failures} failure(s)"
    )
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    """argparse: --input (nargs='+', type=Path, default=DEFAULT_INPUTS), --output
    (type=Path, default=DEFAULT_OUTPUT). Calls load_and_dedupe_jobs, then
    find_hits_and_deltas, then render_report. Prints one summary line to stdout:
    "N jobs, M companies, H hits, report written to <path>". If post-dedupe job
    count < 30, print one WARNING line to stderr with the exact count (informational
    only). Returns 0 on success. If an --input path does not exist, print a one-line
    error to stderr and return 2 (no raw traceback).
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        default=DEFAULT_INPUTS,
        help="Job JSON file(s) to measure (default: <repo root>/data/work/my_details.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "Markdown report path (default: <repo root>/data/work/heading_promoter_fp_report.md; "
            "data/ is gitignored, so the report is not committed)"
        ),
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Only check normalize_heading() against HeadingPromoter._normalize and exit (no spaCy run)",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_test()

    missing = [str(p) for p in args.input if not p.exists()]
    if missing:
        print(f"error: input file not found: {', '.join(missing)}", file=sys.stderr)
        return 2

    # Surface the duplicate-drop count from load_and_dedupe_jobs() on stderr
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        jobs = load_and_dedupe_jobs(args.input)
        hits, deltas = find_hits_and_deltas(jobs)
        render_report(jobs, hits, deltas, args.output)
    finally:
        logger.removeHandler(handler)

    job_count = len(jobs)
    company_count = len({str(job.get("company", "")) for job in jobs})
    print(f"{job_count} jobs, {company_count} companies, {len(hits)} hits, report written to {args.output}")
    if job_count < SMALL_SAMPLE_WARNING_THRESHOLD:
        print(
            f"WARNING: only {job_count} distinct jobs after de-duplication (below {SMALL_SAMPLE_WARNING_THRESHOLD}); "
            "results are a small-sample estimate.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
