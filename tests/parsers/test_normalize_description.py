"""Tests for HTML-to-Markdown description normalization.

Moved off `Crawler` and into `src.parsers.html_to_markdown` (Issue #228):
`normalize_description` / `add_markdown_section_headers` /
`_insert_section_dividers` are now plain module-level functions, callable
directly with no `Crawler()` instantiation, no browser/async fixtures.

Originally rewritten for Issue #195 / Phase 8: `normalize_description` is a
thin wrapper around the shared `html_to_markdown()` utility, since the
crawler extracts `inner_html()` (not `text_content()`) for job descriptions.
These tests assert markdown structure and absence of residual HTML tags,
rather than the old regex label-spacing behavior.
"""

import re

from src.parsers.html_to_markdown import (
    _insert_section_dividers,
    add_markdown_section_headers,
    normalize_description,
)


class TestDescriptionNormalization:
    """Test HTML -> Markdown conversion of job descriptions."""

    def test_normalize_heading_and_paragraph(self):
        """Basic heading + paragraph HTML converts to markdown structure."""
        html = "<h2>About the Role</h2><p>We build great software.</p>"
        result = normalize_description(html)

        assert result.startswith("#")
        assert "About the Role" in result
        assert "We build great software." in result

    def test_normalize_list_items(self):
        """Unordered list HTML converts to markdown list syntax."""
        html = "<ul><li>Python</li><li>SQL</li><li>Docker</li></ul>"
        result = normalize_description(html)

        assert "Python" in result
        assert "SQL" in result
        assert "Docker" in result

    def test_normalize_no_residual_html_tags(self):
        """Converted output should not contain raw HTML tags."""
        html = (
            "<div><h2>Requirements</h2>"
            "<ul><li>5+ years experience</li><li>Strong communication</li></ul>"
            "<p>Remote type: <strong>Hybrid</strong></p></div>"
        )
        result = normalize_description(html)

        assert not re.search(r"<[a-zA-Z/][^>]*>", result)
        assert "Requirements" in result
        assert "5+ years experience" in result
        assert "Hybrid" in result

    def test_normalize_workday_style_metadata(self):
        """Structured metadata table converts cleanly without concatenation."""
        html = (
            "<table>"
            "<tr><td>remote type</td><td>Hybrid</td></tr>"
            "<tr><td>locations</td><td>Seattle, WA</td></tr>"
            "<tr><td>time type</td><td>Full time</td></tr>"
            "</table>"
        )
        result = normalize_description(html)

        assert "Hybrid" in result
        assert "Seattle" in result
        assert "Full time" in result

    def test_normalize_empty_description(self):
        """Handle empty string description."""
        result = normalize_description("")
        assert result == ""

    def test_normalize_none_description(self):
        """Handle None description by returning empty string."""
        # Intentional: test passes None at runtime to verify the guard.
        result = normalize_description(None)  # type: ignore[arg-type]
        assert result == ""

    def test_normalize_plain_text_passthrough(self):
        """Plain text with no HTML tags passes through largely unchanged."""
        text = "Just a plain sentence with no markup at all."
        result = normalize_description(text)
        assert "Just a plain sentence with no markup at all." in result

    def test_normalize_malformed_html_does_not_raise(self):
        """Malformed/unclosed HTML should not raise."""
        html = "<div><p>Unclosed paragraph and div"
        result = normalize_description(html)
        assert isinstance(result, str)
        assert "Unclosed paragraph and div" in result


class TestMarkdownSectionHeaderSynthesis:
    """Test synthesis of ## / ### section headers from keyword/bold/colon lines.

    Issue #196: when the source HTML lacks real <h2>/<h3> tags but uses
    bold-label or plain-colon conventions to signal section boundaries,
    `normalize_description` synthesizes Markdown headers so downstream
    section-aware preprocessing can recognize them.
    """

    def test_bold_qualifications_line_becomes_h2(self):
        """A bold-only 'Qualifications' line (no real <h2>) becomes '## Qualifications'."""
        html = "<p><strong>Qualifications</strong></p><ul><li>5+ years experience</li><li>Bachelor's degree</li></ul>"
        result = normalize_description(html)
        assert "## Qualifications" in result

    def test_plain_requirements_colon_paragraph_becomes_h2(self):
        """A plain 'Requirements:' paragraph (no real heading) becomes '## Requirements'."""
        html = "<p>Requirements:</p><ul><li>Python</li><li>SQL</li></ul>"
        result = normalize_description(html)
        assert "## Requirements" in result

    def test_bold_subsection_followed_by_list_becomes_h3(self):
        """A bold standalone line followed by a bullet list becomes a '### Subsection'."""
        html = "<p><strong>Team Culture</strong></p><ul><li>We value transparency</li><li>We move fast</li></ul>"
        result = normalize_description(html)
        assert "### Team Culture" in result

    def test_trailing_colon_line_becomes_h3(self):
        """A generic trailing-colon line (e.g. 'Pay Range:') produces a '###' header.

        Note: the source orphan commit had three redundant if/elif/else
        branches here (pay-range/salary, hiring-practice/EOE, generic
        fallback) that all executed the identical transform. This is
        collapsed into a single branch, so we only assert that *a* '###'
        header is produced, not on the removed dead-branch behavior.
        """
        html = "<p>Pay Range:</p><p>$100,000 - $150,000</p>"
        result = normalize_description(html)
        assert re.search(r"^### .+$", result, re.MULTILINE)

    def test_workday_style_metadata_table_unaffected(self):
        """Table-based metadata (no keyword/colon/bold lines) does not acquire headers.

        Regression guard for `test_normalize_workday_style_metadata`: header
        synthesis must not spuriously introduce '##'/'###' markers into
        structured table content.
        """
        html = (
            "<table>"
            "<tr><td>remote type</td><td>Hybrid</td></tr>"
            "<tr><td>locations</td><td>Seattle, WA</td></tr>"
            "<tr><td>time type</td><td>Full time</td></tr>"
            "</table>"
        )
        result = normalize_description(html)
        assert "Hybrid" in result
        assert "Seattle" in result
        assert "Full time" in result
        assert "##" not in result


