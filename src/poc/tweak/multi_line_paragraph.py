"""Multi-line paragraph parsing and markdown section extraction.

This module provides utilities for parsing markdown text into structured sections,
detecting section headers (H1-H3 and bold markers), and extracting rich metadata
about each section. Uses spaCy for linguistic analysis and spaCy Doc extensions
for integration with spaCy pipelines.

Classes:
    MarkdownSpanRuler: Main class for parsing markdown and extracting sections
    MarkdownSection: Dataclass representing a single markdown section with metadata

Functions:
    extract_title: Extract title text from a header line
    get_header_level: Determine the header level (1-3) or bold (-1)
    count_words: Count non-empty words in text
    detect_has_list: Detect presence of bullet points in content
"""

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from spacy.language import Language

# ============================================================================
# Phase 1: Constants and Pattern Definitions
# ============================================================================

# Header patterns from span_sections_markdown.py lines 5-36
HEADER_PATTERN = r"^#{1,3}"
"""Regex pattern for H1, H2, H3 headers (e.g., #, ##, ###)."""

HEADER_BOLD_PATTERN = r"^## \*\*"
"""Regex pattern for ## ** (bold after H2 marker)."""

BOLD_PATTERN = r"^\*\*.+\*\*\s*$"
"""Regex pattern for standalone bold title (entire line is bold)."""

COMBINED_PATTERN = f"({HEADER_PATTERN})|({HEADER_BOLD_PATTERN})|({BOLD_PATTERN})"
"""Combined regex for all header marker types."""

# Map pattern to header level
PATTERN_TO_LEVEL = {
    HEADER_PATTERN: "numeric",  # Will be extracted from actual text
    HEADER_BOLD_PATTERN: 2,
    BOLD_PATTERN: -1,  # Bold marker (non-numbered)
}

# List markers for detection
LIST_MARKERS = {"*", "-", "•", "+"}
"""Set of bullet point markers to detect lists."""


# ============================================================================
# Phase 1: Data Structures
# ============================================================================


