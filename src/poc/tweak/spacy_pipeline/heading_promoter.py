"""Plain-text heading promotion to markdown section headers.

Promotes plain-text lines that match known job description heading patterns
to markdown section headers (## prefix), enabling MarkdownSpanRuler to
recognize section boundaries in unstructured job descriptions.

Rules for promotion:
- Line must be non-empty after stripping whitespace
- Line must not start with markdown markers (#, *, -, +) or list indicators (digits + .)
- Line must not be already formatted (bold **, italic *, or table |)
- Previous line must be blank OR this is the first line of the document
- Normalised line (casefold, apostrophe normalisation, collapse spaces, strip trailing ':')
  must match a known heading phrase from KNOWN_PLAIN_HEADINGS (exact match)
- Promotion is idempotent: already-promoted lines (starting with ##) are not re-promoted

Also isolates trailing EEO (Equal Opportunity Employer) paragraphs by inserting
a synthesized ## Equal Opportunity Employer heading before them (Issue #374).

Example:
    >>> promoter = HeadingPromoter()
    >>> text = "Job Description\\nRequirements below.\\nRole Overview\\nFocus areas."
    >>> result = promoter.process(text)
    >>> "## Job Description" in result
    True
    >>> "## Role Overview" in result
    True

The promoter is designed to be non-fatal; if any error occurs during processing,
the original text is returned unchanged.
"""

import logging
import re
from typing import FrozenSet, List, Optional, Tuple

from src.poc.tweak.spacy_pipeline.base import PipelineComponent
from src.poc.tweak.spacy_pipeline.heading_text import KNOWN_HEADING_PHRASES
from src.poc.tweak.spacy_pipeline.section_header_keywords import SECTION_HEADER_KEYWORDS_ONLY

logger = logging.getLogger(__name__)

# Promoter-only set: 61 phrases (Issue #365 base set plus live-job-seen extras), none classified 'other'.
# duties, education and nice to have are 'other' but in-vocabulary via SECTION_HEADER_KEYWORDS_ONLY (#733), not here.
# The canonical filter phrases (KNOWN_HEADING_PHRASES) are unioned in below rather than listed twice.
_PROMOTER_ONLY_HEADINGS: FrozenSet[str] = frozenset(
    [
        "ability",
        "about",
        "about the position",
        "about the role",
        "about this opportunity",
        "about this position",
        "about this role",
        "about us",
        "about you",
        "basic qualifications",
        "benefits",
        "compensation",
        "core competencies",
        "core skills",
        "day to day responsibilities",
        "description",
        "desired qualifications",
        "duty",
        "equal opportunity employer",
        "essential",
        "essential functions",
        "essential qualifications",
        "essential requirements",
        "experience",
        "expertise",
        "how to apply",
        "in this role you will",
        "job description",
        "job overview",
        "job responsibilities",
        "knowledge",
        "minimum requirements",
        "organization overview",
        "overview",
        "physical requirements",
        "position description",
        "position overview",
        "preferred requirements",
        "preferred skills",
        "qualifications",
        "required experience",
        "required skills",
        "requirement",
        "requirements",
        "responsibilities",
        "role description",
        "role overview",
        "role responsibilities",
        "salary",
        "skill",
        "skills",
        "summary",
        "technical",
        "technical knowledge",
        "technical skills",
        "travel requirements",
        "what will make you succeed",
        "what you bring",
        "what you will bring",
        "what you will do",
        "work location",
    ]
)

# Full vocabulary (83): promoter-only (61) + canonical filter phrases (6) + 16 section-header keywords (Issue #733).
# Promoting them regardless of SectionClassifier labels is a human decision (#733), not a consistency result.
# The allowlist test pins this behaviour.
KNOWN_PLAIN_HEADINGS: FrozenSet[str] = _PROMOTER_ONLY_HEADINGS | KNOWN_HEADING_PHRASES | SECTION_HEADER_KEYWORDS_ONLY

EEO_HEADING_NORMALIZED = "equal opportunity employer"

