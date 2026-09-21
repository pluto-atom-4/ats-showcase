"""Tests for HTML scoping via CSS selector (Issue #363).

Tests validate:
1. Single match returns fragment (inner HTML)
2. Zero matches returns fragment=None, match_count=0
3. Multiple matches uses first, warns with count
4. Invalid CSS selector raises ValueError
5. Empty fragment returns fragment=None
6. Nested/complex markup handled correctly
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
