"""Skill extraction processor for spaCy pipeline.

Implements pattern-based skill detection using spaCy Matcher with action verb lemmas
and noun-led fallback for bullet-point skills (Issue #372).

Extracts skills from SKILLS section type only (B2 decision - Issue #321).

Processes spaCy Doc with classified sections (doc._.classified_sections) and
extracts skills into doc._.skills extension.

Classes:
    SkillProcessor: spaCy pipeline component for skill extraction

Usage:
    >>> import spacy
    >>> from src.poc.tweak.spacy_pipeline import SkillProcessor
    >>>
    >>> nlp = spacy.load("en_core_web_md")
    >>> processor = SkillProcessor(nlp, "skill_processor")
    >>> nlp.add_pipe("skill_processor", last=True)
    >>>
    >>> doc = nlp("Building scalable architectures with Python")
    >>> doc._.skills
    [{"skill": "building scalable architectures", "confidence": 1.0}]

Issue #321: Implement skill processor for batch pipeline.
Issue #372: Add noun-led fallback for bullet-point skills.
"""

import logging
import re
from typing import Any, Dict, List, Set

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc
from spacy.util import filter_spans

from src.poc.tweak.patterns import SectionType
from src.poc.tweak.spacy_pipeline.patterns import QUALIFIER_STOPLIST, SKILL_VERBS, TECH_TERMS

logger = logging.getLogger(__name__)