# EEO phrase triggers (Issue #374): small, high-precision set, matched in the first sentence, first ~200 chars.
# Known limitation (accepted): generic triggers such as "is an equal opportunity" can false-positive on non-EEO text,
# e.g. "This is an equal opportunity to grow your career."
EEO_TRIGGERS: FrozenSet[str] = frozenset(
    [
        "equal opportunity employer",
        "equal employment opportunity",
        "is an equal opportunity",
        "are an equal opportunity",
        "does not discriminate",
        "affirmative action",
    ]
)

# Markdown heading prefix (Issue #374). Stripped before the known-heading check so that a line already
# promoted to "## Benefits" by an earlier pass still matches "benefits".
HEADING_PREFIX_PATTERN = re.compile(r"^#{1,6}\s+")

# End of a sentence: sentence-ending punctuation followed by whitespace (Issue #374).
# An EEO paragraph is only a candidate when its trigger sits in this first sentence.
FIRST_SENTENCE_END_PATTERN = re.compile(r"[.!?](?=\s)")

# Sentence boundary used to examine every sentence after the first (Issue #374).
# Known limitation (accepted): it also splits after abbreviations such as "U.S.", and the fragment "Applicants from the
# U.S." then blocks isolation.
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")

# DEI vocabulary that may follow an EEO sentence in the same paragraph (Issue #374).
# Known limitation: hand-picked, so a job sentence containing "diversity" is also treated as EEO-ish.
EEO_CONTINUATION_PATTERN = re.compile(r"\b(diversity|diverse|inclusion|inclusive|belonging)\b", re.IGNORECASE)

# "without regard to" + protected-class term within ~60 chars (Issue #374 Defect 3); terms are singular or plural.
# A bare "on the basis of" lead-in is deliberately absent: "Pay is set on the basis of age and experience."
# would otherwise read as an EEO statement.
PROTECTED_CLASS_PATTERN = re.compile(
    r"without regard to\s+.{0,60}?\b(races?|colors?|religions?|religious|sex(?:es)?|genders?|"
    r"national origins?|ages?|disabilit(?:y|ies)|veterans?|sexual orientations?|marital status(?:es)?|"
    r"genetics?)\b",
    re.IGNORECASE,
)

# Disclaimer sentence after an EEO first sentence (Issue #374 round 6): "We do not discriminate." or
# "do/does/will not discriminate" followed by on/against/based, so it does not block isolation.
# Known limitation: a first-person job sentence "We do not discriminat..." is also read as EEO-ish.
DISCRIMINATE_PATTERN = re.compile(
    r"\b(?:(?:we|i)\s+(?:do|will)\s+not\s+discriminat\w*|"
    r"(?:do(?:es)?|will)\s+not\s+discriminat\w*\s+(?:on|against|based)\b)",
    re.IGNORECASE,
)

# "encouraged to apply" (Issue #374 round 6), e.g. "Women, minorities, veterans and individuals with disabilities are
# encouraged to apply."
# Only consulted for sentences after an EEO first sentence, so it cannot trigger isolation by itself.
ENCOURAGED_TO_APPLY_PATTERN = re.compile(r"encouraged to apply", re.IGNORECASE)

# Word boundaries keep "ada" out of "Canada"/"adapt" (Issue #374); ADA is case-sensitive so the language "Ada" passes.
# Bare "contact", "email" and "accommodation" are deliberately absent (they open ordinary job sentences).
# Known limitation: bare "disability" and "by email" still match case-insensitively.
BOILERPLATE_WORD_PATTERN = re.compile(
    r"\b(?:(?-i:ADA)|disability|contact\s+(?:us|hr)|email\s+(?:us|hr)|by\s+email)\b",
    re.IGNORECASE,
)

