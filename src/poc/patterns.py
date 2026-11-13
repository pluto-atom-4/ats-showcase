"""Centralized pattern definitions for POC-C section-aware extraction.

Contains:
- SECTION_RULER_PATTERNS: SpanRuler patterns (token-based + regex-based)
- CONFIDENCE_ADJUSTMENT_BY_SECTION: Section-specific confidence boosts/penalties
- SECTION_DISPLAY_NAMES: Human-readable section labels
- DEFAULT_TARGET_SECTIONS: Sections to extract requirements from

Issue #265: Redesigned to support multi-word section headers via regex patterns.
"""

from typing import Any, Dict, List

# Regex entries need "type": "regex" (a bare string is not a token pattern).
SECTION_RULER_PATTERNS: List[Dict[str, Any]] = [
    {
        "label": "SECTION_KNOWLEDGE_SKILLS",
        "pattern": [
            {"LOWER": "knowledge"},
            {"IS_PUNCT": True, "OP": "?"},
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
            # "you'll" tokenizes as [you, 'll]; this optional token is the 'll or "will", which is not punctuation.
            {"IS_PUNCT": False, "OP": "?"},
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


# Added to base pattern confidence; range -0.50 to +0.50, final confidence clamped to [0.0, 1.0].
CONFIDENCE_ADJUSTMENT_BY_SECTION: Dict[str, float] = {
    "SECTION_REQUIREMENTS": 0.15,
    "SECTION_QUALIFICATIONS": 0.10,
    "SECTION_TECHNICAL_SKILLS": 0.12,
    "SECTION_KNOWLEDGE_SKILLS": 0.12,
    "SECTION_EXPERIENCE": 0.08,
    "SECTION_IN_OFFICE": 0.08,
    "SECTION_EDUCATION": 0.05,
    "SECTION_PREFERRED_SKILLS": -0.15,
    "SECTION_NICE_TO_HAVE": -0.25,
    "SECTION_WHAT_YOU_DO": -0.05,
    "SECTION_BENEFITS": -0.50,
    "SECTION_COMPENSATION": -0.50,
    "SECTION_HIRING_PROCESS": -0.50,
}


SECTION_DISPLAY_NAMES: Dict[str, str] = {
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
    "SECTION_BENEFITS": "Benefits",
    "SECTION_COMPENSATION": "Compensation",
    "SECTION_HIRING_PROCESS": "Hiring Process",
}


# SECTION_WHAT_YOU_DO is intentionally excluded (responsibilities, not requirements; penalty -0.05).
DEFAULT_TARGET_SECTIONS: List[str] = [
    "SECTION_REQUIREMENTS",
    "SECTION_QUALIFICATIONS",
    "SECTION_TECHNICAL_SKILLS",
    "SECTION_PREFERRED_SKILLS",
    "SECTION_NICE_TO_HAVE",
    "SECTION_EDUCATION",
    "SECTION_EXPERIENCE",
    "SECTION_KNOWLEDGE_SKILLS",
    "SECTION_IN_OFFICE",
]
