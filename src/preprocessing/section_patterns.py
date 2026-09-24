"""Section ruler patterns for requirement extraction (Issue #281).

Promoted from src/poc/patterns.py for production use.
Contains centralized section pattern definitions for SpanRuler-based section detection:
- SECTION_RULER_PATTERNS: SpanRuler patterns (token-based + regex-based)
- CONFIDENCE_ADJUSTMENT_BY_SECTION: Section-specific confidence boosts/penalties
- SECTION_DISPLAY_NAMES: Human-readable section labels
- DEFAULT_TARGET_SECTIONS: Sections to extract requirements from
- FILTER_SECTIONS: Sections to skip during extraction

No spaCy imports; pure data structures suitable for any section detection system.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class SectionLabel(StrEnum):
    """Section labels for requirement extraction.

    Each label's value starts with "SECTION_" and matches the pattern dict labels
    in SECTION_RULER_PATTERNS.
    """

    REQUIREMENTS = "SECTION_REQUIREMENTS"
    QUALIFICATIONS = "SECTION_QUALIFICATIONS"
    TECHNICAL_SKILLS = "SECTION_TECHNICAL_SKILLS"
    KNOWLEDGE_SKILLS = "SECTION_KNOWLEDGE_SKILLS"
    IN_OFFICE = "SECTION_IN_OFFICE"
    WHAT_YOU_DO = "SECTION_WHAT_YOU_DO"
    PREFERRED_SKILLS = "SECTION_PREFERRED_SKILLS"
    NICE_TO_HAVE = "SECTION_NICE_TO_HAVE"
    EDUCATION = "SECTION_EDUCATION"
    EXPERIENCE = "SECTION_EXPERIENCE"
    BENEFITS = "SECTION_BENEFITS"
    COMPENSATION = "SECTION_COMPENSATION"
    HIRING_PROCESS = "SECTION_HIRING_PROCESS"


SECTION_RULER_PATTERNS: tuple[dict[str, Any], ...] = (
    # =================================================================
    # TARGET SECTIONS (extract requirements from these)
    # =================================================================
    # TOKEN PATTERNS (Multi-word headers - tokenized to match spaCy output)
    {
        "label": SectionLabel.KNOWLEDGE_SKILLS.value,
        "pattern": [
            {"LOWER": "knowledge"},
            {"IS_PUNCT": True, "OP": "?"},  # optional comma
            {"LOWER": "skills"},
            {"LOWER": {"IN": ["&", "and"]}},
            {"LOWER": "abilities"},
        ],
    },
    {
        "label": SectionLabel.IN_OFFICE.value,
        "pattern": [
            {"LOWER": {"IN": ["in"]}},
            {"LOWER": "office"},
            {"LOWER": {"IN": ["requirements", "location"]}},
        ],
    },
    {
        "label": SectionLabel.WHAT_YOU_DO.value,
        "pattern": [
            {"LOWER": "what"},
            {"LOWER": {"IN": ["you'll", "you"]}},
            {"IS_PUNCT": False, "OP": "?"},  # optional 'll or will
            {"LOWER": "do"},
        ],
    },
    # TOKEN PATTERNS (Single-word headers, backward compatible)
    {
        "label": SectionLabel.REQUIREMENTS.value,
        "pattern": [
            {"LOWER": "requirements"},
        ],
    },
    {
        "label": SectionLabel.QUALIFICATIONS.value,
        "pattern": [
            {"LOWER": "qualifications"},
        ],
    },
    {
        "label": SectionLabel.TECHNICAL_SKILLS.value,
        "pattern": r"(?i)technical\s+skills",
        "type": "regex",
    },
    {
        "label": SectionLabel.PREFERRED_SKILLS.value,
        "pattern": [
            {"LOWER": "preferred"},
            {"LOWER": "skills", "OP": "?"},
        ],
    },
    {
        "label": SectionLabel.NICE_TO_HAVE.value,
        "pattern": [
            {"LOWER": "nice"},
            {"LOWER": "to"},
            {"LOWER": "have"},
        ],
    },
    {
        "label": SectionLabel.EDUCATION.value,
        "pattern": [
            {"LOWER": "education"},
        ],
    },
    {
        "label": SectionLabel.EXPERIENCE.value,
        "pattern": r"(?i)(?:required\s+)?(?:professional\s+)?experience(?:\s+(?:section|level|required))?(?:\s*$|\n)",
        "type": "regex",
    },
    # =================================================================
    # FILTER SECTIONS (skip extraction from these)
    # =================================================================
    {
        "label": SectionLabel.BENEFITS.value,
        "pattern": [
            {"LOWER": "benefits"},
        ],
    },
    {
        "label": SectionLabel.COMPENSATION.value,
        "pattern": [
            {"LOWER": {"IN": ["salary", "compensation", "pay"]}},
        ],
    },
    {
        "label": SectionLabel.HIRING_PROCESS.value,
        "pattern": [
            {"LOWER": {"IN": ["hiring", "application", "process"]}},
        ],
    },
)


CONFIDENCE_ADJUSTMENT_BY_SECTION: Mapping[SectionLabel, float] = MappingProxyType(
    {
        # High priority sections (explicit requirements)
        SectionLabel.REQUIREMENTS: 0.15,
        SectionLabel.QUALIFICATIONS: 0.10,
        SectionLabel.TECHNICAL_SKILLS: 0.12,
        SectionLabel.KNOWLEDGE_SKILLS: 0.12,
        # Medium priority sections
        SectionLabel.EXPERIENCE: 0.08,
        SectionLabel.IN_OFFICE: 0.08,
        SectionLabel.EDUCATION: 0.05,
        # Lower priority sections
        SectionLabel.PREFERRED_SKILLS: -0.15,
        SectionLabel.NICE_TO_HAVE: -0.25,
        SectionLabel.WHAT_YOU_DO: -0.05,
        # Filter sections (exclude from extraction)
        SectionLabel.BENEFITS: -0.50,
        SectionLabel.COMPENSATION: -0.50,
        SectionLabel.HIRING_PROCESS: -0.50,
    }
)


SECTION_DISPLAY_NAMES: Mapping[SectionLabel, str] = MappingProxyType(
    {
        # Token-based patterns
        SectionLabel.REQUIREMENTS: "Requirements",
        SectionLabel.QUALIFICATIONS: "Qualifications",
        SectionLabel.TECHNICAL_SKILLS: "Technical Skills",
        SectionLabel.PREFERRED_SKILLS: "Preferred Skills",
        SectionLabel.NICE_TO_HAVE: "Nice to Have",
        SectionLabel.EDUCATION: "Education",
        SectionLabel.EXPERIENCE: "Experience",
        # Regex-based patterns
        SectionLabel.KNOWLEDGE_SKILLS: "Knowledge, Skills & Abilities",
        SectionLabel.IN_OFFICE: "In Office Requirements",
        SectionLabel.WHAT_YOU_DO: "What You'll Do",
        # Filter sections
        SectionLabel.BENEFITS: "Benefits",
        SectionLabel.COMPENSATION: "Compensation",
        SectionLabel.HIRING_PROCESS: "Hiring Process",
    }
)


FILTER_SECTIONS: frozenset[SectionLabel] = frozenset(
    {SectionLabel.BENEFITS, SectionLabel.COMPENSATION, SectionLabel.HIRING_PROCESS}
)


DEFAULT_TARGET_SECTIONS: frozenset[SectionLabel] = frozenset(
    {
        SectionLabel.REQUIREMENTS,
        SectionLabel.QUALIFICATIONS,
        SectionLabel.TECHNICAL_SKILLS,
        SectionLabel.PREFERRED_SKILLS,
        SectionLabel.NICE_TO_HAVE,
        SectionLabel.EDUCATION,
        SectionLabel.EXPERIENCE,
        SectionLabel.KNOWLEDGE_SKILLS,
        SectionLabel.IN_OFFICE,
        # WHAT_YOU_DO intentionally excluded: responsibilities, not requirements (boost: -0.05)
    }
)


__all__ = [
    "SectionLabel",
    "SECTION_RULER_PATTERNS",
    "CONFIDENCE_ADJUSTMENT_BY_SECTION",
    "SECTION_DISPLAY_NAMES",
    "FILTER_SECTIONS",
    "DEFAULT_TARGET_SECTIONS",
]
