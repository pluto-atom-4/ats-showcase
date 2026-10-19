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

# Edge-anchored only. Leading: '#', '*', '_', whitespace. Trailing: any run of '*', '_', ':',
# '.', whitespace, and a closing ATX run of '#' only when preceded by whitespace
# ("## Heading ##"), in any order, so "**Foo** ##" and "**Foo ##**" both strip fully.
# A '#' attached to a word is kept, so "C#" stays "c#".
# Interior punctuation (e.g. "C++", "snake_case", "e.g.") is kept.
# Trailing '.' is stripped together with markers so "**Foo**." matches "**Foo.**".
_HEADING_MARKER_PATTERN = re.compile(r"^[#*_\s]+|(?:[*_:.\s]|\s#+(?=[\s*_:.#]*$))+$")

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

# Boilerplate sentence family dropped as non-requirements. Deliberately narrow: it matches only
# the "applicants who do not meet ... will not be forwarded to the hiring department" notice and
# its small wording variants, not a general boilerplate detector. Matched against the normalized
# key (lowercased, markers/trailing periods stripped, whitespace collapsed).
_BOILERPLATE_PATTERN = re.compile(
    r"applicants who do not meet (?:these|the minimum|the) qualifications "
    r"will not be forwarded to the hiring department$"
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


_TRAILING_MARKER_PATTERN = re.compile(r"[*_.\s]+$")


def _is_structural_level(level: int) -> bool:
    """True for ruler bold-only level (-1) or an ATX heading depth (1-6)."""
    return level == -1 or 1 <= level <= 6


def is_heading_only(candidate: str, heading: Optional[str] = None, level: Optional[int] = None) -> bool:
    """Return True if candidate is heading or boilerplate text, not a requirement.

    A candidate is dropped when, after normalization and stripping trailing
    periods, it equals the section heading, matches a ``KNOWN_HEADING_PHRASES``
    entry, or matches ``_BOILERPLATE_PATTERN`` (the narrow applicants-not-forwarded notice).

    Structural narrowing (only when ``level`` is given): a candidate is also
    dropped when ``level`` is structural (ruler -1 or ATX depth 1-6) AND either
    it equals the section heading, or its raw text ends with a colon once
    trailing markers are ignored (e.g. ``**Also required:**``). ``level`` is
    never a standalone trigger, so a bold real requirement that differs from
    the title and has no trailing colon is kept.

    Accepted trade-off: a candidate equal to its section title is dropped even
    when it is a real one-word requirement (e.g. "Python" under a section
    titled "Python").

    Args:
        candidate: Requirement text to test
        heading: Optional section heading to compare against
        level: Optional ruler level (-1 bold-only, 1-6 ATX). None disables
            the structural narrowing and keeps the legacy behavior.

    Returns:
        True if the candidate should be dropped as heading/boilerplate text.
        False for empty candidates.
    """
    key = normalize_heading_text(candidate)
    if not key:
        return False
    norm_heading = normalize_heading_text(heading) if heading is not None else ""
    title_equal = bool(norm_heading) and key == norm_heading
    if title_equal:
        return True
    if level is not None and _is_structural_level(level):
        ends_with_colon = _TRAILING_MARKER_PATTERN.sub("", candidate).endswith(":")
        if ends_with_colon:
            return True
    return key in KNOWN_HEADING_PHRASES or _BOILERPLATE_PATTERN.match(key) is not None
