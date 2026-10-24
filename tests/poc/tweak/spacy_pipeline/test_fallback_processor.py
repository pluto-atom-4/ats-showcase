"""Tests for the merged Tier 1+2 fallback pass (Issue #739, Part of #735).

Covers:
- apply_fallback is a no-op unless extraction_outcome is NEEDS_HUMAN_REVIEW.
- Sub-pass A (tier1_relaxed_section): section confidence between FALLBACK_MIN_SECTION_CONFIDENCE
  and the 0.70 gate recovers requirements, skills and technologies (Walmart / UW shape).
- Sub-pass B (tier2_taxonomy): ungated whole-text taxonomy when skills/technologies are still empty.
- Confidence caps, extraction_tier tags and the COMPLETE outcome after recovery.
- The shared de-duplication guard: no duplicate text across normal-path and fallback output.
- Pipeline isolation: the shared batch nlp's entity_ruler patterns are unchanged after a fallback run.

The job fixtures are synthetic markdown mirroring the UW / Walmart shape (a qualifications
section and a skills section classified in the 0.45-0.70 band, plus a description section);
they are not real job data.

Run with:
    uv run pytest tests/poc/tweak/spacy_pipeline/test_fallback_processor.py -v
"""

import copy
from typing import Any, Dict, List, Optional, Tuple

import pytest
import spacy
from spacy.language import Language

from src.poc.tweak.batch_processor import JobResult
from src.poc.tweak.extraction_status import (
    FALLBACK_MIN_SECTION_CONFIDENCE,
    ExtractionOutcome,
)
from src.poc.tweak.section_model import MarkdownSection
from src.poc.tweak.spacy_pipeline import TechnologyProcessor
from src.poc.tweak.spacy_pipeline import fallback_processor as fp
from src.poc.tweak.spacy_pipeline.fallback_processor import (
    TIER1_CONFIDENCE,
    TIER1_TAG,
    TIER2_CONFIDENCE,
    TIER2_TAG,
    apply_fallback,
)

NEEDS = ExtractionOutcome.NEEDS_HUMAN_REVIEW

# ============================================================================
# Fixtures and builders
# ============================================================================


@pytest.fixture(scope="session")
def shared_nlp() -> Language:
    """Batch-shaped shared pipeline: entity_ruler with TECH patterns, as run_batch() builds it."""
    nlp = spacy.load("en_core_web_md")
    if "entity_ruler" not in nlp.pipe_names:
        nlp.add_pipe("entity_ruler", before="ner")
    nlp.get_pipe("entity_ruler").add_patterns(TechnologyProcessor.generate_tech_patterns())  # type: ignore[attr-defined]
    return nlp


def _section(
    index: int,
    heading: str,
    content: str,
    types: List[Tuple[str, float]],
) -> MarkdownSection:
    """Build a persisted MarkdownSection carrying all_types-ranked classification data."""
    ranked = sorted(types, key=lambda t: t[1], reverse=True)
    return MarkdownSection(
        section_id=f"sec_{index}",
        heading=heading,
        content=content,
        section_type=ranked[0][0],
        confidence=ranked[0][1],
        line_start=index * 10,
        line_end=index * 10 + 5,
        matched_keywords=[],
        all_types=[{"section_type": t, "confidence": c} for t, c in ranked],
        labels=[t for t, _ in ranked],
        is_skip=False,
        keyword_matches=[],
    )


def _job(
    sections: List[MarkdownSection],
    *,
    outcome: Optional[ExtractionOutcome] = NEEDS,
    requirements: Optional[List[Dict[str, Any]]] = None,
    skills: Optional[List[Dict[str, Any]]] = None,
    technologies: Optional[List[Dict[str, Any]]] = None,
) -> JobResult:
    return JobResult(
        job_id="job-1",
        title="Synthetic role",
        company="Synthetic Co",
        sections_detected=len(sections),
        keyword_matches=0,
        confidence_min=0.0,
        confidence_max=0.0,
        confidence_avg=0.0,
        requirements=list(requirements or []),
        skills=list(skills or []),
        technologies=list(technologies or []),
        markdown_sections=list(sections),
        extraction_outcome=outcome,
    )


