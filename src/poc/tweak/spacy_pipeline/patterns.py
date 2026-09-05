"""Consolidated extraction patterns for requirement, skill, and technology processors.

Combines patterns from three separate sources:
- REQUIREMENT_PATTERNS: Pattern-based requirement detection (from requirement_classifier.py)
- SKILL_VERBS: Action verbs for skill extraction (from src.poc.skills.patterns.py)
- TECH_TERMS: Technology/framework terms (from src.poc.technologies.patterns.py)

Issue #321: Consolidate patterns for batch processing pipeline.
"""

from typing import List, Set, TypedDict


class RequirementPattern(TypedDict):
    """Type definition for requirement pattern dict."""

    trigger: str
    regex: str
    confidence: float
    priority: int


# =============================================================================
# REQUIREMENT PATTERNS (from src/poc/requirement_patterns.py)
# =============================================================================

REQUIREMENT_PATTERNS: List[RequirementPattern] = [
    # TIER 1: High-confidence (0.90-0.95) - Mandatory language
    {
        "trigger": "required",
        "regex": r"\brequired\b",
        "confidence": 0.95,
        "priority": 1,
    },
    {
        "trigger": "must",
        "regex": r"\bmust\s+(?:have|be|possess|know|understand)",
        "confidence": 0.93,
        "priority": 1,
    },
    {
        "trigger": "essential",
        "regex": r"\bessential\b",
        "confidence": 0.90,
        "priority": 1,
    },
    {
        "trigger": "mandatory",
        "regex": r"\bmandatory\b",
        "confidence": 0.92,
        "priority": 1,
    },
    {
        "trigger": "ability to",
        "regex": r"\bability\s+to\b",
        "confidence": 0.92,
        "priority": 1,
    },
    {
        "trigger": "experience with",
        "regex": r"\b(?:experience|background)\s+(?:with|in)\b",
        "confidence": 0.88,
        "priority": 1,
    },
    {
        "trigger": "proficiency",
        "regex": r"\bproficiency\b",
        "confidence": 0.91,
        "priority": 1,
    },
    {
        "trigger": "knowledge of",
        "regex": r"\bknowledge\s+of\b",
        "confidence": 0.85,
        "priority": 1,
    },
    {
        "trigger": "understanding of",
        "regex": r"\bunderstanding\s+of\b",
        "confidence": 0.83,
        "priority": 1,
    },
    # TIER 2: Medium-confidence (0.65-0.80) - Softer requirements
    {
        "trigger": "should",
        "regex": r"\bshould\s+(?:have|know|be|possess)",
        "confidence": 0.70,
        "priority": 2,
    },
    {
        "trigger": "prefer",
        "regex": r"\b(?:prefer|preferred)\b",
        "confidence": 0.65,
        "priority": 2,
    },
    {
        "trigger": "bachelor's degree",
        "regex": r"\b(?:bachelor's?|master's?|phd)\s+(?:degree|in)\b",
        "confidence": 0.89,
        "priority": 2,
    },
    {
        "trigger": "years of",
        "regex": r"\b(\d+\+?)\s+years?\s+(?:of|in)\b",
        "confidence": 0.80,
        "priority": 2,
    },
    # TIER 3: Lower-confidence (0.40-0.55) - Nice-to-have, aspirational
    {
        "trigger": "nice to have",
        "regex": r"\bnice\s+to\s+have\b",
        "confidence": 0.40,
        "priority": 3,
    },
    {
        "trigger": "ideal",
        "regex": r"\bideal\b",
        "confidence": 0.55,
        "priority": 3,
    },
    {
        "trigger": "bonus",
        "regex": r"\bbonus\b",
        "confidence": 0.45,
        "priority": 3,
    },
    # BULLET-SPECIFIC PATTERNS (extracted from bullets)
    {
        "trigger": "years_in_bullet",
        "regex": r"\b(\d+\+?)\s+years?\b",
        "confidence": 0.85,
        "priority": 2,
    },
    {
        "trigger": "ability_in_bullet",
        "regex": r"\bability\b",
        "confidence": 0.90,
        "priority": 1,
    },
    {
        "trigger": "required_prefix",
        "regex": r"\brequired\b",
        "confidence": 0.95,
        "priority": 1,
    },
    {
        "trigger": "degree_in_bullet",
        "regex": r"\b(?:bachelor's?|master's?|phd|degree)\b",
        "confidence": 0.92,
        "priority": 2,
    },
    # PHASE C EXPANSION: Education Patterns (4 patterns)
    {
        "trigger": "degree abbreviation",
        "regex": r"\b(?:BS\+|MS\+|BA\+|MA\+|BS|MS|BA|MA|PhD)\b",
        "confidence": 0.89,
        "priority": 2,
    },
    {
        "trigger": "degree",
        "regex": r"\b(?:bachelor's?|master's?|phd|bs|ms|ba|ma)\s+(?:degree|in|of)?\b",
        "confidence": 0.89,
        "priority": 2,
    },
    {
        "trigger": "certification",
        "regex": r"\b(?:certified?|certification)\s+(?:in|by)?\b",
        "confidence": 0.80,
        "priority": 2,
    },
    {
        "trigger": "qualified in",
        "regex": r"\b(?:qualified|qualification)\s+(?:in|with)\b",
        "confidence": 0.78,
        "priority": 2,
    },
    # PHASE C EXPANSION: Location/On-site Patterns (2 patterns)
    {
        "trigger": "on-site location",
        "regex": r"\b(?:on-site|on site|office|in-office|remote|hybrid|office-based)\b",
        "confidence": 0.85,
        "priority": 2,
    },
    {
        "trigger": "location based",
        "regex": r"\b(?:location|based\s+in|located\s+in|work\s+(?:from|in))\b",
        "confidence": 0.75,
        "priority": 2,
    },
    # PHASE C EXPANSION: Soft Skill Patterns (4 patterns)
    {
        "trigger": "communication skills",
        "regex": r"\b(?:communicat(?:e|ion|or)|written|verbal|presentation)\s+(?:skills?|abilities?)\b",
        "confidence": 0.82,
        "priority": 2,
    },
    {
        "trigger": "leadership mentoring",
        "regex": r"\b(?:leadership|mentor(?:ing)?|team\s+lead|technical\s+lead)\b",
        "confidence": 0.81,
        "priority": 2,
    },
    {
        "trigger": "teamwork collaboration",
        "regex": r"\b(?:teamwork|collaboration|collaborat(?:e|ive)|cross-functional|team\s+player)\b",
        "confidence": 0.79,
        "priority": 2,
    },
    {
        "trigger": "strong attribute",
        "regex": r"\bstrong\s+(?:experience|understanding|expertise|ability|skills?|background)\b",
        "confidence": 0.76,
        "priority": 2,
    },
]


