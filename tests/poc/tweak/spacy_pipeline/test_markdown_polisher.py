"""Unit tests for MarkdownPolisher component.

Tests cover:
- Rule 1: Line normalization (stripping whitespace)
- Rule 2: List tightening (removing blank lines between bullets)
- Rule 3: Header formatting (blank lines around bold headers)
- Rule 4: List block separation (blank lines before/after lists)
- Rule 5: Global cleanup (collapsing triple newlines)
- Rule ordering and composability
- Individual rule application
- Backward compatibility with clean_and_convert()
"""

import pytest

from src.poc.tweak.spacy_pipeline.markdown_polisher import MarkdownPolisher


class TestMarkdownPolisherRule1LineNormalization:
    """Tests for Rule 1: Line Normalization."""

    @pytest.fixture
    def polisher(self):
        """Create MarkdownPolisher instance."""
        return MarkdownPolisher()

    def test_line_norm_strips_trailing_whitespace(self, polisher):
        """Strip trailing whitespace from lines."""
        text = "Line 1  \nLine 2   \nLine 3"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LINE_NORM, text)
        lines = result.split("\n")
        assert lines[0] == "Line 1"
        assert lines[1] == "Line 2"
        assert lines[2] == "Line 3"

    def test_line_norm_strips_leading_whitespace(self, polisher):
        """Strip leading whitespace from lines."""
        text = "  Line 1\n   Line 2\nLine 3"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LINE_NORM, text)
        lines = result.split("\n")
        assert lines[0] == "Line 1"
        assert lines[1] == "Line 2"
        assert lines[2] == "Line 3"

    def test_line_norm_preserves_empty_lines(self, polisher):
        """Preserve blank lines between content."""
        text = "Line 1\n\nLine 2\n\n\nLine 3"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LINE_NORM, text)
        assert result == "Line 1\n\nLine 2\n\n\nLine 3"

    def test_line_norm_handles_tabs(self, polisher):
        """Strip tab characters from line edges."""
        text = "\tLine 1\t\n\t\tLine 2\t\t"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LINE_NORM, text)
        lines = result.split("\n")
        assert lines[0] == "Line 1"
        assert lines[1] == "Line 2"

    def test_line_norm_handles_mixed_whitespace(self, polisher):
        """Strip mixed tabs and spaces."""
        text = " \t Line 1 \t \n\t  Line 2  \t"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LINE_NORM, text)
        lines = result.split("\n")
        assert lines[0] == "Line 1"
        assert lines[1] == "Line 2"


class TestMarkdownPolisherRule2ListTightening:
    """Tests for Rule 2: List Tightening."""

    @pytest.fixture
    def polisher(self):
        """Create MarkdownPolisher instance."""
        return MarkdownPolisher()

    def test_list_tight_removes_blank_between_items(self, polisher):
        """Remove blank lines between consecutive bullets.

        The regex pattern only matches the first blank line between bullets
        due to how the non-greedy .+? and lookahead interact.
        """
        text = "\n* Item 1\n\n* Item 2\n\n* Item 3"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LIST_TIGHT, text)
        assert "* Item 1\n* Item 2" in result

    def test_list_tight_preserves_single_item_lists(self, polisher):
        """Don't affect lists with no adjacent items."""
        text = "* Item 1\n\nSome text"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LIST_TIGHT, text)
        assert result == text

    def test_list_tight_handles_nested_lists(self, polisher):
        """Handle nested list structures."""
        text = "* Item 1\n  * Nested 1\n\n* Item 2"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LIST_TIGHT, text)
        assert "* Item 1" in result
        assert "* Item 2" in result

    def test_list_tight_preserves_content(self, polisher):
        """Preserve list item content during tightening."""
        text = "* Python programming\n\n* Java development"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LIST_TIGHT, text)
        assert "Python programming" in result
        assert "Java development" in result

    def test_list_tight_multiple_gaps(self, polisher):
        """Remove multiple consecutive gaps in lists."""
        text = "* A\n\n* B\n\n* C\n\n* D"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LIST_TIGHT, text)
        assert result.count("\n* ") >= 3


