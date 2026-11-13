"""Bullet-point preprocessing for enhanced requirement extraction.

Normalizes bullet points (*, -, +, numbered) into sentence-like format.
Handles embedded newlines, inline headers, and period insertion.

Phase A: Markdown & Unicode Cleaning
- Normalizes markdown artifacts (**bold**, etc.)
- Converts unicode characters (em-dash, curly quotes)
- Removes excessive line breaks while preserving bullet structure
"""

import re


def normalize_bullet_points(markdown: str) -> str:
    """Normalize bullet points to sentence-like format.

    Converts:
    - * prefix bullets to plain sentences
    - - prefix bullets to plain sentences
    - + prefix bullets to plain sentences
    - 1. numbered bullets to plain sentences
    - Inline header + bullet combos

    Adds trailing periods to bullets missing punctuation.
    Handles embedded newlines within bullets.

    Args:
        markdown: Raw markdown text with bullets

    Returns:
        Markdown with normalized bullets (periods added, prefixes removed)
    """
    lines = markdown.split("\n")
    result = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # Check for bullet prefix (*, -, +)
        if re.match(r"^[*\-+]\s+", stripped):
            content = re.sub(r"^[*\-+]\s+", "", stripped, count=1).strip()
            if content and not content.endswith((".", "!", "?")):
                content += "."
            result.append(content)

        # Check for numbered bullet (1., 2., etc.)
        elif re.match(r"^\d+\.\s+", stripped):
            content = re.sub(r"^\d+\.\s+", "", stripped, count=1).strip()
            if content and not content.endswith((".", "!", "?")):
                content += "."
            result.append(content)

        # Check for inline header + bullet (e.g., "### Some Header* Bullet")
        elif re.search(r"^#+\s+.+[*\-+]\s+", stripped):
            # Split header from bullet content
            match = re.match(r"(^#+\s+.+?)\s*[*\-+]\s+(.+)", stripped)
            if match:
                header = match.group(1).strip()
                bullet_content = match.group(2).strip()
                result.append(header)
                if bullet_content and not bullet_content.endswith((".", "!", "?")):
                    bullet_content += "."
                result.append(bullet_content)
            else:
                result.append(line)

        else:
            result.append(line)

        i += 1

    return "\n".join(result)


def normalize_asterisk_bullets(markdown: str) -> str:
    """Normalize asterisk (*) bullet points.

    Args:
        markdown: Markdown text with asterisk bullets

    Returns:
        Text with asterisk bullets normalized and periods added
    """
    lines = markdown.split("\n")
    result = []

    for line in lines:
        stripped = line.lstrip()
        if re.match(r"^\*\s+", stripped):
            content = re.sub(r"^\*\s+", "", stripped, count=1).strip()
            if content and not content.endswith((".", "!", "?")):
                content += "."
            result.append(content)
        else:
            result.append(line)

    return "\n".join(result)


def normalize_hyphen_bullets(markdown: str) -> str:
    """Normalize hyphen (-) bullet points.

    Args:
        markdown: Markdown text with hyphen bullets

    Returns:
        Text with hyphen bullets normalized and periods added
    """
    lines = markdown.split("\n")
    result = []

    for line in lines:
        stripped = line.lstrip()
        if re.match(r"^-\s+", stripped):
            content = re.sub(r"^-\s+", "", stripped, count=1).strip()
            if content and not content.endswith((".", "!", "?")):
                content += "."
            result.append(content)
        else:
            result.append(line)

    return "\n".join(result)


def normalize_numbered_bullets(markdown: str) -> str:
    """Normalize numbered (1., 2., etc.) bullet points.

    Args:
        markdown: Markdown text with numbered bullets

    Returns:
        Text with numbered bullets normalized and periods added
    """
    lines = markdown.split("\n")
    result = []

    for line in lines:
        stripped = line.lstrip()
        if re.match(r"^\d+\.\s+", stripped):
            content = re.sub(r"^\d+\.\s+", "", stripped, count=1).strip()
            if content and not content.endswith((".", "!", "?")):
                content += "."
            result.append(content)
        else:
            result.append(line)

    return "\n".join(result)