# Accommodation notices only; "Manage travel accommodation requests" or bare "require ... accommodation" do not match.
# Known limitation: lead-ins "all" and "people" match job wording ("All who require accommodations for travel.").
# Accepted false positives: test_travel_booking_accommodation_wording_is_boilerplate_known_limitation.
ACCOMMODATION_REQUEST_PATTERN = re.compile(
    r"\baccommodations?\b[^.!?]{0,60}\b(?:on|upon|to)\s+request\w*|"
    r"\brequest\w*\s+(?:a\s+)?(?:reasonable\s+)?accommodations?\b|"
    r"\baccommodations?\s+requests?\s+(?:can|may|should|will)\s+be\s+(?:made|submitted|sent|directed)\b|"
    r"\b(?:if\s+you\s+require|should\s+you\s+require)\b[^.!?]{0,80}?\baccommodations?\b|"
    r"\b(?:applicants|candidates|individuals|persons|those|anyone|people|someone|all)\s+(?:who|whom)\s+require\w*\b[^.!?]{0,80}?\baccommodations?\b",
    re.IGNORECASE,
)

# A paragraph that is only a bare "Accommodations" section label (optional trailing colon).
ACCOMMODATION_LABEL_PATTERN = re.compile(r"accommodations?:?", re.IGNORECASE)

# Multi-word boilerplate phrases, matched as plain substrings.
BOILERPLATE_PHRASES: Tuple[str, ...] = (
    "if you need",
    "reasonable accommodation",
    "please contact",
    "get in touch",
)


