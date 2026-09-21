"""Standalone pattern definitions for SectionRuler matching (Issue #301).

This module contains standalone copies of section ruler patterns, confidence adjustments,
and label mappings. Patterns are duplicated from src/poc/patterns.py to avoid circular
dependencies and support independent POC development.

Contains:
- SectionType: Enum of section types (moved from markdown_section_classifier.py)
- SECTION_RULER_PATTERNS: SpanRuler patterns (token-based + regex-based)
- CONFIDENCE_ADJUSTMENT_BY_SECTION: Section-specific confidence boosts/penalties
- SECTION_DISPLAY_NAMES: Human-readable section labels
- RULER_LABEL_TO_SECTION_TYPE: Mapping from ruler labels to SectionType enum values
- RULER_BASE_CONFIDENCE: Base confidence for ruler-matched patterns
- KEYWORD CLASSIFICATION CONSTANTS: Semantic section keywords (Issue #303)

Issue #301: Enhance classify() with Section Ruler Pattern matching
Issue #303: Extract keyword classification constants to centralize configuration
"""

from enum import Enum
from typing import Any, Dict, FrozenSet, List, Tuple

# =============================================================================
# SECTION TYPE ENUM (Moved from markdown_section_classifier.py)
# =============================================================================
# Moved here to avoid circular dependency when markdown_section_classifier imports
# from patterns.py and patterns.py needs SectionType for type hints.


class SectionType(Enum):
    """Semantic classification of a markdown section.

    Enum Values:
        SKILLS: Technical skills, abilities, competencies (e.g., "Skills", "Technical")
        QUALIFICATIONS: Required or desired qualifications (e.g., "Requirements", "Qualifications")
        RESPONSIBILITIES: Job duties and responsibilities (e.g., "Responsibilities", "Duties")
        KNOWLEDGE: Knowledge and experience (e.g., "Knowledge", "Experience")
        DESCRIPTION: General job or role description (e.g., "Description", "Summary")
        SKIP: Boilerplate sections to exclude (e.g., "Benefits", "Company Info", "Legal")
        OTHER: Sections that don't fit primary categories
        UNLABELED: Sections with no title and unclassifiable content
    """

    SKILLS = "skills"
    QUALIFICATIONS = "qualifications"
    RESPONSIBILITIES = "responsibilities"
    KNOWLEDGE = "knowledge"
    DESCRIPTION = "description"
    SKIP = "skip"
    OTHER = "other"
    UNLABELED = "unlabeled"


# =============================================================================
# SECTION RULER PATTERNS (SpanRuler)
# =============================================================================
# Hybrid approach: token-based patterns for single-word headers,
# regex-based patterns for multi-word headers and special chars.
#
# Pattern dict structure: {"label": str, "pattern": str | List[Dict]}
# - Token pattern: List of token attribute dicts (spaCy format)
# - Regex pattern: Single regex string (requires type: "regex")
#
# Copied from src/poc/patterns.py (Issue #301 Phase 2)