class SkillProcessor:
    """spaCy pipeline component for skill extraction.

    Reads classified sections from doc._.classified_sections and extracts
    skills from sections classified as SKILLS type only.

    Uses spaCy Matcher with action verb lemmas to identify skill phrases.
    Falls back to noun-led extraction for bullet-point skills when verb
    matcher yields no results (Issue #372).

    Attributes:
        nlp: spaCy Language object
        _name: Component identifier for logging
        matcher: spaCy Matcher instance for skill pattern matching
    """

    def __init__(self, nlp: Language, name: str, min_confidence: float = 0.70) -> None:
        """Initialize SkillProcessor.

        Creates Matcher pattern for skill detection and registers doc._.skills
        extension if not already present.

        Args:
            nlp: spaCy Language object (required by factory pattern)
            name: Component name for logging (typically 'skill_processor')
            min_confidence: Minimum confidence threshold for SKILLS classification
                (Issue #347). Default 0.70. See __call__ for threshold logic.

        Raises:
            ValueError: If name is None or empty
        """
        if not name:
            raise ValueError("Component name cannot be None or empty")

        self.nlp = nlp
        self._name = name
        self.min_confidence = min_confidence
        self.matcher = Matcher(nlp.vocab)

        pattern = [
            {"POS": "VERB", "LEMMA": {"IN": SKILL_VERBS}},
            {"POS": {"IN": ["ADP", "DET", "PART"]}, "OP": "?"},
            {"POS": {"IN": ["ADJ", "NOUN", "PROPN", "VERB"]}, "OP": "+"},
        ]

        self.matcher.add("SKILL_PHRASE", [pattern])

        if not Doc.has_extension("skills"):
            Doc.set_extension("skills", default=[])

    def _is_title_echo(self, line: str, section_title: str) -> bool:
        """Check if line merely echoes the section title (e.g., 'Technical Skills').

        Args:
            line: The line to check
            section_title: The section title

        Returns:
            True if line appears to be an echo of the title
        """
        if not section_title:
            return False
        line_lower = line.lower().strip()
        title_lower = section_title.lower().strip()
        return line_lower == title_lower or line_lower == title_lower.rstrip(":")

    def _strip_bullet_marker(self, line: str) -> str:
        """Strip leading bullet markers (-, *, •, numbered 1.).

        Args:
            line: The line to process

        Returns:
            Line with bullet marker removed
        """
        line = line.lstrip()
        line = re.sub(r"^[-*•]\s*", "", line)
        line = re.sub(r"^\d+\.\s*", "", line)
        return line

    def _is_colon_terminated_header(self, line: str) -> bool:
        """Check if line is a colon-terminated header (e.g., 'Skills:').

        Args:
            line: The line to check

        Returns:
            True if line ends with ':' and contains only alphanumeric/spaces before it
        """
        stripped = line.strip()
        if not stripped.endswith(":"):
            return False
        before_colon = stripped[:-1].strip()
        return bool(re.match(r"^[\w\s]+$", before_colon))

    def _split_skill_items(self, text: str) -> List[str]:
        """Split text on delimiter characters (comma, semicolon, forward slash, 'and').

        Args:
            text: The text to split

        Returns:
            List of skill items
        """
        # Replace ' and ' with a delimiter
        text = re.sub(r"\s+and\s+", ",", text, flags=re.IGNORECASE)
        # Split on comma, semicolon, or forward slash
        items = re.split(r"[,;/]", text)
        # Strip whitespace from each item
        return [item.strip() for item in items if item.strip()]

    def _strip_trailing_qualifiers(self, text: str) -> str:
        """Strip trailing qualifier words (required, preferred, experience, etc).

        Args:
            text: The text to process

        Returns:
            Text with trailing qualifiers removed
        """
        words = text.split()
        if not words:
            return ""

        # Check if last word (or last two words for 'a plus') is in stoplist
        while words:
            last_word = words[-1].lower().rstrip(".,;:")
            if len(words) >= 2:
                last_two = " ".join(words[-2:]).lower().rstrip(".,;:")
                if last_two in QUALIFIER_STOPLIST:
                    words = words[:-2]
                    continue
            if last_word in QUALIFIER_STOPLIST:
                words.pop()
            else:
                break

        return " ".join(words)

    def _has_whole_token_tech_term(self, doc: Any) -> bool:
        """Check if doc contains any whole-token TECH_TERMS or special tokens.

        Uses whole-token matching: tokenizes chunk and compares actual tokens
        against TECH_TERMS (with word boundaries for multi-word terms).

        Args:
            doc: spaCy Doc to check (must be pre-parsed)

        Returns:
            True if chunk contains a tech term or special token
        """
        special_tokens = {"c++", "c#", "sql"}

        doc_tokens_lower = {token.text.lower() for token in doc}

        if doc_tokens_lower & special_tokens:
            return True

        for tech_term in TECH_TERMS:
            tech_lower = tech_term.lower()
            if " " not in tech_term:
                if tech_lower in doc_tokens_lower:
                    return True
            else:
                doc_text = " ".join(token.text.lower() for token in doc)
                # Word boundaries so a multi-word term does not match inside a longer word.
                pattern = r"\b" + re.escape(tech_lower) + r"\b"
                if re.search(pattern, doc_text):
                    return True

        return False

    def _is_tech_token(self, token: Any) -> bool:
        """Check if a token is a recognized tech term.

        Args:
            token: spaCy token

        Returns:
            True if token is a tech term
        """
        special_tokens = {"c++", "c#", "sql"}
        token_lower = token.text.lower()

        if token_lower in special_tokens:
            return True

        if token_lower in TECH_TERMS:
            return True

        return False

    def _is_valid_skill_chunk(self, chunk_text: str) -> bool:
        """Validate a skill chunk against noise filters.

        Args:
            chunk_text: The chunk to validate

        Returns:
            True if chunk passes all filters
        """
        chunk_text = chunk_text.strip()
        if not chunk_text:
            return False

        try:
            chunk_doc = self.nlp(chunk_text)
        except Exception:
            return False

        # At most 6 tokens.
        if len(chunk_doc) > 6:
            return False

        chunk_lower = chunk_text.lower()
        if chunk_lower in QUALIFIER_STOPLIST:
            return False

        has_noun_propn_x = any(token.pos_ in ("NOUN", "PROPN", "X") for token in chunk_doc)

        for token in chunk_doc:
            # Reject chunks containing a verb, auxiliary or pronoun token unless it is a tech term ("going forward" vs
            # "Go").
            if token.pos_ in ("VERB", "AUX", "PRON"):
                if not self._is_tech_token(token):
                    return False

        has_tech_term = self._has_whole_token_tech_term(chunk_doc)

        if not has_noun_propn_x and not has_tech_term:
            return False

        return True

    def _extract_noun_led_skills(self, line: str, section_title: str) -> List[str]:
        """Extract skills from a line using noun-led fallback strategy.

        Args:
            line: The line to process
            section_title: The section title (for title echo detection)

        Returns:
            List of skill strings
        """
        if self._is_title_echo(line, section_title):
            return []

        line = self._strip_bullet_marker(line)

        if self._is_colon_terminated_header(line):
            return []

        line = line.strip()
        if not line:
            return []

        items = self._split_skill_items(line)

        skills = []
        for item in items:
            item = self._strip_trailing_qualifiers(item)
            item = item.strip()

            if self._is_valid_skill_chunk(item):
                skills.append(item.lower())

        return skills

    def __call__(self, doc: Doc) -> Doc:
        """Process a spaCy Doc and extract skills.

        Reads doc._.classified_sections and extracts skills from sections
        classified as SKILLS type only.

        Only section content lines are candidates; section titles and literal
        "#" heading lines are never extracted (Issue #375).

        For each line:
        1. First attempts verb-led extraction using Matcher
        2. If verb Matcher yields no spans, falls back to noun-led extraction
           (Issue #372) from bullet-point formatted skills

        Returns dict list: [{"skill": str, "confidence": 1.0}, ...]

        Handles edge cases gracefully:
        - If doc._.classified_sections is None: treats as empty list
        - If doc._.classified_sections is empty: doc._.skills = []
        - Extraction errors are logged but do not halt processing

        Args:
            doc: spaCy Doc to process

        Returns:
            Modified doc with doc._.skills populated

        Raises:
            TypeError: If doc is not a spaCy Doc
        """
        classified_sections = doc._.classified_sections if doc._.classified_sections else []

        skills: List[Dict[str, Any]] = []
        seen_skills: Set[str] = set()

        for section, classification in classified_sections:
            try:
                if SectionType.SKILLS not in classification.labels:
                    continue

                # Confidence gate (Issue #347). If all_types is empty/absent, the gate is skipped.
                all_types = getattr(classification, "all_types", None)
                if all_types:
                    top_type = all_types[0]
                    if top_type.section_type == SectionType.SKILLS:
                        skills_confidence = top_type.confidence
                    else:
                        # SKILLS is a label but not ranked first: look up its own confidence so the gate still applies.
                        skills_entry = next(
                            (tc for tc in all_types if tc.section_type == SectionType.SKILLS),
                            None,
                        )
                        skills_confidence = skills_entry.confidence if skills_entry else None

                    if skills_confidence is not None and skills_confidence < self.min_confidence:
                        logger.info(
                            f"Skipping SKILLS extraction: confidence {skills_confidence:.2f} "
                            f"< threshold {self.min_confidence:.2f}"
                        )
                        continue

                # Only content lines are candidate text; section titles are not (Issue #354, Issue #375).
                text_lines = []
                if section.content:
                    text_lines.extend(section.content.splitlines())

                if not text_lines:
                    continue

                for line in text_lines:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue

                    # Skip markdown heading lines so heading text never reaches the Matcher or noun-led fallback (Issue
                    # #375).
                    if line_stripped.startswith("#"):
                        continue

                    try:
                        skill_doc = self.nlp(line_stripped)
                    except Exception as e:
                        logger.error(f"Failed to process skills line: {e}")
                        continue

                    try:
                        matches = self.matcher(skill_doc, as_spans=True)

                        unique_spans = filter_spans(matches)

                        for span in unique_spans:
                            skill_text = span.text.strip().lower()
                            if skill_text and skill_text not in seen_skills:
                                skills.append({"skill": skill_text, "confidence": 1.0})
                                seen_skills.add(skill_text)

                    except Exception as e:
                        logger.error(
                            f"Matcher extraction failed for section '{section.title}', line '{line_stripped}': {e}"
                        )
                        continue

                    if not unique_spans:
                        try:
                            noun_led_skills = self._extract_noun_led_skills(line_stripped, section.title or "")
                            for skill_text in noun_led_skills:
                                if skill_text and skill_text not in seen_skills:
                                    skills.append({"skill": skill_text, "confidence": 1.0})
                                    seen_skills.add(skill_text)
                        except Exception as e:
                            logger.error(
                                f"Noun-led extraction failed for section '{section.title}', line '{line_stripped}': {e}"
                            )
                            continue

            except Exception as e:
                logger.error(f"Error extracting skills from section '{section.title}': {e}")
                continue

        doc._.skills = skills

        return doc

    @property
    def name(self) -> str:
        """Component name for logging and identification."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Allow spaCy to set component name."""
        if not value:
            raise ValueError("Component name cannot be None or empty")
        self._name = value
