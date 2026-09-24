"""Multi-token span extraction component for requirement boundaries.

Implements Phase 8b span extraction using token adjacency and POS tags.
Converts Phase 8a requirements to spaCy Span objects with boundary detection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from spacy.language import Language
from spacy.tokens import Doc, Span

from src.preprocessing.span_types import DEFAULT_RULES, BoundaryRules

if TYPE_CHECKING:
    from src.preprocessing.custom_span_categorizer import (
        SpanCategorizerComponent,
    )
    from src.preprocessing.span_types import SpanPattern

# Register custom attribute if not already registered
if not Doc.has_extension("requirement_spans"):
    Doc.set_extension("requirement_spans", default=None)


def _get_span_type_and_conjunct_count(tokens: list[int], doc: Doc) -> tuple[str, int]:
    """Determine span type (atomic/compound) and conjunct count.

    Args:
        tokens: List of token indices in span
        doc: spaCy Doc object

    Returns:
        Tuple of (span_type, conjunct_count)
    """
    conjunct_count = 1
    for idx in tokens:
        token = doc[idx]
        if token.pos_ == "CCONJ" and token.text.lower() in ["and", "or"]:
            conjunct_count += 1

    span_type = "compound" if conjunct_count > 1 else "atomic"
    return span_type, conjunct_count


def _is_hard_boundary(
    token_text: str,
    token_pos: str,
    token_dep: str,
    rules: BoundaryRules = DEFAULT_RULES,
) -> bool:
    """Check if token marks hard span boundary.

    Args:
        token_text: Text of token
        token_pos: POS tag
        token_dep: Dependency tag
        rules: Boundary rules for span extraction

    Returns:
        True if hard boundary
    """
    if token_pos == "PUNCT" and token_text in rules.hard_stops:
        return True
    return False


def _is_soft_boundary(
    token_text: str,
    token_pos: str,
    next_token_text: str | None = None,
    rules: BoundaryRules = DEFAULT_RULES,
) -> bool:
    """Check if token marks soft boundary.

    Args:
        token_text: Text of token
        token_pos: POS tag
        next_token_text: Text of next token (if available)
        rules: Boundary rules for span extraction

    Returns:
        True if soft boundary
    """
    if token_pos == "PUNCT" and token_text in rules.soft_stops:
        # Soft stop unless followed by 'and' or 'or'
        if next_token_text and next_token_text.lower() in ["and", "or"]:
            return False
        return True
    return False


def _extract_span_boundaries(
    doc: Doc,
    char_start: int,
    char_end: int,
) -> tuple[int | None, int | None]:
    """Extract token indices for character span.

    Args:
        doc: spaCy Doc object
        char_start: Character start offset
        char_end: Character end offset

    Returns:
        Tuple of (start_token_idx, end_token_idx) or (None, None) if invalid
    """
    # Validate input offsets
    if char_start < 0 or char_end < 0:
        return (None, None)
    if char_start >= char_end:
        return (None, None)
    if char_start >= len(doc.text):
        return (None, None)

    # Find token indices corresponding to character offsets
    start_token_idx = None
    end_token_idx = None

    for token in doc:
        # Include token if it starts before or at char_start AND ends after char_start (overlaps start)
        if start_token_idx is None and token.idx + len(token.text) > char_start:
            start_token_idx = token.i
        # End token: found token that ends at or after char_end
        if token.idx + len(token.text) >= char_end:
            end_token_idx = token.i
            break

    # Return None if boundaries not found (don't default to edge indices)
    if start_token_idx is None or end_token_idx is None:
        return (None, None)

    return start_token_idx, end_token_idx


def _skip_initial_articles(doc: Doc, start_idx: int) -> int:
    """Skip articles and SPACE tokens at span start.

    Args:
        doc: spaCy Doc object
        start_idx: Initial start index

    Returns:
        First non-article token index
    """
    current = start_idx
    while current < len(doc):
        token = doc[current]
        if token.pos_ in ["DET", "SPACE"]:
            current += 1
        else:
            break
    return current


def _should_stop_at_token(
    token: str,
    token_pos: str,
    next_token_text: str | None,
    rules: BoundaryRules = DEFAULT_RULES,
) -> bool:
    """Check if we should stop expanding span at this token.

    Args:
        token: Token text
        token_pos: POS tag
        next_token_text: Next token text (if available)
        rules: Boundary rules for span extraction

    Returns:
        True if should stop
    """
    if token_pos == "PUNCT":
        if token in rules.hard_stops:
            return True
        if token in rules.soft_stops and not (next_token_text and next_token_text.lower() in ["and", "or"]):
            return True

    if token_pos == "SCONJ" and token.lower() in rules.stop_words:
        return True

    return False


def _expand_span(
    doc: Doc,
    start_idx: int,
    end_idx: int,
    rules: BoundaryRules = DEFAULT_RULES,
) -> tuple[int, int]:
    """Expand span boundaries using POS/DEP tag logic.

    Args:
        doc: spaCy Doc object
        start_idx: Initial start token index
        end_idx: Initial end token index
        rules: Boundary rules for span extraction

    Returns:
        Tuple of (expanded_start, expanded_end)
    """
    # Skip articles at start
    current_start = _skip_initial_articles(doc, start_idx)

    # Scan forward from initial end for boundary conditions
    current_end = end_idx
    while current_end < len(doc):  # Bug #4 fix: removed -1 to include last token
        token = doc[current_end]
        next_token = doc[current_end + 1] if current_end + 1 < len(doc) else None
        next_token_text = next_token.text if next_token else None

        # Check stop conditions
        if _should_stop_at_token(token.text, token.pos_, next_token_text, rules):
            break

        # Conjunction expansion (and/or)
        if token.pos_ == "CCONJ" and token.text.lower() in ["and", "or"]:
            current_end += 1
            continue

        # Hyphenated compounds should not break
        if token.pos_ == "PUNCT" and token.text == "-" and token.dep_ == "compound":
            current_end += 1
            continue

        # Include relative clauses
        if token.pos_ == "SCONJ" and token.text.lower() in ["that", "which"]:
            current_end += 1
            continue

        # Continue accumulating
        current_end += 1

    # Trim trailing hard boundary tokens
    # Ensure current_end is within bounds (may have incremented past end)
    if current_end >= len(doc):
        current_end = len(doc) - 1

    # Trim trailing punctuation, but don't make end < start (Bug #3 fix)
    while current_end > current_start:
        token = doc[current_end]
        if token.pos_ == "PUNCT" and token.text in [".", ";", "!", "?"]:
            current_end -= 1
        else:
            break

    # Guard: ensure valid range (start <= end)
    if current_end < current_start:
        current_end = current_start

    return current_start, current_end


def _create_requirement_span_dict(
    span: Span,
    requirement: dict[str, Any],
    span_type: str,
    conjunct_count: int,
) -> dict[str, Any]:
    """Create enriched requirement span dictionary.

    Args:
        span: spaCy Span object
        requirement: Original requirement dict from Phase 8a
        span_type: "atomic" or "compound"
        conjunct_count: Number of conjuncts

    Returns:
        Enriched requirement dict with span metadata
    """
    return {
        "text": requirement["text"],
        "trigger_word": requirement["trigger_word"],
        "confidence": requirement["confidence"],
        "original_span": requirement["span"],
        "expanded_span": (span.start_char, span.end_char),
        "span_text": span.text,
        "start_token": span.start,
        "end_token": span.end,
        "span_type": span_type,
        "conjunct_count": conjunct_count,
        "token_count": len(span),
    }


def categorize_spans(
    doc: Doc,
    rules: BoundaryRules = DEFAULT_RULES,
) -> Doc:
    """Extract multi-token requirement spans using POS/DEP tag boundaries.

    Phase 8b implementation that processes Doc._.requirements (from Phase 8a)
    and creates spaCy Span objects with accurate boundaries.

    Args:
        doc: spaCy Doc object with Doc._.requirements populated
        rules: Boundary rules for span extraction

    Returns:
        Doc with Doc._.requirement_spans attribute set
    """
    requirement_spans: list[dict[str, Any]] = []

    # Skip if no requirements from Phase 8a
    if not doc._.requirements:
        doc._.requirement_spans = requirement_spans
        return doc

    # Process each requirement from Phase 8a
    for requirement in doc._.requirements:
        char_start, char_end = requirement["span"]

        # Map character offsets to token indices
        start_token_idx, end_token_idx = _extract_span_boundaries(
            doc,
            char_start,
            char_end,
        )

        if start_token_idx is None or end_token_idx is None:
            continue

        # Expand span using boundary rules
        expanded_start, expanded_end = _expand_span(
            doc,
            start_token_idx,
            end_token_idx,
            rules,
        )

        # Create spaCy Span object
        try:
            span = doc[expanded_start : expanded_end + 1]
        except (IndexError, ValueError):
            continue

        # Determine span type and conjunct count
        token_indices = list(range(expanded_start, expanded_end + 1))
        span_type, conjunct_count = _get_span_type_and_conjunct_count(
            token_indices,
            doc,
        )

        # Create enriched requirement dict
        enriched_req = _create_requirement_span_dict(
            span,
            requirement,
            span_type,
            conjunct_count,
        )

        requirement_spans.append(enriched_req)

    doc._.requirement_spans = requirement_spans
    return doc


@Language.component("span_categorizer")
def span_categorizer(doc: Doc) -> Doc:
    """Extract multi-token requirement spans using POS/DEP tag boundaries.

    Phase 8b component that processes Doc._.requirements (from Phase 8a)
    and creates spaCy Span objects with accurate boundaries.

    Args:
        doc: spaCy Doc object with Doc._.requirements populated

    Returns:
        Doc with Doc._.requirement_spans attribute set
    """
    return categorize_spans(doc)


class NLPSpanCategorizer:
    """POS/DEP-based span categorizer with configurable boundary rules."""

    def __init__(self, rules: BoundaryRules = DEFAULT_RULES) -> None:
        self.rules = rules

    def __call__(self, doc: Doc) -> Doc:
        return categorize_spans(doc, self.rules)


def create_span_categorizer(
    strategy: Literal["nlp", "custom"] = "nlp",
    rules: BoundaryRules = DEFAULT_RULES,
    patterns: list[SpanPattern] | None = None,
) -> NLPSpanCategorizer | SpanCategorizerComponent:
    """Create a span categorizer for the given strategy.

    Args:
        strategy: "nlp" for POS/DEP-based, "custom" for regex-based categorizer.
        rules: Boundary rules for span extraction (NLP strategy only).
        patterns: List of SpanPattern objects (required for custom strategy).

    Returns:
        NLPSpanCategorizer for "nlp" strategy, SpanCategorizerComponent for
        "custom" strategy.

    Raises:
        ValueError: Unknown strategy, or "custom" without patterns.
    """
    if strategy == "nlp":
        return NLPSpanCategorizer(rules)
    if strategy == "custom":
        if patterns is None:
            raise ValueError("custom strategy requires patterns")
        from src.preprocessing.custom_span_categorizer import (
            CustomSpanCategorizer,
            SpanCategorizerComponent,
        )

        return SpanCategorizerComponent(CustomSpanCategorizer(patterns))
    raise ValueError(f"Unknown strategy: {strategy}")