SECTION_RULER_PATTERNS: List[Dict[str, Any]] = [
    # =================================================================
    # TARGET SECTIONS (extract requirements from these)
    # =================================================================
    # TOKEN PATTERNS (Multi-word headers - tokenized to match spaCy output)
    {
        "label": "SECTION_KNOWLEDGE_SKILLS",
        "pattern": [
            {"LOWER": "knowledge"},
            {"IS_PUNCT": True, "OP": "?"},  # optional comma
            {"LOWER": "skills"},
            {"LOWER": {"IN": ["&", "and"]}},
            {"LOWER": "abilities"},
        ],
    },
    {
        "label": "SECTION_IN_OFFICE",
        "pattern": [
            {"LOWER": {"IN": ["in"]}},
            {"LOWER": "office"},
            {"LOWER": {"IN": ["requirements", "location"]}},
        ],
    },
    {
        "label": "SECTION_WHAT_YOU_DO",
        "pattern": [
            {"LOWER": "what"},
            {"LOWER": {"IN": ["you'll", "you"]}},
            {"IS_PUNCT": False, "OP": "?"},  # optional 'll or will
            {"LOWER": "do"},
        ],
    },
    # TOKEN PATTERNS (Single-word headers, backward compatible)
    {
        "label": "SECTION_REQUIREMENTS",
        "pattern": [
            {"LOWER": "requirements"},
        ],
    },
    {
        "label": "SECTION_QUALIFICATIONS",
        "pattern": [
            {"LOWER": "qualifications"},
        ],
    },
    {
        "label": "SECTION_TECHNICAL_SKILLS",
        "pattern": r"(?i)technical\s+skills",
        "type": "regex",
    },
    {
        "label": "SECTION_PREFERRED_SKILLS",
        "pattern": [
            {"LOWER": "preferred"},
            {"LOWER": "skills", "OP": "?"},
        ],
    },
    {
        "label": "SECTION_NICE_TO_HAVE",
        "pattern": [
            {"LOWER": "nice"},
            {"LOWER": "to"},
            {"LOWER": "have"},
        ],
    },
    {
        "label": "SECTION_EDUCATION",
        "pattern": [
            {"LOWER": "education"},
        ],
    },
    {
        "label": "SECTION_EXPERIENCE",
        "pattern": r"(?i)(?:required\s+)?(?:professional\s+)?experience(?:\s+(?:section|level|required))?(?:\s*$|\n)",
        "type": "regex",
    },
    # =================================================================
    # FILTER SECTIONS (skip extraction from these)
    # =================================================================
    {
        "label": "SECTION_BENEFITS",
        "pattern": [
            {"LOWER": "benefits"},
        ],
    },
    {
        "label": "SECTION_COMPENSATION",
        "pattern": [
            {"LOWER": {"IN": ["salary", "compensation", "pay"]}},
        ],
    },
    {
        "label": "SECTION_HIRING_PROCESS",
        "pattern": [
            {"LOWER": {"IN": ["hiring", "application", "process"]}},
        ],
    },
]


# =============================================================================
# CONFIDENCE ADJUSTMENTS BY SECTION
# =============================================================================
# Applied to base pattern confidence when extracting from specific sections.
# Range: -0.50 to +0.50. Final confidence clamped to [0.0, 1.0].
# Copied from src/poc/patterns.py (Issue #301 Phase 2)

CONFIDENCE_ADJUSTMENT_BY_SECTION: Dict[str, float] = {
    # High priority sections (explicit requirements)
    "SECTION_REQUIREMENTS": 0.15,
    "SECTION_QUALIFICATIONS": 0.10,
    "SECTION_TECHNICAL_SKILLS": 0.12,
    "SECTION_KNOWLEDGE_SKILLS": 0.12,  # NEW: explicit "Skills & Abilities" section
    # Medium priority sections
    "SECTION_EXPERIENCE": 0.08,
    "SECTION_IN_OFFICE": 0.08,  # NEW: location/on-site requirement
    "SECTION_EDUCATION": 0.05,
    # Lower priority sections
    "SECTION_PREFERRED_SKILLS": -0.15,
    "SECTION_NICE_TO_HAVE": -0.25,
    "SECTION_WHAT_YOU_DO": -0.05,  # NEW: responsibilities, not requirements
    # Filter sections (exclude from extraction)
    "SECTION_BENEFITS": -0.50,
    "SECTION_COMPENSATION": -0.50,
    "SECTION_HIRING_PROCESS": -0.50,
}


# =============================================================================
# SECTION DISPLAY NAMES (Human-Readable Labels)
# =============================================================================
# Copied from src/poc/patterns.py (Issue #301 Phase 2)

SECTION_DISPLAY_NAMES: Dict[str, str] = {
    # Token-based patterns
    "SECTION_REQUIREMENTS": "Requirements",
    "SECTION_QUALIFICATIONS": "Qualifications",
    "SECTION_TECHNICAL_SKILLS": "Technical Skills",
    "SECTION_PREFERRED_SKILLS": "Preferred Skills",
    "SECTION_NICE_TO_HAVE": "Nice to Have",
    "SECTION_EDUCATION": "Education",
    "SECTION_EXPERIENCE": "Experience",
    # Regex-based patterns (Issue #265)
    "SECTION_KNOWLEDGE_SKILLS": "Knowledge, Skills & Abilities",
    "SECTION_IN_OFFICE": "In Office Requirements",
    "SECTION_WHAT_YOU_DO": "What You'll Do",
    # Filter sections
    "SECTION_BENEFITS": "Benefits",
    "SECTION_COMPENSATION": "Compensation",
    "SECTION_HIRING_PROCESS": "Hiring Process",
}


