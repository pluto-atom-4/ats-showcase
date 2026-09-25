"""Tests for requirement pattern definitions and classification.

Tests cover:
- Pattern structure and validity
- Classification logic with various inputs
- Confidence adjustments
- Negation detection
- Sentence truncation
- Module isolation
"""

import dataclasses
import inspect
import re

import pytest

from src.preprocessing.requirement_patterns import (
    COMPILED_PATTERNS,
    MAX_SENTENCE_CHARS,
    REQUIREMENT_PATTERNS,
    SentenceMatch,
    apply_confidence_adjustments,
    classify_sentence,
    has_negation_context,
)


class TestPatternStructure:
    """Test REQUIREMENT_PATTERNS tuple structure and validity."""

    def test_patterns_is_tuple(self) -> None:
        """REQUIREMENT_PATTERNS must be a tuple, not a list."""
        assert isinstance(REQUIREMENT_PATTERNS, tuple)

    def test_pattern_count_equals_30(self) -> None:
        """All 30 patterns from POC must be present."""
        assert len(REQUIREMENT_PATTERNS) == 30

    def test_compiled_patterns_count(self) -> None:
        """COMPILED_PATTERNS must have same count as REQUIREMENT_PATTERNS."""
        assert len(COMPILED_PATTERNS) == len(REQUIREMENT_PATTERNS)

    def test_each_pattern_has_required_keys(self) -> None:
        """Each pattern must have trigger, regex, confidence, priority."""
        required_keys = {"trigger", "regex", "confidence", "priority"}
        for pattern in REQUIREMENT_PATTERNS:
            assert set(pattern.keys()) == required_keys

    def test_all_triggers_are_non_empty_strings(self) -> None:
        """All triggers must be non-empty strings."""
        for pattern in REQUIREMENT_PATTERNS:
            trigger = pattern["trigger"]
            assert isinstance(trigger, str)
            assert len(trigger) > 0

    def test_all_confidence_in_valid_range(self) -> None:
        """All confidence values must be in [0.0, 1.0]."""
        for pattern in REQUIREMENT_PATTERNS:
            confidence = pattern["confidence"]
            assert 0.0 <= confidence <= 1.0

    def test_all_regexes_compile(self) -> None:
        """All regex patterns must compile without error."""
        for pattern in REQUIREMENT_PATTERNS:
            regex_str = pattern["regex"]
            try:
                re.compile(regex_str, re.IGNORECASE)
            except re.error as err:
                pytest.fail(f"Regex for trigger '{pattern['trigger']}' failed to compile: {err}")

    def test_all_priorities_are_integers(self) -> None:
        """All priority values must be integers."""
        for pattern in REQUIREMENT_PATTERNS:
            priority = pattern["priority"]
            assert isinstance(priority, int)

    def test_compiled_patterns_are_re_pattern_objects(self) -> None:
        """Each compiled pattern must be a re.Pattern object."""
        for pattern_dict, compiled in COMPILED_PATTERNS:
            assert isinstance(pattern_dict, dict)
            assert isinstance(compiled, re.Pattern)

    def test_specific_patterns_present(self) -> None:
        """Verify critical patterns from POC are present."""
        triggers = {p["trigger"] for p in REQUIREMENT_PATTERNS}
        # Representative patterns from each tier
        assert "required" in triggers
        assert "must" in triggers
        assert "essential" in triggers
        assert "should" in triggers
        assert "prefer" in triggers
        assert "nice to have" in triggers
        # Phase C patterns
        assert "degree abbreviation" in triggers
        assert "communication skills" in triggers