@dataclass
class MarkdownSection:
    """Represents a single section in markdown text.

    Attributes:
        title: Optional title extracted from the header line.
               None indicates a preamble or unlabeled section (no header).
        content: Raw content of the section (preserves original formatting)
        level: Header level (1, 2, 3 for #/##/###; -1 for bold marker; -2 for preamble/unlabeled)
        start_line: Zero-based line index where this section starts
        end_line: Zero-based line index where this section ends (inclusive)
        word_count: Number of non-empty words in content
        line_count: Number of non-empty lines in content
        has_list: True if content contains bullet points
        metadata: Dictionary for extensible metadata storage
    """

    title: Optional[str]
    content: str
    level: int
    start_line: int
    end_line: int
    word_count: int
    line_count: int
    has_list: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert section to dictionary representation.

        Returns:
            Dictionary with all section fields, suitable for JSON serialization.
        """
        return asdict(self)


# ============================================================================
# Phase 1: Helper Functions
# ============================================================================


def extract_title(line: str, level: int) -> Optional[str]:
    """Extract title text from a header line.

    Removes header markers (# ## ###) and bold markers (* **) from the line,
    returning clean title text. Returns None if line has no extractable title.

    Args:
        line: A single line of text that may contain header markers
        level: Header level (1, 2, 3, -1, etc.)

    Returns:
        Cleaned title text without markers, or None if empty after cleaning

    Example:
        >>> extract_title("## **Qualifications**", 2)
        'Qualifications'
        >>> extract_title("# Requirements", 1)
        'Requirements'
        >>> extract_title("**Bold Text**", -1)
        'Bold Text'
    """
    cleaned = line.strip()

    # Remove heading markers (#, ##, ###)
    if level in [1, 2, 3]:
        cleaned = re.sub(r"^#{1,3}\s*", "", cleaned)

    # Remove bold markers (** at start and end)
    if level == -1 or "**" in cleaned:
        cleaned = re.sub(r"^\*\*", "", cleaned)
        cleaned = re.sub(r"\*\*\s*$", "", cleaned)

    cleaned = cleaned.strip()
    return cleaned if cleaned else None


def get_header_level(line: str) -> int:
    """Determine header level from a line.

    Checks line against markdown header patterns and returns:
    - 1, 2, or 3 for #, ##, ###
    - -1 for bold markers (** **)
    - -2 for regular content with no marker

    Args:
        line: A single line of text

    Returns:
        Header level as integer, or -2 if no header marker found

    Example:
        >>> get_header_level("## **Section**")
        2
        >>> get_header_level("**Bold Title**")
        -1
        >>> get_header_level("Regular text")
        -2
    """
    stripped = line.strip()

    # Check for # markers (H1, H2, H3)
    match = re.match(r"^(#{1,3})", stripped)
    if match:
        return len(match.group(1))

    # Check for bold markers
    if re.match(BOLD_PATTERN, stripped):
        return -1

    # Check for ## ** pattern
    if re.match(HEADER_BOLD_PATTERN, stripped):
        return 2

    # No marker found
    return -2


def count_words(text: str) -> int:
    """Count non-empty words in text.

    Splits text on whitespace and counts non-empty tokens.

    Args:
        text: Text to count words in

    Returns:
        Number of words

    Example:
        >>> count_words("  hello   world  ")
        2
    """
    return len([w for w in text.split() if w])


def detect_has_list(content: str) -> bool:
    """Detect presence of bullet points in content.

    Checks each non-empty line for bullet point markers (*, -, •, +).

    Args:
        content: Text content to check

    Returns:
        True if any line starts with a bullet point marker

    Example:
        >>> detect_has_list("* Item 1\\n* Item 2")
        True
        >>> detect_has_list("Regular text\\nMore text")
        False
    """
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped and stripped[0] in LIST_MARKERS:
            return True
    return False


def map_line_to_token_position(text: str, line_idx: int) -> tuple:
    """Map a line index to character and token positions in text.

    Args:
        text: Full text
        line_idx: Zero-based line number

    Returns:
        Tuple of (char_start, char_end) positions, or (None, None) if invalid
    """
    lines = text.split("\n")
    if line_idx >= len(lines):
        return (None, None)

    char_pos = 0
    for i, line in enumerate(lines):
        if i == line_idx:
            return (char_pos, char_pos + len(line))
        char_pos += len(line) + 1  # +1 for newline

    return (None, None)


# ============================================================================
# Phase 2: MarkdownSpanRuler Class
# ============================================================================


class MarkdownSpanRuler:
    """Parse markdown text into structured sections with metadata.

    Uses regex patterns to detect section headers and extract rich metadata
    including title, content, header level, line boundaries, word count,
    line count, and list detection.

    Attributes:
        nlp: spaCy Language model instance
        doc_sections: Most recently parsed sections list

    Example:
        >>> nlp = spacy.load("en_core_web_sm")
        >>> ruler = MarkdownSpanRuler(nlp)
        >>> sections = ruler.parse("# Title\\n\\nContent here")
        >>> for sec in sections:
        ...     print(f"{sec.title}: {sec.word_count} words")
    """

    def __init__(self, nlp: Language) -> None:
        """Initialize MarkdownSpanRuler.

        Registers spaCy Doc extension for sections if not already registered.

        Args:
            nlp: Loaded spaCy Language model (e.g., en_core_web_sm)
        """
        self.nlp = nlp
        self.doc_sections: List[MarkdownSection] = []

        # Register Doc extension for storing parsed sections
        from spacy.tokens import Doc

        if not Doc.has_extension("sections"):
            Doc.set_extension("sections", default=[])

    def parse(self, text: str) -> List[MarkdownSection]:
        """Parse markdown text into sections.

        Splits text on newlines, identifies section headers (# ## ### and bold),
        extracts content between headers, and calculates metadata for each section.
        Preserves original formatting and content exactly.

        Preamble text (content before the first header) is emitted as a section
        with title=None and level=-2. Whitespace-only preambles are dropped.

        Args:
            text: Raw markdown text to parse

        Returns:
            List of MarkdownSection objects, one per detected section (including preamble)

        Example:
            >>> sections = ruler.parse("# Title\\n\\nContent\\n\\n## Section 2\\nMore content")
            >>> len(sections)
            2
            >>> sections[0].title
            'Title'
        """
        lines = text.split("\n")
        sections: List[MarkdownSection] = []

        # Find all section boundary lines (headers)
        boundaries = self._find_boundaries(lines)

        # If there's text before the first boundary, emit it as a preamble section
        if boundaries and boundaries[0] > 0:
            preamble_lines = lines[0 : boundaries[0]]
            preamble_text = "\n".join(preamble_lines).strip()
            if preamble_text:
                # Build preamble section with title=None, level=-2
                preamble_section = self._build_section(
                    lines=lines,
                    start_line=0,
                    end_line=boundaries[0] - 1,
                    title=None,
                    level=-2,
                    content=preamble_text,
                )
                sections.append(preamble_section)

        # Extract sections between boundaries
        for i, boundary_idx in enumerate(boundaries):
            # End of current section is one line before next boundary
            if i + 1 < len(boundaries):
                current_end = boundaries[i + 1] - 1
            else:
                # Last section goes to end of text
                current_end = len(lines) - 1

            # Extract section starting at boundary
            section = self._extract_section(lines, boundary_idx, current_end)
            if section:
                sections.append(section)

        # Add any trailing content after last header (if no headers at all)
        if not boundaries and lines:
            content = "\n".join(lines).strip()
            if content:
                section = self._build_section(
                    lines=lines,
                    start_line=0,
                    end_line=len(lines) - 1,
                    title=None,
                    level=-2,
                    content=content,
                )
                sections.append(section)

        # Store in instance and attach to doc
        self.doc_sections = sections
        doc = self.nlp(text)
        doc._.sections = sections

        return sections

    def _find_boundaries(self, lines: List[str]) -> List[int]:
        """Find line indices where sections start (header markers).

        Identifies lines matching header patterns (#, ##, ###, bold).

        Args:
            lines: List of text lines from split('\n')

        Returns:
            List of zero-based line indices where headers are found
        """
        boundaries = []
        for i, line in enumerate(lines):
            if re.match(COMBINED_PATTERN, line.strip()):
                boundaries.append(i)
        return boundaries

    def _build_section(
        self,
        lines: List[str],
        start_line: int,
        end_line: int,
        title: Optional[str],
        level: int,
        content: str,
    ) -> MarkdownSection:
        """Build a MarkdownSection with computed metadata.

        Helper function for constructing sections with consistent metadata calculation.

        Args:
            lines: All lines of text (used to compute line_count)
            start_line: Zero-based starting line index
            end_line: Zero-based ending line index (inclusive)
            title: Optional title (None for preamble/unlabeled sections)
            level: Header level (1-3, -1, -2, etc.)
            content: Section content (already stripped)

        Returns:
            MarkdownSection object with computed metadata
        """
        content_lines = lines[start_line : end_line + 1]
        word_count = count_words(content)
        non_empty_lines = [line for line in content_lines if line.strip()]
        line_count = len(non_empty_lines)
        has_list = detect_has_list(content)

        return MarkdownSection(
            title=title,
            content=content.strip() if isinstance(content, str) else content,
            level=level,
            start_line=start_line,
            end_line=end_line,
            word_count=word_count,
            line_count=line_count,
            has_list=has_list,
        )

    def _extract_section(self, lines: List[str], start: int, end: int) -> Optional[MarkdownSection]:
        """Extract a single section from start to end line index.

        Constructs content between start and end, determines header level
        from start line, extracts title, and calculates metadata.

        Args:
            lines: All lines of text
            start: Zero-based starting line index (header line)
            end: Zero-based ending line index (inclusive)

        Returns:
            MarkdownSection object, or None if section is invalid
        """
        if start >= len(lines):
            return None

        # Get header line and determine level
        header_line = lines[start]
        level = get_header_level(header_line)

        # Extract title from header
        title = extract_title(header_line, level)

        # Build content from start to end (include all lines)
        content_lines = lines[start : end + 1]
        content = "\n".join(content_lines)

        return self._build_section(
            lines=lines,
            start_line=start,
            end_line=end,
            title=title,
            level=level,
            content=content,
        )

    def to_dict(self, sections: Optional[List[MarkdownSection]] = None) -> Dict[str, Any]:
        """Export sections to dictionary format.

        If sections not provided, uses most recently parsed sections.

        Args:
            sections: Optional list of MarkdownSection objects. If None, uses self.doc_sections

        Returns:
            Dictionary with 'sections' key containing list of section dicts
        """
        if sections is None:
            sections = self.doc_sections

        return {"sections": [section.to_dict() for section in sections]}

    def to_json(self, sections: Optional[List[MarkdownSection]] = None, indent: int = 2) -> str:
        """Export sections to JSON string.

        If sections not provided, uses most recently parsed sections.

        Args:
            sections: Optional list of MarkdownSection objects. If None, uses self.doc_sections
            indent: JSON indentation level (default: 2)

        Returns:
            JSON string representation of sections
        """
        data = self.to_dict(sections)
        return json.dumps(data, indent=indent, ensure_ascii=False)
