"""Shared HTML-to-Markdown conversion utility.

MarkItDown's ``convert()`` treats its argument as a file path (or a stream),
not a literal HTML string. Passing raw HTML directly raises ``FileNotFoundError``.
This module works around that by writing the HTML to a temporary file first,
converting that file, and cleaning up afterward.

Also owns the section-header synthesis pass (``normalize_description`` /
``add_markdown_section_headers``) formerly on ``Crawler`` (see Issue #228):
when the source HTML lacked real heading tags, keyword/bold/colon-terminated
standalone lines are promoted to "## "/"### " headers so downstream chunking
and NER section-routing (``src/tokenization/preprocessor.py``) have structure
to work with.

Issue #230: Unified HTML cleaning pipeline (clean_html) combining MarkItDown,
section header synthesis, boilerplate removal, and entity normalization.
"""

import logging
import os
import re
import tempfile
from typing import List, Optional, Set

from markitdown import MarkItDown

from src.parsers import _boilerplate_patterns

logger = logging.getLogger(__name__)


def _normalize_html_before_extraction(html: str) -> str:
    r"""Normalize HTML structure before BeautifulSoup extraction (Phase 1).

    Handles Workday-specific patterns:
    - dt/dd pairs: Replace with div+p structure to force newlines
    - Nested tables: Convert to structured text
    - Workday metadata: Remove data-*, aria-* attributes
    - Workday IDs: Remove :R\d+ patterns from dd elements

    Args:
        html: Raw HTML string to normalize

    Returns:
        Normalized HTML with improved structure for text extraction
    """
    if not html:
        return html

    # Remove Workday metadata attributes (data-*, aria-*)
    html = re.sub(r'\s+(?:data-|aria-)[a-z\-]+=(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', "", html)

    # Convert <dt>Label</dt><dd>Value</dd> to <div><p>Label</p><p>Value</p></div> so each lands on its own line.
    html = re.sub(
        r"<dt>([^<]+)</dt>\s*<dd>([^<]+)</dd>",
        r"<div><p>\1</p><p>\2</p></div>",
        html,
        flags=re.IGNORECASE,
    )

    # Remove Workday ID refs (e.g. ":R69380"); pure-digit refs go only at 4+ digits, so ":1" to ":999" survive.
    html = re.sub(r":\s*R\d+", "", html)
    html = re.sub(r":\s*[A-Za-z]+\d+", "", html)
    html = re.sub(r":\s*\d{4,}", "", html)

    # Drop colons left orphaned by the removals above.
    html = re.sub(r">:\s*", "> ", html)

    # Remove empty paired tags; the backreference avoids matching unrelated tags.
    html = re.sub(r"<(\w+)[^>]*>\s*</\1>", "", html, flags=re.IGNORECASE)

    return html