class TestClassifySentence:
    """Test classify_sentence classification logic."""

    def test_empty_string_returns_none(self) -> None:
        """Empty string should return None."""
        result = classify_sentence("")
        assert result is None

    def test_whitespace_only_returns_none(self) -> None:
        """Whitespace-only string should return None."""
        result = classify_sentence("   \t\n  ")
        assert result is None

    def test_no_trigger_returns_none(self) -> None:
        """Sentence with no trigger match should return None."""
        result = classify_sentence("The weather is sunny today.")
        assert result is None

    def test_must_pattern_match(self) -> None:
        """'Must have 5 years' should match 'must' pattern."""
        result = classify_sentence("Must have 5 years of Python experience.")
        assert result is not None
        assert result.trigger_word == "must"
        # Confidence 0.93, no adjustments applied
        assert result.confidence == pytest.approx(0.93)
        assert result.priority == 1

    def test_required_pattern_match(self) -> None:
        """'Required' should match 'required' pattern."""
        result = classify_sentence("Python is required for this role.")
        assert result is not None
        assert result.trigger_word == "required"
        assert result.confidence == pytest.approx(0.95)

    def test_result_text_is_input_sentence(self) -> None:
        """Result text must equal input sentence (truncated if needed)."""
        sentence = "Must have strong Python skills."
        result = classify_sentence(sentence)
        assert result is not None
        assert result.text == sentence

    def test_case_insensitive_match(self) -> None:
        """Pattern matching must be case-insensitive."""
        result_lower = classify_sentence("must have python")
        result_upper = classify_sentence("MUST HAVE PYTHON")
        result_mixed = classify_sentence("MuSt HaVe PyThOn")

        assert result_lower is not None
        assert result_upper is not None
        assert result_mixed is not None
        assert result_lower.trigger_word == "must"
        assert result_upper.trigger_word == "must"
        assert result_mixed.trigger_word == "must"

    def test_negation_not_required_returns_none(self) -> None:
        """'not required' should trigger negation and return None."""
        result = classify_sentence("Experience with Python is not required.")
        assert result is None

    def test_negation_no_experience_returns_none(self) -> None:
        """'no experience' with negation context returns None."""
        result = classify_sentence("No experience with Docker is required, but helpful.")
        # "required" is in sentence but "no" is nearby, should negate
        assert result is None

    def test_negation_without_returns_none(self) -> None:
        """'without' negation should return None."""
        result = classify_sentence("Can work without prior experience required.")
        assert result is None

    def test_parenthetical_lowers_confidence(self) -> None:
        """Parentheticals should lower confidence by 0.10."""
        no_paren = classify_sentence("Must have Python experience.")
        with_paren = classify_sentence("Must have Python experience (preferred).")

        assert no_paren is not None
        assert with_paren is not None
        # Both match "must", but paren reduces confidence
        assert with_paren.confidence == pytest.approx(no_paren.confidence - 0.10)

    def test_conditional_if_lowers_confidence(self) -> None:
        """'if' keyword should lower confidence by 0.15."""
        no_if = classify_sentence("Must have Python experience.")
        with_if = classify_sentence("Must have Python experience if you're building backend.")

        assert no_if is not None
        assert with_if is not None
        # Both match "must", but "if" reduces confidence
        assert with_if.confidence == pytest.approx(no_if.confidence - 0.15)

    def test_nice_to_have_lowers_confidence(self) -> None:
        """'nice to have' should lower confidence by 0.25."""
        nice_to_have_sentence = "Nice to have TypeScript would be great."
        result = classify_sentence(nice_to_have_sentence)
        assert result is not None
        # "nice to have" pattern has confidence 0.40
        # Extra adjustment: -0.25
        expected = 0.40 - 0.25
        assert result.confidence == pytest.approx(expected)

    def test_all_caps_boost_confidence(self) -> None:
        """3+ all-caps words of 4+ letters should boost confidence by 0.05."""
        no_caps = classify_sentence("Must have python experience.")
        with_caps = classify_sentence("Must have PYTHON EXPERIENCE WITH DATA processing.")

        assert no_caps is not None
        assert with_caps is not None
        # Both match "must", but all-caps boosts confidence
        assert with_caps.confidence == pytest.approx(no_caps.confidence + 0.05)

    def test_confidence_clamped_to_lower_bound(self) -> None:
        """Confidence must not go below 0.0."""
        # Find a low-confidence pattern and apply heavy adjustments
        sentence = "Nice to have (preferred) experience if you have some background knowledge."
        result = classify_sentence(sentence)
        # If result is not None, confidence must be >= 0.0
        if result is not None:
            assert result.confidence >= 0.0

    def test_confidence_clamped_to_upper_bound(self) -> None:
        """Confidence must not exceed 1.0."""
        # Create sentence that might boost beyond 1.0 (unlikely but safe)
        sentence = "Must have PYTHON SKILLS KNOWLEDGE WITH LANGUAGE EXPERIENCE."
        result = classify_sentence(sentence)
        assert result is not None
        assert result.confidence <= 1.0

    def test_priority_in_result(self) -> None:
        """Result must include priority field from pattern."""
        result = classify_sentence("Must have experience.")
        assert result is not None
        assert hasattr(result, "priority")
        assert isinstance(result.priority, int)
        assert result.priority == 1

    def test_sentence_truncation_at_max_chars(self) -> None:
        """Sentences longer than MAX_SENTENCE_CHARS should be truncated."""
        long_sentence = "Required: " + "x" * (MAX_SENTENCE_CHARS + 500)
        result = classify_sentence(long_sentence)
        assert result is not None
        assert result.trigger_word == "required"
        assert result.text == long_sentence[:MAX_SENTENCE_CHARS]

        # A trigger beyond MAX_SENTENCE_CHARS is not seen
        late_trigger = "x" * MAX_SENTENCE_CHARS + " required"
        assert classify_sentence(late_trigger) is None

    def test_best_match_by_priority(self) -> None:
        """When multiple patterns match, lower priority wins."""
        # "required" (priority 1, conf 0.95) and "prefer" (priority 2, conf 0.65)
        sentence = "Preferred but required skill."
        result = classify_sentence(sentence)
        # Should match both, but "required" has lower priority number
        assert result is not None
        assert result.trigger_word == "required"
        assert result.priority == 1

    def test_best_match_by_confidence_same_priority(self) -> None:
        """When priorities match, higher confidence wins."""
        # "must" (priority 1, conf 0.93) and "ability_in_bullet" (priority 1,
        # conf 0.90)
        sentence = "Must have ability to code."
        result = classify_sentence(sentence)
        # Both should match, but "must" has higher confidence
        assert result is not None
        assert result.trigger_word == "must"
        assert result.confidence == pytest.approx(0.93)

    def test_tier_1_pattern_extraction(self) -> None:
        """Verify Tier 1 high-confidence patterns are extracted."""
        tier1_triggers = [
            ("required", 0.95),
            ("essential", 0.90),
            ("mandatory", 0.92),
            ("proficiency", 0.91),
        ]
        for trigger, expected_conf in tier1_triggers:
            sentence = f"This role requires {trigger} knowledge."
            result = classify_sentence(sentence)
            assert result is not None
            assert result.confidence == pytest.approx(expected_conf)

    def test_tier_2_pattern_extraction(self) -> None:
        """Verify Tier 2 medium-confidence patterns are extracted."""
        sentence_should = "You should have Python experience."
        result_should = classify_sentence(sentence_should)
        assert result_should is not None
        assert result_should.trigger_word == "should"
        assert result_should.confidence == pytest.approx(0.70)

    def test_tier_3_pattern_extraction(self) -> None:
        """Verify Tier 3 lower-confidence patterns are extracted."""
        sentence_bonus = "Bonus skills: Docker experience."
        result_bonus = classify_sentence(sentence_bonus)
        assert result_bonus is not None
        assert result_bonus.trigger_word == "bonus"
        assert result_bonus.confidence == pytest.approx(0.45)

    def test_education_pattern_extraction(self) -> None:
        """Verify Phase C education patterns are extracted."""
        sentence_degree = "Bachelor's degree in Computer Science."
        result = classify_sentence(sentence_degree)
        assert result is not None
        assert "degree" in result.trigger_word
        assert result.trigger_word == "degree_in_bullet"
        assert result.confidence == pytest.approx(0.92)

    def test_soft_skills_pattern_extraction(self) -> None:
        """Verify Phase C soft skills patterns are extracted."""
        sentence_comm = "Strong communication and written skills."
        result = classify_sentence(sentence_comm)
        assert result is not None
        assert "communication" in result.trigger_word
        assert result.trigger_word == "communication skills"
        assert result.confidence == pytest.approx(0.82)


