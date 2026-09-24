"""Tests for span type definitions and boundary rules.

Tests dataclass instantiation, validation, and immutability for span types.
"""

import dataclasses
import re

import pytest

from src.preprocessing.span_types import (
    DEFAULT_RULES,
    BoundaryRules,
    SpanCategory,
    SpanPattern,
)


class TestBoundaryRules:
    """Tests for BoundaryRules dataclass."""

    def test_boundary_rules_default_hard_stops(self) -> None:
        """BoundaryRules default hard_stops matches specification."""
        rules = BoundaryRules()
        expected = frozenset({".", ";", "!", "?", ")"})
        assert rules.hard_stops == expected

    def test_boundary_rules_default_soft_stops(self) -> None:
        """BoundaryRules default soft_stops matches specification."""
        rules = BoundaryRules()
        expected = frozenset({","})
        assert rules.soft_stops == expected

    def test_boundary_rules_default_stop_words(self) -> None:
        """BoundaryRules default stop_words matches specification."""
        rules = BoundaryRules()
        expected = frozenset({"if", "unless", "because"})
        assert rules.stop_words == expected

    def test_default_rules_equals_boundary_rules(self) -> None:
        """DEFAULT_RULES constant equals BoundaryRules()."""
        assert DEFAULT_RULES == BoundaryRules()

    def test_boundary_rules_custom_hard_stops(self) -> None:
        """BoundaryRules custom hard_stops can override default."""
        custom_stops = frozenset({".", "!"})
        rules = BoundaryRules(hard_stops=custom_stops)
        assert rules.hard_stops == custom_stops
        assert rules.soft_stops == frozenset({","})
        assert rules.stop_words == frozenset({"if", "unless", "because"})

    def test_boundary_rules_frozen(self) -> None:
        """BoundaryRules is frozen (immutable)."""
        rules = BoundaryRules()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rules.hard_stops = frozenset({"."})  # type: ignore


class TestSpanPattern:
    """Tests for SpanPattern dataclass."""

    def test_span_pattern_with_valid_regex(self) -> None:
        """SpanPattern with valid regex pattern instantiates successfully."""
        pattern = SpanPattern(
            category="test_category",
            pattern=r"requires? \d+\s+years?",
        )
        assert pattern.category == "test_category"
        assert pattern.pattern == r"requires? \d+\s+years?"
        assert pattern.boundary_rules == DEFAULT_RULES
        assert pattern.metadata == {}

    def test_span_pattern_defaults(self) -> None:
        """SpanPattern with defaults has correct boundary_rules and metadata."""
        pattern = SpanPattern(category="skills")
        assert pattern.category == "skills"
        assert pattern.pattern is None
        assert pattern.boundary_rules is DEFAULT_RULES
        assert pattern.metadata == {}

    def test_span_pattern_custom_metadata(self) -> None:
        """SpanPattern stores custom metadata."""
        meta = {"confidence": 0.95, "source": "test"}
        pattern = SpanPattern(
            category="test",
            metadata=meta,
        )
        assert pattern.metadata == meta

    def test_span_pattern_metadata_isolation(self) -> None:
        """Each SpanPattern instance gets its own metadata dict (no aliasing)."""
        pattern1 = SpanPattern(category="cat1")
        pattern2 = SpanPattern(category="cat2")
        pattern1.metadata["key"] = "value"  # type: ignore[attr-defined]
        assert pattern2.metadata == {}

        # This would fail if metadata dicts were aliased, but frozen so we can't assign
        # Instead verify they are independent instances by creating with explicit dict
        p1 = SpanPattern(category="p1", metadata={})
        p2 = SpanPattern(category="p2", metadata={})
        # They should be separate dict objects (though we can't mutate due to frozen)
        assert p1.metadata is not p2.metadata

    def test_span_pattern_invalid_regex(self) -> None:
        """SpanPattern with invalid regex raises ValueError."""
        with pytest.raises(ValueError, match="Invalid regex for category 'bad'"):
            SpanPattern(
                category="bad",
                pattern="(",
            )

    def test_span_pattern_empty_category(self) -> None:
        """SpanPattern with empty category raises ValueError."""
        with pytest.raises(ValueError, match="category must be a non-empty string"):
            SpanPattern(category="")

    def test_span_pattern_pattern_none_allowed(self) -> None:
        """SpanPattern allows pattern=None."""
        pattern = SpanPattern(
            category="no_pattern",
            pattern=None,
        )
        assert pattern.pattern is None

    def test_span_pattern_frozen(self) -> None:
        """SpanPattern is frozen (immutable)."""
        pattern = SpanPattern(category="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            pattern.category = "new_name"  # type: ignore


class TestSpanCategory:
    """Tests for SpanCategory dataclass."""

    def test_span_category_stores_fields(self) -> None:
        """SpanCategory stores all fields correctly."""
        category = SpanCategory(
            category="skills",
            text="5+ years Python",
            start_char=100,
            end_char=117,
        )
        assert category.category == "skills"
        assert category.text == "5+ years Python"
        assert category.start_char == 100
        assert category.end_char == 117

    def test_span_category_default_metadata(self) -> None:
        """SpanCategory has default empty metadata dict."""
        category = SpanCategory(
            category="test",
            text="text",
            start_char=0,
            end_char=4,
        )
        assert category.metadata == {}

    def test_span_category_custom_metadata(self) -> None:
        """SpanCategory accepts custom metadata."""
        meta = {"confidence": 0.9, "type": "atomic"}
        category = SpanCategory(
            category="skills",
            text="Python",
            start_char=0,
            end_char=6,
            metadata=meta,
        )
        assert category.metadata == meta

    def test_span_category_frozen(self) -> None:
        """SpanCategory is frozen (immutable)."""
        category = SpanCategory(
            category="test",
            text="text",
            start_char=0,
            end_char=4,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            category.category = "new"  # type: ignore
