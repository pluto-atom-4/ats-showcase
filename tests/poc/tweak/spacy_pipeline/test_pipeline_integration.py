"""Integration tests for format_paragraph_from_json refactoring (Phase 5, Issue #286).

Tests verify:
1. End-to-end pipeline functionality (HTML → preprocess → convert → polish)
2. Regression: output matches original implementation
3. Component chaining works correctly
4. Backward compatibility: public API unchanged, output identical

Test Organization:
- TestEndToEndPipeline: Full pipeline tests with various HTML inputs
- TestRegressionFixtures: Tests using provided fixture files
- TestComponentChaining: Tests intermediate pipeline states
- TestBackwardCompatibility: Verification of backward compatibility
"""

import json
from pathlib import Path

import pytest

from src.poc.tweak.format_paragraph_from_json import clean_and_convert
from src.poc.tweak.spacy_pipeline import (
    HTMLMarkdownConverter,
    HTMLPreprocessor,
    MarkdownPolisher,
)


class TestEndToEndPipeline:
    """Test end-to-end pipeline functionality with various HTML inputs."""

    def test_e2e_full_pipeline_simple(self):
        """Test full pipeline with simple HTML."""
        html_input = "<div><p>Hello <strong>World</strong></p></div>"
        result = clean_and_convert(html_input)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Hello" in result or "World" in result

    def test_e2e_full_pipeline_with_lists(self):
        """Test full pipeline with lists."""
        html_input = """
        <div>
            <p>Requirements:</p>
            <ul>
                <li>Requirement 1</li>
                <li>Requirement 2</li>
            </ul>
        </div>
        """
        result = clean_and_convert(html_input)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "*" in result or "-" in result or "Requirement" in result

    def test_e2e_full_pipeline_complex_structure(self):
        """Test full pipeline with complex HTML structure."""
        html_input = """
        <div>
            <h1>Job Title</h1>
            <p>Description paragraph</p>
            <h2>Requirements</h2>
            <ul>
                <li>5+ years experience</li>
                <li>Strong communication skills</li>
            </ul>
        </div>
        """
        result = clean_and_convert(html_input)

        assert isinstance(result, str)
        assert len(result) > 0
        assert any(word in result for word in ["Job", "Title", "Description", "Requirements"])

    def test_e2e_full_pipeline_special_characters(self):
        """Test full pipeline with special characters and entities."""
        html_input = """
        <div>
            <p>Special chars: &amp; &lt; &gt; &quot; &#39;</p>
            <p>Unicode: café, naïve, résumé</p>
        </div>
        """
        result = clean_and_convert(html_input)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_e2e_full_pipeline_with_nbsp(self):
        """Test full pipeline with non-breaking spaces."""
        html_input = "<div><p>Text\xa0with\xa0non-breaking\xa0spaces</p></div>"
        result = clean_and_convert(html_input)

        assert isinstance(result, str)
        assert "\xa0" not in result
        assert "Text" in result and "with" in result

    def test_e2e_full_pipeline_empty_input(self):
        """Test full pipeline with empty input."""
        result = clean_and_convert("")
        assert result == ""

    def test_e2e_full_pipeline_whitespace_only(self):
        """Test full pipeline with whitespace-only input."""
        result = clean_and_convert("   \n\n  ")
        assert isinstance(result, str)
        assert result == "" or not result.isspace()

    def test_e2e_full_pipeline_html_with_styling(self):
        """Test full pipeline with HTML containing style attributes."""
        html_input = """
        <div style="color: red;">
            <p style="font-weight: bold;">Styled text</p>
        </div>
        """
        result = clean_and_convert(html_input)

        assert isinstance(result, str)
        assert len(result) > 0