def normalize_inline_header_bullets(markdown: str) -> str:
    """Normalize inline header + bullet combinations.

    Handles patterns like "### Header* Bullet content"

    Args:
        markdown: Markdown text with inline header bullets

    Returns:
        Text with inline headers and bullets separated
    """
    lines = markdown.split("\n")
    result = []

    for line in lines:
        stripped = line.lstrip()
        if re.search(r"^#+\s+.+[*\-+]\s+", stripped):
            match = re.match(r"(^#+\s+.+?)\s*[*\-+]\s+(.+)", stripped)
            if match:
                header = match.group(1).strip()
                bullet_content = match.group(2).strip()
                result.append(header)
                if bullet_content and not bullet_content.endswith((".", "!", "?")):
                    bullet_content += "."
                result.append(bullet_content)
            else:
                result.append(line)
        else:
            result.append(line)

    return "\n".join(result)


def normalize_nested_bullets(markdown: str) -> str:
    """Normalize nested bullet points (indented bullets).

    Handles multi-level bullets and preserves structure.

    Args:
        markdown: Markdown text with nested bullets

    Returns:
        Text with nested bullets normalized and periods added
    """
    lines = markdown.split("\n")
    result = []

    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Match any bullet pattern (*, -, +) at any indent level
        if re.match(r"^[*\-+]\s+", stripped):
            content = re.sub(r"^[*\-+]\s+", "", stripped, count=1).strip()
            if content and not content.endswith((".", "!", "?")):
                content += "."
            result.append(" " * indent + content)

        # Match numbered bullets at any indent level
        elif re.match(r"^\d+\.\s+", stripped):
            content = re.sub(r"^\d+\.\s+", "", stripped, count=1).strip()
            if content and not content.endswith((".", "!", "?")):
                content += "."
            result.append(" " * indent + content)

        else:
            result.append(line)

    return "\n".join(result)


def normalize_handles_existing_periods(markdown: str) -> str:
    """Normalize bullets while respecting existing periods.

    Prevents double-periods and respects existing punctuation.

    Args:
        markdown: Markdown text with bullets (some may have periods)

    Returns:
        Text with normalized bullets, no double-periods
    """
    lines = markdown.split("\n")
    result = []

    for line in lines:
        stripped = line.lstrip()

        # Match bullet patterns
        if re.match(r"^[*\-+]\s+", stripped):
            content = re.sub(r"^[*\-+]\s+", "", stripped, count=1).strip()
            # Add period only if missing (no double-period)
            if content and not content.endswith((".", "!", "?")):
                content += "."
            result.append(content)

        elif re.match(r"^\d+\.\s+", stripped):
            content = re.sub(r"^\d+\.\s+", "", stripped, count=1).strip()
            # Add period only if missing
            if content and not content.endswith((".", "!", "?")):
                content += "."
            result.append(content)

        else:
            result.append(line)

    return "\n".join(result)


def normalize_markdown_artifacts(text: str) -> str:
    """Normalize markdown bold/italic artifacts before section detection.

    Removes markdown formatting:
    - **bold** → bold
    - __italic__ → italic
    - ***bold-italic*** → bold-italic
    - _text_ → text

    Preserves section headers (###) as they're used by section detection.
    Preserves bullet markers (* at start of line).

    Args:
        text: Text with markdown formatting

    Returns:
        Text with markdown artifacts removed
    """
    # Remove ** (bold) - avoid matching across newlines
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    # Remove __ (bold alternative)
    text = re.sub(r"__([^_\n]+)__", r"\1", text)
    # (?<!\n) skips a "*" right after a newline so bullet markers survive.
    text = re.sub(r"(?<!\n)\*([^*\n]+)\*", r"\1", text)
    text = re.sub(r"_([^_\n]+)_", r"\1", text)

    return text


