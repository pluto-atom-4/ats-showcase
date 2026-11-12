"""Tests for markdown formatting in format_paragraph_from_json."""

import json
import re
import sys

sys.path.insert(0, "/home/pluto-atom-4/Documents/full-stack/ats-playground")

from src.poc.tweak.format_paragraph_from_json import clean_and_convert


def test_list_regex_no_blanks_between_items():
    """Verify Step D regex doesn't add blank lines between consecutive list items."""
    text = "* Item A\n* Item B\n* Item C"
    pattern = r"(^[^*\n][^\n]*[^\n\s])\n(\* )"
    result = re.sub(pattern, r"\1\n\n\2", text, flags=re.MULTILINE)

    assert "* Item A\n\n* Item B" not in result, "Blank line should not be added between list items"
    assert result == text, "Text should remain unchanged"


def test_list_regex_adds_blank_before_list():
    """Verify Step D regex adds blank line before first list item after text."""
    text = "Some text\n* Item A\n* Item B"
    pattern = r"(^[^*\n][^\n]*[^\n\s])\n(\* )"
    result = re.sub(pattern, r"\1\n\n\2", text, flags=re.MULTILINE)

    assert "Some text\n\n* Item A" in result, "Blank line should be added before first list item"


def test_list_regex_adds_blank_after_header():
    """Verify Step D regex adds blank line before list items after headers."""
    text = "## Header\n* Item A\n* Item B"
    pattern = r"(^[^*\n][^\n]*[^\n\s])\n(\* )"
    result = re.sub(pattern, r"\1\n\n\2", text, flags=re.MULTILINE)

    assert "## Header\n\n* Item A" in result, "Blank line should be added before first list item after header"


def test_output_no_blank_lines_between_consecutive_items():
    """Test actual output from clean_and_convert doesn't have blank lines between list items."""
    with open("tests/poc/fixtures/raw_html_description.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    html_content = data.get("description", "")
    result = clean_and_convert(html_content)

    lines = result.split("\n")

    for i in range(len(lines) - 2):
        is_list_item_i = lines[i].strip().startswith("* ")
        is_list_item_i2 = lines[i + 2].strip().startswith("* ")
        is_blank_i1 = lines[i + 1].strip() == ""

        assert not (is_list_item_i and is_blank_i1 and is_list_item_i2), (
            f"Found unexpected blank line between consecutive list items at line {i}: "
            f"{lines[i][:50]} → [blank] → {lines[i + 2][:50]}"
        )


def test_output_has_proper_spacing_before_lists():
    """Test that output has blank lines before lists after text/headers."""
    with open("tests/poc/fixtures/raw_html_description.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    html_content = data.get("description", "")
    result = clean_and_convert(html_content)

    lines = result.split("\n")

    correct_blanks_count = 0
    for i in range(len(lines) - 2):
        if (
            lines[i].strip() != ""
            and not lines[i].strip().startswith("* ")
            and lines[i + 1].strip() == ""
            and lines[i + 2].strip().startswith("* ")
        ):
            correct_blanks_count += 1

    assert correct_blanks_count > 0, "Should have blank lines before list sections"


def test_strong_text_spacing():
    """Test that strong-formatted (bold) text has proper spacing."""
    text = "Normal text\n**Bold Header**\n* List item"
    pattern_before = r"(?<=.)\n(\*\*.*?\*\*)"
    pattern_after = r"(\*\*.*?\*\*)\n(?=.)"

    result = text
    result = re.sub(pattern_before, r"\n\n\1", result)
    result = re.sub(pattern_after, r"\1\n\n", result)

    assert "\n\n**Bold Header**\n\n" in result, "Bold text should have blank lines around it"


if __name__ == "__main__":
    print("Running test_list_regex_no_blanks_between_items...")
    test_list_regex_no_blanks_between_items()
    print("✓ PASS\n")

    print("Running test_list_regex_adds_blank_before_list...")
    test_list_regex_adds_blank_before_list()
    print("✓ PASS\n")

    print("Running test_list_regex_adds_blank_after_header...")
    test_list_regex_adds_blank_after_header()
    print("✓ PASS\n")

    print("Running test_output_no_blank_lines_between_consecutive_items...")
    test_output_no_blank_lines_between_consecutive_items()
    print("✓ PASS\n")

    print("Running test_output_has_proper_spacing_before_lists...")
    test_output_has_proper_spacing_before_lists()
    print("✓ PASS\n")

    print("Running test_strong_text_spacing...")
    test_strong_text_spacing()
    print("✓ PASS\n")

    print("=" * 60)
    print("All tests PASSED!")
    print("=" * 60)
