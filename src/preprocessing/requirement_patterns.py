"""Requirement pattern definitions for sentence-level requirement classification.

Contains hardcoded trigger patterns organized by tier and category:
- Tier 1: High-confidence mandatory language (0.90-0.95)
- Tier 2: Medium-confidence softer requirements (0.65-0.80)
- Tier 3: Lower-confidence nice-to-have patterns (0.40-0.55)
- Bullet-specific patterns for extraction from bullet points
- Phase C expansion: Education, Location, Soft Skills patterns

Issue #281: Promoted from src/poc/requirement_patterns.py and
src/poc/requirement_classifier.py for production use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypedDict


class RequirementPattern(TypedDict):
    """Type definition for requirement pattern dict."""

    trigger: str
    regex: str
    confidence: float
    priority: int


# =============================================================================
# HARDCODED TRIGGER PATTERNS (Tier-Based)
# =============================================================================

REQUIREMENT_PATTERNS: tuple[RequirementPattern, ...] = (
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
    # =============================================================================
    # PHASE C EXPANSION: Education Patterns (4 patterns)
    # =============================================================================
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
    # =============================================================================
    # PHASE C EXPANSION: Location/On-site Patterns (2 patterns)
    # =============================================================================
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
    # =============================================================================
    # PHASE C EXPANSION: Soft Skill Patterns (4 patterns)
    # =============================================================================
    {
        "trigger": "communication skills",
        "regex": (
            r"\b(?:communicat(?:e|ion|or)|written|verbal|presentation)\s+"
            r"(?:skills?|abilities?)\b"
        ),
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
        "regex": (
            r"\b(?:teamwork|collaboration|collaborat(?:e|ive)|cross-functional|"
            r"team\s+player)\b"
        ),
        "confidence": 0.79,
        "priority": 2,
    },
    {
        "trigger": "strong attribute",
        "regex": (
            r"\bstrong\s+(?:experience|understanding|expertise|ability|skills?|"
            r"background)\b"
        ),
        "confidence": 0.76,
        "priority": 2,
    },
)

# Precompile all patterns for efficiency
COMPILED_PATTERNS: tuple[tuple[RequirementPattern, re.Pattern[str]], ...] = tuple(
    (pattern, re.compile(pattern["regex"], re.IGNORECASE)) for pattern in REQUIREMENT_PATTERNS
)

MAX_SENTENCE_CHARS: int = 2000

# Precompile negation patterns
_NEGATION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bnot\b",
        r"\bno\b",
        r"\bdon't\b",
        r"\bdoesn't\b",
        r"\bwithout\b",
    ]
)

# Precompile adjustment patterns
_PARENTHETICAL_PATTERN: re.Pattern[str] = re.compile(r"\(.*?\)")
_CONDITIONAL_PATTERN: re.Pattern[str] = re.compile(r"\bif\b", re.IGNORECASE)
_NICE_TO_HAVE_PATTERN: re.Pattern[str] = re.compile(r"nice\s+to\s+have", re.IGNORECASE)
_ALL_CAPS_PATTERN: re.Pattern[str] = re.compile(r"\b[A-Z]{4,}\b")


@dataclass(frozen=True)
class SentenceMatch:
    """Result of classifying a sentence as containing a requirement."""

    text: str
    trigger_word: str
    confidence: float
    priority: int


def has_negation_context(sentence: str, trigger: str) -> bool:
    """Detect negation patterns near trigger word.

    Detects:
    - "not required"
    - "no experience"
    - "don't need"
    - "doesn't necessary"
    - "without experience"

    Args:
        sentence: Full sentence text
        trigger: Trigger word to search for

    Returns:
        True if negation found near trigger word (within ±50 chars)
    """
    trigger_pos = sentence.lower().find(trigger.lower())
    if trigger_pos == -1:
        return False

    # Look ±50 chars around trigger
    context_start = max(0, trigger_pos - 50)
    context_end = min(len(sentence), trigger_pos + len(trigger) + 50)
    context = sentence[context_start:context_end]

    for neg_pattern in _NEGATION_PATTERNS:
        if neg_pattern.search(context):
            return True

    return False


def apply_confidence_adjustments(base_confidence: float, sentence: str) -> float:
    """Apply confidence adjustments for context.

    Adjustments:
    - Parentheticals (e.g., "(preferred)"): -0.10
    - Conditional ("if you have..."): -0.15
    - Nice to have: -0.25
    - All caps (emphasis, 3+ words of 4+ letters): +0.05

    Args:
        base_confidence: Base confidence score
        sentence: Full sentence text

    Returns:
        Adjusted confidence (clamped to [0.0, 1.0])
    """
    adjustment = base_confidence

    # Parentheticals: lower confidence
    if _PARENTHETICAL_PATTERN.search(sentence):
        adjustment -= 0.10

    # Conditional: lower confidence
    if _CONDITIONAL_PATTERN.search(sentence):
        adjustment -= 0.15

    # Nice to have: significantly lower
    if _NICE_TO_HAVE_PATTERN.search(sentence):
        adjustment -= 0.25

    # All-caps emphasis: boost
    if len(_ALL_CAPS_PATTERN.findall(sentence)) > 2:
        adjustment += 0.05

    return max(0.0, min(1.0, adjustment))


def _is_better(
    candidate: tuple[RequirementPattern, float],
    best: tuple[RequirementPattern, float] | None,
) -> bool:
    """Helper: check if candidate is better than best match.

    Better = lower priority number, or same priority and higher confidence.
    """
    if best is None:
        return True
    candidate_pattern, candidate_confidence = candidate
    best_pattern, best_confidence = best
    return candidate_pattern["priority"] < best_pattern["priority"] or (
        candidate_pattern["priority"] == best_pattern["priority"] and candidate_confidence > best_confidence
    )


def classify_sentence(sentence: str) -> SentenceMatch | None:
    """Classify single sentence as containing a requirement.

    Returns SentenceMatch with requirement info or None if no requirement
    detected.

    Args:
        sentence: Single sentence text

    Returns:
        SentenceMatch with text, trigger_word, confidence, priority
        or None if no requirement detected
    """
    if not sentence.strip():
        return None

    # Truncate if too long
    truncated = sentence[:MAX_SENTENCE_CHARS]

    # Try each pattern
    best_match: tuple[RequirementPattern, float] | None = None

    for pattern, compiled_regex in COMPILED_PATTERNS:
        if compiled_regex.search(truncated):
            # Found a match
            confidence = pattern["confidence"]

            # Check negations
            if has_negation_context(truncated, pattern["trigger"]):
                return None  # Negation found, skip entirely

            # Apply context adjustments
            confidence = apply_confidence_adjustments(confidence, truncated)

            if confidence > 0:
                # Keep best match (by priority, then confidence)
                if _is_better((pattern, confidence), best_match):
                    best_match = (pattern, confidence)

    if best_match:
        pattern, confidence = best_match
        return SentenceMatch(
            text=truncated,
            trigger_word=pattern["trigger"],
            confidence=confidence,
            priority=pattern["priority"],
        )

    return None


__all__ = [
    "RequirementPattern",
    "REQUIREMENT_PATTERNS",
    "COMPILED_PATTERNS",
    "MAX_SENTENCE_CHARS",
    "SentenceMatch",
    "has_negation_context",
    "apply_confidence_adjustments",
    "classify_sentence",
]
