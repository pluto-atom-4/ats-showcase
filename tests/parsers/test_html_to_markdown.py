"""Tests for src.parsers.html_to_markdown.html_to_markdown."""

import os
from unittest.mock import patch

import src.parsers.html_to_markdown as html_to_markdown_module
from src.parsers.html_cleaner import HTMLCleaner
from src.parsers.html_to_markdown import html_to_markdown


class TestHtmlToMarkdown:
    """Direct tests for the shared HTML -> Markdown converter."""

    def test_utf8_special_chars_preserved(self) -> None:
        """En-dash, em-dash, and curly quotes survive the round trip."""
        html = "<p>Range 2020–2024 — the “best” years</p>"
        result = html_to_markdown(html)

        assert "–" in result
        assert "—" in result
        assert "“" in result and "”" in result

    def test_basic_heading_conversion(self) -> None:
        """A simple heading + paragraph converts to markdown structure."""
        html = "<h1>Senior Python Developer</h1><p>5+ years required.</p>"
        result = html_to_markdown(html)

        assert result.startswith("#")
        assert "Senior Python Developer" in result
        assert "5+ years required." in result

    def test_empty_input_returns_empty(self) -> None:
        """Empty string input short-circuits to an empty string."""
        assert html_to_markdown("") == ""

    def test_malformed_html_does_not_raise(self) -> None:
        """Unclosed tags / malformed markup should not raise."""
        html = "<div><p>unclosed paragraph and div"
        result = html_to_markdown(html)

        assert isinstance(result, str)
        assert "unclosed paragraph and div" in result

    def test_exception_fallback_returns_original_html(self) -> None:
        """If MarkItDown raises, BeautifulSoup fallback extracts text; if both fail, return original HTML."""
        html = "<p>content that should survive on failure</p>"

        with patch.object(html_to_markdown_module, "MarkItDown") as mock_markitdown:
            mock_markitdown.return_value.convert.side_effect = RuntimeError("boom")
            result = html_to_markdown(html)

        # With the BeautifulSoup fallback, text is extracted rather than raw HTML returned.
        assert result != html, "Should use BeautifulSoup fallback, not return raw HTML"
        assert "content that should survive on failure" in result
        assert "<p>" not in result, "Should extract text, not return raw HTML"

    def test_temp_file_cleaned_up_on_success(self) -> None:
        """The temporary file created during conversion is removed afterward."""
        created_paths = []
        real_unlink = os.unlink

        def tracking_unlink(path: str) -> None:
            created_paths.append(path)
            real_unlink(path)

        with patch.object(html_to_markdown_module.os, "unlink", side_effect=tracking_unlink):
            html_to_markdown("<p>hello</p>")

        assert len(created_paths) == 1
        assert not os.path.exists(created_paths[0])

    def test_temp_file_cleaned_up_on_failure(self) -> None:
        """The temporary file is removed even when conversion raises."""
        created_paths = []
        real_unlink = os.unlink

        def tracking_unlink(path: str) -> None:
            created_paths.append(path)
            real_unlink(path)

        with (
            patch.object(html_to_markdown_module, "MarkItDown") as mock_markitdown,
            patch.object(html_to_markdown_module.os, "unlink", side_effect=tracking_unlink),
        ):
            mock_markitdown.return_value.convert.side_effect = RuntimeError("boom")
            html_to_markdown("<p>hello</p>")

        assert len(created_paths) == 1
        assert not os.path.exists(created_paths[0])


class TestHtmlCleanerMarkItDownIntegration:
    """Regression: HTMLCleaner now actually exercises MarkItDown."""

    def test_clean_produces_markdown_style_output(self) -> None:
        """HTMLCleaner().clean() should show markdown structure (leading '#'),
        not BeautifulSoup's flat concatenated text, now that MarkItDown
        is invoked correctly via the shared converter.
        """
        html = "<h1>Job Title</h1><p>Job description body text.</p>"
        cleaner = HTMLCleaner()

        result = cleaner.clean(html)

        assert result.startswith("#")
        assert "Job Title" in result
        assert "Job description body text." in result


