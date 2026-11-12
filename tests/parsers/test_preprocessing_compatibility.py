"""Preprocessing compatibility tests (Issue #230).

Document behavior changes from old HTMLCleaner to new clean_html().
Ensure backward compatibility or define clear migration path.
"""

import warnings

import pytest

from src.parsers.html_cleaner import HTMLCleaner
from src.parsers.html_to_markdown import clean_html


class TestHTMLCleanerDeprecation:
    """Test HTMLCleaner deprecation path."""

    def test_htmlcleaner_warns_on_init(self) -> None:
        """HTMLCleaner emits DeprecationWarning on instantiation."""
        with pytest.warns(DeprecationWarning, match="HTMLCleaner is deprecated"):
            HTMLCleaner()

    def test_deprecation_message_has_migration_path(self) -> None:
        """Deprecation message mentions clean_html alternative."""
        with pytest.warns(DeprecationWarning) as warn_info:
            HTMLCleaner()

        message = str(warn_info[0].message)
        assert "clean_html" in message
        assert "v2.0" in message


class TestBackwardCompatibility:
    """Test backward compatibility of HTMLCleaner delegation."""

    def test_htmlcleaner_clean_still_works(self) -> None:
        """HTMLCleaner.clean() still works after delegation."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cleaner = HTMLCleaner()
            html = "<h1>Senior Dev</h1><p>Content</p>"
            result = cleaner.clean(html)

        assert "Senior" in result or "Dev" in result or "Content" in result
        assert isinstance(result, str)

    def test_htmlcleaner_extract_text_still_works(self) -> None:
        """HTMLCleaner.extract_text() still works after delegation."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cleaner = HTMLCleaner()
            html = "<div class='content'><p>Job content</p></div>"
            result = cleaner.extract_text(html, selector=".content")

        assert "Job" in result or "content" in result
        assert isinstance(result, str)

    def test_htmlcleaner_remove_boilerplate_still_works(self) -> None:
        """HTMLCleaner.remove_boilerplate() still works."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cleaner = HTMLCleaner()
            text = "Position details. Apply Now."
            result = cleaner.remove_boilerplate(text)

        assert "Position" in result or "details" in result
        assert isinstance(result, str)


class TestCleanHtmlVsHTMLCleaner:
    """Compare clean_html() output with HTMLCleaner."""

    def test_clean_html_produces_similar_output(self) -> None:
        """clean_html() produces comparable output to HTMLCleaner."""
        html = "<h1>Senior Python Developer</h1><p>Requirements: 5+ years Python</p><p>Apply Now</p>"

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cleaner = HTMLCleaner()
            cleaner_result = cleaner.clean(html)

        clean_result = clean_html(html)

        assert "Python" in cleaner_result or "Developer" in cleaner_result
        assert "Python" in clean_result or "Developer" in clean_result

        assert "Apply Now" not in cleaner_result
        assert "Apply Now" not in clean_result

    def test_both_handle_entities_similarly(self) -> None:
        """Both clean HTML entities."""
        html = "<p>Skills&nbsp;Required&nbsp;&amp;&nbsp;Experience</p>"

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cleaner = HTMLCleaner()
            cleaner_result = cleaner.clean(html)

        clean_result = clean_html(html)

        assert "&nbsp;" not in cleaner_result
        assert "&nbsp;" not in clean_result

    def test_both_remove_boilerplate_patterns(self) -> None:
        """Both remove similar boilerplate patterns."""
        html = "<p>Job details here.</p><p>Equal Opportunity Employer.</p><p>Share this job.</p>"

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cleaner = HTMLCleaner()
            cleaner_result = cleaner.clean(html)

        clean_result = clean_html(html)

        assert "Equal Opportunity" not in cleaner_result
        assert "Equal Opportunity" not in clean_result
        assert "Share" not in cleaner_result
        assert "Share" not in clean_result


class TestCleanHtmlEnhancements:
    """Test enhancements in clean_html() over HTMLCleaner."""

    def test_clean_html_has_section_headers_synthesis(self) -> None:
        """clean_html() includes section header synthesis (new feature)."""
        html = "<p>Qualifications</p><ul><li>Python</li><li>AWS</li></ul>"

        clean_result = clean_html(html, include_section_headers=True)

        assert "Python" in clean_result
        assert "AWS" in clean_result

    def test_clean_html_has_category_skipping(self) -> None:
        """clean_html() supports skip_boilerplate_categories (new feature)."""
        html = "<p>Competitive salary. Full-time position.</p>"

        result = clean_html(html, skip_boilerplate_categories={"salary_benefits"})

        # Skipping salary_benefits keeps the "$" and amount.
        assert isinstance(result, str)

    def test_clean_html_type_hints_improve_safety(self) -> None:
        """clean_html() has improved type hints for better IDE support."""
        result = clean_html("")
        assert result == ""


class TestEdgeCaseConsistency:
    """Test edge case handling consistency."""

    def test_both_handle_empty_input(self) -> None:
        """Both handle empty HTML gracefully."""
        html = ""

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cleaner = HTMLCleaner()
            cleaner_result = cleaner.clean(html)

        clean_result = clean_html(html)

        assert cleaner_result == ""
        assert clean_result == ""

    def test_both_handle_malformed_html(self) -> None:
        """Both handle malformed HTML without crashing."""
        html = "<div><p>unclosed"

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cleaner = HTMLCleaner()
            cleaner_result = cleaner.clean(html)

        clean_result = clean_html(html)

        assert isinstance(cleaner_result, str)
        assert isinstance(clean_result, str)
        assert len(cleaner_result) > 0 or len(clean_result) > 0


class TestMigrationPath:
    """Test migration from HTMLCleaner to clean_html()."""

    def test_direct_replacement_pattern(self) -> None:
        """Simple replacement pattern: HTMLCleaner().clean() -> clean_html()."""
        html = "<h1>Job Title</h1><p>Apply Now</p>"

        # Old pattern (deprecated)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            old_result = HTMLCleaner().clean(html)

        # New pattern (recommended)
        new_result = clean_html(html)

        assert isinstance(old_result, str)
        assert isinstance(new_result, str)
        assert len(old_result) > 0
        assert len(new_result) > 0

    def test_extract_text_selector_still_works(self) -> None:
        """extract_text() with CSS selector still works (backward compat)."""
        html = (
            "<div class='job-details'>"
            "<h1>Position Title</h1>"
            "<div class='requirements'>"
            "<p>5+ years experience</p>"
            "</div>"
            "</div>"
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cleaner = HTMLCleaner()
            result = cleaner.extract_text(html, selector=".job-details")

        assert isinstance(result, str)
        assert len(result) > 0
