"""Tests for section_patterns module (Issue #281).

Comprehensive tests for section label enums, pattern definitions,
confidence adjustments, display names, and filtering logic.
Model-free (no spaCy required).
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from src.preprocessing.custom_span_categorizer import validate_pattern
from src.preprocessing.section_patterns import (
    CONFIDENCE_ADJUSTMENT_BY_SECTION,
    DEFAULT_TARGET_SECTIONS,
    FILTER_SECTIONS,
    SECTION_DISPLAY_NAMES,
    SECTION_RULER_PATTERNS,
    SectionLabel,
)


class TestSectionLabelEnum:
    """Test SectionLabel enum definition and values."""

    def test_13_labels_exist(self) -> None:
        """All 13 section labels are defined."""
        assert len(SectionLabel) == 13

    def test_all_values_start_with_section(self) -> None:
        """All SectionLabel values start with 'SECTION_'."""
        for label in SectionLabel:
            assert label.value.startswith("SECTION_"), f"Label {label.name} has invalid value: {label.value}"

    def test_label_names_and_values_match(self) -> None:
        """Label enum names match their values (without SECTION_ prefix)."""
        for label in SectionLabel:
            expected_name = label.value[8:].upper()  # Strip "SECTION_" prefix
            assert label.name == expected_name, f"Label name {label.name} does not match value {label.value}"


class TestSectionRulerPatterns:
    """Test SECTION_RULER_PATTERNS structure and content."""

    def test_patterns_is_tuple(self) -> None:
        """SECTION_RULER_PATTERNS is a tuple (immutable)."""
        assert isinstance(SECTION_RULER_PATTERNS, tuple)

    def test_13_patterns_defined(self) -> None:
        """All 13 section labels have a corresponding pattern."""
        assert len(SECTION_RULER_PATTERNS) == 13

    def test_every_pattern_has_label(self) -> None:
        """Every pattern dict has a 'label' key."""
        for i, pattern in enumerate(SECTION_RULER_PATTERNS):
            assert "label" in pattern, f"Pattern {i} missing 'label' key"

    def test_all_labels_are_valid(self) -> None:
        """Every pattern's label is a valid SectionLabel value."""
        valid_labels = {lbl.value for lbl in SectionLabel}
        for i, pattern in enumerate(SECTION_RULER_PATTERNS):
            label = pattern["label"]
            assert label in valid_labels, f"Pattern {i} has invalid label: {label}"

    def test_each_label_appears_exactly_once(self) -> None:
        """Each SectionLabel value appears exactly once in patterns."""
        labels_in_patterns = [p["label"] for p in SECTION_RULER_PATTERNS]
        expected_labels = {lbl.value for lbl in SectionLabel}
        assert set(labels_in_patterns) == expected_labels
        assert len(labels_in_patterns) == len(expected_labels)

    def test_every_pattern_has_pattern_key(self) -> None:
        """Every pattern dict has a 'pattern' key."""
        for i, pattern in enumerate(SECTION_RULER_PATTERNS):
            assert "pattern" in pattern, f"Pattern {i} missing 'pattern' key"

    def test_regex_patterns_compile(self) -> None:
        """All regex patterns compile successfully."""
        for i, pattern in enumerate(SECTION_RULER_PATTERNS):
            if pattern.get("type") == "regex":
                pattern_str = pattern["pattern"]
                try:
                    re.compile(pattern_str)
                except re.error as e:
                    pytest.fail(f"Pattern {i} ({pattern['label']}) regex fails to compile: {e}")

    def test_regex_patterns_pass_validate_pattern(self) -> None:
        """All regex patterns pass validate_pattern validation."""
        for i, pattern in enumerate(SECTION_RULER_PATTERNS):
            if pattern.get("type") == "regex":
                pattern_str = pattern["pattern"]
                try:
                    validate_pattern(pattern_str)
                except ValueError as e:
                    pytest.fail(f"Pattern {i} ({pattern['label']}) fails validate_pattern: {e}")

    def test_non_regex_patterns_are_lists(self) -> None:
        """All non-regex patterns are lists."""
        for i, pattern in enumerate(SECTION_RULER_PATTERNS):
            if pattern.get("type") != "regex":
                pattern_content = pattern["pattern"]
                assert isinstance(pattern_content, list), f"Pattern {i} ({pattern['label']}) is not a list"

    def test_non_regex_patterns_are_non_empty(self) -> None:
        """All non-regex patterns contain at least one dict."""
        for i, pattern in enumerate(SECTION_RULER_PATTERNS):
            if pattern.get("type") != "regex":
                pattern_content = pattern["pattern"]
                assert len(pattern_content) > 0, f"Pattern {i} ({pattern['label']}) is empty"

    def test_non_regex_patterns_contain_dicts(self) -> None:
        """All items in non-regex patterns are dicts."""
        for i, pattern in enumerate(SECTION_RULER_PATTERNS):
            if pattern.get("type") != "regex":
                pattern_content = pattern["pattern"]
                for j, item in enumerate(pattern_content):
                    assert isinstance(item, dict), f"Pattern {i} ({pattern['label']}) item {j} is not a dict"