# =============================================================================
# RULER LABEL TO SECTION TYPE MAPPING (Gate 1 Approved)
# =============================================================================
# Maps ruler pattern labels to existing SectionType enum values.
# Q2: Map ruler labels down to 8 existing SectionType values (Option A)
# Q4: Duplicate patterns.py locally (Option A)

RULER_LABEL_TO_SECTION_TYPE: Dict[str, SectionType] = {
    # Target sections
    "SECTION_KNOWLEDGE_SKILLS": SectionType.SKILLS,
    "SECTION_IN_OFFICE": SectionType.QUALIFICATIONS,  # Gate 1 approved
    "SECTION_WHAT_YOU_DO": SectionType.RESPONSIBILITIES,
    "SECTION_REQUIREMENTS": SectionType.QUALIFICATIONS,
    "SECTION_QUALIFICATIONS": SectionType.QUALIFICATIONS,
    "SECTION_TECHNICAL_SKILLS": SectionType.SKILLS,
    "SECTION_PREFERRED_SKILLS": SectionType.SKILLS,
    "SECTION_NICE_TO_HAVE": SectionType.SKILLS,  # Gate 1 approved
    "SECTION_EDUCATION": SectionType.QUALIFICATIONS,  # Gate 1 approved
    "SECTION_EXPERIENCE": SectionType.KNOWLEDGE,
    # Filter sections
    "SECTION_BENEFITS": SectionType.SKIP,
    "SECTION_COMPENSATION": SectionType.SKIP,
    "SECTION_HIRING_PROCESS": SectionType.SKIP,
}


# =============================================================================
# RULER BASE CONFIDENCE (Gate 1 Open Q1 Approved)
# =============================================================================
# Base confidence for ruler-matched patterns (before section adjustment).
# Q1: RULER_BASE_CONFIDENCE = 0.70 (approved)

RULER_BASE_CONFIDENCE: float = 0.70


# =============================================================================
# KEYWORD CLASSIFICATION CONSTANTS (Issue #303)
# =============================================================================
# Keywords used for semantic section classification in SectionClassifier.
# Extracted from markdown_section_classifier.py to centralize configuration.
# Source: lines 490-562 of markdown_section_classifier.py

SKIP_SECTIONS: FrozenSet[str] = frozenset(
    {
        "benefits",
        "compensation",
        "salary",
        "pay range",
        "401",
        "retirement",
        "insurance",
        "health",
        "dental",
        "vision",
        "pto",
        "vacation",
        "about",
        "company",
        "culture",
        "commitment",
        "team",
        "our",
        "equal opportunity",
        "eoe",
        "affirmative action",
        "disability",
        "background check",
        "export control",
        "security clearance",
        "visa",
        "apply",
        "posting date",
        "posted",
        "application close",
        "codevue",
        "shift",
        "location",
        "work location",
        "travel",
        "working condition",
        "fte",
        "temporary",
        "education:",
        "hiring practice",
        "bargaining",
        "conflict of interest",
        "drug free",
        "e-verify",
        "right to work",
        "safety sensitive",
        "technical assessment",
        "total rewards",
        "union",
        "contingent upon award",
        "relocation",
        "hourly",
    }
)

# Keywords indicating skills sections
# Source: src/tokenization/preprocessor.py:1557 & _classify_section_from_header (L1156)
SKILLS_KEYWORDS: Tuple[str, ...] = ("skill", "technical", "core", "competency", "ability", "expertise", "proficiency")

# Keywords indicating qualifications/requirements sections
# Source: _classify_section_from_header (L1154)
QUALIFICATIONS_KEYWORDS: Tuple[str, ...] = ("requirement", "qualif", "essential")

# Keywords indicating responsibilities sections
# Source: _classify_section_from_header (L1160)
RESPONSIBILITIES_KEYWORDS: Tuple[str, ...] = ("respons", "duty", "what you")

# Keywords indicating knowledge/experience sections
# Source: _classify_section_from_header (L1158)
KNOWLEDGE_KEYWORDS: Tuple[str, ...] = ("knowledge", "experience")

# Keywords indicating description/overview sections
DESCRIPTION_KEYWORDS: Tuple[str, ...] = ("description", "overview", "summary", "about", "intro")