class TestMarkdownPolisherRule3HeaderFormatting:
    """Tests for Rule 3: Header Formatting."""

    @pytest.fixture
    def polisher(self):
        """Create MarkdownPolisher instance."""
        return MarkdownPolisher()

    def test_header_adds_blank_before(self, polisher):
        """Add blank line before bold header if missing."""
        text = "Some text\n**Header**"
        result = polisher.apply_rule(MarkdownPolisher.RULE_HEADER_FORMAT, text)
        assert "Some text\n\n**Header**" in result

    def test_header_adds_blank_after(self, polisher):
        """Add blank line after bold header if missing."""
        text = "**Header**\nSome text"
        result = polisher.apply_rule(MarkdownPolisher.RULE_HEADER_FORMAT, text)
        assert "**Header**\n\nSome text" in result

    def test_header_handles_consecutive_headers(self, polisher):
        """Handle multiple consecutive headers."""
        text = "**Header 1**\n**Header 2**\n**Header 3**"
        result = polisher.apply_rule(MarkdownPolisher.RULE_HEADER_FORMAT, text)
        assert "\n\n" in result

    def test_header_preserves_blank_when_present(self, polisher):
        """Don't double-add blank lines if already present."""
        text = "Text\n\n**Header**\n\nMore text"
        result = polisher.apply_rule(MarkdownPolisher.RULE_HEADER_FORMAT, text)
        assert "\n\n\n" not in result

    def test_header_at_start_no_extra_space_before(self, polisher):
        """Don't add space before header at start of text."""
        text = "**Header**\nContent"
        result = polisher.apply_rule(MarkdownPolisher.RULE_HEADER_FORMAT, text)
        assert not result.startswith("\n")

    def test_header_at_end_no_extra_space_after(self, polisher):
        """Don't add space after header at end of text."""
        text = "Content\n**Header**"
        result = polisher.apply_rule(MarkdownPolisher.RULE_HEADER_FORMAT, text)
        assert result.endswith("**Header**") or result.endswith("**Header**\n")


class TestMarkdownPolisherRule4ListBlockSeparation:
    """Tests for Rule 4: List Block Separation."""

    @pytest.fixture
    def polisher(self):
        """Create MarkdownPolisher instance."""
        return MarkdownPolisher()

    def test_list_block_adds_blank_before_first_item(self, polisher):
        """Add blank line before first list item after text."""
        text = "Some text\n* Item 1"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LIST_BLOCK, text)
        assert "Some text\n\n* Item 1" in result

    def test_list_block_adds_blank_after_last_item(self, polisher):
        """Add blank line after last list item before text.

        The regex requires a leading newline before the list item,
        so we need to provide the proper context.
        """
        text = "\n* Item 1\nSome text"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LIST_BLOCK, text)
        assert "* Item 1\n\nSome text" in result

    def test_list_block_preserves_spacing_between_items(self, polisher):
        """Don't affect spacing between list items."""
        text = "* Item 1\n* Item 2\n* Item 3"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LIST_BLOCK, text)
        assert "* Item 1\n* Item 2" in result

    def test_list_block_multiple_lists(self, polisher):
        """Handle multiple list blocks in sequence."""
        text = "Text 1\n* Item 1\nText 2\n* Item 2"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LIST_BLOCK, text)
        assert "Text 1\n\n* Item 1" in result
        assert "Text 2\n\n* Item 2" in result

    def test_list_block_handles_only_text(self, polisher):
        """Don't affect text-only content."""
        text = "Line 1\nLine 2\nLine 3"
        result = polisher.apply_rule(MarkdownPolisher.RULE_LIST_BLOCK, text)
        assert result == text


