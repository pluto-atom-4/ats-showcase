"""Merged Tier 1+2 fallback extraction for NEEDS_HUMAN_REVIEW and complete-gap jobs (Issue #739, #757 B, Part of #735).

Admitted shapes: ``NEEDS_HUMAN_REVIEW`` (Tier 1 then Tier 2), and ``COMPLETE`` with technologies
empty and requirements or skills empty (complete-gap, Tier 2 only).

Runs when a job's ``extraction_outcome`` is ``NEEDS_HUMAN_REVIEW`` (no stage errors,
zero extraction yield, real-looking input), or is ``COMPLETE`` with technologies empty and
requirements or skills empty (complete-gap, Issue #757 B). Complete-gap jobs run sub-pass B
only. Section-type gating at 0.70 is the dominant cause
of zero yield on real content, so the fallback recovers output in two sub-passes:

Sub-pass A (``tier1_relaxed_section``): re-runs the existing RequirementProcessor,
SkillProcessor and TechnologyProcessor over the section classifications already computed by
the normal path, with their confidence gate lowered to ``min_section_confidence`` (default
``FALLBACK_MIN_SECTION_CONFIDENCE``).
The classifications are rebuilt from ``JobResult.markdown_sections`` (their ``all_types``
data is persisted there), so no section classification is recomputed.

Sub-pass B (``tier2_taxonomy``): for ``skills`` / ``technologies`` still empty after sub-pass A,
runs the ungated whole-document extractors (``SkillExtractor``, ``TechExtractor``) over the
full ``polished_markdown``.

Every appended entry passes one shared de-duplication guard (by normalized text, per output
list). Recovered entries carry ``extraction_tier`` and a capped, lower ``confidence``.

Pipeline ownership:
    ``TechExtractor.__init__`` adds TECH patterns to the entity_ruler of the nlp it is given.
    The fallback therefore builds and caches its own dedicated spaCy pipeline
    (``_dedicated_tech_extractor``) and uses it only for ``TechExtractor``. The shared
    batch pipeline passed in as ``shared_nlp`` is never given new patterns. It is only read
    by the processors and ``SkillExtractor``, which do not mutate the pipeline.

Classes / functions:
    apply_fallback: Public entry point; returns the (mutated) JobResult.

Usage (call-site wiring is a follow-up; see the module docs of batch_processor):
    >>> from src.poc.tweak.spacy_pipeline.fallback_processor import apply_fallback
    >>> result = apply_fallback(result, polished_markdown, shared_nlp=nlp)
"""

import functools
import logging
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set, Tuple

import spacy
from spacy.language import Language
from spacy.tokens import Doc

from src.poc.skills.extract_skills_a import SkillExtractor
from src.poc.technologies.extract_technologies_a import TechExtractor
from src.poc.tweak.extraction_status import FALLBACK_MIN_SECTION_CONFIDENCE, ExtractionOutcome
from src.poc.tweak.markdown_section_classifier import SectionClassification, TypeClassification
from src.poc.tweak.multi_line_paragraph import MarkdownSection as RulerSection
from src.poc.tweak.patterns import SectionType
from src.poc.tweak.section_model import MarkdownSection
from src.poc.tweak.spacy_pipeline.requirement_processor import RequirementProcessor
from src.poc.tweak.spacy_pipeline.skill_processor import SkillProcessor
from src.poc.tweak.spacy_pipeline.technology_processor import TechnologyProcessor

if TYPE_CHECKING:
    from src.poc.tweak.batch_processor import JobResult

logger = logging.getLogger(__name__)

TIER1_TAG = "tier1_relaxed_section"
TIER2_TAG = "tier2_taxonomy"

# Confidence caps for recovered entries. Normal-path entries are scored above these
# (skills/technologies are 1.0). Tier 1 entries never exceed TIER1_CONFIDENCE; taxonomy
# entries carry no classification signal and use TIER2_CONFIDENCE.
TIER1_CONFIDENCE = 0.5
TIER2_CONFIDENCE = 0.3

_SPACY_MODEL = "en_core_web_md"
_RELAXED_COMPONENT_NAME = "fallback_relaxed"


@functools.lru_cache(maxsize=1)
def _dedicated_tech_extractor() -> TechExtractor:
    """Return the cached dedicated TechExtractor, building it on first use.

    Owned by this module. ``TechExtractor.__init__`` adds TECH patterns to this pipeline's
    entity_ruler, so the pipeline must not be shared with the batch nlp. Batch processing is
    sequential, so in practice the model is loaded once. Under a first-call race, at most one
    retained instance is kept; a duplicate load is discarded.
    """
    return TechExtractor(spacy.load(_SPACY_MODEL))


