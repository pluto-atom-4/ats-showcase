"""Heading-text helpers for requirement filtering (Issue #268).

Detects bare heading text (e.g. ``**Required Qualifications:**``) that leaked
into ``requirements[]`` as if it were a requirement sentence.

Functions:
    normalize_heading_text: Strip heading markers, trailing colon, lowercase
    is_heading_only: True if candidate is a heading rather than a requirement

Usage:
    >>> from src.poc.tweak.spacy_pipeline.heading_text import is_heading_only
    >>> is_heading_only("**Required Qualifications:**")
    True
    >>> is_heading_only("Required: Python")
    False

Issue #268: Drop heading-only requirements. Issue #724: shared helper.
"""

import re
from typing import Optional

# Edge-anchored only: interior punctuation (e.g. "C++", "snake_case") is kept.
_HEADING_MARKER_PATTERN = re.compile(r"^[#*_\s]+|[#*_:\s]+$")

_INNER_WHITESPACE_PATTERN = re.compile(r"\s+")

KNOWN_HEADING_PHRASES: frozenset[str] = frozenset(
    {
        "minimum qualifications",
        "additional qualifications",
        "preferred qualifications",
        "required qualifications",
        "working conditions",
        "key responsibilities",
        "applicants who do not meet these qualifications will not be forwarded to the hiring department",
    }
)


def normalize_heading_text(text: str) -> str:
    """Strip heading markers and trailing colon, collapse whitespace, lowercase.

    Args:
        text: Raw candidate text (may contain markdown emphasis or ``#`` marks)

    Returns:
        Normalized text, or "" if input is empty or only markers/whitespace
    """
    if not text:
        return ""
    stripped = _HEADING_MARKER_PATTERN.sub("", text).strip()
    collapsed = _INNER_WHITESPACE_PATTERN.sub(" ", stripped)
    return collapsed.lower()


def is_heading_only(candidate: str, heading: Optional[str] = None) -> bool:
    """Return True if candidate is heading text rather than a requirement.

    Args:
        candidate: Requirement text to test
        heading: Optional known section heading to compare against

    Returns:
        True if normalized candidate equals normalized heading, or matches a
        known heading phrase (optionally with a trailing period). False for
        empty candidates.
    """
    norm = normalize_heading_text(candidate)
    if not norm:
        return False
    if heading is not None:
        norm_heading = normalize_heading_text(heading)
        if norm_heading and norm == norm_heading:
            return True
    return norm.rstrip(".") in KNOWN_HEADING_PHRASES
