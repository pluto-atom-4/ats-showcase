"""Tests for HTML scoping via CSS selector (Issue #363, #367).

Tests validate:
1. Single match returns fragment (inner HTML)
2. Zero matches returns fragment=None, match_count=0
3. Multiple matches uses first, warns with count
4. Invalid CSS selector raises ValueError
5. Empty fragment returns fragment=None
6. Nested/complex markup handled correctly
7. Strategy parameter: first, all, longest (Issue #367)
8. Regression test: first match empty, second non-empty (Issue #367)
"""

import pytest

from src.poc.tweak.html_scope import ScopeResult, scope_to_selector


class TestScopeToSelector:
    """Tests for scope_to_selector() function."""

    def test_single_match_returns_fragment(self):
        """Test that a single match returns the fragment correctly."""
        # Arrange
        html = '<div class="description"><p>Job requirements here</p></div>'
        selector = ".description"

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert isinstance(result, ScopeResult)
        assert result.match_count == 1
        assert result.fragment is not None
        assert "Job requirements here" in result.fragment

    def test_zero_matches_returns_none_fragment(self):
        """Test that no matches returns fragment=None and match_count=0."""
        # Arrange
        html = '<div class="other"><p>Content</p></div>'
        selector = ".description"

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert result.match_count == 0
        assert result.fragment is None

    def test_multiple_matches_uses_first(self):
        """Test that multiple matches returns first element and warns with count."""
        # Arrange
        html = """
        <div class="job"><p>First job</p></div>
        <div class="job"><p>Second job</p></div>
        <div class="job"><p>Third job</p></div>
        """
        selector = ".job"

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert result.match_count == 3
        assert result.fragment is not None
        assert "First job" in result.fragment
        assert "Second job" not in result.fragment

    def test_invalid_css_selector_raises_valueerror(self):
        """Test that invalid CSS selector raises ValueError."""
        # Arrange
        html = "<div>Content</div>"
        selector = ">>invalid"  # Invalid CSS syntax

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            scope_to_selector(html, selector)

        assert "Invalid CSS selector" in str(exc_info.value)

    def test_empty_fragment_returns_none(self):
        """Test that empty matched element returns fragment=None."""
        # Arrange
        html = '<div class="description"></div>'
        selector = ".description"

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert result.match_count == 1
        assert result.fragment is None

    def test_fragment_with_whitespace_only_returns_none(self):
        """Test that whitespace-only fragment becomes None after strip()."""
        # Arrange
        html = '<div class="description">   \n  \t  </div>'
        selector = ".description"

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert result.match_count == 1
        assert result.fragment is None

    def test_nested_markup_preserved(self):
        """Test that nested HTML structure is preserved in fragment."""
        # Arrange
        html = """
        <div class="job-details">
            <h2>Senior Developer</h2>
            <ul>
                <li>5 years experience</li>
                <li>Python, JavaScript</li>
            </ul>
        </div>
        """
        selector = ".job-details"

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert result.match_count == 1
        assert result.fragment is not None
        assert "<h2>Senior Developer</h2>" in result.fragment
        assert "<li>5 years experience</li>" in result.fragment

    def test_lwc_like_complex_structure(self):
        """Test handling of complex/LWC-like markup (Issue #363 test case)."""
        # Arrange: Simulating a real job details page structure
        html = """
        <html>
            <body>
                <div class="common-jobdetails-description">
                    <section class="description-body">
                        <p>This is the job description</p>
                        <p>Requirements and qualifications</p>
                    </section>
                </div>
                <div class="other-content">Navigation</div>
            </body>
        </html>
        """
        selector = ".common-jobdetails-description"

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert result.match_count == 1
        assert result.fragment is not None
        assert "job description" in result.fragment
        assert "Navigation" not in result.fragment  # Outside selector

    def test_empty_html_string_returns_zero_match(self):
        """Test that empty HTML string returns zero matches."""
        # Arrange
        html = ""
        selector = ".description"

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert result.match_count == 0
        assert result.fragment is None

    def test_empty_selector_returns_zero_match(self):
        """Test that empty selector string returns zero matches."""
        # Arrange
        html = "<div>Content</div>"
        selector = ""

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert result.match_count == 0
        assert result.fragment is None

    def test_complex_css_selector_works(self):
        """Test that complex CSS selectors work correctly."""
        # Arrange
        html = """
        <div class="container">
            <div class="job-wrapper active">
                <div class="job-content">Matching content</div>
            </div>
            <div class="job-wrapper">
                <div class="job-content">Other content</div>
            </div>
        </div>
        """
        selector = "div.job-wrapper.active div.job-content"

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert result.match_count == 1
        assert "Matching content" in result.fragment

    def test_attribute_selector_works(self):
        """Test that attribute selectors work correctly."""
        # Arrange
        html = """
        <div data-job-id="123">Description for job 123</div>
        <div data-job-id="456">Description for job 456</div>
        """
        selector = '[data-job-id="123"]'

        # Act
        result = scope_to_selector(html, selector)

        # Assert
        assert result.match_count == 1
        assert "job 123" in result.fragment
        assert "job 456" not in result.fragment