class TestConfidenceAdjustments:
    """Test CONFIDENCE_ADJUSTMENT_BY_SECTION mapping."""

    def test_all_labels_have_adjustment(self) -> None:
        """Every SectionLabel has an entry in confidence adjustments."""
        for label in SectionLabel:
            assert label in CONFIDENCE_ADJUSTMENT_BY_SECTION, (
                f"Label {label} missing from CONFIDENCE_ADJUSTMENT_BY_SECTION"
            )

    def test_adjustment_keys_are_valid_labels(self) -> None:
        """All keys in adjustments are valid SectionLabel values."""
        for key in CONFIDENCE_ADJUSTMENT_BY_SECTION.keys():
            assert isinstance(key, SectionLabel), f"Invalid key in CONFIDENCE_ADJUSTMENT_BY_SECTION: {key}"

    def test_adjustment_values_in_range(self) -> None:
        """All confidence adjustments are in [-0.5, 0.5]."""
        for label, adjustment in CONFIDENCE_ADJUSTMENT_BY_SECTION.items():
            assert -0.5 <= adjustment <= 0.5, f"Label {label} adjustment {adjustment} out of range"

    def test_mapping_is_immutable(self) -> None:
        """CONFIDENCE_ADJUSTMENT_BY_SECTION is immutable."""
        with pytest.raises(TypeError):
            CONFIDENCE_ADJUSTMENT_BY_SECTION[SectionLabel.REQUIREMENTS] = 0.99  # type: ignore


class TestSectionDisplayNames:
    """Test SECTION_DISPLAY_NAMES mapping."""

    def test_all_labels_have_display_name(self) -> None:
        """Every SectionLabel has an entry in display names."""
        for label in SectionLabel:
            assert label in SECTION_DISPLAY_NAMES, f"Label {label} missing from SECTION_DISPLAY_NAMES"

    def test_display_name_keys_are_valid_labels(self) -> None:
        """All keys in display names are valid SectionLabel values."""
        for key in SECTION_DISPLAY_NAMES.keys():
            assert isinstance(key, SectionLabel), f"Invalid key in SECTION_DISPLAY_NAMES: {key}"

    def test_display_names_are_non_empty_strings(self) -> None:
        """All display names are non-empty strings."""
        for label, name in SECTION_DISPLAY_NAMES.items():
            assert isinstance(name, str), f"Display name for {label} is not a string"
            assert len(name) > 0, f"Display name for {label} is empty"

    def test_mapping_is_immutable(self) -> None:
        """SECTION_DISPLAY_NAMES is immutable."""
        with pytest.raises(TypeError):
            SECTION_DISPLAY_NAMES[SectionLabel.REQUIREMENTS] = "New Name"  # type: ignore


class TestFilterSections:
    """Test FILTER_SECTIONS frozenset."""

    def test_filter_sections_is_frozenset(self) -> None:
        """FILTER_SECTIONS is a frozenset."""
        assert isinstance(FILTER_SECTIONS, frozenset)

    def test_filter_sections_has_three_members(self) -> None:
        """FILTER_SECTIONS contains exactly 3 labels."""
        assert len(FILTER_SECTIONS) == 3

    def test_filter_sections_contains_expected_labels(self) -> None:
        """FILTER_SECTIONS contains BENEFITS, COMPENSATION, HIRING_PROCESS."""
        expected = {
            SectionLabel.BENEFITS,
            SectionLabel.COMPENSATION,
            SectionLabel.HIRING_PROCESS,
        }
        assert FILTER_SECTIONS == expected

    def test_all_filter_section_labels_have_boost_neg_half(self) -> None:
        """All filter section labels have adjustment == -0.50."""
        for label in FILTER_SECTIONS:
            adjustment = CONFIDENCE_ADJUSTMENT_BY_SECTION[label]
            assert adjustment == -0.50, f"Filter label {label} has adjustment {adjustment}, expected -0.50"


