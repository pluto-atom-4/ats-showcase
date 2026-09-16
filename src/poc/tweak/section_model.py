"""Schema for parsed markdown sections with complete metadata.

This module defines MarkdownSection, which captures section-level information
from the markdown processing pipeline, enabling full traceability and testing.

Issue #338: Each section stores heading, content, classification type, confidence,
and exact position (line numbers) for debugging and reconstruction. Also preserves
full multi-type classification data (all_types, labels, is_skip, keyword_matches)
to close Issue #295's data-loss gap in batch_processor.py.
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
                     "skills", "about_company", "job_overview") — the primary (highest-confidence) type
        confidence: Classification confidence score in range [0.0, 1.0] — confidence of primary type
        line_start: Starting line number in markdown (0-indexed)
        line_end: Ending line number in markdown (inclusive)
        matched_keywords: Keywords that triggered classification of primary type (for traceability)
                         Kept as flat list[str] for backward compatibility.

        all_types: List of all candidate section types with their confidences, sorted by confidence
                   descending (highest first). Each entry is a dict with keys:
                   - "section_type": str (the semantic type name)
                   - "confidence": float (confidence score [0.0, 1.0])
                   Closes Issue #295: preserves secondary types discarded during multi-type classification.
                   Default: empty list (backward compatible).

        labels: List of all matched section type labels (frozenset converted to list for JSON).
                Example: ["requirements", "skills"] if section matched both types.
                Closes Issue #295: preserves all types at once without iteration.
                Default: empty list (backward compatible).

        is_skip: Boolean flag indicating whether this section should be excluded from processing.
                 True if any matched type is SKIP or explicitly marked. Default: False (backward compatible).

        keyword_matches: List of all keyword matches with full position and source metadata.
                        Each entry is a dict with keys:
                        - "keyword": str (the matched keyword)
                        - "section_type": str (which type this keyword indicates)
                        - "source": str ("title" or "content" — where keyword was found)
                        - "position": int (character position in source text, 0-based)
                        Closes Issue #295: preserves full position/source detail lost in primary flattening.
                        Default: empty list (backward compatible).

    Example:
        >>> section = MarkdownSection(
        ...     section_id="sec_0",
        ...     heading="Requirements",
        ...     content="5+ years of Python experience...",
        ...     section_type="requirements",
        ...     confidence=0.92,
        ...     line_start=10,
        ...     line_end=25,
        ...     matched_keywords=["years", "experience"],
        ...     all_types=[
        ...         {"section_type": "requirements", "confidence": 0.92},
        ...         {"section_type": "qualifications", "confidence": 0.75}
        ...     ],
        ...     labels=["requirements", "qualifications"],
        ...     is_skip=False,
        ...     keyword_matches=[
        ...         {"keyword": "years", "section_type": "requirements", "source": "title", "position": 5},
        ...         {"keyword": "experience", "section_type": "qualifications", "source": "content", "position": 25}
        ...     ]
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
    all_types: list[dict] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    is_skip: bool = False
    keyword_matches: list[dict] = field(default_factory=list)

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
    def content_preview(self) -> str:
        """Short content preview for logging.

        Returns:
            First 60 characters of content, with ellipsis if truncated
        """
        max_len = 60
        if len(self.content) <= max_len:
            return self.content
        return self.content[:max_len] + "..."

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns a dict suitable for JSON export, with confidence rounded to 2 decimals.
        Includes all new fields (all_types, labels, is_skip, keyword_matches) for full
        classification data preservation (Issue #338, #295).

        Note: Confidence values are rounded to 2 decimals at serialization boundary only;
        internal representation (self.all_types) maintains full precision for accuracy.
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
            "all_types": [
                {"section_type": entry["section_type"], "confidence": round(entry["confidence"], 2)}
                for entry in self.all_types
            ],
            "labels": self.labels,
            "is_skip": self.is_skip,
            "keyword_matches": self.keyword_matches,
        }