# =============================================================================
# SKILL PATTERNS (from src/poc/skills/patterns.py)
# =============================================================================

SKILL_VERBS: List[str] = [
    "architect",
    "build",
    "communicate",
    "define",
    "deploy",
    "design",
    "develop",
    "drive",
    "execute",
    "explain",
    "implement",
    "innovate",
    "integrate",
    "lead",
    "mentor",
    "model",
    "optimize",
    "own",
    "partner",
    "prioritize",
    "research",
    "scale",
    "scope",
    "validate",
]


# =============================================================================
# TECHNOLOGY PATTERNS (from src/poc/technologies/patterns.py)
# =============================================================================

TECH_TERMS: Set[str] = {
    # --- Carbon Robotics / AI / Robotics Specific ---
    "PyTorch",
    "C++",
    "computer vision",
    "vision transformers",
    "anchor-free detectors",
    "embeddings",
    "web services",
    "ADAS",
    "sensor fusion",
    "perception pipelines",
    "real-time inference",
    "Large Plant Model",
    "LPM",
    # --- Languages ---
    "python",
    "java",
    "javascript",
    "typescript",
    "rust",
    "go",
    "golang",
    "c#",
    # --- Frameworks & Libraries ---
    "react",
    "angular",
    "vue",
    "django",
    "flask",
    "spring",
    "tensorflow",
    "sklearn",
    # --- Cloud & Infrastructure ---
    "aws",
    "azure",
    "gcp",
    "kubernetes",
    "docker",
    # --- Databases & Search ---
    "postgresql",
    "mongodb",
    "redis",
    "elasticsearch",
    # --- Tools & Collaboration ---
    "git",
    "github",
    "gitlab",
    "jira",
}
