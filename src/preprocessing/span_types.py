"""Span type definitions and boundary rules for requirement extraction.

Defines immutable dataclasses for span patterns, categories, and boundary rules
used in Phase 8 requirement and span extraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BoundaryRules:
    """Rules for determining span boundaries during extraction.

    Attributes:
        hard_stops: Punctuation that always terminates a span.
        soft_stops: Punctuation that may terminate a span unless followed by conjunction.
        stop_words: Subordinating conjunctions that terminate span expansion.
    """

    hard_stops: frozenset[str] = frozenset({".", ";", "!", "?", ")"})
    soft_stops: frozenset[str] = frozenset({","})
    stop_words: frozenset[str] = frozenset({"if", "unless", "because"})


DEFAULT_RULES: BoundaryRules = BoundaryRules()


@dataclass(frozen=True)
class SpanPattern:
    """Pattern definition for requirement span extraction.

    Attributes:
        category: Category name for this pattern (non-empty string).
        pattern: Optional regex pattern to match spans. If provided, must be valid regex.
        boundary_rules: Rules for expanding span boundaries.
        metadata: Additional metadata about the pattern.
    """

    category: str
    pattern: str | None = None
    boundary_rules: BoundaryRules = DEFAULT_RULES
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate pattern and category.

        Raises:
            ValueError: If category is empty or pattern is invalid regex.
        """
        if not self.category:
            raise ValueError("category must be a non-empty string")

        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(
                    f"Invalid regex for category '{self.category}': {exc}",
                ) from exc


@dataclass(frozen=True)
class SpanCategory:
    """Extracted span instance with metadata.

    Attributes:
        category: Category name for this span.
        text: The text content of the span.
        start_char: Character offset where span starts in document.
        end_char: Character offset where span ends in document.
        metadata: Additional metadata about this span instance.
    """

    category: str
    text: str
    start_char: int
    end_char: int
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "BoundaryRules",
    "DEFAULT_RULES",
    "SpanPattern",
    "SpanCategory",
]
