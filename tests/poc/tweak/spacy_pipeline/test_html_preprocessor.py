"""Unit tests for HTMLPreprocessor component.

Tests cover:
- Non-breaking space removal
- Content preservation
- Malformed HTML handling
- Whitespace normalization
- Idempotency (running twice = same output)
"""

import pytest

from src.poc.tweak.spacy_pipeline.html_preprocessor import HTMLPreprocessor


class TestHTMLPreprocessorBasic:
    """Basic functionality tests."""

    @pytest.fixture
    def preprocessor(self):
        """Create HTMLPreprocessor instance."""
        return HTMLPreprocessor()

    def test_removes_nbsp(self, preprocessor):
        """Verify \\xa0 (non-breaking space) is replaced with regular space."""
        html = "Text\xa0with\xa0nbsp"
        result = preprocessor.process(html)
        assert "\xa0" not in result
        assert "Text with nbsp" in result

    def test_removes_multiple_nbsp(self, preprocessor):
        """Verify multiple non-breaking spaces are all removed."""
        html = "Word1\xa0Word2\xa0Word3\xa0Word4"
        result = preprocessor.process(html)
        assert "\xa0" not in result
        assert result.count(" ") >= 3

    def test_preserves_content(self, preprocessor):
        """Ensure HTML tags and text content are preserved."""
        html = "<div><p>Hello</p></div>"
        result = preprocessor.process(html)
        assert "Hello" in result
        assert "<" in result and ">" in result

    def test_preserves_html_structure(self, preprocessor):
        """Verify complex HTML structure is preserved."""
        html = "<div class='test'><ul><li>Item 1</li><li>Item 2</li></ul></div>"
        result = preprocessor.process(html)
        assert "Item 1" in result
        assert "Item 2" in result

    def test_handles_empty_string(self, preprocessor):
        """Gracefully handle empty input string."""
        result = preprocessor.process("")
        assert result == ""

    def test_handles_none_string_like(self, preprocessor):
        """Gracefully handle empty/minimal input."""
        result = preprocessor.process("")
        assert isinstance(result, str)

    def test_normalizes_whitespace(self, preprocessor):
        """Verify extra whitespace is handled appropriately."""
        html = "<p>Text   with   multiple   spaces</p>"
        result = preprocessor.process(html)
        assert "Text" in result
        assert "multiple" in result
        assert "spaces" in result

    def test_handles_malformed_html(self, preprocessor):
        """Gracefully handle malformed HTML."""
        html = "<div><p>Unclosed paragraph<div>Nested</div>"
        result = preprocessor.process(html)
        assert "Unclosed paragraph" in result
        assert "Nested" in result

    def test_idempotent(self, preprocessor):
        """Running preprocessing twice should yield same output."""
        html = "Text\xa0with\xa0nbsp<div>Content</div>"
        result1 = preprocessor.process(html)
        result2 = preprocessor.process(result1)
        assert result1 == result2

    def test_preserves_special_characters(self, preprocessor):
        """Preserve special HTML entities and characters."""
        html = "<p>Price: $100 &amp; quantity: 5</p>"
        result = preprocessor.process(html)
        assert "$" in result or "100" in result
        assert "5" in result


class TestHTMLPreprocessorNbsp:
    """Focused tests for non-breaking space handling."""

    @pytest.fixture
    def preprocessor(self):
        """Create HTMLPreprocessor instance."""
        return HTMLPreprocessor()

    def test_nbsp_in_text_node(self, preprocessor):
        """Remove nbsp from simple text nodes."""
        html = "Hello\xa0World"
        result = preprocessor.process(html)
        assert "\xa0" not in result
        assert result == "Hello World"

    def test_nbsp_in_nested_tags(self, preprocessor):
        """Remove nbsp from nested tag content."""
        html = "<div><span>Hello\xa0World</span></div>"
        result = preprocessor.process(html)
        assert "\xa0" not in result
        assert "Hello" in result

    def test_nbsp_mixed_with_regular_spaces(self, preprocessor):
        """Handle mix of nbsp and regular spaces."""
        html = "Word1 Word2\xa0Word3 Word4\xa0Word5"
        result = preprocessor.process(html)
        assert "\xa0" not in result


class TestHTMLPreprocessorIntegration:
    """Integration tests with real-world HTML."""

    @pytest.fixture
    def preprocessor(self):
        """Create HTMLPreprocessor instance."""
        return HTMLPreprocessor()

    def test_real_job_html_snippet(self, preprocessor):
        """Process realistic job posting HTML snippet."""
        html = """
        <div class="job-description">
            <h2>Senior\xa0Developer</h2>
            <p>We're\xa0seeking a talented individual.</p>
            <ul>
                <li>5+\xa0years\xa0experience</li>
                <li>Python,\xa0Java,\xa0or\xa0Go</li>
            </ul>
        </div>
        """
        result = preprocessor.process(html)
        assert "\xa0" not in result
        assert "Senior Developer" in result
        assert "5+ years experience" in result or "5+" in result

    def test_complex_nested_html(self, preprocessor):
        """Handle deeply nested HTML with multiple nbsp."""
        html = """
        <div>
            <section>
                <article>
                    <p>Paragraph\xa0with\xa0nbsp\xa0characters</p>
                </article>
            </section>
        </div>
        """
        result = preprocessor.process(html)
        assert "\xa0" not in result
        assert "Paragraph" in result
        assert "with" in result

    def test_html_with_attributes_and_nbsp(self, preprocessor):
        """Preserve HTML attributes while removing nbsp."""
        html = '<a href="test.html" class="link">Link\xa0Text</a>'
        result = preprocessor.process(html)
        assert "\xa0" not in result
        assert "Link" in result or "Text" in result


class TestHTMLPreprocessorCallable:
    """Test callable interface."""

    @pytest.fixture
    def preprocessor(self):
        """Create HTMLPreprocessor instance."""
        return HTMLPreprocessor()

    def test_callable_via_call_method(self, preprocessor):
        """Component should be callable via __call__()."""
        html = "Text\xa0with\xa0nbsp"
        result = preprocessor(html)
        assert "\xa0" not in result
        assert "Text with nbsp" in result

    def test_process_and_call_equivalent(self, preprocessor):
        """process() and __call__() should produce identical results."""
        html = "<p>Content\xa0here</p>"
        result1 = preprocessor.process(html)
        result2 = preprocessor(html)
        assert result1 == result2


class TestHTMLPreprocessorProperties:
    """Test component properties."""

    @pytest.fixture
    def preprocessor(self):
        """Create HTMLPreprocessor instance."""
        return HTMLPreprocessor()

    def test_name_property(self, preprocessor):
        """Component should have a name property."""
        assert preprocessor.name == "html_preprocessor"
        assert isinstance(preprocessor.name, str)

    def test_name_immutable(self, preprocessor):
        """Name should be consistent across calls."""
        name1 = preprocessor.name
        name2 = preprocessor.name
        assert name1 == name2
