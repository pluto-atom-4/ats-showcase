"""Section detection in job descriptions using spaCy SpanRuler (Issue #281).

Detects job requirement sections (Requirements, Qualifications, Technical Skills, etc.)
using a spaCy blank pipeline with SpanRuler patterns. Character-based offsets for
integration with existing tokenization and chunking pipeline.

No spaCy model download required (blank pipeline only). Pure detection: no global state,
no network I/O, no model loading.
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass
from typing import Any, Collection, Mapping, Sequence

import spacy
from spacy.language import Language

from src.preprocessing.section_patterns import (
    DEFAULT_TARGET_SECTIONS,
    FILTER_SECTIONS,
    SECTION_DISPLAY_NAMES,
    SECTION_RULER_PATTERNS,
    SectionLabel,
)

logger = logging.getLogger(__name__)

MAX_INPUT_CHARS: int = 200_000
SPANS_KEY: str = "sections"
_HEADER_PREFIX_CHARS = " \t#*_->•·0123456789.)"


def _is_heading_like(text: str, start: int, end: int) -> bool:
    """Check if a detected span looks like a section header (not mid-sentence).

    A span is heading-like if:
    1. The line prefix (from line start to span start) contains only whitespace
       and header markers (markdown, bullets, numbers).
    2. The line suffix (from span end to line end) is empty or very short (≤40 chars)
       after stripping whitespace and header markers.

    Args:
        text: Full input text containing the span.
        start: Character offset where span starts.
        end: Character offset where span ends.

    Returns:
        True if the span appears to be a section header, False otherwise.
    """
    # Find line boundaries
    line_start = text.rfind("\n", 0, start) + 1  # +1 so rfind(-1) → 0
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)

    # Check prefix: only whitespace and header markers allowed
    prefix = text[line_start:start]
    # Strip whitespace, markdown markers, bullets, numbers, and other header artifacts
    prefix_stripped = prefix.strip(_HEADER_PREFIX_CHARS)
    if prefix_stripped != "":
        return False

    # Check suffix: should be empty or very short
    suffix = text[end:line_end]
    suffix_stripped = suffix.strip(" \t*_:#")
    if suffix_stripped and len(suffix_stripped) > 40:
        return False

    return True


_CLOSING_MARKERS = re.compile(r"^(?:\*\*|__|:)+")
_RawSpan = tuple[SectionLabel, int, int, str]


def _to_raw_spans(spans: Any) -> list[_RawSpan]:
    """Convert spaCy spans to raw tuples, skipping labels that are not a SectionLabel."""
    raw: list[_RawSpan] = []
    for span in spans:
        try:
            raw.append((SectionLabel(span.label_), span.start_char, span.end_char, span.text))
        except ValueError:
            logger.debug(f"Skipping span with unrecognized label: {span.label_}")
    return raw


def _resolve_overlaps(raw_spans: list[_RawSpan]) -> list[_RawSpan]:
    """Sort spans by start (longest first) and drop any span contained in or overlapping a kept one."""
    ordered = sorted(raw_spans, key=lambda s: (s[1], -(s[2] - s[1])))
    kept: list[_RawSpan] = []
    for span in ordered:
        _, start, end, _ = span
        if any(k[1] <= start and end <= k[2] for k in kept):
            logger.debug(f"Skipping contained span ({start}, {end})")
            continue
        if kept and start < kept[-1][2]:
            logger.debug(f"Skipping partially overlapping span ({start}, {end})")
            continue
        kept.append(span)
    return kept


def _clean_content(raw_content: str, has_next: bool) -> str:
    """Trim header artifacts from a section's raw content slice.

    Drops the next header's line prefix ("##", "**", "1.") when a next header exists, and this
    header's closing "**" / ":" marker (a "* " bullet is kept). Real trailing content is never trimmed.
    """
    if has_next:
        head, sep, tail = raw_content.rpartition("\n")
        if tail.strip(_HEADER_PREFIX_CHARS) == "":
            raw_content = head + sep
    return _CLOSING_MARKERS.sub("", raw_content.lstrip(" \t")).strip()


@dataclass(frozen=True)
class DetectedSection:
    """A detected section in a job description.

    Attributes:
        label: SectionLabel enum value (e.g., SectionLabel.REQUIREMENTS).
        display_name: Human-readable section name (e.g., "Requirements").
        header_text: The matched header text (the span itself).
        header_start: Character offset where header starts in input text.
        header_end: Character offset where header ends in input text.
        content_start: Character offset where section content starts (== header_end).
        content_end: Character offset where section content ends (start of next section or
                     end of text).
        content_text: Section content, stripped, minus the next header's line prefix
                      (e.g. "##") and this header's closing "**" / ":" marker.
    """

    label: SectionLabel
    display_name: str
    header_text: str
    header_start: int
    header_end: int
    content_start: int
    content_end: int
    content_text: str


class SectionDetector:
    """Detects job requirement sections using spaCy SpanRuler with character-based offsets.

    Uses a blank spaCy pipeline (no model download) configured with SpanRuler patterns
    to identify section headers in job descriptions. Overlapping and non-heading-like
    spans are filtered out.
    """

    def __init__(
        self,
        patterns: Sequence[Mapping[str, Any]] | None = None,
        display_names: Mapping[SectionLabel, str] | None = None,
        target_sections: Collection[SectionLabel] | None = None,
        promote_headings: bool = True,
    ) -> None:
        """Initialize SectionDetector with patterns and configuration.

        Args:
            patterns: SpanRuler patterns (default: SECTION_RULER_PATTERNS). Each pattern
                      must have "label" and "pattern" keys.
            display_names: Mapping from SectionLabel to human-readable names
                          (default: SECTION_DISPLAY_NAMES).
            target_sections: Collection of SectionLabel values to include in target_sections()
                            filtering (default: DEFAULT_TARGET_SECTIONS).
            promote_headings: If True, keep only spans that appear to be section headers
                             (default: True).

        Raises:
            OSError: If spaCy blank pipeline creation fails (unlikely in normal use).
        """
        self._patterns = patterns if patterns is not None else SECTION_RULER_PATTERNS
        self._display_names = display_names if display_names is not None else SECTION_DISPLAY_NAMES
        self._target_sections = frozenset(target_sections) if target_sections is not None else DEFAULT_TARGET_SECTIONS
        self._promote_headings = promote_headings

        # Initialize blank spaCy pipeline with SpanRuler
        self._nlp: Language = spacy.blank("en")
        ruler = self._nlp.add_pipe("span_ruler", config={"spans_key": SPANS_KEY})
        # Deep copy patterns to avoid mutating shared module-level data
        ruler.add_patterns(copy.deepcopy([dict(p) for p in self._patterns]))  # type: ignore[attr-defined]

    def detect(self, text: str) -> list[DetectedSection]:
        """Detect sections in text using SpanRuler patterns.

        Args:
            text: Input job description text (plain text or markdown). Empty/None values
                  return []. Text longer than MAX_INPUT_CHARS is truncated with a warning.

        Returns:
            List of DetectedSection objects ordered by header_start, with no overlaps.
            Each section's content_end equals the next section's header_start (or len(text)).

        Raises:
            No exceptions raised; invalid spans are skipped with debug logging.
        """
        # Handle empty or whitespace-only input
        if not text or not text.strip():
            return []

        # Truncate if needed
        if len(text) > MAX_INPUT_CHARS:
            logger.warning(f"Input text ({len(text)} chars) exceeds MAX_INPUT_CHARS ({MAX_INPUT_CHARS}); truncating.")
            text = text[:MAX_INPUT_CHARS]

        # Run spaCy pipeline to extract spans
        doc = self._nlp(text)
        spans = doc.spans.get(SPANS_KEY, [])

        if not spans:
            return []

        raw_spans = _to_raw_spans(spans)
        if not raw_spans:
            return []

        kept_spans = _resolve_overlaps(raw_spans)

        # Filter by promote_headings if enabled
        if self._promote_headings:
            filtered_spans: list[tuple[SectionLabel, int, int, str]] = []
            for label, start, end, header_text in kept_spans:
                # Check if span is heading-like using full text and char offsets
                if _is_heading_like(text, start, end):
                    filtered_spans.append((label, start, end, header_text))
                else:
                    logger.debug(f"Filtering out non-heading span: {label.value} ({start}, {end}) = '{header_text}'")
            kept_spans = filtered_spans

        # Build DetectedSection objects with content boundaries
        detected_sections: list[DetectedSection] = []
        for idx, (label, header_start, header_end, header_text) in enumerate(kept_spans):
            content_start = header_end
            # Content ends at next header's start, or at end of text
            if idx + 1 < len(kept_spans):
                content_end = kept_spans[idx + 1][1]
            else:
                content_end = len(text)

            content_text = _clean_content(text[content_start:content_end], has_next=idx + 1 < len(kept_spans))

            detected_sections.append(
                DetectedSection(
                    label=label,
                    display_name=self._display_names.get(label, label.value),
                    header_text=header_text,
                    header_start=header_start,
                    header_end=header_end,
                    content_start=content_start,
                    content_end=content_end,
                    content_text=content_text,
                )
            )

        return detected_sections

    def target_sections(self, sections: Sequence[DetectedSection]) -> list[DetectedSection]:
        """Filter sections to keep only target sections (excluding filter sections).

        Args:
            sections: List of DetectedSection objects to filter.

        Returns:
            List of sections whose label is in self._target_sections and NOT in
            FILTER_SECTIONS, preserving original order.
        """
        return [s for s in sections if s.label in self._target_sections and s.label not in FILTER_SECTIONS]


__all__ = [
    "MAX_INPUT_CHARS",
    "SPANS_KEY",
    "DetectedSection",
    "SectionDetector",
]