class TestHasNegationContext:
    """Test negation detection logic."""

    def test_negation_far_from_trigger_returns_false(self) -> None:
        """Negation far (>50 chars) from trigger returns False."""
        sentence = "A long sentence with many words. Experience is required."
        result = has_negation_context(sentence, "required")
        assert result is False

    def test_negation_not_found(self) -> None:
        """Trigger with no negation returns False."""
        sentence = "You must have Python experience."
        result = has_negation_context(sentence, "must")
        assert result is False

    def test_trigger_not_in_sentence(self) -> None:
        """Trigger absent from sentence returns False."""
        sentence = "Experience with Java is essential."
        result = has_negation_context(sentence, "python")
        assert result is False

    def test_negation_near_trigger_returns_true(self) -> None:
        """'not' negation near trigger returns True."""
        sentence = "Experience is not required for this role."
        result = has_negation_context(sentence, "required")
        assert result is True

    def test_negation_no_near_trigger(self) -> None:
        """'no' negation near trigger returns True."""
        sentence = "No experience with Python is mandatory."
        result = has_negation_context(sentence, "mandatory")
        assert result is True

    def test_negation_dont_near_trigger(self) -> None:
        """'don't' negation near trigger returns True."""
        sentence = "You don't need years of experience required."
        result = has_negation_context(sentence, "required")
        assert result is True

    def test_negation_doesnt_near_trigger(self) -> None:
        """'doesn't' negation near trigger returns True."""
        sentence = "It doesn't require extensive knowledge of Java."
        result = has_negation_context(sentence, "knowledge")
        assert result is True

    def test_negation_without_near_trigger(self) -> None:
        """'without' negation near trigger returns True."""
        sentence = "Without prior experience, you can still be required here."
        result = has_negation_context(sentence, "required")
        assert result is True

    def test_negation_case_insensitive(self) -> None:
        """Negation detection is case-insensitive."""
        sentence = "Experience is NOT required."
        result = has_negation_context(sentence, "required")
        assert result is True

    def test_all_five_negation_words(self) -> None:
        """Test all 5 negation words."""
        negations = [
            ("Experience is not required.", "required"),
            ("No experience needed.", "needed"),
            ("You don't need skills.", "need"),
            ("It doesn't require knowledge.", "require"),
            ("Without experience, apply here.", "apply"),
        ]
        for sentence, trigger_word in negations:
            result = has_negation_context(sentence, trigger_word)
            assert result is True