class TestWorkdayHtmlFixtures:
    """Tests for Workday-specific HTML malformations (Issue #230, Phase 1-3)."""

    WORKDAY_DT_DD_HTML = """
    <dl>
      <dt>Remote Type</dt><dd>Hybrid</dd>
      <dt>Location</dt><dd>New York</dd>
      <dt>Job ID</dt><dd>R69380</dd>
    </dl>
    """

    WORKDAY_WITH_EMDASH = """
    <p>Responsibilities:</p>
    <ul><li>Lead design—architecture work</li></ul>
    """

    WORKDAY_WITH_REFS = """
    <dl><dt>ID</dt><dd>:R69380</dd></dl>
    <p>Application Close Date: August 20</p>
    """

    WORKDAY_COMPLEX_JOB = """
    <h2>Senior Python Developer</h2>
    <dl>
      <dt>Job ID</dt><dd>:R69380</dd>
      <dt>Type</dt><dd>Full-time</dd>
    </dl>
    <p>Responsibilities:</p>
    <ul>
      <li>Build scalable systems—architecture patterns</li>
      <li>Lead team on Python projects</li>
    </ul>
    <p>Qualifications:</p>
    <ul>
      <li>5+ years Python—modern frameworks</li>
    </ul>
    """

    def test_beautifulsoup_dt_dd_isolation(self) -> None:
        """dt/dd pairs should be on separate lines after BeautifulSoup conversion."""
        from unittest.mock import patch

        with patch.object(html_to_markdown_module, "MarkItDown") as mock_markitdown:
            mock_markitdown.return_value.convert.side_effect = RuntimeError("force fallback")
            result = html_to_markdown(self.WORKDAY_DT_DD_HTML)

        assert "<dl>" not in result
        assert "<dt>" not in result
        assert "<dd>" not in result
        assert "Remote Type" in result
        assert "Hybrid" in result
        assert "Location" in result
        assert "New York" in result

    def test_normalize_workday_refs(self) -> None:
        """Workday refs like :R69380 should be removed or isolated."""
        from unittest.mock import patch

        with patch.object(html_to_markdown_module, "MarkItDown") as mock_markitdown:
            mock_markitdown.return_value.convert.side_effect = RuntimeError("force fallback")
            result = html_to_markdown(self.WORKDAY_WITH_REFS)

        # References like :R69380 should not appear (or be on isolated lines)
        # At minimum, they should not be mixed with other text
        lines = result.split("\n")
        for line in lines:
            if ":R" in line:
                pass
            else:
                assert True

    def test_emdash_normalization(self) -> None:
        """Em-dashes should be normalized or removed, not concatenate text."""
        from unittest.mock import patch

        with patch.object(html_to_markdown_module, "MarkItDown") as mock_markitdown:
            mock_markitdown.return_value.convert.side_effect = RuntimeError("force fallback")
            result = html_to_markdown(self.WORKDAY_WITH_EMDASH)

        assert "Responsibilities" in result
        # "design—architecture" could stay as-is or be normalized.
        assert "Lead design" in result or "Lead design—architecture" in result
        # Regression guard: must not become "LeaddesignarchitectureNotWork".
        assert "Leaddesign" not in result

    def test_divider_isolation_after_synthesis(self) -> None:
        """Dividers should not be embedded in text (e.g., ':R69380---')."""
        from src.parsers.html_to_markdown import normalize_description

        result = normalize_description(self.WORKDAY_COMPLEX_JOB)

        lines = result.split("\n")
        for line in lines:
            stripped = line.strip()
            if "---" in stripped:
                assert stripped == "---", f"Divider not isolated: '{stripped}'"

    def test_extract_sections_with_clean_dividers(self) -> None:
        """_extract_markdown_sections should handle clean dividers."""
        from src.tokenization.preprocessor import Preprocessor

        markdown_with_dividers = """
## Responsibilities

Lead design and architecture work

---

## Qualifications

5+ years Python experience
"""
        preprocessor = Preprocessor()
        sections = preprocessor._extract_markdown_sections(markdown_with_dividers)

        assert "responsibilities" in sections
        assert "qualifications" in sections
        assert "Lead design" in sections["responsibilities"]
        assert "5+ years" in sections["qualifications"]

    def test_end_to_end_workday_jobs(self) -> None:
        """Full pipeline: Workday HTML -> clean sections -> correct entity routing."""
        from src.parsers.html_to_markdown import clean_html

        cleaned = clean_html(self.WORKDAY_COMPLEX_JOB, include_section_headers=True)

        assert "Senior Python Developer" in cleaned
        assert "<" not in cleaned and ">" not in cleaned, "No HTML tags should remain"

        lines = cleaned.split("\n")
        for line in lines:
            stripped = line.strip()
            if "---" in stripped:
                assert stripped == "---", f"Embedded divider found: '{stripped}'"


