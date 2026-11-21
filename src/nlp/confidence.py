"""Confidence scoring for extracted entities."""

from dataclasses import dataclass
from enum import Enum


class ExtractionMethod(str, Enum):
    """How entity was extracted."""

    KEYPHRASE_EXACT = "keyphrase_exact"
    PATTERN_MATCH = "pattern_match"
    CONTEXT_INFERRED = "context_inferred"
    FALLBACK = "fallback"
    STRUCTURED_BULLET = "structured_bullet"
    SKILL_KEYWORD = "skill_keyword"


@dataclass
class ConfidentEntity:
    """Entity with confidence score and extraction method."""

    value: str
    confidence: float  # 0.0 to 1.0
    method: ExtractionMethod

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ConfidentEntity):
            return self.value == other.value
        return self.value == str(other)


CONFIDENCE_SCORES = {
    ExtractionMethod.KEYPHRASE_EXACT: 0.95,
    ExtractionMethod.CONTEXT_INFERRED: 0.70,
    ExtractionMethod.SKILL_KEYWORD: 0.50,
    ExtractionMethod.PATTERN_MATCH: 0.92,
    ExtractionMethod.STRUCTURED_BULLET: 0.90,
    ExtractionMethod.FALLBACK: 0.65,
}


def get_confidence(method: ExtractionMethod) -> float:
    """Get confidence score for extraction method."""
    return CONFIDENCE_SCORES.get(method, 0.5)


def build_extraction_with_confidence(
    values: dict[str, list[str]],
    confidences: dict[str, list[float]],
) -> dict[str, list[dict[str, float | str]]]:
    """Build extraction result with confidence scores.

    Args:
        values: Dict mapping category to list of extracted values
        confidences: Dict mapping category to list of confidence scores

    Returns:
        Dict with category -> [{"value": x, "confidence": y}, ...]
    """
    result: dict[str, list[dict[str, float | str]]] = {}
    for category, value_list in values.items():
        confidence_list = confidences.get(category, [0.5] * len(value_list))
        result[category] = [{"value": v, "confidence": c} for v, c in zip(value_list, confidence_list, strict=False)]
    return result


def average_confidence(items: list[dict[str, float | str]]) -> float:
    """Calculate average confidence for list of confident items."""
    if not items:
        return 0.0
    confidences: list[float] = []
    for item in items:
        conf = item.get("confidence", 0.0)
        if isinstance(conf, (int, float)):
            confidences.append(float(conf))
    return sum(confidences) / len(confidences) if confidences else 0.0