class TestDefaultTargetSections:
    """Test DEFAULT_TARGET_SECTIONS frozenset."""

    def test_default_target_sections_is_frozenset(self) -> None:
        """DEFAULT_TARGET_SECTIONS is a frozenset."""
        assert isinstance(DEFAULT_TARGET_SECTIONS, frozenset)

    def test_default_target_sections_has_nine_members(self) -> None:
        """DEFAULT_TARGET_SECTIONS contains exactly 9 labels."""
        assert len(DEFAULT_TARGET_SECTIONS) == 9

    def test_default_target_sections_contains_expected_labels(self) -> None:
        """DEFAULT_TARGET_SECTIONS contains the 9 expected labels."""
        expected = {
            SectionLabel.REQUIREMENTS,
            SectionLabel.QUALIFICATIONS,
            SectionLabel.TECHNICAL_SKILLS,
            SectionLabel.PREFERRED_SKILLS,
            SectionLabel.NICE_TO_HAVE,
            SectionLabel.EDUCATION,
            SectionLabel.EXPERIENCE,
            SectionLabel.KNOWLEDGE_SKILLS,
            SectionLabel.IN_OFFICE,
        }
        assert DEFAULT_TARGET_SECTIONS == expected

    def test_what_you_do_excluded_from_target_sections(self) -> None:
        """WHAT_YOU_DO is not in DEFAULT_TARGET_SECTIONS."""
        assert SectionLabel.WHAT_YOU_DO not in DEFAULT_TARGET_SECTIONS

    def test_filter_and_target_sections_disjoint(self) -> None:
        """FILTER_SECTIONS and DEFAULT_TARGET_SECTIONS do not overlap."""
        assert FILTER_SECTIONS.isdisjoint(DEFAULT_TARGET_SECTIONS)

    def test_what_you_do_not_in_filter_sections(self) -> None:
        """WHAT_YOU_DO is not in FILTER_SECTIONS."""
        assert SectionLabel.WHAT_YOU_DO not in FILTER_SECTIONS


class TestParityWithPOC:
    """Test parity with src.poc.patterns (original POC module).

    Ensures that promotion to src/preprocessing/section_patterns.py
    preserves all data from the POC exactly.
    """

    def test_poc_import_works(self) -> None:
        """POC module can be imported."""
        import src.poc.patterns as poc  # noqa: F401

    def test_label_sets_match_poc(self) -> None:
        """Section label set matches POC label set."""
        import src.poc.patterns as poc

        poc_labels = set(poc.CONFIDENCE_ADJUSTMENT_BY_SECTION.keys())
        our_labels = {lbl.value for lbl in SectionLabel}
        assert our_labels == poc_labels

    def test_confidence_boosts_match_poc(self) -> None:
        """All confidence boosts match POC values (by string label key)."""
        import src.poc.patterns as poc

        for label in SectionLabel:
            our_boost = CONFIDENCE_ADJUSTMENT_BY_SECTION[label]
            poc_boost = poc.CONFIDENCE_ADJUSTMENT_BY_SECTION[label.value]
            assert our_boost == poc_boost, f"Boost mismatch for {label}: {our_boost} vs POC {poc_boost}"

    def test_display_names_match_poc(self) -> None:
        """All display names match POC values (by string label key)."""
        import src.poc.patterns as poc

        for label in SectionLabel:
            our_name = SECTION_DISPLAY_NAMES[label]
            poc_name = poc.SECTION_DISPLAY_NAMES[label.value]
            assert our_name == poc_name, f"Display name mismatch for {label}: {our_name} vs POC {poc_name}"

    def test_target_sections_match_poc(self) -> None:
        """DEFAULT_TARGET_SECTIONS matches POC DEFAULT_TARGET_SECTIONS (as sets)."""
        import src.poc.patterns as poc

        our_targets = {lbl.value for lbl in DEFAULT_TARGET_SECTIONS}
        poc_targets = set(poc.DEFAULT_TARGET_SECTIONS)
        assert our_targets == poc_targets

    def test_pattern_labels_order_matches_poc(self) -> None:
        """Pattern labels appear in same order as POC."""
        import src.poc.patterns as poc

        our_labels = tuple(p["label"] for p in SECTION_RULER_PATTERNS)
        poc_labels = tuple(p["label"] for p in poc.SECTION_RULER_PATTERNS)
        assert our_labels == poc_labels

    def test_each_pattern_dict_matches_poc(self) -> None:
        """Every pattern dict exactly matches the POC pattern dict."""
        import src.poc.patterns as poc

        for i, our_pattern in enumerate(SECTION_RULER_PATTERNS):
            poc_pattern = poc.SECTION_RULER_PATTERNS[i]
            assert our_pattern == poc_pattern, (
                f"Pattern {i} ({our_pattern.get('label')}) differs from POC:\n"
                f"  Our:  {our_pattern}\n"
                f"  POC:  {poc_pattern}"
            )
