"""Plain-text heading promotion to markdown section headers.

Promotes plain-text lines that match known job description heading patterns
to markdown section headers (## prefix), enabling MarkdownSpanRuler to
recognize section boundaries in unstructured job descriptions.

Rules for promotion:
- Line must be non-empty after stripping whitespace
- Line must not start with markdown markers (#, *, -, +) or list indicators (digits + .)
- Line must not be already formatted (bold **, italic *, or table |)
- Previous line must be blank OR this is the first line of the document
- Normalised line (casefold, apostrophe normalisation, collapse spaces, strip trailing ':')
  must match a known heading phrase from KNOWN_PLAIN_HEADINGS (exact match)
- Promotion is idempotent: already-promoted lines (starting with ##) are not re-promoted

Example:
    >>> promoter = HeadingPromoter()
    >>> text = "Job Description\\nRequirements below.\\nRole Overview\\nFocus areas."
    >>> result = promoter.process(text)
    >>> "## Job Description" in result
    True
    >>> "## Role Overview" in result
    True

The promoter is designed to be non-fatal; if any error occurs during processing,
the original text is returned unchanged.
"""

import re
from typing import FrozenSet, Optional

from src.poc.tweak.spacy_pipeline.base import PipelineComponent

# Strict phrase set: 64 non-'other' headings derived from classifier keywords/patterns
# The 10 excluded 'other' phrases (duties, education, eeo statement, equal employment opportunity,
# job duties, must have, nice to have, the role, who we are, who you are) do NOT appear here.
KNOWN_PLAIN_HEADINGS: FrozenSet[str] = frozenset(
    [
        "ability",
        "about",
        "about the position",
        "about the role",
        "about this opportunity",
        "about this position",
        "about this role",
        "about us",
        "about you",
        "affirmative action",
        "application instructions",
        "application process",
        "basic qualifications",
        "benefits",
        "career path",
        "certification",
        "compensation",
        "competency",
        "contact us",
        "core competencies",
        "core skills",
        "day to day responsibilities",
        "description",
        "desired qualifications",
        "domain knowledge",
        "duty",
        "environment",
        "equal opportunity employer",
        "essential",
        "essential functions",
        "essential qualifications",
        "essential requirements",
        "experience",
        "expertise",
        "growth opportunities",
        "how to apply",
        "ideal candidate",
        "ideal fit",
        "interview process",
        "intro",
        "job description",
        "job function",
        "job overview",
        "job responsibilities",
        "key competencies",
        "key responsibilities",
        "knowledge",
        "learning and development",
        "license",
        "minimum qualifications",
        "minimum requirements",
        "more information",
        "next steps",
        "organization overview",
        "overview",
        "perks",
        "physical requirements",
        "position description",
        "position overview",
        "preferred qualifications",
        "preferred requirements",
        "preferred skills",
        "primary responsibilities",
        "proficiency",
        "qualifications",
        "required education",
        "required experience",
        "required qualifications",
        "required skills",
        "requirement",
        "requirements",
        "responsibilities",
        "role description",
        "role overview",
        "role responsibilities",
        "salary",
        "skill",
        "skills",
        "summary",
        "team overview",
        "technical",
        "technical knowledge",
        "technical skills",
        "travel requirements",
        "we are looking for",
        "we need",
        "we seek",
        "what we are looking for",
        "what you bring",
        "what you will bring",
        "what you will do",
        "work location",
        "work schedule",
        "working conditions",
    ]
)


class HeadingPromoter(PipelineComponent):
    """Promote plain-text section headings to markdown format.

    Scans text line-by-line and converts lines matching known heading patterns
    to markdown section headers (## prefix). This enables structure recovery
    from plain-text job descriptions before the MarkdownSpanRuler parser runs.

    Attributes:
        headings: Frozenset of allowed heading phrases (lowercase, no trailing ':').
                  Defaults to KNOWN_PLAIN_HEADINGS.
    """

    def __init__(self, headings: Optional[FrozenSet[str]] = None) -> None:
        """Initialize the promoter with an optional custom heading set.

        Args:
            headings: Custom frozenset of heading phrases. If None, uses KNOWN_PLAIN_HEADINGS.
        """
        self._headings = headings if headings is not None else KNOWN_PLAIN_HEADINGS

    @property
    def name(self) -> str:
        """Return the component name for logging."""
        return "heading_promoter"

    def process(self, text: str) -> str:
        """Promote plain-text headings to markdown section headers.

        Processes text line-by-line, detecting lines that match known heading patterns
        and converting them to ## markdown format. The conversion preserves line count
        (1:1 replacement) and is idempotent (processing twice produces same output).

        Args:
            text: Input text (may be empty, contain CRLF, or Unicode).

        Returns:
            Text with promoted headings. If any error occurs, returns original text unchanged
            (non-fatal error handling).

        Example:
            >>> promoter = HeadingPromoter()
            >>> text = "Job Description\\nWork with clients.\\nRole Overview\\nFocus on delivery."
            >>> result = promoter.process(text)
            >>> result
            '## Job Description\\nWork with clients.\\n## Role Overview\\nFocus on delivery.'
        """
        try:
            # Handle empty input
            if not text:
                return text

            lines = text.split("\n")
            result_lines = []

            for i, line in enumerate(lines):
                stripped = line.strip()

                # Check if line should be promoted
                if self._should_promote(stripped, i == 0, i > 0 and not lines[i - 1].strip()):
                    # Normalize and check against known headings
                    normalized = self._normalize(stripped)
                    if normalized in self._headings:
                        # Promote: preserve leading/trailing whitespace from original line
                        # Extract the part of the line that should become the heading
                        promoted = "## " + stripped.rstrip(":").strip()
                        result_lines.append(promoted)
                    else:
                        result_lines.append(line)
                else:
                    result_lines.append(line)

            return "\n".join(result_lines)

        except Exception:
            # Non-fatal: return original text on any error
            return text

    def _should_promote(self, stripped_line: str, is_first: bool, prev_blank: bool) -> bool:
        """Check if a line is eligible for promotion (before checking against phrase set).

        Args:
            stripped_line: The line after calling .strip()
            is_first: True if this is the first line of the document
            prev_blank: True if the previous line was blank or first line

        Returns:
            True if the line passes structural checks (not already formatted, correct position)
        """
        # Empty lines cannot be promoted
        if not stripped_line:
            return False

        # Must not start with markdown/list markers
        if stripped_line[0] in "#*-+|":
            return False

        # Must not start with digit (list indicator like "1. ", "2. ")
        if stripped_line[0].isdigit():
            return False

        # Must not be already formatted as bold (**...**)
        if stripped_line.startswith("**") and stripped_line.endswith("**"):
            return False

        # Must not contain list-like patterns (digit followed by . or ))
        if re.match(r"^\d+[\.\)]", stripped_line):
            return False

        # Previous line must be blank or this is first line
        if not (is_first or prev_blank):
            return False

        return True

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison against known headings.

        Transformations:
        - Convert to lowercase (casefold for Unicode)
        - Normalize apostrophes (' and ' both become ')
        - Collapse multiple spaces to single space
        - Strip trailing ':' and whitespace
        - Strip leading/trailing whitespace

        Args:
            text: Raw text from the line

        Returns:
            Normalised text suitable for set membership testing
        """
        # Lowercase
        text = text.casefold()

        # Normalise apostrophes (both straight ' and curly ')
        text = text.replace("'", "'").replace("'", "'")

        # Collapse multiple spaces
        text = " ".join(text.split())

        # Strip trailing colon and whitespace
        text = text.rstrip(":").strip()

        return text