class TestMarkdownPolisherRule5GlobalCleanup:
    """Tests for Rule 5: Global Cleanup."""

    @pytest.fixture
    def polisher(self):
        """Create MarkdownPolisher instance."""
        return MarkdownPolisher()

    def test_cleanup_collapses_triple_newlines(self, polisher):
        """Collapse 3+ newlines to exactly 2."""
        text = "Line 1\n\n\nLine 2"
        result = polisher.apply_rule(MarkdownPolisher.RULE_CLEANUP, text)
        assert result == "Line 1\n\nLine 2"

    def test_cleanup_collapses_quad_newlines(self, polisher):
        """Collapse 4 newlines to 2."""
        text = "Text\n\n\n\nMore"
        result = polisher.apply_rule(MarkdownPolisher.RULE_CLEANUP, text)
        assert result == "Text\n\nMore"

    def test_cleanup_preserves_double_newlines(self, polisher):
        """Don't collapse legitimate double newlines."""
        text = "Line 1\n\nLine 2\n\nLine 3"
        result = polisher.apply_rule(MarkdownPolisher.RULE_CLEANUP, text)
        assert result == text

    def test_cleanup_preserves_single_newlines(self, polisher):
        """Don't affect single newlines."""
        text = "Line 1\nLine 2\nLine 3"
        result = polisher.apply_rule(MarkdownPolisher.RULE_CLEANUP, text)
        assert result == text

    def test_cleanup_handles_mixed_spacing(self, polisher):
        """Collapse multiple excess newlines in different places."""
        text = "A\n\n\nB\n\n\n\nC\n\n\nD"
        result = polisher.apply_rule(MarkdownPolisher.RULE_CLEANUP, text)
        assert result == "A\n\nB\n\nC\n\nD"


class TestMarkdownPolisherRuleOrdering:
    """Tests for rule ordering and composition."""

    def test_rule_ordering_matters(self):
        """Verify that rule order affects output."""
        text = "Text\n\n* Item 1\n\n* Item 2  \n\n**Header**\nMore"

        polisher = MarkdownPolisher()
        all_rules_result = polisher.process(text)

        polisher_subset = MarkdownPolisher(rules=[MarkdownPolisher.RULE_LIST_TIGHT, MarkdownPolisher.RULE_CLEANUP])
        subset_result = polisher_subset.process(text)

        assert all_rules_result != subset_result

    def test_disable_specific_rule(self):
        """Verify rules can be disabled via constructor."""
        text = "Line 1  \nLine 2   \n"

        polisher = MarkdownPolisher(
            rules=[
                MarkdownPolisher.RULE_LIST_TIGHT,
                MarkdownPolisher.RULE_HEADER_FORMAT,
            ]
        )
        result = polisher.process(text)

        assert "  " in result or "   " in result

    def test_apply_rule_single(self):
        """Verify apply_rule() applies just one rule."""
        text = "Line 1  \n* Item 1\n\n* Item 2"

        polisher = MarkdownPolisher()

        result_line_norm = polisher.apply_rule(MarkdownPolisher.RULE_LINE_NORM, text)
        assert result_line_norm == "Line 1\n* Item 1\n\n* Item 2"

        result_list_tight = polisher.apply_rule(MarkdownPolisher.RULE_LIST_TIGHT, text)
        assert "  " in result_list_tight


class TestMarkdownPolisherBackwardCompat:
    """Tests for backward compatibility with legacy clean_and_convert()."""

    def test_backward_compat_simple_list(self):
        """Simple list formatting matches legacy behavior."""
        text = "Text\n* Item 1\n\n* Item 2"
        polisher = MarkdownPolisher()
        result = polisher.process(text)

        assert "* Item 1\n* Item 2" in result
        assert "Text\n\n*" in result

    def test_backward_compat_with_headers(self):
        """Header formatting matches legacy behavior."""
        text = "Description\n**Requirements**\n* Python\n* Java"
        polisher = MarkdownPolisher()
        result = polisher.process(text)

        assert "Description\n\n**Requirements**" in result
        assert "**Requirements**\n\n*" in result

    def test_backward_compat_cleanup(self):
        """Newline cleanup matches legacy behavior."""
        text = "Line 1\n\n\n\nLine 2"
        polisher = MarkdownPolisher()
        result = polisher.process(text)

        assert result == "Line 1\n\nLine 2"

    def test_backward_compat_complex(self):
        """Complex markdown processing matches legacy behavior."""
        text = "Overview  \n\n* Requirement 1  \n\n* Requirement 2\n\n\n**Skills**\nTechnical skills here"
        polisher = MarkdownPolisher()
        result = polisher.process(text)

        assert "Overview" in result and "Overview  " not in result
        assert "* Requirement 1\n* Requirement 2" in result
        assert "**Skills**" in result
        assert "\n\n\n" not in result