class TestScopeToSelectorStrategies:
    """Tests for multi-match strategies (Issue #367)."""

    def test_strategy_all_joins_in_document_order_with_exact_separator(self):
        """Test that strategy='all' joins all non-empty matches with exact separator."""
        # Arrange
        html = """
        <div class="desc"><p>First part</p></div>
        <div class="desc"><p>Second part</p></div>
        <div class="desc"><p>Third part</p></div>
        """
        selector = ".desc"

        # Act
        result = scope_to_selector(html, selector, strategy="all")

        # Assert
        assert result.match_count == 3
        assert result.fragment is not None
        # Verify exact separator "\n\n---\n\n" is used
        expected = "<p>First part</p>\n\n---\n\n<p>Second part</p>\n\n---\n\n<p>Third part</p>"
        assert expected == result.fragment

    def test_strategy_longest_picks_longest_match_when_first_is_short(self):
        """Test that strategy='longest' picks longest match (WorkSource case: first short, second long)."""
        # Arrange: Simulating WorkSource: first match ~short benefits, second ~long description
        html = """
        <div class="desc">Benefits Offered: Health insurance, 401k</div>
        <div class="desc">This is the full job description with comprehensive requirements
        including technical skills, soft skills, education, years of experience, and detailed
        responsibilities. It contains much more content than the benefits snippet.</div>
        """
        selector = ".desc"

        # Act
        result = scope_to_selector(html, selector, strategy="longest")

        # Assert
        assert result.match_count == 2
        assert result.fragment is not None
        # Should pick the longer second match
        assert "comprehensive requirements" in result.fragment
        assert "Benefits Offered" not in result.fragment

    def test_strategy_longest_picks_first_match_on_tie(self):
        """Test that strategy='longest' picks first match when all are equal length."""
        # Arrange
        html = """
        <div class="desc"><p>Match A ABC</p></div>
        <div class="desc"><p>Match B XYZ</p></div>
        """
        selector = ".desc"

        # Act
        result = scope_to_selector(html, selector, strategy="longest")

        # Assert
        assert result.match_count == 2
        assert result.fragment is not None
        # Both fragments are equal length after stripping, so first one wins
        assert "Match A ABC" in result.fragment
        assert "Match B XYZ" not in result.fragment

    def test_single_match_identical_behavior_all_three_strategies(self):
        """Test that single match produces identical result for all 3 strategies."""
        # Arrange
        html = '<div class="desc"><p>Single match content</p></div>'
        selector = ".desc"

        # Act
        result_first = scope_to_selector(html, selector, strategy="first")
        result_all = scope_to_selector(html, selector, strategy="all")
        result_longest = scope_to_selector(html, selector, strategy="longest")

        # Assert
        assert result_first.fragment == result_all.fragment == result_longest.fragment
        assert result_first.match_count == result_all.match_count == result_longest.match_count == 1
        assert "Single match content" in result_first.fragment

    def test_zero_match_unchanged_across_strategies(self):
        """Test that zero matches returns None fragment regardless of strategy."""
        # Arrange
        html = '<div class="other"><p>No match</p></div>'
        selector = ".desc"

        # Act
        result_first = scope_to_selector(html, selector, strategy="first")
        result_all = scope_to_selector(html, selector, strategy="all")
        result_longest = scope_to_selector(html, selector, strategy="longest")

        # Assert
        assert result_first.match_count == 0
        assert result_all.match_count == 0
        assert result_longest.match_count == 0
        assert result_first.fragment is None
        assert result_all.fragment is None
        assert result_longest.fragment is None

    def test_strategy_first_preserves_old_behavior_first_match_empty(self):
        """Test regression: first match empty, second non-empty, strategy='first' -> fragment None, match_count 2.

        This verifies that strategy='first' preserves original behavior (uses matches[0])
        and does NOT skip to first non-empty match.
        """
        # Arrange
        html = """
        <div class="desc"></div>
        <div class="desc"><p>Second non-empty</p></div>
        """
        selector = ".desc"

        # Act
        result = scope_to_selector(html, selector, strategy="first")

        # Assert
        assert result.match_count == 2
        assert result.fragment is None  # First match is empty, so fragment is None
        # Verify we're NOT returning the second non-empty match
        # (if we were, fragment would contain "Second non-empty")

    def test_all_empty_matches_returns_none_fragment_keeps_match_count(self):
        """Test that all-empty matches return fragment=None but preserve match_count."""
        # Arrange
        html = """
        <div class="desc"></div>
        <div class="desc">   </div>
        <div class="desc"></div>
        """
        selector = ".desc"

        # Act
        result = scope_to_selector(html, selector, strategy="all")

        # Assert
        assert result.match_count == 3
        assert result.fragment is None

    def test_unknown_strategy_behaves_as_first(self):
        """Test that unknown strategy value is treated as 'first'."""
        # Arrange
        html = """
        <div class="desc"><p>First content</p></div>
        <div class="desc"><p>Second content</p></div>
        """
        selector = ".desc"

        # Act
        result_unknown = scope_to_selector(html, selector, strategy="unknown_strategy")
        result_first = scope_to_selector(html, selector, strategy="first")

        # Assert
        assert result_unknown.fragment == result_first.fragment
        assert result_unknown.match_count == result_first.match_count
        assert "First content" in result_unknown.fragment
        assert "Second content" not in result_unknown.fragment

    def test_strategy_all_with_mixed_empty_and_nonempty_matches(self):
        """Test that strategy='all' joins only non-empty matches, skipping empty ones."""
        # Arrange
        html = """
        <div class="desc"><p>First non-empty</p></div>
        <div class="desc"></div>
        <div class="desc"><p>Third non-empty</p></div>
        """
        selector = ".desc"

        # Act
        result = scope_to_selector(html, selector, strategy="all")

        # Assert
        assert result.match_count == 3
        assert result.fragment is not None
        # Only non-empty fragments joined
        assert result.fragment == "<p>First non-empty</p>\n\n---\n\n<p>Third non-empty</p>"
        assert "<p>Second non-empty</p>" not in result.fragment
