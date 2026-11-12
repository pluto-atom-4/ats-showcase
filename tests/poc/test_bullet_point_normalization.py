"""Tests for bullet-point normalization functionality.

150 LOC covering:
- Asterisk bullet normalization
- Hyphen bullet normalization
- Numbered bullet normalization
- Inline header bullet normalization
- Nested bullet handling
- Existing period handling (no double-periods)
"""

import pytest

from src.poc.bullet_point_preprocessor import (
    normalize_asterisk_bullets,
    normalize_bullet_points,
    normalize_handles_existing_periods,
    normalize_hyphen_bullets,
    normalize_inline_header_bullets,
    normalize_nested_bullets,
    normalize_numbered_bullets,
)


class TestNormalizeAsteriskBullets:
    """Test asterisk (*) bullet normalization."""

    def test_simple_asterisk_bullet(self):
        """Test normalization of simple asterisk bullet."""
        markdown = "* 2-7 years experience"
        result = normalize_asterisk_bullets(markdown)
        assert "2-7 years experience." in result
        assert "*" not in result

    def test_multiple_asterisk_bullets(self):
        """Test normalization of multiple asterisk bullets."""
        markdown = "* First requirement\n* Second requirement"
        result = normalize_asterisk_bullets(markdown)
        assert "First requirement." in result
        assert "Second requirement." in result

    def test_asterisk_bullet_with_existing_period(self):
        """Test asterisk bullet already has period."""
        markdown = "* Python experience."
        result = normalize_asterisk_bullets(markdown)
        assert result.count(".") == 1

    def test_asterisk_with_indentation(self):
        """Test asterisk bullet with indentation."""
        markdown = "  * Indented bullet"
        result = normalize_asterisk_bullets(markdown)
        assert "Indented bullet." in result

    def test_asterisk_mixed_with_text(self):
        """Test asterisk bullets mixed with regular text."""
        markdown = "Regular text\n* Bullet point\nMore text"
        result = normalize_asterisk_bullets(markdown)
        assert "Regular text" in result
        assert "Bullet point." in result
        assert "More text" in result


class TestNormalizeHyphenBullets:
    """Test hyphen (-) bullet normalization."""

    def test_simple_hyphen_bullet(self):
        """Test normalization of simple hyphen bullet."""
        markdown = "- 3+ years Python"
        result = normalize_hyphen_bullets(markdown)
        assert "3+ years Python." in result
        assert "-" not in result.split("\n")[0]

    def test_multiple_hyphen_bullets(self):
        """Test normalization of multiple hyphen bullets."""
        markdown = "- Experience with PyTorch\n- Understanding of CNNs"
        result = normalize_hyphen_bullets(markdown)
        assert "Experience with PyTorch." in result
        assert "Understanding of CNNs." in result

    def test_hyphen_bullet_with_question_mark(self):
        """Test hyphen bullet with question mark (no period added)."""
        markdown = "- What skills needed?"
        result = normalize_hyphen_bullets(markdown)
        assert result.count("?") == 1
        assert "What skills needed?" in result

    def test_hyphen_with_exclamation(self):
        """Test hyphen bullet with exclamation (no period added)."""
        markdown = "- Critical requirement!"
        result = normalize_hyphen_bullets(markdown)
        assert result.count("!") == 1
        assert "Critical requirement!" in result

    def test_hyphen_nested(self):
        """Test nested hyphen bullets."""
        markdown = "- Main point\n  - Sub-point"
        result = normalize_hyphen_bullets(markdown)
        assert "Main point." in result
        assert "Sub-point." in result