class TestApplyConfidenceAdjustments:
    """Test confidence adjustment logic."""

    def test_no_adjustments_unchanged(self) -> None:
        """Sentence with no adjustment patterns returns base confidence."""
        base = 0.85
        sentence = "Simple sentence without adjustments."
        result = apply_confidence_adjustments(base, sentence)
        assert result == pytest.approx(base)

    def test_parenthetical_adjustment(self) -> None:
        """Parentheticals reduce confidence by exactly 0.10."""
        base = 0.85
        sentence = "Must have experience (preferred)."
        result = apply_confidence_adjustments(base, sentence)
        assert result == pytest.approx(base - 0.10)

    def test_conditional_if_adjustment(self) -> None:
        """'if' reduces confidence by exactly 0.15."""
        base = 0.85
        sentence = "Must have experience if you know Python."
        result = apply_confidence_adjustments(base, sentence)
        assert result == pytest.approx(base - 0.15)

    def test_nice_to_have_adjustment(self) -> None:
        """'nice to have' reduces confidence by exactly 0.25."""
        base = 0.85
        sentence = "Nice to have Docker experience."
        result = apply_confidence_adjustments(base, sentence)
        assert result == pytest.approx(base - 0.25)

    def test_all_caps_boost_adjustment(self) -> None:
        """3+ all-caps words of 4+ letters boost by 0.05."""
        base = 0.85
        sentence = "Must have PYTHON SKILLS AND KNOWLEDGE."
        result = apply_confidence_adjustments(base, sentence)
        assert result == pytest.approx(base + 0.05)

    def test_multiple_adjustments_stack(self) -> None:
        """Multiple adjustments stack cumulatively."""
        base = 0.85
        # Parenthetical (-0.10) + conditional (-0.15) = -0.25
        sentence = "Must have experience (preferred) if you know Python."
        result = apply_confidence_adjustments(base, sentence)
        assert result == pytest.approx(base - 0.10 - 0.15)

    def test_clamped_at_zero(self) -> None:
        """Adjustments clamped at 0.0."""
        base = 0.10
        sentence = "Nice to have (preferred) if you know something."
        result = apply_confidence_adjustments(base, sentence)
        # -0.25 -0.10 -0.15 = -0.50, clamped to 0.0
        assert result == pytest.approx(0.0)

    def test_clamped_at_one(self) -> None:
        """Adjustments clamped at 1.0."""
        base = 0.97
        sentence = "Must have PYTHON SKILLS KNOWLEDGE LANGUAGE EXPERIENCE FRAMEWORK."
        result = apply_confidence_adjustments(base, sentence)
        # +0.05 = 1.02, clamped to 1.0
        assert result == pytest.approx(1.0)

    def test_all_caps_requires_three_words(self) -> None:
        """All-caps boost requires 3+ words of 4+ letters."""
        base = 0.85
        # Only 2 all-caps words: no boost
        sentence = "Must have PYTHON and java experience."
        result = apply_confidence_adjustments(base, sentence)
        assert result == pytest.approx(base)


class TestSentenceMatchDataClass:
    """Test SentenceMatch dataclass properties."""

    def test_sentence_match_is_frozen(self) -> None:
        """SentenceMatch must be frozen (immutable)."""
        match = SentenceMatch(text="Must have Python.", trigger_word="must", confidence=0.93, priority=1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            match.confidence = 0.85  # type: ignore

    def test_sentence_match_fields(self) -> None:
        """SentenceMatch must have all required fields."""
        match = SentenceMatch(text="Test sentence.", trigger_word="required", confidence=0.95, priority=1)
        assert match.text == "Test sentence."
        assert match.trigger_word == "required"
        assert match.confidence == 0.95
        assert match.priority == 1


class TestModuleIsolation:
    """Test module does not have forbidden imports."""

    def test_no_spacy_import(self) -> None:
        """Module must not import spacy."""
        module_source = inspect.getsource(
            __import__(
                "src.preprocessing.requirement_patterns",
                fromlist=["requirement_patterns"],
            )
        )
        assert "spacy" not in module_source

    def test_no_poc_import(self) -> None:
        """Module must not import from src.poc."""
        module_source = inspect.getsource(
            __import__(
                "src.preprocessing.requirement_patterns",
                fromlist=["requirement_patterns"],
            )
        )
        assert "src.poc" not in module_source