class TestMarkdownSectionDividers:
    """Test '---' divider insertion before synthesized section headers.

    Issue #211 / Phase 10: synthesized headers (from
    `add_markdown_section_headers`) are preceded by a blank line + '---'
    divider so the preprocessor's divider-aware section splitting
    (`_extract_markdown_sections`) can determine section boundaries even
    when content doesn't end with a blank line before the next header.

    Issue #224: the divider moved from immediately *after* the header to
    immediately *before* it (preceded by a blank line), except when the
    header is the very first line of the document or directly follows
    another header/divider.
    """

    def test_synthesized_h2_header_is_first_line_gets_no_leading_divider(self):
        """A synthesized '## Qualifications' header that is the very first
        line of the document gets no leading blank line / '---' (nothing
        precedes it to separate)."""
        html = "<p><strong>Qualifications</strong></p><ul><li>5+ years experience</li><li>Bachelor's degree</li></ul>"
        result = normalize_description(html)
        lines = result.split("\n")
        assert lines[0] == "## Qualifications"
        assert "---" not in lines

    def test_synthesized_h3_header_is_first_line_gets_no_leading_divider(self):
        """A synthesized '### Team Culture' header that is the very first
        line of the document also gets no leading divider."""
        html = "<p><strong>Team Culture</strong></p><ul><li>We value transparency</li><li>We move fast</li></ul>"
        result = normalize_description(html)
        lines = result.split("\n")
        assert lines[0] == "### Team Culture"
        assert "---" not in lines

    def test_synthesized_header_preceded_by_content_gets_leading_divider(self):
        """A synthesized header that follows ordinary content gets a blank
        line + '---' immediately before it."""
        markdown = "Some intro content\n**Requirements**\n5+ years experience"
        result = add_markdown_section_headers(markdown)
        lines = result.split("\n")
        header_idx = next(i for i, line in enumerate(lines) if line == "## Requirements")
        assert lines[header_idx - 1] == "---"
        assert lines[header_idx - 2] == ""
        assert lines[header_idx - 3] == "Some intro content"

    def test_no_synthesized_headers_no_spurious_dividers(self):
        """Input with no synthesized headers gains no spurious dividers."""
        html = (
            "<table>"
            "<tr><td>remote type</td><td>Hybrid</td></tr>"
            "<tr><td>locations</td><td>Seattle, WA</td></tr>"
            "<tr><td>time type</td><td>Full time</td></tr>"
            "</table>"
        )
        result = normalize_description(html)
        # A standalone '---' divider line is what the header-insertion pass
        # would add; markdown table separator rows (e.g. '| --- | --- |')
        # are unrelated and expected here, so check for exact '---' lines.
        assert "---" not in result.split("\n")

    def test_no_doubled_dividers_on_consecutive_headers(self):
        """Two headers landing on consecutive lines do not each get a divider."""
        markdown = "## Requirements\n### Subsection\nSome content"
        result = add_markdown_section_headers(markdown)
        lines = result.split("\n")
        # "## Requirements" is the first line of the document (no leading
        # divider), and "### Subsection" immediately follows another
        # header, so it is also skipped -- no divider anywhere.
        assert lines.count("---") == 0
        req_idx = lines.index("## Requirements")
        sub_idx = lines.index("### Subsection")
        assert sub_idx == req_idx + 1


class TestInsertSectionDividersUnit:
    """Direct unit tests for `_insert_section_dividers` (Issue #224).

    Exercises the list-in/list-out contract directly, independent of the
    html-normalization pipeline, covering the dedup and leading-blank-line
    edge cases the divider-before-header placement introduces.
    """

    def test_single_header_preceded_by_content_gets_blank_and_divider(self):
        """A header preceded by ordinary content gets '' + '---' inserted
        directly before it, with the header itself left untouched."""
        lines = ["Some content", "## Header", "More content"]
        result = _insert_section_dividers(lines)
        assert result == ["Some content", "", "---", "## Header", "More content"]

    def test_consecutive_headers_no_doubled_divider(self):
        """Back-to-back headers do not each get a divider between them."""
        lines = ["## Requirements", "### Subsection", "content"]
        result = _insert_section_dividers(lines)
        assert result == ["## Requirements", "### Subsection", "content"]
        assert result.count("---") == 0

    def test_header_as_very_first_line_gets_no_leading_blank_or_divider(self):
        """A header at index 0 has nothing preceding it, so no blank line
        or divider is spuriously prepended to the document."""
        lines = ["## Header", "content"]
        result = _insert_section_dividers(lines)
        assert result == ["## Header", "content"]
        assert result[0] == "## Header"

    def test_header_preceded_by_ordinary_content_general_case(self):
        """General case: non-header, non-divider preceding line triggers
        insertion of a blank line followed by '---' immediately before the
        header, leaving unrelated lines untouched."""
        lines = ["Intro line one", "Intro line two", "## Skills", "Python"]
        result = _insert_section_dividers(lines)
        assert result == [
            "Intro line one",
            "Intro line two",
            "",
            "---",
            "## Skills",
            "Python",
        ]