def normalize_unicode_characters(text: str) -> str:
    """Normalize unicode characters to ASCII equivalents.

    Converts:
    - — (em dash U+2014) → -
    - – (en dash U+2013) → -
    - ' (right single quote U+2019) → '
    - ' (left single quote U+2018) → '
    - " (left double quote U+201C) → "
    - " (right double quote U+201D) → "
    - … (ellipsis U+2026) → ...

    Args:
        text: Text with unicode characters

    Returns:
        Text with unicode characters normalized to ASCII
    """
    text = text.replace("—", "-")
    text = text.replace("–", "-")
    text = text.replace("’", "'")
    text = text.replace("‘", "'")
    text = text.replace("“", '"')
    text = text.replace("”", '"')
    text = text.replace("…", "...")

    return text


def remove_excessive_newlines(text: str) -> str:
    """Remove excessive line breaks (3+ in a row).

    Preserves single and double newlines (important for bullet/section boundaries).
    Converts 3+ consecutive newlines to just 2 (one blank line).

    Args:
        text: Text with potential excessive newlines

    Returns:
        Text with excessive newlines normalized
    """
    # Replace 3+ newlines with exactly 2 (one blank line)
    text = re.sub(r"\n\n\n+", "\n\n", text)
    return text


def normalize_markdown_artifacts_complete(text: str) -> str:
    """Complete markdown + unicode normalization pipeline.

    Applies all three normalization steps in sequence:
    1. Markdown artifacts (bold, italic)
    2. Unicode characters (dashes, quotes, ellipsis)
    3. Excessive newlines

    Preserves section headers and single newlines between bullets.

    Args:
        text: Raw text with markdown/unicode artifacts

    Returns:
        Cleaned text ready for section detection
    """
    text = normalize_markdown_artifacts(text)
    text = normalize_unicode_characters(text)
    text = remove_excessive_newlines(text)

    return text


def contains_bullets(text: str) -> bool:
    """Check if text contains bullet point markers.

    Looks for patterns like:
    - * text (at start or after newline)
    - - text
    - + text
    - 1. text (numbered bullets)

    Args:
        text: Text to check

    Returns:
        True if text contains bullet markers, False otherwise
    """
    return bool(re.search(r"(^|\n)[*\-+]\s+|(^|\n)\d+\.\s+", text, re.MULTILINE))


def split_by_bullet_markers(text: str) -> list[str]:
    """Split text by bullet point markers into individual bullets.

    Handles:
    - * Bullet text
    - - Bullet text
    - + Bullet text
    - 1. Bullet text (numbered)

    Preserves bullet content, removes markers. Handles continuation lines
    (indented text following a bullet).

    Args:
        text: Text with bullet points

    Returns:
        List of bullet texts (content only, no markers)
    """
    bullets: list[str] = []
    lines = text.split("\n")
    current_bullet: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # Check for bullet marker at start of line
        unordered_match = re.match(r"^[*\-+]\s+(.+)", stripped)
        numbered_match = re.match(r"^\d+\.\s+(.+)", stripped)

        if unordered_match or numbered_match:
            if current_bullet:
                bullet_text = " ".join(current_bullet).strip()
                if bullet_text:
                    bullets.append(bullet_text)
                current_bullet = []

            if unordered_match:
                current_bullet.append(unordered_match.group(1))
            elif numbered_match:
                current_bullet.append(numbered_match.group(1))

        elif stripped and indent > 0:
            if current_bullet:
                current_bullet.append(stripped)

        elif stripped and indent == 0 and current_bullet:
            if current_bullet:
                bullet_text = " ".join(current_bullet).strip()
                if bullet_text:
                    bullets.append(bullet_text)
                current_bullet = []
            # Don't add this line to bullets (it's either a section header or other text)

        elif not stripped and current_bullet:
            current_bullet.append("")

        i += 1

    if current_bullet:
        bullet_text = " ".join(current_bullet).strip()
        if bullet_text:
            bullets.append(bullet_text)

    return bullets