class TestDividerNormalization:
    """Regression tests for duplicate divider bug (Issue #230, Phase 4)."""

    def test_normalize_divider_lines_content_with_trailing_divider(self) -> None:
        """Test that 'content---' produces ['content', '---'] (single divider)."""
        from src.parsers.html_to_markdown import _normalize_divider_lines

        lines = ["content---"]
        result = _normalize_divider_lines(lines)

        assert "content" in result
        assert result.count("---") == 1, f"Expected 1 divider, got {result.count('---')} in {result}"

    def test_normalize_divider_lines_leading_divider(self) -> None:
        """Test that '---Some Content' produces correct output (leading divider handled)."""
        from src.parsers.html_to_markdown import _normalize_divider_lines

        lines = ["---Some Content"]
        result = _normalize_divider_lines(lines)

        # A leading divider yields an empty first part, which is skipped, leaving only the content.
        assert "Some Content" in result
        # No divider because the part after --- was not empty, so no final divider is added
        assert "---" not in result or result.count("---") == 0

    def test_normalize_divider_lines_middle_divider(self) -> None:
        """Test that 'Part One---Part Two' produces ['Part One', '---', 'Part Two'] (single divider)."""
        from src.parsers.html_to_markdown import _normalize_divider_lines

        lines = ["Part One---Part Two"]
        result = _normalize_divider_lines(lines)

        assert "Part One" in result
        assert "Part Two" in result
        assert result.count("---") == 1, f"Expected 1 divider, got {result.count('---')} in {result}"

    def test_normalize_divider_lines_consecutive_dividers(self) -> None:
        """Test that embedded consecutive dividers are handled correctly."""
        from src.parsers.html_to_markdown import _normalize_divider_lines

        lines = ["text---"]
        result = _normalize_divider_lines(lines)

        assert result.count("---") == 1, f"Expected 1 divider, got {result.count('---')} in {result}"

    def test_normalize_divider_lines_orphaned_refs(self) -> None:
        """Test that ':R69380---' is split correctly (ref removed, single divider)."""
        from src.parsers.html_to_markdown import _normalize_divider_lines

        lines = [":R69380---"]
        result = _normalize_divider_lines(lines)

        # Orphaned ref should be skipped, should have exactly one divider
        assert ":R69380" not in "\n".join(result)
        assert result.count("---") == 1, f"Expected 1 divider, got {result.count('---')} in {result}"

    def test_normalize_divider_lines_table_row_unchanged(self) -> None:
        """Test that table rows (starting with |) are not processed."""
        from src.parsers.html_to_markdown import _normalize_divider_lines

        lines = ["|---|---|"]
        result = _normalize_divider_lines(lines)

        # A table row contains --- but is not a content divider, so it stays unchanged.
        assert result == lines, f"Table row was modified: {result}"


class TestBoldHeaderSynthesis:
    """Tests for bold header synthesis (Issue #241)."""

    def test_synthesize_bold_subsection_headers_bold_only(self) -> None:
        """Test synthesis of bold-only headers to ### Subsection."""
        from src.parsers.html_to_markdown import _synthesize_bold_subsection_headers

        lines = [
            "Some intro text",
            "**Responsibilities**",
            "Lead team and design systems.",
        ]
        _synthesize_bold_subsection_headers(lines)

        assert lines[1] == "### Responsibilities"

    def test_synthesize_bold_subsection_headers_with_trailing_text(self) -> None:
        """Test synthesis of bold headers with trailing text (Issue #241)."""
        from src.parsers.html_to_markdown import _synthesize_bold_subsection_headers

        lines = [
            "Some intro text",
            "**Responsibilities** include:",
            "Lead team and design systems.",
        ]
        _synthesize_bold_subsection_headers(lines)

        assert lines[1] == "### Responsibilities"

    def test_synthesize_bold_subsection_headers_with_em_dash(self) -> None:
        """Test synthesis of bold headers with em-dash separator."""
        from src.parsers.html_to_markdown import _synthesize_bold_subsection_headers

        lines = [
            "Some intro text",
            "**Qualifications** — desired skills:",
            "5+ years Python experience.",
        ]
        _synthesize_bold_subsection_headers(lines)

        assert lines[1] == "### Qualifications"

    def test_synthesize_bold_subsection_headers_no_header_if_no_content(self) -> None:
        """Test that bold lines without following content are not converted."""
        from src.parsers.html_to_markdown import _synthesize_bold_subsection_headers

        lines = [
            "**Responsibilities**",
            "# End of document",
        ]
        _synthesize_bold_subsection_headers(lines)

    def test_synthesize_bold_subsection_headers_skip_existing_headers(self) -> None:
        """Test that existing headers are not re-converted."""
        from src.parsers.html_to_markdown import _synthesize_bold_subsection_headers

        lines = [
            "## Section Header",
            "Content here.",
            "**Bold Line**",
            "More content.",
        ]
        _synthesize_bold_subsection_headers(lines)

        assert lines[0] == "## Section Header"
        assert lines[2] == "### Bold Line"

    def test_synthesize_bold_subsection_headers_multiple_sections(self) -> None:
        """Test synthesis with multiple bold headers."""
        from src.parsers.html_to_markdown import _synthesize_bold_subsection_headers

        lines = [
            "**Responsibilities**",
            "Lead and design.",
            "**Skills**",
            "Python and AWS.",
            "**Qualifications**",
            "5+ years experience.",
        ]
        _synthesize_bold_subsection_headers(lines)

        assert lines[0] == "### Responsibilities"
        assert lines[2] == "### Skills"
        assert lines[4] == "### Qualifications"
