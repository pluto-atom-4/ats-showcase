"""Custom regex-based span categorizer without spaCy NLP overhead.

Pure regex pattern matching for requirement span extraction, ideal for
lightweight categorization without full NLP pipeline dependency.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from spacy.tokens import Doc

from src.preprocessing.span_types import (
    DEFAULT_RULES,
    BoundaryRules,
    SpanCategory,
    SpanPattern,
)

# Constants
MAX_PATTERN_LENGTH = 500
MAX_TEXT_LENGTH = 200_000

# Register custom extension at module level
if not Doc.has_extension("custom_spans"):
    Doc.set_extension("custom_spans", default=None)


def validate_pattern(pattern: str) -> None:
    """Validate regex pattern for safety and correctness.

    Checks pattern length and detects ReDoS-prone nested quantifiers
    like (a+)+, (a*)*. Lazy quantifiers (+?, *?) are safe and not flagged.

    Args:
        pattern: Regex pattern string to validate.

    Raises:
        ValueError: If pattern exceeds length limit, contains ReDoS-prone
            nested quantifiers, or fails to compile.

    Examples:
        >>> validate_pattern("a+b")  # OK
        >>> validate_pattern("a+?b")  # OK (lazy quantifier)
        >>> validate_pattern("(a+)+")  # Raises ValueError (ReDoS)
    """
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise ValueError(f"Pattern exceeds max length {MAX_PATTERN_LENGTH}: {len(pattern)}")

    # Strip lazy quantifiers (? directly after +, *, or })
    # to detect nested quantifiers properly
    stripped = re.sub(r"([+*}])\?", r"\1", pattern)

    # Check for nested quantifiers: [+*}] followed optionally by )
    # then another quantifier [+*{]
    redos_pattern = r"[+*}]\)?[+*{]"
    if re.search(redos_pattern, stripped):
        raise ValueError(f"Pattern contains ReDoS-prone nested quantifiers: {pattern}")

    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid regex pattern: {exc}") from exc


class CustomSpanCategorizer:
    """Pure regex-based span categorizer without spaCy NLP.

    Matches text against a list of regex patterns and extracts spans
    with category labels and metadata. Zero-length matches are skipped.

    Attributes:
        patterns: List of (SpanPattern, compiled regex) tuples.
    """

    def __init__(self, patterns: list[SpanPattern]) -> None:
        """Initialize categorizer with patterns.

        Filters out patterns with None regex, validates each pattern,
        and pre-compiles regexes for efficiency.

        Args:
            patterns: List of SpanPattern objects. Patterns with
                .pattern = None are silently skipped.

        Raises:
            ValueError: If any pattern fails validation.
        """
        self.patterns: list[tuple[SpanPattern, re.Pattern[str]]] = []

        for sp in patterns:
            # Skip patterns with None regex
            if sp.pattern is None:
                continue

            # Validate pattern (raises ValueError if invalid)
            validate_pattern(sp.pattern)

            # Compile and store
            compiled = re.compile(sp.pattern)
            self.patterns.append((sp, compiled))

    def categorize(self, text: str) -> list[SpanCategory]:
        """Extract and categorize spans from text.

        Applies all patterns to text, collects matches, and returns
        sorted list of SpanCategory objects. Zero-length matches are
        skipped. Metadata from pattern is deep-copied per match.

        Args:
            text: Input text to categorize.

        Returns:
            List of SpanCategory objects sorted by (start_char, end_char).

        Raises:
            ValueError: If text exceeds MAX_TEXT_LENGTH.
        """
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError(f"Text exceeds max length {MAX_TEXT_LENGTH}: {len(text)}")

        results: list[SpanCategory] = []

        for pattern_obj, compiled_regex in self.patterns:
            for match in compiled_regex.finditer(text):
                # Skip zero-length matches
                if match.start() == match.end():
                    continue

                # Copy metadata to isolate per match
                metadata = dict(pattern_obj.metadata)

                span = SpanCategory(
                    category=pattern_obj.category,
                    text=match.group(0),
                    start_char=match.start(),
                    end_char=match.end(),
                    metadata=metadata,
                )
                results.append(span)

        # Sort by start position, then end position
        results.sort(key=lambda s: (s.start_char, s.end_char))

        return results


def load_patterns(path: str | Path) -> list[SpanPattern]:
    """Load patterns from JSON file.

    File format: JSON array of objects with keys:
    - category (required, string)
    - pattern (optional, string regex)
    - metadata (optional, dict)
    - boundary_rules (optional, object with optional lists
      hard_stops, soft_stops, stop_words)

    Each pattern is validated during construction (via SpanPattern
    __post_init__ and validate_pattern).

    Args:
        path: Path to JSON file.

    Returns:
        List of SpanPattern objects.

    Raises:
        ValueError: If JSON top-level is not a list or category is
            missing from any object.
        FileNotFoundError: If file does not exist.
        json.JSONDecodeError: If JSON is malformed.

    Examples:
        >>> patterns = load_patterns("config/patterns.json")
    """
    path = Path(path)

    with open(path) as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON file must contain a top-level array")

    patterns = []
    for obj in data:
        if not isinstance(obj, dict):
            raise ValueError("Each pattern entry must be a dict")

        category = obj.get("category")
        if not category:
            raise ValueError("Each pattern must have a 'category' key")

        pattern_str = obj.get("pattern")
        metadata = obj.get("metadata", {})

        # Parse boundary_rules if present
        boundary_rules = DEFAULT_RULES
        if "boundary_rules" in obj:
            br_obj = obj["boundary_rules"]
            hard_stops = frozenset(br_obj.get("hard_stops", DEFAULT_RULES.hard_stops))
            soft_stops = frozenset(br_obj.get("soft_stops", DEFAULT_RULES.soft_stops))
            stop_words = frozenset(br_obj.get("stop_words", DEFAULT_RULES.stop_words))
            boundary_rules = BoundaryRules(
                hard_stops=hard_stops,
                soft_stops=soft_stops,
                stop_words=stop_words,
            )

        # Validate pattern if provided
        if pattern_str is not None:
            validate_pattern(pattern_str)

        sp = SpanPattern(
            category=category,
            pattern=pattern_str,
            boundary_rules=boundary_rules,
            metadata=metadata,
        )
        patterns.append(sp)

    return patterns


class SpanCategorizerComponent:
    """Thin spaCy wrapper for CustomSpanCategorizer.

    Wraps CustomSpanCategorizer to use as a spaCy pipeline component
    (without @Language.factory decorator). Sets doc._.custom_spans
    attribute.

    Attributes:
        categorizer: CustomSpanCategorizer instance.

    Examples:
        >>> import spacy
        >>> nlp = spacy.blank("en")
        >>> patterns = [SpanPattern(category="skill", pattern=r"Python")]
        >>> cat = CustomSpanCategorizer(patterns)
        >>> comp = SpanCategorizerComponent(cat)
        >>> doc = nlp("I know Python")
        >>> doc = comp(doc)
        >>> print(doc._.custom_spans)
    """

    def __init__(self, categorizer: CustomSpanCategorizer) -> None:
        """Initialize component with categorizer.

        Args:
            categorizer: CustomSpanCategorizer instance.
        """
        self.categorizer = categorizer

    def __call__(self, doc: Doc) -> Doc:
        """Extract spans and attach to doc.

        Runs categorizer on doc.text and stores results as list of dicts
        (category, text, start_char, end_char, metadata) in doc._.custom_spans.

        Args:
            doc: spaCy Doc object.

        Returns:
            Doc with custom_spans attribute set.
        """
        spans = self.categorizer.categorize(doc.text)

        # Convert to list of dicts for serialization
        spans_list = [
            {
                "category": s.category,
                "text": s.text,
                "start_char": s.start_char,
                "end_char": s.end_char,
                "metadata": s.metadata,
            }
            for s in spans
        ]

        doc._.custom_spans = spans_list
        return doc


__all__ = [
    "MAX_PATTERN_LENGTH",
    "MAX_TEXT_LENGTH",
    "validate_pattern",
    "CustomSpanCategorizer",
    "load_patterns",
    "SpanCategorizerComponent",
]
