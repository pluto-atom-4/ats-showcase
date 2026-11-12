"""Sentence classification for requirement detection.

Implements pattern-based classification with confidence scoring, negation detection,
and context adjustments. Used by extract_requirements_b.py.
"""

import logging
import re
from typing import Any, Dict, Optional

from spacy.language import Language

from .requirement_patterns import REQUIREMENT_PATTERNS

logger = logging.getLogger(__name__)


def _has_negation_context(sentence: str, trigger: str) -> bool:
    """Detect negation patterns near trigger word.

    Detects:
    - "not required"
    - "no experience"
    - "don't need"
    - "isn't necessary"
    - "without experience"

    Args:
        sentence: Full sentence text
        trigger: Trigger word to search for

    Returns:
        True if negation found near trigger word
    """
    negation_words = [
        r"\bnot\b",
        r"\bno\b",
        r"\bdon't\b",
        r"\bdoesn't\b",
        r"\bwithout\b",
    ]

    trigger_pos = sentence.lower().find(trigger.lower())
    if trigger_pos == -1:
        return False

    # Negation must fall within 50 chars of the trigger.
    context_start = max(0, trigger_pos - 50)
    context_end = min(len(sentence), trigger_pos + len(trigger) + 50)
    context = sentence[context_start:context_end]

    for neg_pattern in negation_words:
        if re.search(neg_pattern, context, re.IGNORECASE):
            return True

    return False


def _apply_adjustments(base_confidence: float, sentence: str) -> float:
    """Apply confidence adjustments for context.

    Adjustments:
    - Parentheticals (e.g., "(preferred)"): -0.10
    - Conditional ("if you have..."): -0.15
    - Nice to have: -0.25
    - All caps (emphasis): +0.05

    Args:
        base_confidence: Base confidence score
        sentence: Full sentence text

    Returns:
        Adjusted confidence (clamped to [0.0, 1.0])
    """
    adj = base_confidence

    # Parentheticals: lower confidence
    if re.search(r"\(.*?\)", sentence):
        adj -= 0.10

    if re.search(r"\bif\b", sentence, re.IGNORECASE):
        adj -= 0.15

    if re.search(r"nice\s+to\s+have", sentence, re.IGNORECASE):
        adj -= 0.25

    # All-caps emphasis: boost
    if len(re.findall(r"\b[A-Z]{4,}\b", sentence)) > 2:
        adj += 0.05

    return max(0.0, min(1.0, adj))


def classify_sentence_as_requirement(
    sentence: str,
    nlp: Language,
) -> Optional[Dict[str, Any]]:
    """Classify single sentence as containing a requirement.

    Returns dict with requirement info or None if no requirement detected.

    Args:
        sentence: Single sentence text
        nlp: Loaded spaCy Language object

    Returns:
        Dict with keys: text, trigger_word, confidence, negated, source
        or None if no requirement detected
    """
    if not sentence.strip():
        return None

    best_match: Optional[Dict[str, Any]] = None

    for pattern in REQUIREMENT_PATTERNS:
        if re.search(pattern["regex"], sentence, re.IGNORECASE):
            confidence: float = pattern["confidence"]

            # A negated trigger discards the whole sentence, even if another pattern would match.
            if _has_negation_context(sentence, pattern["trigger"]):
                return None

            confidence = _apply_adjustments(confidence, sentence)

            if confidence > 0:
                # Lower priority number wins; ties go to higher confidence.
                if best_match is None:
                    should_update = True
                else:
                    best_priority: int = best_match["priority"]  # type: ignore
                    best_confidence: float = best_match["confidence"]  # type: ignore
                    should_update = pattern["priority"] < best_priority or (
                        pattern["priority"] == best_priority and confidence > best_confidence
                    )

                if should_update:
                    best_match = {
                        "text": sentence,
                        "trigger_word": pattern["trigger"],
                        "confidence": confidence,
                        "negated": False,
                        "source": "single_sentence",
                        "priority": pattern["priority"],
                    }

    if best_match:
        best_match.pop("priority")
        return best_match

    return None