# UW / Walmart shape: qualifications and skills sections sit in the relaxed band (0.45 - 0.70),
# below the normal 0.70 gate; a description section carries the rest of the text.
UW_WALMART_MD = """## Qualifications

Must have 5+ years of Python experience.

## Skills

- Build scalable data pipelines using Spark and Airflow
- Python, Docker, Kubernetes

## About the role

We ship data products on AWS and Terraform.
"""


def _uw_walmart_job() -> JobResult:
    return _job(
        [
            _section(0, "Qualifications", "Must have 5+ years of Python experience.", [("qualifications", 0.55)]),
            _section(
                1,
                "Skills",
                "- Build scalable data pipelines using Spark and Airflow\n- Python, Docker, Kubernetes",
                [("skills", 0.55)],
            ),
            _section(2, "About the role", "We ship data products on AWS and Terraform.", [("description", 0.90)]),
        ]
    )


def _texts(entries: List[Dict[str, Any]], key: str) -> List[str]:
    return [entry[key] for entry in entries]


# ============================================================================
# Gating and outcome
# ============================================================================


@pytest.mark.parametrize(
    "outcome",
    [ExtractionOutcome.COMPLETE, ExtractionOutcome.ERROR, ExtractionOutcome.LIKELY_UNPARSEABLE_INPUT],
)
def test_noop_unless_needs_human_review(shared_nlp: Language, outcome: ExtractionOutcome) -> None:
    """Only NEEDS_HUMAN_REVIEW jobs are eligible; other outcomes come back untouched."""
    job = _uw_walmart_job()
    job.extraction_outcome = outcome
    before = copy.deepcopy(job)

    result = apply_fallback(job, UW_WALMART_MD, shared_nlp=shared_nlp)

    assert result is job
    assert result == before


def test_noop_when_outcome_unset(shared_nlp: Language) -> None:
    job = _uw_walmart_job()
    job.extraction_outcome = None
    before = copy.deepcopy(job)

    assert apply_fallback(job, UW_WALMART_MD, shared_nlp=shared_nlp) == before


def test_nothing_recovered_keeps_needs_human_review(shared_nlp: Language) -> None:
    """Weak section confidence and no taxonomy hits: the job stays NEEDS_HUMAN_REVIEW."""
    md = "Welcome to the team. We value curiosity and kindness."
    job = _job([_section(0, "Welcome", md, [("skills", 0.30)])])

    result = apply_fallback(job, md, shared_nlp=shared_nlp)

    assert result.extraction_outcome is NEEDS
    assert result.requirements == []
    assert result.skills == []
    assert result.technologies == []


# ============================================================================
# Sub-pass A: relaxed section confidence (tier1_relaxed_section)
# ============================================================================


def test_tier1_recovers_skills_and_technologies_walmart_shape(shared_nlp: Language) -> None:
    result = apply_fallback(_uw_walmart_job(), UW_WALMART_MD, shared_nlp=shared_nlp)

    skill_texts = _texts(result.skills, "skill")
    tech_texts = _texts(result.technologies, "tech")
    assert skill_texts, "skills section in the relaxed band should yield skills"
    assert "python" in tech_texts
    assert "docker" in tech_texts
    assert "kubernetes" in tech_texts
    assert all(s["extraction_tier"] == TIER1_TAG for s in result.skills)
    assert all(t["extraction_tier"] == TIER1_TAG for t in result.technologies)
    assert result.extraction_outcome is ExtractionOutcome.COMPLETE


def test_tier1_recovers_requirements_uw_shape(shared_nlp: Language) -> None:
    result = apply_fallback(_uw_walmart_job(), UW_WALMART_MD, shared_nlp=shared_nlp)

    assert _texts(result.requirements, "text") == ["Must have 5+ years of Python experience"]
    assert result.requirements[0]["extraction_tier"] == TIER1_TAG


