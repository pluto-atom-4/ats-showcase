"""Schema for parsed markdown sections with complete metadata.

This module defines MarkdownSection, which captures section-level information
from the markdown processing pipeline, enabling full traceability and testing.

Issue #338: Each section stores heading, content, classification type, confidence,
and exact position (line numbers) for debugging and reconstruction.
"""

from dataclasses import dataclass, field


@dataclass
class MarkdownSection:
    """Parsed section from markdown with complete metadata.

    Enables full traceability from section through classification to output.
    Used for testing, debugging, and downstream processing (HTML reconstruction,
    vector embedding, etc.).

    Attributes:
        section_id: Unique identifier within job (e.g., "sec_0", "sec_1")
        heading: Section heading/title (may be empty string if no heading detected)
        content: Full section text content
        section_type: Classified semantic type (e.g., "responsibilities", "requirements",
                     "skills", "about_company", "job_overview")
        confidence: Classification confidence score in range [0.0, 1.0]
        line_start: Starting line number in markdown (0-indexed)
        line_end: Ending line number in markdown (inclusive)
        matched_keywords: Keywords that triggered classification (for traceability)

    Example:
        >>> section = MarkdownSection(
        ...     section_id="sec_0",
        ...     heading="Requirements",
        ...     content="5+ years of Python experience...",
        ...     section_type="requirements",
        ...     confidence=0.92,
        ...     line_start=10,
        ...     line_end=25,
        ...     matched_keywords=["years", "experience"]
        ... )
        >>> section.summary
        'sec_0: requirements (conf=0.92) @ lines 10-25'
    """

    section_id: str
    heading: str
    content: str
    section_type: str
    confidence: float
    line_start: int
    line_end: int
    matched_keywords: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        if self.line_end < self.line_start:
            raise ValueError(f"line_end ({self.line_end}) must be >= line_start ({self.line_start})")

    @property
    def summary(self) -> str:
        """One-line summary for logging and debugging.

        Returns a compact string representation including ID, type, confidence, and position.
        """
        return (
            f"{self.section_id}: {self.section_type} "
            f"(conf={self.confidence:.2f}) @ lines {self.line_start}-{self.line_end}"
        )

    @property
    def content_preview(self, max_len: int = 60) -> str:
        """Short content preview for logging.

        Args:
            max_len: Maximum length of preview (default 60)

        Returns:
            First max_len characters of content, with ellipsis if truncated
        """
        if len(self.content) <= max_len:
            return self.content
        return self.content[:max_len] + "..."

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns a dict suitable for JSON export, with confidence rounded to 2 decimals.
        """
        return {
            "section_id": self.section_id,
            "heading": self.heading,
            "content": self.content,
            "section_type": self.section_type,
            "confidence": round(self.confidence, 2),
            "line_start": self.line_start,
            "line_end": self.line_end,
            "matched_keywords": self.matched_keywords,
        }