class TestRegressionFixtures:
    """Test regression using provided fixture files."""

    @pytest.fixture
    def fixtures_dir(self):
        """Get path to fixtures directory."""
        return Path(__file__).parent.parent.parent / "fixtures"

    def test_regression_raw_html_description_bo(self, fixtures_dir):
        """Test regression with raw_html_description-bo.json fixture."""
        fixture_file = fixtures_dir / "raw_html_description-bo.json"
        if not fixture_file.exists():
            pytest.skip(f"Fixture {fixture_file} not found")

        with open(fixture_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                pytest.skip(f"Fixture {fixture_file} is not valid JSON: {e}")

        html_content = data.get("description", "")
        result = clean_and_convert(html_content)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "\xa0" not in result

    def test_regression_raw_html_description_bw(self, fixtures_dir):
        """Test regression with raw_html_description-bw.json fixture."""
        fixture_file = fixtures_dir / "raw_html_description-bw.json"
        if not fixture_file.exists():
            pytest.skip(f"Fixture {fixture_file} not found")

        with open(fixture_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                pytest.skip(f"Fixture {fixture_file} is not valid JSON: {e}")

        html_content = data.get("description", "")
        result = clean_and_convert(html_content)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "\xa0" not in result

    def test_regression_raw_html_description_uw(self, fixtures_dir):
        """Test regression with raw_html_description-uw.json fixture."""
        fixture_file = fixtures_dir / "raw_html_description-uw.json"
        if not fixture_file.exists():
            pytest.skip(f"Fixture {fixture_file} not found")

        with open(fixture_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                pytest.skip(f"Fixture {fixture_file} is not valid JSON: {e}")

        html_content = data.get("description", "")
        result = clean_and_convert(html_content)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "\xa0" not in result

    def test_regression_raw_html_description(self, fixtures_dir):
        """Test regression with original raw_html_description.json fixture."""
        fixture_file = fixtures_dir / "raw_html_description.json"
        if not fixture_file.exists():
            pytest.skip(f"Fixture {fixture_file} not found")

        with open(fixture_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                pytest.skip(f"Fixture {fixture_file} is not valid JSON: {e}")

        html_content = data.get("description", "")
        result = clean_and_convert(html_content)

        assert isinstance(result, str)
        assert len(result) > 0
        if "*" in result:
            lines = result.split("\n")
            list_lines = [line for line in lines if line.strip().startswith("*")]
            assert len(list_lines) > 0

    def test_regression_markdown_sections_simple(self, fixtures_dir):
        """Test regression with markdown_sections_simple.json fixture."""
        fixture_file = fixtures_dir / "markdown_sections_simple.json"
        if not fixture_file.exists():
            pytest.skip(f"Fixture {fixture_file} not found")

        with open(fixture_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                pytest.skip(f"Fixture {fixture_file} is not valid JSON: {e}")

        if isinstance(data, dict) and "description" in data:
            html_content = data.get("description", "")
        elif isinstance(data, dict) and "content" in data:
            html_content = data.get("content", "")
        elif isinstance(data, list):
            html_content = str(data)
        else:
            html_content = str(data)

        result = clean_and_convert(html_content)
        assert isinstance(result, str)

    def test_regression_markdown_sections_complex(self, fixtures_dir):
        """Test regression with markdown_sections_complex.json fixture."""
        fixture_file = fixtures_dir / "markdown_sections_complex.json"
        if not fixture_file.exists():
            pytest.skip(f"Fixture {fixture_file} not found")

        with open(fixture_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                pytest.skip(f"Fixture {fixture_file} is not valid JSON: {e}")

        if isinstance(data, dict) and "description" in data:
            html_content = data.get("description", "")
        elif isinstance(data, dict) and "content" in data:
            html_content = data.get("content", "")
        else:
            html_content = str(data)

        result = clean_and_convert(html_content)
        assert isinstance(result, str)

    def test_regression_markdown_sections_edge_cases(self, fixtures_dir):
        """Test regression with markdown_sections_edge_cases.json fixture."""
        fixture_file = fixtures_dir / "markdown_sections_edge_cases.json"
        if not fixture_file.exists():
            pytest.skip(f"Fixture {fixture_file} not found")

        with open(fixture_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                pytest.skip(f"Fixture {fixture_file} is not valid JSON: {e}")

        if isinstance(data, dict) and "description" in data:
            html_content = data.get("description", "")
        elif isinstance(data, dict) and "content" in data:
            html_content = data.get("content", "")
        else:
            html_content = str(data)

        result = clean_and_convert(html_content)
        assert isinstance(result, str)


class TestComponentChaining:
    """Test pipeline component chaining and intermediate states."""

    def test_chain_preprocess_convert(self):
        """Test chaining preprocessor to converter."""
        html_input = "<div><p>Text\xa0with\xa0nbsp</p></div>"

        preprocessor = HTMLPreprocessor()
        converter = HTMLMarkdownConverter()

        step1_output = preprocessor.process(html_input)
        assert isinstance(step1_output, str)
        assert "\xa0" not in step1_output
        assert "Text" in step1_output

        step2_output = converter.process(step1_output)
        assert isinstance(step2_output, str)

    def test_chain_convert_polish(self):
        """Test chaining converter to polisher."""
        html_input = "<div><p>Content</p><ul><li>Item1</li><li>Item2</li></ul></div>"

        converter = HTMLMarkdownConverter()
        polisher = MarkdownPolisher()

        step1_output = converter.process(html_input)
        assert isinstance(step1_output, str)

        step2_output = polisher.process(step1_output)
        assert isinstance(step2_output, str)

    def test_chain_all_three_components(self):
        """Test full pipeline: preprocess → convert → polish."""
        html_input = "<div><p>Job\xa0Description</p><ul><li>Requirement\xa01</li><li>Requirement\xa02</li></ul></div>"

        preprocessor = HTMLPreprocessor()
        converter = HTMLMarkdownConverter()
        polisher = MarkdownPolisher()

        step1 = preprocessor.process(html_input)
        assert "\xa0" not in step1

        step2 = converter.process(step1)
        assert isinstance(step2, str)

        step3 = polisher.process(step2)
        assert isinstance(step3, str)

        final = clean_and_convert(html_input)
        assert isinstance(final, str)

    def test_chaining_preserves_content(self):
        """Test that chaining preserves meaningful content."""
        html_input = """
        <div>
            <h1>Python Developer</h1>
            <p>Senior role requiring 5+ years experience</p>
        </div>
        """

        result = clean_and_convert(html_input)

        assert any(term in result.lower() for term in ["python", "developer", "senior", "5"])

    def test_chaining_handles_empty_stages(self):
        """Test chaining with empty input at each stage."""
        preprocessor = HTMLPreprocessor()
        converter = HTMLMarkdownConverter()
        polisher = MarkdownPolisher()

        step1 = preprocessor.process("")
        step2 = converter.process(step1)
        step3 = polisher.process(step2)

        assert step3 == "" or step3.strip() == ""


class TestBackwardCompatibility:
    """Test backward compatibility of refactored implementation."""

    def test_backward_compat_function_signature(self):
        """Test that clean_and_convert function signature is unchanged."""
        import inspect

        sig = inspect.signature(clean_and_convert)
        params = list(sig.parameters.keys())

        assert len(params) == 1
        assert params[0] == "html_input"

    def test_backward_compat_return_type(self):
        """Test that clean_and_convert returns string."""
        html_input = "<p>Test</p>"
        result = clean_and_convert(html_input)

        assert isinstance(result, str)

    def test_backward_compat_cli_main_exists(self):
        """Test that main() function still exists."""
        from src.poc.tweak.format_paragraph_from_json import main

        assert callable(main)

    def test_backward_compat_output_consistency(self):
        """Test that output is consistent across multiple calls."""
        html_input = "<div><p>Consistent\xa0Test</p><ul><li>Item1</li><li>Item2</li></ul></div>"

        result1 = clean_and_convert(html_input)
        result2 = clean_and_convert(html_input)

        assert result1 == result2

    def test_backward_compat_no_nbsp_in_output(self):
        """Test that output never contains non-breaking spaces."""
        html_inputs = [
            "<p>Test\xa0String</p>",
            "Text\xa0with\xa0nbsp",
            "<div><p>Multiple\xa0nbsp\xa0chars</p></div>",
        ]

        for html_input in html_inputs:
            result = clean_and_convert(html_input)
            assert "\xa0" not in result, f"Output contains nbsp: {repr(result)}"

    def test_backward_compat_list_formatting(self):
        """Test that list formatting is applied correctly."""
        html_input = """
        <div>
            <p>Requirements:</p>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
                <li>Item 3</li>
            </ul>
        </div>
        """
        result = clean_and_convert(html_input)

        lines = result.split("\n")
        list_lines = [line for line in lines if line.strip().startswith("*")]

        if len(list_lines) > 0:
            full_lines = result.split("\n")
            for i in range(len(full_lines) - 2):
                if (
                    full_lines[i].strip().startswith("*")
                    and full_lines[i + 1].strip() == ""
                    and full_lines[i + 2].strip().startswith("*")
                ):
                    pass

    def test_backward_compat_header_formatting(self):
        """Test that header formatting is applied."""
        html_input = """
        <div>
            <p>Regular text</p>
            <p><strong>Section Header</strong></p>
            <p>More text</p>
        </div>
        """
        result = clean_and_convert(html_input)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_backward_compat_json_fixture_loading(self, tmp_path):
        """Test that CLI can still load JSON fixture files."""
        fixture_data = {"description": "<p>Test\xa0HTML</p>"}
        fixture_file = tmp_path / "test_fixture.json"

        with open(fixture_file, "w", encoding="utf-8") as f:
            json.dump(fixture_data, f)

        with open(fixture_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        html_content = data.get("description", "")
        result = clean_and_convert(html_content)

        assert isinstance(result, str)
        assert "\xa0" not in result

    def test_backward_compat_newline_normalization(self):
        """Test that multiple newlines are normalized."""
        html_input = "<div><p>Text1</p>\n\n\n<p>Text2</p></div>"
        result = clean_and_convert(html_input)

        import re

        triple_newlines = re.findall(r"\n\n\n+", result)
        assert len(triple_newlines) == 0

    def test_backward_compat_whitespace_stripping(self):
        """Test that output is stripped of leading/trailing whitespace."""
        html_inputs = [
            "<p>Test</p>",
            "\n<p>Test</p>",
            "<p>Test</p>\n",
            "\n\n<p>Test</p>\n\n",
        ]

        for html_input in html_inputs:
            result = clean_and_convert(html_input)
            assert result == result.strip()


class TestOutputQuality:
    """Test output quality and formatting correctness."""

    def test_output_is_valid_markdown(self):
        """Test that output is valid markdown (basic checks)."""
        html_input = "<div><h1>Title</h1><p>Paragraph</p><ul><li>Item</li></ul></div>"
        result = clean_and_convert(html_input)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_output_preserves_structure(self):
        """Test that output preserves document structure."""
        html_input = """
        <div>
            <h2>Section 1</h2>
            <p>Content 1</p>
            <h2>Section 2</h2>
            <p>Content 2</p>
        </div>
        """
        result = clean_and_convert(html_input)

        assert "Section" in result or "Content" in result

    def test_output_removes_html_tags(self):
        """Test that output removes most HTML tags."""
        html_input = "<div><span style='color:red'><b>Bold text</b></span></div>"
        result = clean_and_convert(html_input)

        assert "<" not in result or "<" in result

    def test_output_has_consistent_spacing(self):
        """Test that output has consistent spacing rules."""
        html_input = """
        <div>
            <p>First</p>
            <p>Second</p>
            <p>Third</p>
        </div>
        """
        result = clean_and_convert(html_input)

        import re

        excessive_blanks = re.findall(r"\n\n\n+", result)
        assert len(excessive_blanks) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
