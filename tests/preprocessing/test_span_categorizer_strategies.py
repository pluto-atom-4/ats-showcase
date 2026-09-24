"""Tests for span categorizer strategies and factory function.

MODEL-FREE tests (no spacy.load). Tests NLPSpanCategorizer, boundary rules,
and create_span_categorizer factory.
"""

import pytest
import spacy

from src.preprocessing import custom_span_categorizer
from src.preprocessing.span_categorizer import (
    DEFAULT_RULES,
    NLPSpanCategorizer,
    _is_hard_boundary,
    _is_soft_boundary,
    _should_stop_at_token,
    create_span_categorizer,
)
from src.preprocessing.span_types import BoundaryRules, SpanPattern


class TestNLPSpanCategorizer:
    """Tests for NLPSpanCategorizer class."""

    def test_nlp_span_categorizer_default_rules(self) -> None:
        """NLPSpanCategorizer uses DEFAULT_RULES by default."""
        categorizer = NLPSpanCategorizer()
        assert categorizer.rules == DEFAULT_RULES

    def test_nlp_span_categorizer_custom_rules(self) -> None:
        """NLPSpanCategorizer accepts custom BoundaryRules."""
        custom_rules = BoundaryRules(
            hard_stops=frozenset({"|"}),
            soft_stops=frozenset(),
            stop_words=frozenset(),
        )
        categorizer = NLPSpanCategorizer(custom_rules)
        assert categorizer.rules == custom_rules

    def test_nlp_span_categorizer_callable(self) -> None:
        """NLPSpanCategorizer is callable and returns Doc."""
        categorizer = NLPSpanCategorizer()
        doc = spacy.blank("en")("test text")
        # Register extension if not already present
        if not doc.has_extension("requirements"):
            doc.set_extension("requirements", default=None)
        doc._.requirements = []
        result = categorizer(doc)
        assert result is doc
        assert result._.requirement_spans == []


class TestShouldStopAtToken:
    """Tests for _should_stop_at_token function."""

    def test_should_stop_at_token_hard_stop_default(self) -> None:
        """_should_stop_at_token returns True for hard stop with default rules."""
        result = _should_stop_at_token(".", "PUNCT", None)
        assert result is True

    def test_should_stop_at_token_soft_stop_default_no_next(self) -> None:
        """_should_stop_at_token returns True for soft stop without next token."""
        result = _should_stop_at_token(",", "PUNCT", None)
        assert result is True

    def test_should_stop_at_token_soft_stop_with_conjunction(self) -> None:
        """_should_stop_at_token returns False for soft stop when next is 'and'."""
        result = _should_stop_at_token(",", "PUNCT", "and")
        assert result is False

    def test_should_stop_at_token_sconj_if(self) -> None:
        """_should_stop_at_token returns True for SCONJ 'if'."""
        result = _should_stop_at_token("if", "SCONJ", None)
        assert result is True

    def test_should_stop_at_token_sconj_because(self) -> None:
        """_should_stop_at_token returns True for SCONJ 'Because' (case-insensitive)."""
        result = _should_stop_at_token("Because", "SCONJ", None)
        assert result is True

    def test_should_stop_at_token_custom_rules_pipe(self) -> None:
        """_should_stop_at_token with custom rules: '|' is hard stop."""
        custom_rules = BoundaryRules(
            hard_stops=frozenset({"|"}),
            soft_stops=frozenset(),
            stop_words=frozenset(),
        )
        result = _should_stop_at_token("|", "PUNCT", None, custom_rules)
        assert result is True

    def test_should_stop_at_token_custom_rules_period(self) -> None:
        """_should_stop_at_token with custom rules: '.' is not a stop."""
        custom_rules = BoundaryRules(
            hard_stops=frozenset({"|"}),
            soft_stops=frozenset(),
            stop_words=frozenset(),
        )
        result = _should_stop_at_token(".", "PUNCT", None, custom_rules)
        assert result is False


class TestIsHardBoundary:
    """Tests for _is_hard_boundary function."""

    def test_is_hard_boundary_default_period(self) -> None:
        """_is_hard_boundary returns True for '.' with default rules."""
        result = _is_hard_boundary(".", "PUNCT", "sentence")
        assert result is True

    def test_is_hard_boundary_default_question(self) -> None:
        """_is_hard_boundary returns True for '?' with default rules."""
        result = _is_hard_boundary("?", "PUNCT", "sentence")
        assert result is True

    def test_is_hard_boundary_custom_pipe(self) -> None:
        """_is_hard_boundary returns True for '|' with custom rules."""
        custom_rules = BoundaryRules(
            hard_stops=frozenset({"|"}),
            soft_stops=frozenset(),
            stop_words=frozenset(),
        )
        result = _is_hard_boundary("|", "PUNCT", "word", custom_rules)
        assert result is True

    def test_is_hard_boundary_custom_period_not_stop(self) -> None:
        """_is_hard_boundary returns False for '.' with custom rules (not in set)."""
        custom_rules = BoundaryRules(
            hard_stops=frozenset({"|"}),
            soft_stops=frozenset(),
            stop_words=frozenset(),
        )
        result = _is_hard_boundary(".", "PUNCT", "word", custom_rules)
        assert result is False

    def test_is_hard_boundary_non_punct(self) -> None:
        """_is_hard_boundary returns False for non-PUNCT tokens."""
        result = _is_hard_boundary(".", "NOUN", "word")
        assert result is False


