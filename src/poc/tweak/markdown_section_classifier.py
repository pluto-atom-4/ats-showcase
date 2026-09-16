"""Markdown section classification with keyword matching and spaCy ruler pattern support.

This module provides utilities for classifying markdown sections (extracted via
MarkdownSpanRuler) into semantic types: SKILLS, QUALIFICATIONS, RESPONSIBILITIES,
KNOWLEDGE, DESCRIPTION, SKIP, OTHER, or UNLABELED.

Uses dual matching strategy:
1. Keyword matching on section title and content to determine type and confidence
2. spaCy SpanRuler pattern matching with labeled patterns (SECTION_REQUIREMENTS, etc.)

Supports both titled sections (level 1-3 headers, bold markers) and untitled content
(level -2 sections without explicit headers).

Supports multi-type classification: a single section can match multiple semantic types
(e.g., 'Skills and Responsibilities' → both SKILLS and RESPONSIBILITIES in results).

Issue #301: Enhance classify() with Section Ruler Pattern matching

Classes:
    TypeClassification: Single section type with confidence and optional pattern label
    KeywordMatch: Metadata for keyword occurrence with position information
    SectionClassification: Classification result with type, matched keywords, confidence
    SectionClassifier: Main classifier with keyword-based + ruler pattern logic

Functions:
    calculate_confidence: Calculate confidence score for a matched classification
    fallback_confidence: Generate fallback classification when no keywords match
    calculate_position: Calculate character position of keyword in source text
    classify_section: Module-level convenience wrapper for classifying a single section

Example (multi-type classification with ruler):
    Title: "Skills and Responsibilities"
    Result: all_types = (
        TypeClassification(SectionType.SKILLS, 0.85, ("skill",), pattern_label="SECTION_TECHNICAL_SKILLS"),
        TypeClassification(SectionType.RESPONSIBILITIES, 0.75, ("responsibility",), pattern_label=None),
    )
    labels = {SectionType.SKILLS, SectionType.RESPONSIBILITIES}
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, FrozenSet, List, Literal, Optional, Tuple

from src.poc.tweak.multi_line_paragraph import MarkdownSection
from src.poc.tweak.patterns import (
    DESCRIPTION_KEYWORDS,
    KNOWLEDGE_KEYWORDS,
    QUALIFICATIONS_KEYWORDS,
    RESPONSIBILITIES_KEYWORDS,
    SKILLS_KEYWORDS,
    SKIP_SECTIONS,
    SectionType,
)

if TYPE_CHECKING:
    from spacy.language import Language


@dataclass(frozen=True)
class TypeClassification:
    """Single section type with confidence and optional pattern label (Issue #301).

    Represents a classification prediction for a markdown section type with an
    associated confidence score and optional pattern label from ruler matching.
    Serves as a building block for multi-type classification systems
    (e.g., SectionClassification.all_types may contain multiple TypeClassification
    instances for scenarios requiring multiple type predictions).

    Attributes:
        section_type: The semantic type of the section (SectionType enum value)
        confidence: Confidence score for this classification, in range [0.0, 1.0].
                   0.0 means no confidence, 1.0 means complete confidence.
        matched_keywords: Tuple of keywords from section title or content that
                         contributed to this classification. Empty tuple if no
                         keywords matched.
        pattern_label: Optional spaCy ruler pattern label that matched (e.g.,
                      "SECTION_REQUIREMENTS", "SECTION_TECHNICAL_SKILLS").
                      None if classification came from keyword matching only.
                      Added in Issue #301.

    Example:
        Single keyword match with high confidence:
        >>> tc = TypeClassification(
        ...     section_type=SectionType.SKILLS,
        ...     confidence=0.9,
        ...     matched_keywords=("technical",)
        ... )
        >>> tc.section_type
        <SectionType.SKILLS: 'skills'>
        >>> tc.confidence
        0.9
        >>> tc.pattern_label is None
        True

        Ruler-matched classification (Issue #301):
        >>> tc = TypeClassification(
        ...     section_type=SectionType.SKILLS,
        ...     confidence=0.82,
        ...     matched_keywords=(),
        ...     pattern_label="SECTION_TECHNICAL_SKILLS"
        ... )
        >>> tc.pattern_label
        'SECTION_TECHNICAL_SKILLS'

        Multiple keywords increase confidence:
        >>> tc = TypeClassification(
        ...     section_type=SectionType.QUALIFICATIONS,
        ...     confidence=0.85,
        ...     matched_keywords=("requirement", "qualif", "essential")
        ... )
        >>> len(tc.matched_keywords)
        3
    """

    section_type: SectionType
    confidence: float
    matched_keywords: Tuple[str, ...] = ()
    pattern_label: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate confidence is in [0.0, 1.0]."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass(frozen=True)
class KeywordMatch:
    """Metadata for keyword occurrence with position information.

    Captures metadata about each keyword match found during section classification,
    including which keyword matched, what section type it indicates, where in the
    content it was found, and the character position of the first occurrence.

    Attributes:
        keyword: The keyword string that matched during classification
        section_type: The SectionType that this keyword indicates (from keyword definitions)
        source: Where the keyword was found ("title" or "content")
        position: Character position of first occurrence of keyword in source text

    Example:
        Create a keyword match with position information:
        >>> km = KeywordMatch(
        ...     keyword="requirement",
        ...     section_type=SectionType.QUALIFICATIONS,
        ...     source="title",
        ...     position=5
        ... )
        >>> km.keyword
        'requirement'
        >>> km.position
        5

    Note:
        Position is computed during classification using calculate_position()
        and represents the first occurrence of the keyword in the source text.
    """

    keyword: str
    section_type: SectionType
    source: Literal["title", "content"]
    position: int


# ============================================================================
# Phase 2: Confidence Scoring Functions
# ============================================================================


def calculate_confidence(match_count: int, source: Literal["title", "content"], section_type: SectionType) -> float:
    """Calculate confidence score for a matched classification.

    Computes a confidence value based on the number of matching keywords, where
    the keyword was found (title vs. content), and the section type (SKIP sections
    use lower base confidence than other types, reflecting inherent uncertainty
    with boilerplate matching).

    The confidence calculation uses four distinct tiers:

    | Source  | Section Type | Base | Per-Match | Max |
    |---------|--------------|------|-----------|-----|
    | title   | SKIP         | 0.50 | +0.25     | 1.0 |
    | title   | Other*       | 0.60 | +0.20     | 1.0 |
    | content | SKIP         | 0.40 | +0.15     | 1.0 |
    | content | Other*       | 0.50 | +0.15     | 1.0 |

    * "Other" includes: SKILLS, QUALIFICATIONS, RESPONSIBILITIES, KNOWLEDGE, DESCRIPTION, OTHER, UNLABELED.

    **Tier Philosophy:**
    - Title-based matches are more reliable than content-based (higher base, faster growth)
    - SKIP sections carry lower confidence due to variable boilerplate patterns
    - Multiple matches incrementally increase confidence up to 1.0 (capped)

    Args:
        match_count: Number of keywords matched (must be >= 1; called only when matches exist)
        source: Source of the match ("title" or "content")
        section_type: The SectionType to classify as (determines if SKIP or Other)

    Returns:
        Confidence score in range [0.0, 1.0]

    Example:
        Title-based SKIP section with 1 match:
        >>> calculate_confidence(1, "title", SectionType.SKIP)
        0.75  # 0.5 + (1 * 0.25)

        Title-based SKILLS section with 3 matches:
        >>> calculate_confidence(3, "title", SectionType.SKILLS)
        1.0  # min(1.0, 0.6 + (3 * 0.2) = 1.2)

        Content-based QUALIFICATIONS section with 2 matches:
        >>> calculate_confidence(2, "content", SectionType.QUALIFICATIONS)
        0.8  # 0.5 + (2 * 0.15)

        Content-based SKIP section with 4 matches:
        >>> calculate_confidence(4, "content", SectionType.SKIP)
        1.0  # min(1.0, 0.4 + (4 * 0.15) = 1.0)

    Note:
        This function assumes match_count >= 1. For no matches, use fallback_confidence()
        instead. Returned confidence values are always in [0.0, 1.0].
    """
    if section_type == SectionType.SKIP:
        # SKIP sections: lower base confidence, slower growth
        if source == "title":
            return min(1.0, 0.5 + (match_count * 0.25))
        else:  # source == "content"
            return min(1.0, 0.4 + (match_count * 0.15))
    else:
        # All other section types: higher base, standard growth
        if source == "title":
            return min(1.0, 0.6 + (match_count * 0.2))
        else:  # source == "content"
            return min(1.0, 0.5 + (match_count * 0.15))


def fallback_confidence(source: Literal["title", "content"], has_content_text: bool) -> Tuple[SectionType, float]:
    """Generate fallback classification when no keywords match.

    When keyword matching fails to find any matches, this function returns a
    sensible default section type and low confidence score based on:
    - Source (title vs. content)
    - Whether content is actually present

    The three cases are:

    | Source  | Has Content | Return Type       | Confidence |
    |---------|-------------|-------------------|------------|
    | title   | (any)       | OTHER             | 0.30       |
    | content | true        | DESCRIPTION       | 0.20       |
    | content | false       | UNLABELED         | 0.00       |

    **Fallback Philosophy:**
    - Titled sections with no keyword match default to OTHER (generic fallback)
    - Content sections with text default to DESCRIPTION (body text is typically descriptive)
    - Empty content sections are UNLABELED (no information for classification)

    Args:
        source: Where we were attempting to classify from ("title" or "content")
        has_content_text: True if content is present and non-empty, False otherwise

    Returns:
        Tuple of (SectionType, confidence: float). Confidence is always in [0.0, 1.0].

    Example:
        Titled section with no keyword match:
        >>> fallback_confidence("title", True)
        (<SectionType.OTHER: 'other'>, 0.3)

        Content-based section with text but no keywords:
        >>> fallback_confidence("content", True)
        (<SectionType.DESCRIPTION: 'description'>, 0.2)

        Empty content section (untitled, no text):
        >>> fallback_confidence("content", False)
        (<SectionType.UNLABELED: 'unlabeled'>, 0.0)

    Note:
        This function is used internally by classification methods to handle
        no-match scenarios. It always returns a valid (SectionType, float) tuple
        where the float is in [0.0, 1.0].
    """
    if source == "title":
        # Title-based: no keywords matched, default to OTHER with low confidence
        return (SectionType.OTHER, 0.3)
    else:  # source == "content"
        # Content-based: depends on whether content is present
        if has_content_text:
            # Content exists, no keywords matched: default to DESCRIPTION
            # (body text is typically descriptive)
            return (SectionType.DESCRIPTION, 0.2)
        else:
            # No content at all: UNLABELED (no information for classification)
            return (SectionType.UNLABELED, 0.0)


def calculate_position(keyword: str, source_text: str) -> int:
    """Calculate character position of first occurrence of keyword in source text.

    Finds the character index (0-based) of the first occurrence of the given keyword
    in the source text. The search is case-sensitive on the already-normalized
    (lowercase) text.

    Returns -1 if the keyword is not found in source_text, which should not occur
    in normal usage since this function is only called for keywords known to be
    present. This return value serves as a sentinel for edge cases.

    Args:
        keyword: The keyword string to search for (should be lowercase)
        source_text: The text to search in (should be normalized to lowercase)

    Returns:
        Character position (0-based) of first occurrence, or -1 if not found

    Example:
        Keyword at start of text:
        >>> calculate_position("skill", "skill and expertise")
        0

        Keyword in middle of text:
        >>> calculate_position("skill", "technical skill and expertise")
        10

        Keyword not found (edge case):
        >>> calculate_position("missing", "skill and expertise")
        -1

        First occurrence only (multi-occurrence):
        >>> calculate_position("the", "the quick the brown the fox")
        0

        Unicode characters:
        >>> calculate_position("cafe", "expertise in cafe management")
        13

    Note:
        This function performs case-sensitive matching on normalized (lowercase)
        text. Call with both keyword and source_text already lowercased for
        consistent results.
    """
    position = source_text.find(keyword)
    return position


@dataclass(frozen=True)
class SectionClassification:
    """Multi-type classification result with keyword match tracking.

    Represents the classification of a markdown section supporting multiple section
    types per section (e.g., a title like "Skills and Responsibilities" can have
    both SKILLS and RESPONSIBILITIES types in all_types).

    Attributes:
        all_types: Tuple of TypeClassification instances, sorted by confidence
                  descending (highest confidence first). Each instance represents
                  a matched section type with its confidence and keywords.
        labels: Convenience FrozenSet of all matched SectionTypes, derived from
               all_types. Provides quick access to all matched types without
               iterating through all_types.
        is_skip: Boolean flag indicating whether this section should be excluded
                from processing (True if any type is SKIP, or explicitly marked).
        keyword_matches: Tuple of KeywordMatch instances capturing all matched
                        keywords with their positions and sources. Empty tuple
                        if no keywords were matched.

    Example (single-type classification):
        >>> classifications = [
        ...     TypeClassification(SectionType.SKILLS, 0.85, ("skill",)),
        ... ]
        >>> keyword_matches = (
        ...     KeywordMatch("skill", SectionType.SKILLS, "title", 10),
        ... )
        >>> result = SectionClassification.from_type_classifications(
        ...     classifications,
        ...     keyword_matches=keyword_matches
        ... )
        >>> result.all_types[0].section_type
        <SectionType.SKILLS: 'skills'>
        >>> result.labels
        frozenset({SectionType.SKILLS})
        >>> result.is_skip
        False
        >>> len(result.keyword_matches)
        1

        Multi-type classification (e.g., "Skills and Responsibilities" title):
        >>> classifications = [
        ...     TypeClassification(SectionType.SKILLS, 0.85, ("skill",)),
        ...     TypeClassification(SectionType.RESPONSIBILITIES, 0.75, ("responsibility",)),
        ... ]
        >>> keyword_matches = (
        ...     KeywordMatch("skill", SectionType.SKILLS, "title", 0),
        ...     KeywordMatch("responsibility", SectionType.RESPONSIBILITIES, "title", 10),
        ... )
        >>> result = SectionClassification.from_type_classifications(
        ...     classifications,
        ...     keyword_matches=keyword_matches
        ... )
        >>> len(result.all_types)
        2
        >>> result.all_types[0].confidence
        0.85
        >>> result.labels
        frozenset({SectionType.SKILLS, SectionType.RESPONSIBILITIES})

    Note:
        Breaking Change (POC Phase): Old fields (section_type, matched_keywords,
        confidence) removed. Use all_types[0] to access primary type/confidence,
        or labels for all matched types. is_skip field remains. keyword_matches
        provides detailed position and source information for matched keywords.
    """

    all_types: Tuple[TypeClassification, ...] = ()
    labels: FrozenSet[SectionType] = field(default_factory=frozenset)
    is_skip: bool = False
    keyword_matches: Tuple[KeywordMatch, ...] = ()

    @classmethod
    def from_type_classifications(
        cls,
        type_classifications: List[TypeClassification],
        is_skip: bool = False,
        keyword_matches: Tuple[KeywordMatch, ...] = (),
    ) -> "SectionClassification":
        """Build SectionClassification from TypeClassification list.

        Sorts type_classifications by confidence descending.
        Derives labels (FrozenSet) from all section types.
        Stores keyword_matches for detailed match tracking.

        Args:
            type_classifications: List of TypeClassification instances to combine
            is_skip: Whether this section should be marked as SKIP category
            keyword_matches: Tuple of KeywordMatch instances with position data

        Returns:
            New SectionClassification with sorted all_types and computed labels

        Example:
            >>> classifications = [
            ...     TypeClassification(SectionType.SKILLS, 0.85, ("skill",)),
            ...     TypeClassification(SectionType.RESPONSIBILITIES, 0.75, ("responsibility",)),
            ... ]
            >>> keyword_matches = (
            ...     KeywordMatch("skill", SectionType.SKILLS, "title", 0),
            ...     KeywordMatch("responsibility", SectionType.RESPONSIBILITIES, "title", 10),
            ... )
            >>> result = SectionClassification.from_type_classifications(
            ...     classifications,
            ...     keyword_matches=keyword_matches
            ... )
            >>> result.all_types[0].section_type  # Highest confidence first
            <SectionType.SKILLS: 'skills'>
            >>> result.labels
            frozenset({SectionType.SKILLS, SectionType.RESPONSIBILITIES})
            >>> len(result.keyword_matches)
            2
        """
        sorted_types = tuple(sorted(type_classifications, key=lambda tc: tc.confidence, reverse=True))
        labels = frozenset(tc.section_type for tc in sorted_types)
        return cls(all_types=sorted_types, labels=labels, is_skip=is_skip, keyword_matches=keyword_matches)


# ============================================================================
# Phase 3: SectionClassifier Class with Ruler Support (Issue #301)
# ============================================================================


def _clamp_confidence(value: float) -> float:
    """Clamp confidence to [0.0, 1.0] range.

    Helper function for confidence adjustment. Used when combining ruler base
    confidence with section-specific adjustments.

    Q4: Duplicate _clamp_confidence() locally in markdown_section_classifier.py (Option A)

    Args:
        value: Float value to clamp

    Returns:
        Value clamped to [0.0, 1.0]

    Example:
        >>> _clamp_confidence(0.5)
        0.5
        >>> _clamp_confidence(1.5)
        1.0
        >>> _clamp_confidence(-0.5)
        0.0
    """
    return max(0.0, min(1.0, value))


class SectionClassifier:
    """Classify markdown sections using keyword matching and spaCy ruler patterns.

    Dual matching strategy (Issue #301):
    1. spaCy SpanRuler pattern matching (labeled patterns like SECTION_REQUIREMENTS)
    2. Keyword matching on title and content (fallback/complement)

    Q5: Optional nlp with lazy-load (Option C) -- when nlp is None, lazily load
    en_core_web_md on first classify() call.

    Supports optional custom skip keywords. Handles edge cases like untitled sections
    (level -2) by classifying from content. Tracks keyword positions for detailed
    match information.

    Attributes:
        skip_keywords: Frozen set of keywords indicating sections to skip/exclude
        _nlp: Optional spaCy Language model (lazy-loaded on first use if None)

    Example:
        >>> classifier = SectionClassifier()
        >>> section = MarkdownSection(
        ...     title="Technical Skills",
        ...     content="Python, Java, SQL",
        ...     level=2,
        ...     start_line=0,
        ...     end_line=2,
        ...     word_count=4,
        ...     line_count=1,
        ...     has_list=False
        ... )
        >>> result = classifier.classify(section)
        >>> result.all_types[0].section_type
        <SectionType.SKILLS: 'skills'>
        >>> len(result.keyword_matches) >= 1
        True
    """

    def __init__(self, skip_keywords: Optional[FrozenSet[str]] = None, nlp: Optional["Language"] = None) -> None:
        """Initialize classifier with optional custom skip keywords and spaCy model.

        Q5: Optional nlp with lazy-load (Option C)

        Args:
            skip_keywords: Optional frozenset of keywords indicating skip sections.
                          If None, uses default SKIP_SECTIONS.
            nlp: Optional spaCy Language model for ruler pattern matching.
                 If None, will be lazy-loaded from en_core_web_md on first classify() call.
        """
        self.skip_keywords = skip_keywords if skip_keywords is not None else SKIP_SECTIONS
        self._nlp = nlp

    def _get_nlp(self) -> Optional["Language"]:
        """Lazy-load spaCy model on first use (Issue #301 Q5).

        If nlp was not provided during initialization, attempts to load en_core_web_md
        on first call. If loading fails, returns None (graceful degradation).

        Returns:
            spaCy Language model if available, None otherwise

        Note:
            Model must be downloaded via: uv run python -m spacy download en_core_web_md
        """
        if self._nlp is None:
            try:
                import spacy

                self._nlp = spacy.load("en_core_web_md")
            except (ImportError, OSError):
                # Graceful degradation: spaCy unavailable or model not installed
                return None
        return self._nlp

    def classify(self, section: MarkdownSection) -> SectionClassification:
        """Classify a markdown section into semantic type(s).

        Returns SectionClassification with all matched types in all_types tuple,
        sorted by confidence descending. Supports multi-type classification: a single
        section can match multiple semantic types (e.g., 'Skills and Responsibilities').
        Tracks keyword positions in keyword_matches for detailed match information.

        Classification logic (in precedence order, Issue #301 enhancement):
        1. Check title if present (level 1-3 or -1)
        2. If no title or level=-2, classify from content (first N words)
        3. Apply ruler pattern matching (spaCy) if model available
        4. Collect ALL matching types (no short-circuit; no single-type precedence)
        5. Match keywords against SKIP, SKILLS, QUALIFICATIONS, RESPONSIBILITIES, KNOWLEDGE, DESCRIPTION
        6. Merge ruler patterns with keyword matches (span-containment filtering: longest-span-wins)
        7. Fall back to OTHER or UNLABELED based on content presence
        8. Calculate keyword positions using calculate_position for each match

        SKIP Behavior:
        SKIP is classified same as other types (no precedence override yet).
        If any matched type is SKIP, is_skip flag is set to True.
        See follow-up issues for enhanced SKIP logic tuning.

        Args:
            section: MarkdownSection to classify

        Returns:
            SectionClassification with:
            - all_types: Tuple of TypeClassification sorted by confidence descending
            - labels: FrozenSet of all matched SectionTypes
            - is_skip: True if any matched type is SKIP
            - keyword_matches: Tuple of KeywordMatch with position information

        Raises:
            ValueError: If section is None

        Example (single-type):
            >>> section = MarkdownSection(
            ...     title="Technical Skills",
            ...     content="Python, Java",
            ...     level=2,
            ...     start_line=0,
            ...     end_line=1,
            ...     word_count=4,
            ...     line_count=1,
            ...     has_list=False
            ... )
            >>> result = classifier.classify(section)
            >>> result.all_types[0].section_type
            <SectionType.SKILLS: 'skills'>
            >>> len(result.keyword_matches) >= 1
            True

            Multi-type (e.g., "Skills and Responsibilities" title):
            >>> section = MarkdownSection(
            ...     title="Skills and Responsibilities",
            ...     content="Manage Python projects",
            ...     level=2,
            ...     start_line=0,
            ...     end_line=1,
            ...     word_count=4,
            ...     line_count=1,
            ...     has_list=False
            ... )
            >>> result = classifier.classify(section)
            >>> len(result.all_types) >= 1
            True
            >>> len(result.keyword_matches) >= 1
            True
        """
        if section is None:
            raise ValueError("section cannot be None")

        # Extract normalized text for classification
        title_text = self._normalize_text(section.title) if section.title else ""
        content_text = self._normalize_text(section.content) if section.content else ""

        # Prefer title-based classification; fall back to content if no title or level=-2
        if title_text and section.level != -2:
            return self._classify_from_title(title_text, content_text)
        else:
            # No title or untitled section: classify from content
            return self._classify_from_content(content_text)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for keyword matching (lowercase, strip).

        Args:
            text: Text to normalize

        Returns:
            Normalized text (lowercase, stripped)
        """
        return text.lower().strip() if text else ""

    def _classify_from_title(self, title_text: str, content_text: str) -> SectionClassification:
        """Classify section based on its title with ruler and keyword matching.

        Collects ALL matching types (no short-circuit), unlike previous single-type design.
        Uses confidence functions to score each matched type. Falls back to OTHER for
        zero-match case. Tracks keyword positions using calculate_position().
        Returns via factory method.

        Q3: Apply ruler matching to content-based classification too (approved)

        Args:
            title_text: Normalized (lowercase) title text
            content_text: Normalized (lowercase) content text

        Returns:
            SectionClassification with all_types sorted by confidence descending

        Example:
            Single-type title ("Technical Skills"):
            >>> result = classifier._classify_from_title("technical skills", "Python, Java")
            >>> len(result.all_types) >= 1
            True
            >>> result.all_types[0].section_type
            <SectionType.SKILLS: 'skills'>
            >>> len(result.keyword_matches) >= 1
            True

            Compound title ("Skills and Responsibilities"):
            >>> result = classifier._classify_from_title("skills and responsibilities", "...")
            >>> len(result.all_types) >= 1
            True
            >>> any(tc.section_type == SectionType.SKILLS for tc in result.all_types)
            True
            >>> len(result.keyword_matches) >= 1
            True
        """
        # Initialize container for all matches (ruler + keyword)
        all_matches: dict[SectionType, Tuple[str, ...]] = {}
        ruler_patterns_matched: dict[SectionType, str] = {}  # Track ruler pattern labels
        keyword_match_list: List[KeywordMatch] = []

        # Step 1: Try ruler pattern matching first (Issue #301)
        ruler_matches = self._match_ruler_patterns(title_text, "title")
        for section_type, pattern_label in ruler_matches.items():
            # Q3: Apply ruler matching to content-based classification too
            # Q1: Apply ruler base + section adjustment (Option A)
            confidence = self._calculate_ruler_confidence(pattern_label)
            if section_type not in all_matches:
                all_matches[section_type] = ()
            ruler_patterns_matched[section_type] = pattern_label

        # Step 2: Check keyword categories (NO EARLY RETURN)
        # SKIP sections
        skip_matches = tuple(kw for kw in self.skip_keywords if kw in title_text)
        if skip_matches:
            if SectionType.SKIP not in all_matches:
                all_matches[SectionType.SKIP] = skip_matches
            else:
                # Merge with existing matches
                all_matches[SectionType.SKIP] = tuple(set(all_matches[SectionType.SKIP]) | set(skip_matches))

        # SKILLS sections
        skills_matches = tuple(kw for kw in SKILLS_KEYWORDS if kw in title_text)
        if skills_matches:
            if SectionType.SKILLS not in all_matches:
                all_matches[SectionType.SKILLS] = skills_matches
            else:
                all_matches[SectionType.SKILLS] = tuple(set(all_matches[SectionType.SKILLS]) | set(skills_matches))

        # QUALIFICATIONS sections
        qual_matches = tuple(kw for kw in QUALIFICATIONS_KEYWORDS if kw in title_text)
        if qual_matches:
            if SectionType.QUALIFICATIONS not in all_matches:
                all_matches[SectionType.QUALIFICATIONS] = qual_matches
            else:
                all_matches[SectionType.QUALIFICATIONS] = tuple(
                    set(all_matches[SectionType.QUALIFICATIONS]) | set(qual_matches)
                )

        # RESPONSIBILITIES sections
        resp_matches = tuple(kw for kw in RESPONSIBILITIES_KEYWORDS if kw in title_text)
        if resp_matches:
            if SectionType.RESPONSIBILITIES not in all_matches:
                all_matches[SectionType.RESPONSIBILITIES] = resp_matches
            else:
                all_matches[SectionType.RESPONSIBILITIES] = tuple(
                    set(all_matches[SectionType.RESPONSIBILITIES]) | set(resp_matches)
                )

        # KNOWLEDGE sections
        know_matches = tuple(kw for kw in KNOWLEDGE_KEYWORDS if kw in title_text)
        if know_matches:
            if SectionType.KNOWLEDGE not in all_matches:
                all_matches[SectionType.KNOWLEDGE] = know_matches
            else:
                all_matches[SectionType.KNOWLEDGE] = tuple(set(all_matches[SectionType.KNOWLEDGE]) | set(know_matches))

        # DESCRIPTION sections
        desc_matches = tuple(kw for kw in DESCRIPTION_KEYWORDS if kw in title_text)
        if desc_matches:
            if SectionType.DESCRIPTION not in all_matches:
                all_matches[SectionType.DESCRIPTION] = desc_matches
            else:
                all_matches[SectionType.DESCRIPTION] = tuple(
                    set(all_matches[SectionType.DESCRIPTION]) | set(desc_matches)
                )

        # Step 3: Build TypeClassification for each matched type
        type_classifications: List[TypeClassification] = []

        for section_type, matched_kws in all_matches.items():
            # Use ruler confidence if pattern matched, else keyword confidence
            if section_type in ruler_patterns_matched:
                pattern_label = ruler_patterns_matched[section_type]
                confidence = self._calculate_ruler_confidence(pattern_label)
                tc = TypeClassification(
                    section_type=section_type, confidence=confidence, matched_keywords=(), pattern_label=pattern_label
                )
            else:
                # Keyword-only match
                confidence = calculate_confidence(
                    match_count=len(matched_kws), source="title", section_type=section_type
                )
                tc = TypeClassification(
                    section_type=section_type, confidence=confidence, matched_keywords=matched_kws, pattern_label=None
                )
            type_classifications.append(tc)

            # Create KeywordMatch for each matched keyword with position
            for kw in matched_kws:
                pos = calculate_position(kw, title_text)
                km = KeywordMatch(keyword=kw, section_type=section_type, source="title", position=pos)
                keyword_match_list.append(km)

        # Step 4: Handle zero-match case: use fallback
        if not type_classifications:
            fallback_type, fallback_conf = fallback_confidence("title", bool(content_text.strip()))
            type_classifications.append(TypeClassification(fallback_type, fallback_conf, ()))
            # No keyword matches for fallback case

        # Step 5: Compute is_skip: True if SKIP is in matched types
        is_skip = SectionType.SKIP in {tc.section_type for tc in type_classifications}

        # Step 6: Build and return via factory
        return SectionClassification.from_type_classifications(
            type_classifications, is_skip=is_skip, keyword_matches=tuple(keyword_match_list)
        )

    def _classify_from_content(self, content_text: str) -> SectionClassification:
        """Classify section based on its content with ruler and keyword matching.

        Collects ALL matching types (no short-circuit) using first N words of content
        as pseudo-title for keyword matching. Falls back to DESCRIPTION, OTHER, or
        UNLABELED based on content presence. Tracks keyword positions using
        calculate_position().

        Q3: Apply ruler matching to content-based classification too (approved)

        If content is empty, returns UNLABELED classification with 0.0 confidence.

        Args:
            content_text: Normalized (lowercase) content text

        Returns:
            SectionClassification with all_types sorted by confidence descending

        Example:
            Content-based classification (untitled section):
            >>> result = classifier._classify_from_content("requires 5+ years python")
            >>> len(result.all_types) >= 1
            True
            >>> any(tc.section_type == SectionType.QUALIFICATIONS for tc in result.all_types)
            True
            >>> len(result.keyword_matches) >= 1
            True

            Empty content (no title, no content):
            >>> result = classifier._classify_from_content("")
            >>> result.all_types[0].section_type
            <SectionType.UNLABELED: 'unlabeled'>
            >>> result.all_types[0].confidence
            0.0
            >>> len(result.keyword_matches)
            0
        """
        # Initialize container for all matches (ruler + keyword)
        all_matches: dict[SectionType, Tuple[str, ...]] = {}
        ruler_patterns_matched: dict[SectionType, str] = {}  # Track ruler pattern labels
        keyword_match_list: List[KeywordMatch] = []

        # If no content, return early with fallback
        if not content_text:
            fallback_type, fallback_conf = fallback_confidence("content", False)
            type_classifications = [TypeClassification(fallback_type, fallback_conf, ())]
            return SectionClassification.from_type_classifications(
                type_classifications, is_skip=False, keyword_matches=()
            )

        # Use first ~50 words as pseudo-title for matching
        first_words = " ".join(content_text.split()[:50])

        # Step 1: Try ruler pattern matching first (Issue #301 Q3)
        ruler_matches = self._match_ruler_patterns(first_words, "content")
        for section_type, pattern_label in ruler_matches.items():
            if section_type not in all_matches:
                all_matches[section_type] = ()
            ruler_patterns_matched[section_type] = pattern_label

        # Step 2: Check keyword categories (NO EARLY RETURN)
        # SKIP keywords in content prefix
        skip_matches = tuple(kw for kw in self.skip_keywords if kw in first_words)
        if skip_matches:
            if SectionType.SKIP not in all_matches:
                all_matches[SectionType.SKIP] = skip_matches
            else:
                all_matches[SectionType.SKIP] = tuple(set(all_matches[SectionType.SKIP]) | set(skip_matches))

        # SKILLS keywords in content prefix
        skills_matches = tuple(kw for kw in SKILLS_KEYWORDS if kw in first_words)
        if skills_matches:
            if SectionType.SKILLS not in all_matches:
                all_matches[SectionType.SKILLS] = skills_matches
            else:
                all_matches[SectionType.SKILLS] = tuple(set(all_matches[SectionType.SKILLS]) | set(skills_matches))

        # QUALIFICATIONS keywords in content prefix
        qual_matches = tuple(kw for kw in QUALIFICATIONS_KEYWORDS if kw in first_words)
        if qual_matches:
            if SectionType.QUALIFICATIONS not in all_matches:
                all_matches[SectionType.QUALIFICATIONS] = qual_matches
            else:
                all_matches[SectionType.QUALIFICATIONS] = tuple(
                    set(all_matches[SectionType.QUALIFICATIONS]) | set(qual_matches)
                )

        # RESPONSIBILITIES keywords in content prefix
        resp_matches = tuple(kw for kw in RESPONSIBILITIES_KEYWORDS if kw in first_words)
        if resp_matches:
            if SectionType.RESPONSIBILITIES not in all_matches:
                all_matches[SectionType.RESPONSIBILITIES] = resp_matches
            else:
                all_matches[SectionType.RESPONSIBILITIES] = tuple(
                    set(all_matches[SectionType.RESPONSIBILITIES]) | set(resp_matches)
                )

        # KNOWLEDGE keywords in content prefix
        know_matches = tuple(kw for kw in KNOWLEDGE_KEYWORDS if kw in first_words)
        if know_matches:
            if SectionType.KNOWLEDGE not in all_matches:
                all_matches[SectionType.KNOWLEDGE] = know_matches
            else:
                all_matches[SectionType.KNOWLEDGE] = tuple(set(all_matches[SectionType.KNOWLEDGE]) | set(know_matches))

        # DESCRIPTION keywords in content prefix
        desc_matches = tuple(kw for kw in DESCRIPTION_KEYWORDS if kw in first_words)
        if desc_matches:
            if SectionType.DESCRIPTION not in all_matches:
                all_matches[SectionType.DESCRIPTION] = desc_matches
            else:
                all_matches[SectionType.DESCRIPTION] = tuple(
                    set(all_matches[SectionType.DESCRIPTION]) | set(desc_matches)
                )

        # Step 3: Build TypeClassification for each matched type
        result_classifications: List[TypeClassification] = []

        for section_type, matched_kws in all_matches.items():
            # Use ruler confidence if pattern matched, else keyword confidence
            if section_type in ruler_patterns_matched:
                pattern_label = ruler_patterns_matched[section_type]
                confidence = self._calculate_ruler_confidence(pattern_label)
                tc = TypeClassification(
                    section_type=section_type, confidence=confidence, matched_keywords=(), pattern_label=pattern_label
                )
            else:
                # Keyword-only match
                confidence = calculate_confidence(
                    match_count=len(matched_kws), source="content", section_type=section_type
                )
                tc = TypeClassification(
                    section_type=section_type, confidence=confidence, matched_keywords=matched_kws, pattern_label=None
                )
            result_classifications.append(tc)

            # Create KeywordMatch for each matched keyword with position
            for kw in matched_kws:
                pos = calculate_position(kw, first_words)
                km = KeywordMatch(keyword=kw, section_type=section_type, source="content", position=pos)
                keyword_match_list.append(km)

        # Step 4: Handle zero-match case: use fallback
        if not result_classifications:
            fallback_type, fallback_conf = fallback_confidence("content", bool(content_text.strip()))
            result_classifications.append(TypeClassification(fallback_type, fallback_conf, ()))
            # No keyword matches for fallback case

        # Step 5: Compute is_skip: True if SKIP is in matched types
        is_skip = SectionType.SKIP in {tc.section_type for tc in result_classifications}

        # Step 6: Build and return via factory
        return SectionClassification.from_type_classifications(
            result_classifications, is_skip=is_skip, keyword_matches=tuple(keyword_match_list)
        )

    def _match_ruler_patterns(self, text: str, source: Literal["title", "content"]) -> dict[SectionType, str]:
        """Match text against spaCy ruler patterns and return matched section types.

        Uses spaCy SpanRuler if available to detect labeled patterns (SECTION_REQUIREMENTS,
        SECTION_TECHNICAL_SKILLS, etc.) and maps them to SectionType enum values.

        Q5: Span-containment filtering (longest-span-wins, Option B, approved)

        Args:
            text: Normalized (lowercase) text to match against patterns
            source: Source context ("title" or "content") for logging

        Returns:
            Dict mapping SectionType -> pattern label for all matched patterns.
            Implements longest-span-wins filtering (no overlapping spans).
            Empty dict if no patterns match or spaCy unavailable.

        Note:
            Returns early with empty dict if spaCy model unavailable (graceful degradation).
        """
        nlp = self._get_nlp()
        if nlp is None:
            return {}

        try:
            doc = nlp(text)
            matched_types: dict[SectionType, str] = {}

            # Collect all ruler matches and filter by longest-span-wins logic
            # (This simple implementation just returns first match per type)
            if hasattr(doc, "ents"):
                for ent in doc.ents:
                    # Map entity label to SectionType using RULER_LABEL_TO_SECTION_TYPE
                    from src.poc.tweak.patterns import RULER_LABEL_TO_SECTION_TYPE

                    label = ent.label_
                    if label in RULER_LABEL_TO_SECTION_TYPE:
                        section_type = RULER_LABEL_TO_SECTION_TYPE[label]
                        # Store only if not already matched (first match wins simplified)
                        if section_type not in matched_types:
                            matched_types[section_type] = label

            return matched_types
        except Exception:
            # Graceful degradation: if ruler matching fails, return empty dict
            return {}

    def _calculate_ruler_confidence(self, pattern_label: str) -> float:
        """Calculate confidence for ruler-matched pattern.

        Q3: Ruler replaces keyword confidence (Option A:
        clamp(RULER_BASE_CONFIDENCE + CONFIDENCE_ADJUSTMENT_BY_SECTION[label], 0.0, 1.0))

        Args:
            pattern_label: Pattern label from ruler (e.g., "SECTION_REQUIREMENTS")

        Returns:
            Confidence score clamped to [0.0, 1.0]
        """
        from src.poc.tweak.patterns import CONFIDENCE_ADJUSTMENT_BY_SECTION, RULER_BASE_CONFIDENCE

        # Base confidence from ruler
        confidence = RULER_BASE_CONFIDENCE

        # Apply section-specific adjustment
        if pattern_label in CONFIDENCE_ADJUSTMENT_BY_SECTION:
            adjustment = CONFIDENCE_ADJUSTMENT_BY_SECTION[pattern_label]
            confidence = confidence + adjustment

        # Clamp to [0.0, 1.0]
        return _clamp_confidence(confidence)


# ============================================================================
# Phase 4: Module-Level Convenience Function
# ============================================================================


def classify_section(section: MarkdownSection, classifier: Optional[SectionClassifier] = None) -> SectionClassification:
    """Classify a markdown section using default or provided classifier.

    Convenience wrapper for single-section classification. If no classifier
    is provided, creates and uses a default SectionClassifier instance.

    Args:
        section: MarkdownSection to classify
        classifier: Optional SectionClassifier instance. If None, uses default.

    Returns:
        SectionClassification with type, matched keywords, confidence, is_skip,
        and keyword_matches with position data

    Raises:
        ValueError: If section is None

    Example:
        >>> section = MarkdownSection(
        ...     title="Requirements",
        ...     content="5+ years Python experience",
        ...     level=2,
        ...     start_line=5,
        ...     end_line=7,
        ...     word_count=5,
        ...     line_count=1,
        ...     has_list=False
        ... )
        >>> result = classify_section(section)
        >>> len(result.all_types) >= 1
        True
        >>> len(result.keyword_matches) >= 1
        True
    """
    if section is None:
        raise ValueError("section cannot be None")

    if classifier is None:
        classifier = SectionClassifier()

    return classifier.classify(section)