class HeadingPromoter(PipelineComponent):
    """Promote plain-text section headings to markdown format.

    Scans text line-by-line and converts lines matching known heading patterns
    to markdown section headers (## prefix). This enables structure recovery
    from plain-text job descriptions before the MarkdownSpanRuler parser runs.

    Also isolates trailing EEO paragraphs by inserting a synthesized heading
    before them (Issue #374). An EEO paragraph is a candidate if its first sentence
    contains an EEO trigger phrase (first ~200 characters), or "without regard to"
    followed by a protected-class term within ~60 characters (first ~400 characters).
    Every later sentence of the paragraph must also be EEO-ish: an EEO trigger, a
    protected-class pattern, a discrimination disclaimer (DISCRIMINATE_PATTERN),
    "encouraged to apply", DEI vocabulary, or empty/boilerplate wording. It is isolated
    only if every paragraph after it is empty, boilerplate (ADA/contact/accommodation
    notices), or another EEO paragraph.

    Attributes:
        headings: Frozenset of allowed heading phrases (lowercase, no trailing ':').
                  Defaults to KNOWN_PLAIN_HEADINGS.
    """

    def __init__(self, headings: Optional[FrozenSet[str]] = None) -> None:
        """Initialize the promoter with an optional custom heading set.

        Args:
            headings: Custom frozenset of heading phrases. If None, uses KNOWN_PLAIN_HEADINGS.
        """
        self._headings = headings if headings is not None else KNOWN_PLAIN_HEADINGS

    @property
    def name(self) -> str:
        """Return the component name for logging."""
        return "heading_promoter"

    def process(self, text: str) -> str:
        """Promote plain-text headings to markdown section headers and isolate EEO.

        Processes text in two phases:
        1. Detect and isolate trailing EEO paragraphs by inserting a synthesized
           ## Equal Opportunity Employer heading before them.
        2. Promote plain-text lines matching known heading patterns to ## format.

        The output preserves existing lines; EEO isolation adds a heading and blank
        line; mixed line endings are normalized to the first one detected.
        Idempotent: a second pass over its own output yields the same text.

        Args:
            text: Input text (may be empty, contain CRLF, or Unicode).

        Returns:
            Text with promoted headings and isolated EEO paragraphs. If any error
            occurs, returns original text unchanged (non-fatal error handling).

        Example:
            >>> promoter = HeadingPromoter()
            >>> text = "Job Description\\n\\nWork with clients.\\n\\nRole Overview\\n\\nFocus on delivery."
            >>> result = promoter.process(text)
            >>> result
            '## Job Description\\n\\nWork with clients.\\n\\n## Role Overview\\n\\nFocus on delivery.'
        """
        original = text
        try:
            if not text:
                return text

            # Normalise line endings to the first one detected (CRLF or LF) so mixed input produces uniform output.
            # Everything below works on LF.
            first_newline = text.find("\n")
            line_ending = "\r\n" if first_newline > 0 and text[first_newline - 1] == "\r" else "\n"
            text = text.replace("\r\n", "\n")

            # Phase 1: isolate trailing EEO paragraphs
            text = self._isolate_eeo_paragraphs(text)

            # Phase 2: promote plain-text headings
            lines = text.split("\n")
            result_lines = []

            for i, line in enumerate(lines):
                stripped = line.strip()

                if self._should_promote(stripped, i == 0, i > 0 and not lines[i - 1].strip()):
                    normalized = self._normalize(stripped)
                    if normalized in self._headings:
                        promoted = "## " + stripped.rstrip(":").strip()
                        result_lines.append(promoted)
                    else:
                        result_lines.append(line)
                else:
                    result_lines.append(line)

            result = "\n".join(result_lines)
            if line_ending == "\r\n":
                result = result.replace("\n", "\r\n")
            return result

        except Exception as e:
            logger.warning(f"Error in heading_promoter.process(): {e}")
            return original

    def _isolate_eeo_paragraphs(self, text: str) -> str:
        """Isolate trailing EEO paragraphs by inserting a synthesized heading.

        Detects EEO paragraphs and inserts ## Equal Opportunity Employer before them,
        but only if all paragraphs after the EEO paragraph are empty, boilerplate
        (ADA/contact/accommodation notices) or further EEO paragraphs. A paragraph is
        an EEO candidate when its first sentence has an EEO trigger or a "without regard
        to" protected-class phrase (see _is_eeo_paragraph). Each later sentence of the
        candidate is then checked on its own by _is_eeo_ish_sentence: a sentence that is
        job content makes the whole paragraph a non-EEO paragraph. Insert directly into
        original line list, preserving blank lines and line endings.

        Idempotent: repeated calls produce same result.

        Args:
            text: LF-normalised input text with possible EEO paragraphs (process() converts
                CRLF to LF before calling this method)

        Returns:
            Text with EEO paragraphs isolated under a heading if conditions are met
        """
        if not text:
            return text

        # Input is LF-normalised by process(); the original trailing-newline status is restored on return.
        line_ending = "\n"
        has_trailing_newline = text.endswith(line_ending)

        lines = text.split(line_ending)
        paragraphs, para_starts = self._split_paragraphs_with_indices(lines)

        if len(paragraphs) < 2:
            return text

        # Find the first EEO paragraph such that everything after it is boilerplate or further EEO paragraphs.
        # Because the first qualifying EEO paragraph is chosen, a run of EEO paragraphs is isolated at its first member.
        first_eeo_idx = -1
        for i in range(len(paragraphs)):
            if self._is_eeo_paragraph(paragraphs[i]):
                all_trailing_ok = True
                for j in range(i + 1, len(paragraphs)):
                    if not (self._is_empty_or_boilerplate(paragraphs[j]) or self._is_eeo_paragraph(paragraphs[j])):
                        all_trailing_ok = False
                        break

                if all_trailing_ok:
                    first_eeo_idx = i
                    break

        if first_eeo_idx < 0:
            return text

        eeo_para = paragraphs[first_eeo_idx]
        if not eeo_para:
            return text

        # Guard 1: _is_eeo_paragraph ignores a leading heading marker, so a paragraph whose first line is already
        # a markdown heading can be selected; leave it unchanged rather than heading it twice.
        first_line_stripped = eeo_para[0].strip()
        if HEADING_PREFIX_PATTERN.match(first_line_stripped):
            return text

        # Guard 2: the first line is a known heading. Return unchanged if it is the EEO heading or a 1-line paragraph;
        # otherwise split the heading off so the EEO sentence gets its own synthetic section below it (Issue #493).
        # Applied after Guards 3 and 5, so it only runs when no preceding or existing EEO heading applies.
        heading_text = HEADING_PREFIX_PATTERN.sub("", first_line_stripped).strip("*_: ")
        normalized = self._normalize(heading_text)
        split_glued_heading = False
        if normalized in self._headings:
            if normalized == EEO_HEADING_NORMALIZED or len(eeo_para) < 2:
                return text
            split_glued_heading = True

        # Guard 3: the preceding paragraph ends with a heading
        if first_eeo_idx > 0:
            preceding_para = paragraphs[first_eeo_idx - 1]
            if preceding_para and HEADING_PREFIX_PATTERN.match(preceding_para[-1].strip()):
                return text

        # Guard 5 (silent skip): an EEO heading already exists anywhere in the document, with a "#" marker and/or "*" or
        # "_" emphasis;
        # inserting another would duplicate it.
        for line in lines:
            if self._normalize(line.strip().strip("#*_: ")) == EEO_HEADING_NORMALIZED:
                return text

        insert_line_idx = para_starts[first_eeo_idx]

        result_lines = list(lines)
        # Keep the glued known heading line in place and insert the synthetic EEO heading, with blank lines around it,
        # after that line.
        if split_glued_heading:
            result_lines.insert(insert_line_idx + 1, "")
            result_lines.insert(insert_line_idx + 2, "## Equal Opportunity Employer")
            result_lines.insert(insert_line_idx + 3, "")
        else:
            result_lines.insert(insert_line_idx, "## Equal Opportunity Employer")
            result_lines.insert(insert_line_idx + 1, "")

        result = line_ending.join(result_lines)
        if not has_trailing_newline and result.endswith(line_ending):
            result = result[: -len(line_ending)]
        elif has_trailing_newline and not result.endswith(line_ending):
            result = result + line_ending
        return result

    def _split_paragraphs_with_indices(self, lines: List[str]) -> Tuple[List[List[str]], List[int]]:
        """Split lines into paragraphs, tracking each paragraph's start index.

        Args:
            lines: List of text lines

        Returns:
            Tuple of (paragraphs, start_indices) where start_indices[i] is the
            line index where paragraphs[i] starts in the original lines list
        """
        paragraphs: List[List[str]] = []
        start_indices: List[int] = []
        current_para: List[str] = []
        para_start = 0

        for i, line in enumerate(lines):
            if not line.strip():
                if current_para:
                    paragraphs.append(current_para)
                    start_indices.append(para_start)
                    current_para = []
            else:
                if not current_para:
                    para_start = i
                current_para.append(line)

        if current_para:
            paragraphs.append(current_para)
            start_indices.append(para_start)

        return paragraphs, start_indices

    def _is_eeo_paragraph(self, para: List[str]) -> bool:
        """Check if a paragraph is an EEO paragraph.

        Checks if the paragraph's first sentence (first ~200 chars) matches an EEO trigger
        phrase, or a protected-class pattern within its first ~400 chars. Must not be a
        bullet, table or list line. A leading "#{1,6} " heading marker and trailing ':' on
        the first line are ignored, so a paragraph gives the same answer before and after
        Phase 2 promotes its first line (idempotence, Issue #374).

        Args:
            para: Paragraph as list of lines

        Returns:
            True if paragraph is an EEO paragraph
        """
        if not para:
            return False

        first_line = HEADING_PREFIX_PATTERN.sub("", para[0].strip()).rstrip(":").strip()

        if not first_line or first_line[0] in "#*-+|" or first_line[0].isdigit():
            return False

        para_text = " ".join([first_line] + [line.strip() for line in para[1:]])
        # Triggers are searched in the first sentence only; later sentences are checked below so EEO text is not
        # isolated together with job content (Issue #374).
        first_sentence = self._first_sentence(para_text)
        check_text = first_sentence[:200].casefold()

        triggered = any(trigger in check_text for trigger in EEO_TRIGGERS) or bool(
            PROTECTED_CLASS_PATTERN.search(first_sentence[:400])
        )
        if not triggered:
            return False

        # A paragraph whose later sentences are job content is not an EEO paragraph (Issue #374).
        for sentence in _SENTENCE_SPLIT_PATTERN.split(para_text)[1:]:
            if not self._is_eeo_ish_sentence(sentence):
                return False

        return True

    def _is_eeo_ish_sentence(self, sentence: str) -> bool:
        """Check if a sentence after an EEO trigger is EEO, DEI or boilerplate wording.

        The sentence is EEO-ish if any of these branches matches, checked in this order:
        1. EEO_TRIGGERS: a substring of EEO_TRIGGERS (casefolded) appears in the sentence.
        2. PROTECTED_CLASS_PATTERN: "without regard to" followed by a protected-class term.
        3. DISCRIMINATE_PATTERN: a first-person, or on/against/based, discrimination disclaimer.
        4. ENCOURAGED_TO_APPLY_PATTERN: "encouraged to apply".
        5. EEO_CONTINUATION_PATTERN: DEI vocabulary (diversity, inclusion, belonging, ...).
        6. Boilerplate fallback: the sentence is empty or _is_empty_or_boilerplate is True.

        Args:
            sentence: One sentence of a paragraph

        Returns:
            True if any branch above matches, otherwise False (job content)
        """
        casefolded = sentence.casefold()
        if any(trigger in casefolded for trigger in EEO_TRIGGERS):
            return True
        if PROTECTED_CLASS_PATTERN.search(sentence):
            return True
        if DISCRIMINATE_PATTERN.search(sentence) or ENCOURAGED_TO_APPLY_PATTERN.search(sentence):
            return True
        if EEO_CONTINUATION_PATTERN.search(sentence):
            return True
        return self._is_empty_or_boilerplate([sentence])

    @staticmethod
    def _first_sentence(text: str) -> str:
        """Return the text up to and including the first sentence-ending punctuation.

        Args:
            text: Single-line paragraph text

        Returns:
            The first sentence, or the whole text if no sentence end is found
        """
        match = FIRST_SENTENCE_END_PATTERN.search(text)
        return text[: match.end()] if match else text

    def _is_empty_or_boilerplate(self, para: List[str]) -> bool:
        """Check if paragraph is empty or boilerplate (ADA/contact/accommodation).

        Boilerplate patterns: disability, ADA (uppercase only), contact us/hr, email us/hr,
        by email (whole words); accommodation with a request phrase; a bare "Accommodations"
        label; plus the phrases "if you need", "please contact", "reasonable accommodation"
        and "get in touch". A bare "accommodation" in job content is not boilerplate.

        Args:
            para: Paragraph as list of lines

        Returns:
            True if paragraph is empty or boilerplate
        """
        if not para:
            return True

        text = " ".join(line.strip() for line in para).strip()
        if not text:
            return True

        if BOILERPLATE_WORD_PATTERN.search(text):
            return True

        # Strip a markdown heading marker and emphasis so "## Accommodations", "**Accommodations**" and
        # "_Accommodations_" count as a bare label (Issue #374).
        label_text = HEADING_PREFIX_PATTERN.sub("", text).strip().strip("*_: ")
        if ACCOMMODATION_REQUEST_PATTERN.search(text) or ACCOMMODATION_LABEL_PATTERN.fullmatch(label_text):
            return True

        text_lower = text.lower()
        return any(phrase in text_lower for phrase in BOILERPLATE_PHRASES)

    def _should_promote(self, stripped_line: str, is_first: bool, prev_blank: bool) -> bool:
        """Check if a line is eligible for promotion (before checking against phrase set).

        Args:
            stripped_line: The line after calling .strip()
            is_first: True if this is the first line of the document
            prev_blank: True if the previous line was blank or first line

        Returns:
            True if the line passes structural checks (not already formatted, correct position)
        """
        if not stripped_line:
            return False

        if stripped_line[0] in "#*-+|":
            return False

        if stripped_line[0].isdigit():
            return False

        if stripped_line.startswith("**") and stripped_line.endswith("**"):
            return False

        if re.match(r"^\d+[\.\)]", stripped_line):
            return False

        if not (is_first or prev_blank):
            return False

        return True

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison against known headings.

        Transformations:
        - Convert to lowercase (casefold for Unicode)
        - Normalize apostrophes (' and ' both become ')
        - Collapse multiple spaces to single space
        - Strip trailing ':' and whitespace
        - Strip leading/trailing whitespace

        Args:
            text: Raw text from the line

        Returns:
            Normalised text suitable for set membership testing
        """
        text = text.casefold()

        text = text.replace("\u2019", "'").replace("\u2018", "'")

        text = " ".join(text.split())

        text = text.rstrip(":").strip()

        return text