class TestIsSoftBoundary:
    """Tests for _is_soft_boundary function."""

    def test_is_soft_boundary_default_comma(self) -> None:
        """_is_soft_boundary returns True for ',' with default rules (no next)."""
        result = _is_soft_boundary(",", "PUNCT", None)
        assert result is True

    def test_is_soft_boundary_comma_with_and(self) -> None:
        """_is_soft_boundary returns False for ',' when followed by 'and'."""
        result = _is_soft_boundary(",", "PUNCT", "and")
        assert result is False

    def test_is_soft_boundary_comma_with_or(self) -> None:
        """_is_soft_boundary returns False for ',' when followed by 'or'."""
        result = _is_soft_boundary(",", "PUNCT", "or")
        assert result is False

    def test_is_soft_boundary_comma_with_other(self) -> None:
        """_is_soft_boundary returns True for ',' when followed by non-conjunction."""
        result = _is_soft_boundary(",", "PUNCT", "but")
        assert result is True

    def test_is_soft_boundary_custom_rules(self) -> None:
        """_is_soft_boundary with custom rules: no soft stops."""
        custom_rules = BoundaryRules(
            hard_stops=frozenset({"|"}),
            soft_stops=frozenset(),
            stop_words=frozenset(),
        )
        result = _is_soft_boundary(",", "PUNCT", None, custom_rules)
        assert result is False

    def test_is_soft_boundary_non_punct(self) -> None:
        """_is_soft_boundary returns False for non-PUNCT tokens."""
        result = _is_soft_boundary(",", "NOUN", None)
        assert result is False


class TestCreateSpanCategorizer:
    """Tests for create_span_categorizer factory function."""

    def test_create_span_categorizer_nlp_default(self) -> None:
        """create_span_categorizer('nlp') returns NLPSpanCategorizer."""
        categorizer = create_span_categorizer("nlp")
        assert isinstance(categorizer, NLPSpanCategorizer)
        assert categorizer.rules == DEFAULT_RULES

    def test_create_span_categorizer_nlp_explicit(self) -> None:
        """create_span_categorizer with default strategy returns NLPSpanCategorizer."""
        categorizer = create_span_categorizer()
        assert isinstance(categorizer, NLPSpanCategorizer)
        assert categorizer.rules == DEFAULT_RULES

    def test_create_span_categorizer_nlp_custom_rules(self) -> None:
        """create_span_categorizer('nlp') with custom rules uses those rules."""
        custom_rules = BoundaryRules(
            hard_stops=frozenset({"|"}),
            soft_stops=frozenset(),
            stop_words=frozenset(),
        )
        categorizer = create_span_categorizer("nlp", custom_rules)
        assert categorizer.rules == custom_rules

    def test_create_span_categorizer_custom_requires_patterns(self) -> None:
        """create_span_categorizer('custom') without patterns raises ValueError."""
        with pytest.raises(ValueError, match="requires patterns"):
            create_span_categorizer("custom")

    def test_create_span_categorizer_custom_with_patterns(self) -> None:
        """create_span_categorizer('custom') with patterns returns categorizer."""
        patterns = [SpanPattern(category="years", pattern=r"\d+ years")]
        categorizer = create_span_categorizer("custom", patterns=patterns)
        doc = spacy.blank("en")("needs 5 years")
        result = categorizer(doc)
        assert hasattr(result._, "custom_spans")
        assert len(result._.custom_spans) == 1
        assert result._.custom_spans[0]["text"] == "5 years"

    def test_create_span_categorizer_bogus_raises(self) -> None:
        """create_span_categorizer with unknown strategy raises ValueError."""
        with pytest.raises(ValueError, match="Unknown strategy: bogus"):
            create_span_categorizer("bogus")  # type: ignore[arg-type]


class TestNLPSpanCategorizerOnBlankDoc:
    """Tests for NLPSpanCategorizer called on blank spaCy Doc."""

    def test_categorizer_blank_doc_empty_requirements(self) -> None:
        """Categorizer on blank doc with empty requirements returns empty spans."""
        doc = spacy.blank("en")("test text")
        # Register extension if not already present
        if not doc.has_extension("requirements"):
            doc.set_extension("requirements", default=None)
        doc._.requirements = []
        categorizer = NLPSpanCategorizer()
        result = categorizer(doc)
        assert result._.requirement_spans == []

    def test_categorizer_blank_doc_returns_same_doc(self) -> None:
        """Categorizer returns the same Doc object (in-place modification)."""
        doc = spacy.blank("en")("test text")
        if not doc.has_extension("requirements"):
            doc.set_extension("requirements", default=None)
        doc._.requirements = []
        categorizer = NLPSpanCategorizer()
        result = categorizer(doc)
        assert result is doc