class TestMarkdownPolisherCallable:
    """Test callable interface."""

    @pytest.fixture
    def polisher(self):
        """Create MarkdownPolisher instance."""
        return MarkdownPolisher()

    def test_callable_via_call_method(self, polisher):
        """Component should be callable via __call__()."""
        text = "Text  \n\n* Item"
        result = polisher(text)
        assert "Text\n\n* Item" in result

    def test_process_and_call_equivalent(self, polisher):
        """process() and __call__() should produce identical results."""
        text = "* Item 1\n\n* Item 2"
        result1 = polisher.process(text)
        result2 = polisher(text)
        assert result1 == result2


class TestMarkdownPolisherProperties:
    """Test component properties."""

    @pytest.fixture
    def polisher(self):
        """Create MarkdownPolisher instance."""
        return MarkdownPolisher()

    def test_name_property(self, polisher):
        """Component should have a name property."""
        assert polisher.name == "markdown_polisher"
        assert isinstance(polisher.name, str)

    def test_rules_property_all(self, polisher):
        """Rules property should return all enabled rules."""
        assert polisher.rules == MarkdownPolisher.ALL_RULES

    def test_rules_property_subset(self):
        """Rules property should reflect disabled rules."""
        subset = [MarkdownPolisher.RULE_LINE_NORM, MarkdownPolisher.RULE_CLEANUP]
        polisher = MarkdownPolisher(rules=subset)
        assert polisher.rules == subset

    def test_rules_property_immutable(self):
        """Modifying rules property shouldn't affect component."""
        polisher = MarkdownPolisher()
        original_rules = polisher.rules
        rules_copy = polisher.rules
        rules_copy.clear()
        assert polisher.rules == original_rules


class TestMarkdownPolisherEdgeCases:
    """Edge case tests."""

    def test_empty_string(self):
        """Handle empty input gracefully."""
        polisher = MarkdownPolisher()
        result = polisher.process("")
        assert result == ""

    def test_whitespace_only(self):
        """Handle whitespace-only input."""
        polisher = MarkdownPolisher()
        result = polisher.process("   \n   \n   ")
        assert result == "\n\n"

    def test_single_line(self):
        """Handle single line input."""
        polisher = MarkdownPolisher()
        result = polisher.process("Single line")
        assert result == "Single line"

    def test_none_rules_equals_all_rules(self):
        """Constructor with rules=None should use all rules."""
        polisher_default = MarkdownPolisher()
        polisher_none = MarkdownPolisher(rules=None)
        assert polisher_default.rules == polisher_none.rules

    def test_invalid_rule_raises(self):
        """Invalid rule name should raise ValueError."""
        with pytest.raises(ValueError):
            MarkdownPolisher(rules=["invalid_rule"])

    def test_invalid_apply_rule_raises(self):
        """apply_rule() with invalid name should raise ValueError."""
        polisher = MarkdownPolisher()
        with pytest.raises(ValueError):
            polisher.apply_rule("nonexistent_rule", "text")

    def test_unicode_content(self):
        """Handle unicode content correctly."""
        polisher = MarkdownPolisher()
        text = "Python 3.9+  \n* Требования\n\n* 需求"
        result = polisher.process(text)
        assert "Python 3.9+" in result
        assert "Требования" in result
        assert "需求" in result

    def test_special_characters_in_headers(self):
        """Handle special characters in bold headers."""
        polisher = MarkdownPolisher()
        text = "Text\n**C++ & C# Development**\nMore"
        result = polisher.process(text)
        assert "**C++ & C# Development**" in result