def test_section_below_relaxed_floor_is_not_recovered(shared_nlp: Language) -> None:
    """A skills section under FALLBACK_MIN_SECTION_CONFIDENCE stays unrecovered."""
    content = "- Build scalable data pipelines using Spark"
    md = f"## Skills\n\n{content}\n"
    below = FALLBACK_MIN_SECTION_CONFIDENCE - 0.10
    job = _job([_section(0, "Skills", content, [("skills", below)])])

    result = apply_fallback(job, md, shared_nlp=shared_nlp)

    assert not [s for s in result.skills if s.get("extraction_tier") == TIER1_TAG]


def test_tier1_recovers_at_relaxed_floor_boundary(shared_nlp: Language) -> None:
    """A section exactly at the relaxed floor is eligible (>= gate)."""
    content = "- Build scalable data pipelines using Spark"
    md = f"## Skills\n\n{content}\n"
    job = _job([_section(0, "Skills", content, [("skills", FALLBACK_MIN_SECTION_CONFIDENCE)])])

    result = apply_fallback(job, md, shared_nlp=shared_nlp)

    assert _texts(result.skills, "skill") == ["build scalable data pipelines using spark"]


# ============================================================================
# Sub-pass B: whole-text taxonomy reuse (tier2_taxonomy)
# ============================================================================

TAXONOMY_MD = (
    "## About the role\n\n"
    "We build data pipelines with Python and Docker on AWS.\n"
    "Our team will ship reliable services and design resilient systems.\n"
)


def test_tier2_taxonomy_runs_when_sections_yield_nothing(shared_nlp: Language) -> None:
    """Only a non-gated description section: sub-pass A is empty, so sub-pass B supplies output."""
    job = _job([_section(0, "About the role", TAXONOMY_MD, [("description", 0.90)])])

    result = apply_fallback(job, TAXONOMY_MD, shared_nlp=shared_nlp)

    assert "python" in _texts(result.technologies, "tech")
    assert "docker" in _texts(result.technologies, "tech")
    assert result.technologies and all(t["extraction_tier"] == TIER2_TAG for t in result.technologies)
    assert result.skills and all(s["extraction_tier"] == TIER2_TAG for s in result.skills)
    assert result.extraction_outcome is ExtractionOutcome.COMPLETE


def test_tier2_confidence_is_lower_than_tier1_and_normal_path(shared_nlp: Language) -> None:
    job = _job([_section(0, "About the role", TAXONOMY_MD, [("description", 0.90)])])

    result = apply_fallback(job, TAXONOMY_MD, shared_nlp=shared_nlp)

    assert TIER2_CONFIDENCE < TIER1_CONFIDENCE < 1.0
    assert all(t["confidence"] == TIER2_CONFIDENCE for t in result.technologies)
    assert all(s["confidence"] == TIER2_CONFIDENCE for s in result.skills)


def test_tier1_confidence_is_capped_below_normal_path(shared_nlp: Language) -> None:
    result = apply_fallback(_uw_walmart_job(), UW_WALMART_MD, shared_nlp=shared_nlp)

    assert result.skills and all(s["confidence"] <= TIER1_CONFIDENCE for s in result.skills)
    assert result.technologies and all(t["confidence"] <= TIER1_CONFIDENCE for t in result.technologies)
    assert result.requirements and all(r["confidence"] <= TIER1_CONFIDENCE for r in result.requirements)


def test_tier2_skills_skipped_when_skills_already_present(shared_nlp: Language) -> None:
    """Per-field gating: sub-pass B fills only the empty list (skills here already has a normal entry)."""
    normal_skill = {"skill": "lead platform teams", "confidence": 1.0}
    job = _job(
        [_section(0, "About the role", TAXONOMY_MD, [("description", 0.90)])],
        skills=[normal_skill],
    )

    result = apply_fallback(job, TAXONOMY_MD, shared_nlp=shared_nlp)

    assert result.skills == [normal_skill]
    assert "python" in _texts(result.technologies, "tech")


# ============================================================================
# De-duplication guard
# ============================================================================


