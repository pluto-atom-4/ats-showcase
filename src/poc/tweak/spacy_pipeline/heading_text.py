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

# Edge-anchored only: interior punctuation (e.g. "C++", "snake_case", "e.g.") is kept.
# Trailing '.' is stripped together with markers so "**Foo**." matches "**Foo.**".
_HEADING_MARKER_PATTERN = re.compile(r"^[#*_\s]+|[#*_:.\s]+$")

_INNER_WHITESPACE_PATTERN = re.compile(r"\s+")

KNOWN_HEADING_PHRASES: frozenset[str] = frozenset(
    {
        "minimum qualifications",
        "additional qualifications",
        "preferred qualifications",
        "required qualifications",
        "working conditions",
        "key responsibilities",
    }
)

# Boilerplate sentences that are not headings but are dropped as non-requirements.
KNOWN_BOILERPLATE_SENTENCES: frozenset[str] = frozenset(
    {
        "applicants who do not meet these qualifications will not be forwarded to the hiring department",
    }
)


def normalize_heading_text(text: str) -> str:
    """Strip heading markers and trailing colon/period, collapse whitespace, lowercase.

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
    """Return True if candidate is heading or boilerplate text, not a requirement.

    A candidate is dropped when, after normalization and stripping trailing
    periods, it equals the section heading, matches a ``KNOWN_HEADING_PHRASES``
    entry, or matches a ``KNOWN_BOILERPLATE_SENTENCES`` entry.

    Accepted trade-off: a candidate equal to its section title is dropped even
    when it is a real one-word requirement (e.g. "Python" under a section
    titled "Python").

    Args:
        candidate: Requirement text to test
        heading: Optional section heading to compare against

    Returns:
        True if the candidate should be dropped as heading/boilerplate text.
        False for empty candidates.
    """
    key = normalize_heading_text(candidate)
    if not key:
        return False
    if heading is not None:
        norm_heading = normalize_heading_text(heading)
        if norm_heading and key == norm_heading:
            return True
    return key in KNOWN_HEADING_PHRASES or key in KNOWN_BOILERPLATE_SENTENCES