def _dedupe_key(text: str) -> str:
    """Normalize an entry's text for the de-duplication guard."""
    return " ".join(text.split()).lower()


def _append_new(
    target: List[Dict[str, Any]],
    text_key: str,
    candidates: Iterable[Tuple[str, float]],
    tier: str,
) -> int:
    """Shared de-duplication guard: append only entries whose text is not already present.

    The seen-set is built from ``target`` (normal-path output and earlier sub-pass output),
    so an entry is never appended twice across passes.

    Args:
        target: The JobResult list to append to (requirements, skills or technologies).
        text_key: Dict key holding the entry text ("text", "skill" or "tech").
        candidates: (text, confidence) pairs in the order they should be appended.
        tier: extraction_tier tag for appended entries.

    Returns:
        Number of entries appended.
    """
    seen: Set[str] = {_dedupe_key(str(entry.get(text_key, ""))) for entry in target}
    added = 0
    for text, confidence in candidates:
        key = _dedupe_key(text)
        if not key or key in seen:
            continue
        seen.add(key)
        target.append({text_key: text, "confidence": round(confidence, 2), "extraction_tier": tier})
        added += 1
    return added


def _to_ruler_section(section: MarkdownSection) -> RulerSection:
    """Rebuild the parsed-section object the processors read from a persisted MarkdownSection.

    Approximation: ``level`` is not persisted on MarkdownSection, so titled sections use
    ATX level 2 and untitled sections use the preamble level -2. No processor reads ``.level``
    today, so the approximation has no effect on output; revisit if one starts to.
    """
    content = section.content or ""
    lines = content.splitlines()
    return RulerSection(
        title=section.heading or None,
        content=content,
        level=2 if section.heading else -2,
        start_line=section.line_start,
        end_line=section.line_end,
        word_count=len(content.split()),
        line_count=sum(1 for line in lines if line.strip()),
        has_list=any(line.lstrip().startswith(("-", "*", "•")) for line in lines),
    )


def _to_classification(section: MarkdownSection) -> Optional[SectionClassification]:
    """Rebuild the all_types-ranked classification from a persisted MarkdownSection.

    Returns None when no classification is available (unknown or unparseable types).
    """
    types: List[TypeClassification] = []
    for entry in section.all_types:
        try:
            section_type = SectionType(entry["section_type"])
        except (KeyError, ValueError):
            continue
        types.append(TypeClassification(section_type=section_type, confidence=float(entry["confidence"])))
    if not types:
        return None
    types.sort(key=lambda tc: tc.confidence, reverse=True)
    return SectionClassification(
        all_types=tuple(types),
        labels=frozenset(tc.section_type for tc in types),
    )


def _relaxed_section_pass(
    job_result: "JobResult",
    shared_nlp: Language,
    min_section_confidence: float = FALLBACK_MIN_SECTION_CONFIDENCE,
) -> Dict[str, List[Tuple[str, float]]]:
    """Sub-pass A: rerun the processors over computed classifications at the relaxed threshold.

    The processors run on ``shared_nlp`` (read-only here). Sections already above the normal
    0.70 gate yield the same entries as the normal path; the de-duplication guard drops them.
    Sections below ``min_section_confidence`` are not accepted.

    Returns:
        Mapping with "requirements", "skills" and "technologies" lists of (text, confidence).
    """
    pairs: List[Tuple[RulerSection, SectionClassification]] = []
    for section in job_result.markdown_sections:
        classification = _to_classification(section)
        if classification is not None:
            pairs.append((_to_ruler_section(section), classification))

    if not pairs:
        return {"requirements": [], "skills": [], "technologies": []}

    if not Doc.has_extension("classified_sections"):
        Doc.set_extension("classified_sections", default=[])
    doc = Doc(shared_nlp.vocab)
    doc._.classified_sections = pairs

    req_processor = RequirementProcessor(shared_nlp, _RELAXED_COMPONENT_NAME, min_confidence=min_section_confidence)
    skill_processor = SkillProcessor(shared_nlp, _RELAXED_COMPONENT_NAME, min_confidence=min_section_confidence)
    tech_processor = TechnologyProcessor(shared_nlp, _RELAXED_COMPONENT_NAME, min_confidence=min_section_confidence)

    doc = req_processor(doc)
    requirements = [(r["text"], min(float(r["confidence"]), TIER1_CONFIDENCE)) for r in doc._.requirements]
    doc = skill_processor(doc)
    skills = [(s["skill"], TIER1_CONFIDENCE) for s in doc._.skills]
    doc = tech_processor(doc)
    technologies = [(t["tech"], TIER1_CONFIDENCE) for t in doc._.technologies]

    return {"requirements": requirements, "skills": skills, "technologies": technologies}