def test_complete_job_skips_fallback_outcome_gate(shared_nlp: Language) -> None:
    """Outcome gate only (not de-dupe): a COMPLETE job with existing output is returned untouched.

    Trade Desk shape (skills=2). The fallback never runs for COMPLETE, so this checks the
    NEEDS_HUMAN_REVIEW gate. Duplicate suppression is covered by the de-dupe tests below.
    """
    normal_skills = [
        {"skill": "design systems", "confidence": 1.0},
        {"skill": "build pipelines", "confidence": 1.0},
    ]
    job = _job(
        [_section(0, "Skills", "- Build pipelines\n- Python", [("skills", 0.55)])],
        outcome=ExtractionOutcome.COMPLETE,
        skills=normal_skills,
    )
    before = copy.deepcopy(job)

    result = apply_fallback(job, "- Build pipelines\n- Python\n", shared_nlp=shared_nlp)

    assert result == before
    assert _texts(result.skills, "skill") == ["design systems", "build pipelines"]


def test_no_duplicate_text_across_normal_and_fallback_output(shared_nlp: Language) -> None:
    """Normal-path tech 'python' is not appended again by the relaxed pass or taxonomy."""
    normal_tech = [{"tech": "python", "confidence": 1.0}]
    job = _job(
        [_section(0, "Skills", "- Build scalable data pipelines using Spark\n- Python", [("skills", 0.55)])],
        technologies=normal_tech,
    )

    result = apply_fallback(job, "- Build scalable data pipelines using Spark\n- Python\n", shared_nlp=shared_nlp)

    tech_texts = _texts(result.technologies, "tech")
    assert tech_texts.count("python") == 1
    assert result.technologies[0] == normal_tech[0]
    assert len(tech_texts) == len(set(tech_texts))
    skill_texts = _texts(result.skills, "skill")
    assert len(skill_texts) == len(set(skill_texts))


def test_fallback_does_not_reappend_case_variant_of_normal_entry(shared_nlp: Language) -> None:
    """Normal path holds '  Python ' (case/whitespace variant); the relaxed tech pass yields 'python'.

    The guard must drop the fallback copy and keep the normal-path entry unchanged.
    """
    content = "- Build scalable data pipelines using Spark\n- Python\n"
    normal_tech = [{"tech": "  Python ", "confidence": 1.0}]
    job = _job(
        [_section(0, "Skills", content, [("skills", 0.55)])],
        technologies=normal_tech,
    )

    # Precondition: the relaxed pass really does produce 'python', so the guard is what is tested.
    relaxed = fp._relaxed_section_pass(job, shared_nlp)
    assert "python" in [text.lower() for text, _ in relaxed["technologies"]]

    result = apply_fallback(job, f"## Skills\n\n{content}", shared_nlp=shared_nlp)

    assert result.technologies == normal_tech
    assert _texts(result.technologies, "tech") == ["  Python "]


def test_no_duplicate_text_within_fallback_output(shared_nlp: Language) -> None:
    """Repeated mentions in the relaxed sections and the taxonomy pass each appear once."""
    content = "- Python, Docker\n- Python, Docker, Kubernetes\n"
    md = f"## Skills\n\n{content}\nWe use Python and Docker daily.\n"
    job = _job([_section(0, "Skills", content, [("skills", 0.55)])])

    result = apply_fallback(job, md, shared_nlp=shared_nlp)

    for key, entries in (("tech", result.technologies), ("skill", result.skills)):
        texts = _texts(entries, key)
        assert len(texts) == len(set(texts)), f"duplicate {key} entries: {texts}"


def test_guard_is_case_and_whitespace_insensitive() -> None:
    target: List[Dict[str, Any]] = [{"tech": "Python", "confidence": 1.0}]

    added = fp._append_new(
        target,
        "tech",
        [("  python ", 0.5), ("PYTHON", 0.5), ("Docker", 0.5), ("docker", 0.5), ("", 0.5)],
        TIER1_TAG,
    )

    assert added == 1
    assert _texts(target, "tech") == ["Python", "Docker"]
    assert target[1]["extraction_tier"] == TIER1_TAG


# ============================================================================
# Pipeline isolation
# ============================================================================


