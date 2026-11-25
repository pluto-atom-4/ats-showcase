"""Parity tests between src.preprocessing.section_patterns and the POC module (Issue #281)."""

from __future__ import annotations

from src.preprocessing.section_patterns import (
    CONFIDENCE_ADJUSTMENT_BY_SECTION,
    DEFAULT_TARGET_SECTIONS,
    SECTION_DISPLAY_NAMES,
    SECTION_RULER_PATTERNS,
    SectionLabel,
)


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