def _taxonomy_pass(
    polished_markdown: str, shared_nlp: Language, need_skills: bool, need_technologies: bool
) -> Dict[str, List[str]]:
    """Sub-pass B: ungated whole-document extraction over ``polished_markdown``.

    Technologies run through the dedicated pipeline only; skills run on plain text through
    ``SkillExtractor`` bound to the shared nlp (read-only).
    """
    result: Dict[str, List[str]] = {"skills": [], "technologies": []}
    if need_skills:
        result["skills"] = SkillExtractor(nlp=shared_nlp).extract(polished_markdown)
    if need_technologies:
        tech_extractor = _dedicated_tech_extractor()
        result["technologies"] = tech_extractor.extract(tech_extractor.nlp(polished_markdown))
    return result


def _is_complete_gap(job_result: "JobResult") -> bool:
    """True for a COMPLETE job with no technologies and a missing requirements or skills list (#757 B)."""
    return (
        job_result.extraction_outcome is ExtractionOutcome.COMPLETE
        and not job_result.technologies
        and (not job_result.requirements or not job_result.skills)
    )


def apply_fallback(
    job_result: "JobResult",
    polished_markdown: str,
    *,
    shared_nlp: Language,
    min_section_confidence: float = FALLBACK_MIN_SECTION_CONFIDENCE,
) -> "JobResult":
    """Recover zero-yield extraction for NEEDS_HUMAN_REVIEW and complete-gap jobs (Issue #739, #757 B).

    Two admitted shapes:
      - ``NEEDS_HUMAN_REVIEW``: Tier 1 (relaxed sections) then Tier 2 (taxonomy).
      - ``COMPLETE`` with empty technologies and empty requirements or skills (complete-gap):
        Tier 2 only. Requirements are never modified.

    All other outcomes, and COMPLETE jobs outside the gap shape, are returned untouched.
    Mutates and returns ``job_result``: recovered entries are appended to
    requirements/skills/technologies with ``extraction_tier`` tags. When anything is recovered,
    ``extraction_outcome`` is set to ``PARTIAL_RECOVERY``; otherwise it is left unchanged.

    Args:
        job_result: Result of ``process_job`` for the job.
        polished_markdown: The job's polished markdown (the text ``process_job`` parsed).
            Not stored on JobResult, so the caller must pass it.
        shared_nlp: The batch pipeline's nlp. Read-only here; its entity_ruler is never modified.
        min_section_confidence: Section confidence floor for sub-pass A (Tier 1). Sections below
            it are not accepted. Defaults to ``FALLBACK_MIN_SECTION_CONFIDENCE`` (0.45), which is
            the behavior without this argument. Sub-pass B (Tier 2) is ungated and ignores it.

    Returns:
        The same JobResult object, updated in place.
    """
    is_needs_review = job_result.extraction_outcome is ExtractionOutcome.NEEDS_HUMAN_REVIEW
    if not is_needs_review and not _is_complete_gap(job_result):
        return job_result

    recovered = 0
    if is_needs_review:
        relaxed = _relaxed_section_pass(job_result, shared_nlp, min_section_confidence)
        recovered += _append_new(job_result.requirements, "text", relaxed["requirements"], TIER1_TAG)
        recovered += _append_new(job_result.skills, "skill", relaxed["skills"], TIER1_TAG)
        recovered += _append_new(job_result.technologies, "tech", relaxed["technologies"], TIER1_TAG)

    taxonomy = _taxonomy_pass(
        polished_markdown,
        shared_nlp,
        need_skills=not job_result.skills,
        # Always True on the complete-gap path (technologies is empty there by definition).
        need_technologies=not job_result.technologies,
    )
    recovered += _append_new(job_result.skills, "skill", [(s, TIER2_CONFIDENCE) for s in taxonomy["skills"]], TIER2_TAG)
    recovered += _append_new(
        job_result.technologies, "tech", [(t, TIER2_CONFIDENCE) for t in taxonomy["technologies"]], TIER2_TAG
    )

    if recovered:
        job_result.extraction_outcome = ExtractionOutcome.PARTIAL_RECOVERY
    logger.info(f"Fallback for job {job_result.job_id}: recovered {recovered} entries")
    return job_result


__all__ = ["TIER1_CONFIDENCE", "TIER1_TAG", "TIER2_CONFIDENCE", "TIER2_TAG", "apply_fallback"]