class TestNormalizeNumberedBullets:
    """Test numbered (1., 2., etc.) bullet normalization."""

    def test_simple_numbered_bullet(self):
        """Test normalization of simple numbered bullet."""
        markdown = "1. Python proficiency"
        result = normalize_numbered_bullets(markdown)
        assert "Python proficiency." in result
        assert "1." not in result

    def test_multiple_numbered_bullets(self):
        """Test normalization of multiple numbered bullets."""
        markdown = "1. Requirement A\n2. Requirement B\n3. Requirement C"
        result = normalize_numbered_bullets(markdown)
        assert "Requirement A." in result
        assert "Requirement B." in result
        assert "Requirement C." in result

    def test_numbered_with_high_numbers(self):
        """Test numbered bullets with high numbers."""
        markdown = "12. Twelfth requirement\n25. Twenty-fifth requirement"
        result = normalize_numbered_bullets(markdown)
        assert "Twelfth requirement." in result
        assert "Twenty-fifth requirement." in result

    def test_numbered_with_period_exists(self):
        """Test numbered bullet where content already has period."""
        markdown = "1. Already has period."
        result = normalize_numbered_bullets(markdown)
        assert result.count(".") == 1

    def test_numbered_with_indentation(self):
        """Test numbered bullet with indentation."""
        markdown = "  1. Indented numbered item"
        result = normalize_numbered_bullets(markdown)
        assert "Indented numbered item." in result


class TestNormalizeInlineHeaderBullets:
    """Test inline header + bullet normalization."""

    def test_header_with_asterisk_bullet(self):
        """Test h3 header with asterisk bullet."""
        markdown = "### Requirements* 2-7 years experience"
        result = normalize_inline_header_bullets(markdown)
        assert "### Requirements" in result
        assert "2-7 years experience." in result

    def test_header_with_hyphen_bullet(self):
        """Test h2 header with hyphen bullet."""
        markdown = "## Skills- Python proficiency"
        result = normalize_inline_header_bullets(markdown)
        assert "## Skills" in result
        assert "Python proficiency." in result

    def test_header_with_plus_bullet(self):
        """Test header with plus bullet."""
        markdown = "# Main Section+ Requirement text"
        result = normalize_inline_header_bullets(markdown)
        assert "# Main Section" in result
        assert "Requirement text." in result

    def test_header_without_bullet(self):
        """Test header without bullet (no change)."""
        markdown = "## Regular Header\nSome content"
        result = normalize_inline_header_bullets(markdown)
        assert "## Regular Header" in result
        assert "Some content" in result

    def test_multiple_inline_headers(self):
        """Test multiple inline headers with bullets."""
        markdown = "### Requirements* Python\n### Skills+ Communication"
        result = normalize_inline_header_bullets(markdown)
        lines = result.split("\n")
        assert any("### Requirements" in line for line in lines)
        assert any("Python." in line for line in lines)


class TestNormalizeNestedBullets:
    """Test nested bullet point normalization."""

    def test_two_level_asterisk_nesting(self):
        """Test two-level asterisk nesting."""
        markdown = "* Level 1\n  * Level 2"
        result = normalize_nested_bullets(markdown)
        assert "Level 1." in result
        assert "Level 2." in result

    def test_three_level_nesting(self):
        """Test three-level bullet nesting."""
        markdown = "* L1\n  * L2\n    * L3"
        result = normalize_nested_bullets(markdown)
        assert "L1." in result
        assert "L2." in result
        assert "L3." in result

    def test_mixed_bullet_types_nested(self):
        """Test nested bullets with mixed types (- and *)."""
        markdown = "* Parent\n  - Child 1\n  - Child 2"
        result = normalize_nested_bullets(markdown)
        assert "Parent." in result
        assert "Child 1." in result
        assert "Child 2." in result

    def test_nested_numbered_bullets(self):
        """Test nested numbered bullets."""
        markdown = "1. Item 1\n  1. Sub-item 1.1\n  2. Sub-item 1.2"
        result = normalize_nested_bullets(markdown)
        assert "Item 1." in result
        assert "Sub-item 1.1." in result
        assert "Sub-item 1.2." in result

    def test_preserve_indentation_structure(self):
        """Test that indentation is preserved."""
        markdown = "* Bullet\n  * Nested"
        result = normalize_nested_bullets(markdown)
        lines = result.split("\n")
        assert lines[1].startswith("  ")