def html_to_markdown(html: str) -> str:
    """
    Convert an HTML string to clean text using a 3-tier fallback chain (Phase 1 enhanced).

    Attempts conversion in this order:
    1. MarkItDown (primary) - preserves structure, handles rich content
    2. BeautifulSoup + lxml (fallback) - basic text extraction
    3. Original HTML (safe fallback) - never returns empty/None

    Phase 1: Normalize HTML structure (Workday patterns) before conversion.

    MarkItDown requires a file path, so ``html`` is written to a temporary
    ``.html`` file (UTF-8) before conversion. On any failure (I/O error,
    MarkItDown exception, etc.), falls back to BeautifulSoup. If both fail,
    returns the original ``html`` unchanged so callers always get a usable string.

    Args:
        html: Raw HTML string to convert.

    Returns:
        Clean text from MarkItDown/BeautifulSoup, or the original ``html`` on complete failure.
    """
    if not html:
        return html

    normalized_html = _normalize_html_before_extraction(html)

    tmp_path: str = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".html",
            encoding="utf-8",
            delete=False,
        ) as tmp_file:
            tmp_file.write(normalized_html)
            tmp_path = tmp_file.name

        result = MarkItDown().convert(tmp_path)
        markdown: str = result.markdown
        return markdown
    except Exception as e:
        logger.warning(f"html_to_markdown MarkItDown failed: {e}, trying BeautifulSoup fallback")
        try:
            return _html_to_markdown_via_beautifulsoup(html)
        except Exception as bs_error:
            logger.error(f"BeautifulSoup fallback also failed: {bs_error}, returning original HTML")
            return html
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _html_to_markdown_via_beautifulsoup(html: str) -> str:
    """Convert HTML to text using BeautifulSoup + lxml (fallback).

    Used when MarkItDown is unavailable or fails. Returns normalized text
    suitable for downstream tokenization and chunking.

    Phase 1: Normalize HTML structure before extraction (Workday dt/dd, refs, metadata).

    Args:
        html: Raw HTML string to convert

    Returns:
        Cleaned text with script/style tags removed

    Raises:
        ImportError: If BeautifulSoup not available
        Exception: If BeautifulSoup parsing fails
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("BeautifulSoup not available for fallback")
        raise

    normalized_html = _normalize_html_before_extraction(html)

    soup = BeautifulSoup(normalized_html, "lxml")

    for script in soup(["script", "style"]):
        script.decompose()

    text = soup.get_text()
    return _postprocess_markdown_text(text)


def _postprocess_markdown_text(text: str) -> str:
    """Normalize BeautifulSoup output to readable text (Phase 1 enhancement).

    Collapse whitespace, remove extra newlines, normalize spacing, and
    clean up Workday-specific artifacts (refs, em-dashes).

    Args:
        text: Raw text from BeautifulSoup

    Returns:
        Cleaned and normalized text
    """
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = "\n".join(chunk for chunk in chunks if chunk)

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    # Drop standalone Workday ID refs (lines that are just ":R69380" or similar).
    text_lines = text.split("\n")
    cleaned_lines = []
    for line in text_lines:
        stripped = line.strip()
        if stripped and re.match(r"^:?\s*R\d+\s*$", stripped):
            logger.debug(f"Skipping orphaned Workday ref: '{stripped}'")
            continue
        if stripped and re.match(r"^:?\s*\w+\d+\s*$", stripped):
            if not any(c.isalpha() for c in stripped if c.lower() not in "rid"):
                logger.debug(f"Skipping orphaned ID-like ref: '{stripped}'")
                continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Normalize em-dashes/en-dashes: ensure they don't concatenate text
    text = re.sub(r"(\w)([—–])(\w)", r"\1\n\2\3", text)

    return text.strip()


# Standalone lines matching these become "## " headers when the HTML lacks real heading tags.
# Matching is case-insensitive, after stripping bold markers and a trailing colon, with curly apostrophes normalized.
_SECTION_HEADER_KEYWORDS = frozenset(
    {
        # qualifications
        "qualifications",
        "desired qualifications",
        "preferred qualifications",
        "minimum qualifications",
        "essential qualifications",
        # requirements
        "requirements",
        "must-have",
        "must haves",
        "must-haves",
        "nice-to-have",
        "nice-to-haves",
        "nice to have",
        "nice to haves",
        "needed",
        # skills
        "skills",
        "technical skills",
        "core skills",
        "competencies",
        # knowledge
        "knowledge",
        "understanding",
        # responsibilities
        "responsibilities",
        "what you'll do",
        "duties",
        "accountabilities",
        # experience
        "experience",
        "background",
        # education
        "education",
        # benefits / compensation
        "benefits",
        "compensation",
        # about-the-role variants
        "about the role",
        "about this role",
        "what we're looking for",
    }
)


def _extract_bold_label(text: str) -> Optional[str]:
    """Return the inner text of a bold-only standalone line, or None.

    Matches Markdown bold (``**label**``) and MarkItDown-escaped bold
    (``\\*\\*label\\*\\*``) wrapping the entire line.
    """
    match = re.match(r"^\\\*\\\*(.+?)\\\*\\\*$", text)
    if match:
        return match.group(1).strip()
    match = re.match(r"^\*\*(.+?)\*\*$", text)
    if match:
        return match.group(1).strip()
    return None


def _extract_standalone_label(text: str) -> Optional[str]:
    """Return the label of a standalone plain/bold line, or None.

    Excludes list items, headers, and table rows so only genuine
    heading-like lines are considered.
    """
    bold_label = _extract_bold_label(text)
    if bold_label is not None:
        return bold_label
    if text.startswith(("#", "-", "*", "+", ">", "|")) or re.match(r"^\d+\.\s", text):
        return None
    return text


def _synthesize_keyword_headers(lines: List[str]) -> None:
    """Step 1: standalone lines matching a known section keyword -> '## Header'.

    Mutates ``lines`` in place.
    """
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        label = _extract_standalone_label(stripped)
        if label is None:
            continue
        normalized = label.rstrip(":").strip()
        if normalized.replace("’", "'").lower() in _SECTION_HEADER_KEYWORDS:
            lines[i] = f"## {normalized}"


def _synthesize_bold_subsection_headers(lines: List[str]) -> None:
    """Step 2: bold-only or bold-at-start line followed by content -> '### Subsection'.

    Mutates ``lines`` in place.

    Phase 11 (Issue #241): Handle partial bold (text after bold, e.g., `**Label** — description`)
    and bold-formatted headers at line start.
    """
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        label = _extract_bold_label(stripped)
        if label is None:
            # Bold at line start with trailing text, e.g. "**Responsibilities** include" or "**Label** — description".
            match = re.match(r"^\*\*([^\*]+)\*\*", stripped)
            if not match:
                continue
            label = match.group(1).strip()
            trailing = stripped[match.end() :].strip()
            # Both branches are no-ops: trailing text is a separator or inline content, and the label is used either way.
            if trailing and trailing.startswith(("—", "-", ":", ",")):
                pass
            elif trailing:
                pass

        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            continue
        next_stripped = lines[j].strip()
        if next_stripped and not next_stripped.startswith("#"):
            lines[i] = f"### {label.rstrip(':').strip()}"


def _synthesize_colon_subsection_headers(lines: List[str]) -> None:
    """Step 3: any remaining non-header line ending in ':' -> '### Subsection'.

    Mutates ``lines`` in place.
    """
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.endswith(":"):
            continue
        label = stripped[:-1].strip()
        if not label:
            continue
        lines[i] = f"### {label}"


def _should_skip_divider_part(part: str) -> bool:
    """Check if a divider-split part should be skipped.

    Skips empty parts and pure Workday refs (IDs).

    Args:
        part: Text part from divider split

    Returns:
        True if part should be skipped, False otherwise
    """
    part = part.strip()
    if not part:
        return True
    if re.match(r"^(?:R\d+|\w+\d+)\s*$", part):
        logger.debug(f"Skipping orphaned ref in divider normalization: '{part}'")
        return True
    return False


def _process_divider_parts(parts: List[str], result: List[str]) -> None:
    """Process parts from a divider-split line and append to result.

    Splits content parts, adds dividers between non-skipped parts.

    Args:
        parts: Text parts from splitting on "---"
        result: List to append processed parts to (mutated in place)
    """
    for i, part in enumerate(parts):
        part = part.strip()
        # Remove leading colons from parts (Workday artifact cleanup)
        part = re.sub(r"^:+\s*", "", part).strip()

        if _should_skip_divider_part(part):
            continue

        result.append(part)
        if i < len(parts) - 1:
            result.append("---")


def _normalize_divider_lines(lines: List[str]) -> List[str]:
    """Phase 2: Normalize divider lines to ensure dividers are isolated.

    Scans for embedded dividers (e.g., "text---" or ":R69380---") and splits
    them onto separate lines. Removes orphaned colons and refs.

    Skips processing table rows (lines starting with |) to avoid interfering
    with markdown table separator rows.

    Args:
        lines: List of text lines (may contain embedded dividers)

    Returns:
        New list with dividers isolated on their own lines
    """
    result: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue

        # Skip processing table rows (lines starting with | are table markup)
        if stripped.startswith("|"):
            result.append(line)
            continue

        # Embedded dividers: "text---", "---text", ":R69380---", "---:R69380", ":---".
        if "---" in stripped:
            parts = stripped.split("---")
            _process_divider_parts(parts, result)

            # Add a final divider only if the line ended with "---" and the loop did not already add one.
            if len(parts) > 1 and not parts[-1].strip():
                if not result or result[-1].strip() != "---":
                    result.append("---")
        else:
            result.append(line)

    return result


def _insert_section_dividers(lines: List[str]) -> List[str]:
    """Step 4: insert a blank line + '---' immediately before every
    synthesized header (Phase 2 enhancement).

    Phase 2: Normalize dividers to ensure they are isolated (no embedded dividers).

    Skips insertion if the header is the very first line of the
    document (nothing precedes it, so there's nothing to separate) or
    if the immediately preceding emitted line is already '---' or
    another header, to avoid doubled/redundant dividers on consecutive
    headers. Returns a new list (unlike the mutate-in-place synthesis
    passes) since insertion changes list length.

    Args:
        lines: List of text lines (may contain embedded dividers)

    Returns:
        List with dividers inserted before headers and isolated on own lines
    """
    # Normalize embedded dividers first, then drop consecutive duplicates.
    normalized_lines = _normalize_divider_lines(lines)

    deduplicated: List[str] = []
    for line in normalized_lines:
        if line.strip() == "---" and deduplicated and deduplicated[-1].strip() == "---":
            logger.debug("Removing consecutive duplicate divider in post-normalization deduplication")
            continue
        deduplicated.append(line)
    normalized_lines = deduplicated

    header_re = re.compile(r"^#{2,3}\s")
    result: List[str] = []
    for line in normalized_lines:
        if header_re.match(line) and result:
            prev_line = result[-1].strip()
            if prev_line != "---" and not header_re.match(prev_line):
                result.append("")
                result.append("---")
        result.append(line)

    for i, line in enumerate(result):
        stripped = line.strip()
        if "---" in stripped and stripped != "---":
            logger.warning(f"Divider isolation validation failed at line {i}: '{stripped}'")

    return result


def add_markdown_section_headers(markdown: str) -> str:
    """
    Synthesize "## "/"### " section headers from keyword, bold, and
    colon-terminated standalone lines when the source HTML lacked real
    heading tags.

    Runs four passes in sequence:
    1. Standalone lines matching a known section keyword (plain, bold,
       or MarkItDown-escaped bold, with an optional trailing colon)
       become "## <Header>".
    2. Remaining bold-only standalone lines followed by non-empty,
       non-header content become "### <Subsection>".
    3. Remaining non-header lines ending in ":" become
       "### <Subsection>".
    4. A blank line + "---" divider is inserted immediately before
       every "##"/"###" header produced above (skipped when the header
       is the first line of the document, or immediately follows
       another header/divider), activating the preprocessor's
       divider-aware section splitting.
    """
    lines = markdown.split("\n")
    _synthesize_keyword_headers(lines)
    _synthesize_bold_subsection_headers(lines)
    _synthesize_colon_subsection_headers(lines)
    lines = _insert_section_dividers(lines)
    return "\n".join(lines)


def normalize_description(description: str) -> str:
    """
    Normalize a job description by converting HTML to Markdown and
    synthesizing section headers.

    Uses ``html_to_markdown()`` so that structural formatting (headings,
    lists, etc.) is preserved instead of collapsing into a flat, ambiguous
    run of text, then runs ``add_markdown_section_headers()`` to promote
    keyword/bold/colon-terminated standalone lines into real headers when
    the source HTML lacked heading tags.
    """
    if not description:
        return ""
    markdown = html_to_markdown(description)
    return add_markdown_section_headers(markdown) if markdown else markdown


def clean_html(
    html: str | None,
    include_section_headers: bool = True,
    skip_boilerplate_categories: Optional[Set[str]] = None,
) -> str:
    """
    Unified HTML cleaning pipeline (Issue #230).

    Converts raw HTML to clean, readable text through a 6-step pipeline:
    1. ``html_to_markdown()`` – MarkItDown + BeautifulSoup fallback
    2. ``add_markdown_section_headers()`` – Synthesize missing headers (if enabled)
    3. ``_insert_section_dividers()`` – Add dividers before headers
    4. ``remove_boilerplate_fast()`` – Remove legal, section, company, salary, etc.
    5. ``remove_html_entities()`` – Normalize &nbsp;, &amp;, &#\\d+;, etc.
    6. ``_normalize_whitespace()`` – Collapse multi-space/newline to single

    Args:
        html: Raw HTML string to clean
        include_section_headers: If True, synthesize missing "##"/"###" headers
            from keyword/bold/colon-terminated lines (default: True)
        skip_boilerplate_categories: Optional set of category names to skip
            (e.g., {"section_headers", "time_references"}). Supported categories:
            "legal_compliance", "section_headers", "company_boilerplate",
            "time_references", "salary_benefits", "special_formatting", "navigation"

    Returns:
        Clean text content with boilerplate removed and entities normalized

    Examples:
        >>> html = '<h1>Senior Dev</h1><p>Equal Opportunity Employer.</p>'
        >>> clean_html(html)
        '# Senior Dev\\nSenior Dev'

        >>> html = '<p>Salary: $100K</p>'
        >>> clean_html(html, skip_boilerplate_categories={"salary_benefits"})
        'Salary: $100K'

        >>> html = ''  # Empty input
        >>> clean_html(html)
        ''
    """
    if not html or not isinstance(html, str):
        return ""

    # Step 1: Convert HTML to Markdown (MarkItDown + BeautifulSoup fallback)
    markdown = html_to_markdown(html)
    if not markdown:
        return ""

    # Step 2: Synthesize section headers (if enabled)
    if include_section_headers:
        markdown = add_markdown_section_headers(markdown)

    # Step 3 (section dividers) is folded into add_markdown_section_headers.

    # Step 4: Remove boilerplate using pre-compiled patterns
    cleaned = _boilerplate_patterns.remove_boilerplate_fast(markdown, skip_categories=skip_boilerplate_categories)

    # Step 5: Remove HTML entities
    cleaned = _boilerplate_patterns.remove_html_entities(cleaned)

    # Step 6: Normalize whitespace
    cleaned = _boilerplate_patterns._normalize_whitespace(cleaned)

    # Step 7: Repair dividers that boilerplate removal's whitespace collapse may have embedded in text.
    cleaned_lines = cleaned.split("\n")
    repaired_lines = _normalize_divider_lines(cleaned_lines)
    cleaned = "\n".join(repaired_lines)

    logger.debug(
        f"clean_html: {len(html)} chars → {len(cleaned)} chars "
        f"(reduction: {(len(html) - len(cleaned)) / len(html) * 100:.1f}%)"
    )

    return cleaned