def test_shared_entity_ruler_patterns_unchanged_after_fallback(shared_nlp: Language) -> None:
    """A fallback run that exercises TechExtractor must not touch the shared batch pipeline.

    TechExtractor.__init__ adds patterns to the entity_ruler of the nlp it is given. The
    fallback uses its own cached pipeline, so the shared ruler's patterns are unchanged.
    """
    ruler = shared_nlp.get_pipe("entity_ruler")
    before = copy.deepcopy(ruler.patterns)  # type: ignore[attr-defined]
    assert before, "shared pipeline should carry the batch TECH patterns"

    # Tier 2 runs TechExtractor (no classified tech yield), so this is the path under test.
    job = _job([_section(0, "About the role", TAXONOMY_MD, [("description", 0.90)])])
    apply_fallback(job, TAXONOMY_MD, shared_nlp=shared_nlp)
    apply_fallback(_uw_walmart_job(), UW_WALMART_MD, shared_nlp=shared_nlp)

    assert ruler.patterns == before  # type: ignore[attr-defined]


def test_dedicated_pipeline_is_separate_and_built_once(shared_nlp: Language) -> None:
    dedicated = fp._dedicated_tech_extractor()
    assert dedicated.nlp is not shared_nlp
    assert fp._dedicated_tech_extractor() is dedicated

    count = len(dedicated.nlp.get_pipe("entity_ruler").patterns)  # type: ignore[attr-defined]
    job = _job([_section(0, "About the role", TAXONOMY_MD, [("description", 0.90)])])
    apply_fallback(job, TAXONOMY_MD, shared_nlp=shared_nlp)
    apply_fallback(job, TAXONOMY_MD, shared_nlp=shared_nlp)

    assert len(dedicated.nlp.get_pipe("entity_ruler").patterns) == count  # type: ignore[attr-defined]


# ============================================================================
# min_section_confidence parameter (Issue #756, part 1/2)
# ============================================================================


def test_default_min_section_confidence_matches_module_constant(shared_nlp: Language) -> None:
    """Omitting the parameter and passing the constant explicitly give identical output."""
    implicit = apply_fallback(_uw_walmart_job(), UW_WALMART_MD, shared_nlp=shared_nlp)
    explicit = apply_fallback(
        _uw_walmart_job(),
        UW_WALMART_MD,
        shared_nlp=shared_nlp,
        min_section_confidence=FALLBACK_MIN_SECTION_CONFIDENCE,
    )

    assert implicit == explicit
    assert any(s["extraction_tier"] == TIER1_TAG for s in implicit.skills)


def test_min_section_confidence_flag_changes_tier1_acceptance(shared_nlp: Language) -> None:
    """UW/Walmart sections sit at 0.55: accepted at the default floor, rejected above it."""
    accepted = apply_fallback(_uw_walmart_job(), UW_WALMART_MD, shared_nlp=shared_nlp)
    rejected = apply_fallback(_uw_walmart_job(), UW_WALMART_MD, shared_nlp=shared_nlp, min_section_confidence=0.60)

    assert any(s["extraction_tier"] == TIER1_TAG for s in accepted.skills)
    assert _texts(accepted.requirements, "text") == ["Must have 5+ years of Python experience"]
    assert not [e for e in rejected.requirements if e.get("extraction_tier") == TIER1_TAG]
    assert not [e for e in rejected.skills if e.get("extraction_tier") == TIER1_TAG]
    assert not [e for e in rejected.technologies if e.get("extraction_tier") == TIER1_TAG]


def test_min_section_confidence_lowering_recovers_below_default(shared_nlp: Language) -> None:
    """A section at 0.40 is not recovered at the default 0.45 floor but is at a lowered floor."""
    content = "- Build scalable data pipelines using Spark"
    md = f"## Skills\n\n{content}\n"
    job_default = _job([_section(0, "Skills", content, [("skills", 0.40)])])
    job_lowered = _job([_section(0, "Skills", content, [("skills", 0.40)])])

    default = apply_fallback(job_default, md, shared_nlp=shared_nlp)
    lowered = apply_fallback(job_lowered, md, shared_nlp=shared_nlp, min_section_confidence=0.30)

    assert not [s for s in default.skills if s.get("extraction_tier") == TIER1_TAG]
    assert _texts(lowered.skills, "skill") == ["build scalable data pipelines using spark"]
    assert all(s["extraction_tier"] == TIER1_TAG for s in lowered.skills)