class TestNormalizeHandlesExistingPeriods:
    """Test period handling (no double-periods)."""

    def test_no_double_period_asterisk(self):
        """Test asterisk bullet with period, no double-period."""
        markdown = "* Python experience."
        result = normalize_handles_existing_periods(markdown)
        assert result.count(".") == 1

    def test_no_double_period_hyphen(self):
        """Test hyphen bullet with period, no double-period."""
        markdown = "- Java knowledge."
        result = normalize_handles_existing_periods(markdown)
        assert result.count(".") == 1

    def test_no_double_period_numbered(self):
        """Test numbered bullet with period, no double-period."""
        markdown = "1. Requirement here."
        result = normalize_handles_existing_periods(markdown)
        assert result.count(".") == 1

    def test_add_period_when_missing_asterisk(self):
        """Test asterisk bullet without period, period added."""
        markdown = "* Python experience"
        result = normalize_handles_existing_periods(markdown)
        assert "Python experience." in result

    def test_preserve_question_mark(self):
        """Test that question marks are preserved."""
        markdown = "* What is required?"
        result = normalize_handles_existing_periods(markdown)
        assert "What is required?" in result
        assert result.count(".") == 0

    def test_preserve_exclamation_mark(self):
        """Test that exclamation marks are preserved."""
        markdown = "* Critical skill!"
        result = normalize_handles_existing_periods(markdown)
        assert "Critical skill!" in result
        assert result.count(".") == 0

    def test_mixed_punctuation_handling(self):
        """Test mixed punctuation in bullets."""
        markdown = "* First requirement.\n- Second skill\n1. Third point?"
        result = normalize_handles_existing_periods(markdown)
        assert "First requirement." in result
        assert "Second skill." in result
        assert "Third point?" in result


class TestNormalizeBulletPoints:
    """Test main normalize_bullet_points() function."""

    def test_normalize_mixed_bullets(self):
        """Test normalization with mixed bullet types."""
        markdown = "* Python\n- Java\n+ C++"
        result = normalize_bullet_points(markdown)
        assert "Python." in result
        assert "Java." in result
        assert "C++." in result

    def test_normalize_carbon_robotics_example(self):
        """Test on Carbon Robotics job fixture structure."""
        markdown = """## Requirements
* 2-7 years experience
* 3+ years Python
* Experience with PyTorch is essential"""
        result = normalize_bullet_points(markdown)
        assert "2-7 years experience." in result
        assert "3+ years Python." in result
        assert "Experience with PyTorch is essential." in result

    def test_normalize_preserves_headers(self):
        """Test that headers are preserved."""
        markdown = "## Requirements\n* Python\n* Java"
        result = normalize_bullet_points(markdown)
        assert "## Requirements" in result

    def test_normalize_handles_empty_input(self):
        """Test with empty input."""
        result = normalize_bullet_points("")
        assert result == ""

    def test_normalize_text_without_bullets(self):
        """Test text without bullets (unchanged)."""
        markdown = "Regular text without bullets."
        result = normalize_bullet_points(markdown)
        assert "Regular text without bullets." in result

    def test_normalize_real_job_description(self):
        """Test on real job description structure."""
        markdown = """## What You'll Do
* Lead the design and execution of experiments
* Own model optimization and deployment pipelines
* Drive end-to-end ML workflows

## Knowledge, Skills & Abilities
* 2-4 years professional experience
* Deep understanding of deep learning"""
        result = normalize_bullet_points(markdown)
        assert "Lead the design and execution of experiments." in result
        assert "Own model optimization and deployment pipelines." in result
        assert "2-4 years professional experience." in result

    def test_normalize_no_embedded_newlines(self):
        """Test that result has no embedded newlines in requirements."""
        markdown = "* Long requirement that spans\nmultiple lines"
        result = normalize_bullet_points(markdown)
        lines = result.split("\n")
        assert all(line for line in lines if line.strip())


class TestNormalizeDegreeInBullet:
    """Test degree/education bullet normalization."""

    def test_normalize_bachelor_degree(self):
        """Test Bachelor's degree bullet."""
        markdown = "* Bachelor's degree in Computer Science"
        result = normalize_handles_existing_periods(markdown)
        assert "Bachelor's degree in Computer Science." in result

    def test_normalize_master_degree(self):
        """Test Master's degree bullet."""
        markdown = "- Master's in Machine Learning"
        result = normalize_handles_existing_periods(markdown)
        assert "Master's in Machine Learning." in result

    def test_normalize_phd(self):
        """Test PhD bullet."""
        markdown = "1. PhD or equivalent experience"
        result = normalize_handles_existing_periods(markdown)
        assert "PhD or equivalent experience." in result
