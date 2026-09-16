"""Skill extraction processor for spaCy pipeline.

Implements pattern-based skill detection using spaCy Matcher with action verb lemmas.
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
"""

import logging
from typing import Any, Dict, List

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc
from spacy.util import filter_spans

from src.poc.tweak.patterns import SectionType
from src.poc.tweak.spacy_pipeline.patterns import SKILL_VERBS

logger = logging.getLogger(__name__)


class SkillProcessor:
    """spaCy pipeline component for skill extraction.

    Reads classified sections from doc._.classified_sections and extracts
    skills from sections classified as SKILLS type only.

    Uses spaCy Matcher with action verb lemmas to identify skill phrases.

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

        # Define the Matcher Pattern
        # Logic: [Action Verb] + [Optional Preposition/Article] + [Descriptive Nouns/Adjectives]
        pattern = [
            # The Action: Must be a verb and its base form must be in our list
            {"POS": "VERB", "LEMMA": {"IN": SKILL_VERBS}},
            # Optional: Connector words like "with", "the", "of"
            # (e.g., "partner WITH", "lead THE")
            {"POS": {"IN": ["ADP", "DET", "PART"]}, "OP": "?"},
            # The Meat: A sequence of Nouns, Adjectives, or Proper Nouns
            # (e.g., "novel deep learning architectures")
            # Note: ADP excluded from this group (prepositions shouldn't appear as descriptors)
            {"POS": {"IN": ["ADJ", "NOUN", "PROPN"]}, "OP": "+"},
        ]

        # Add pattern to matcher
        self.matcher.add("SKILL_PHRASE", [pattern])

        # Register Doc extension for skills if not present
        if not Doc.has_extension("skills"):
            Doc.set_extension("skills", default=[])

    def __call__(self, doc: Doc) -> Doc:
        """Process a spaCy Doc and extract skills.

        Reads doc._.classified_sections and extracts skills from sections
        classified as SKILLS type only.

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
        # Get classified sections from doc extension (handle None/missing gracefully)
        classified_sections = doc._.classified_sections if doc._.classified_sections else []

        # Extract skills from sections
        skills: List[Dict[str, Any]] = []
        seen_skills: set = set()  # Deduplicate skills

        for section, classification in classified_sections:
            try:
                # Filter to SKILLS section type only (B2 decision)
                if SectionType.SKILLS not in classification.labels:
                    continue

                # Confidence gate (Issue #347). If all_types is empty/absent,
                # fall back to labels-only behavior above (backward compatible).
                all_types = getattr(classification, "all_types", None)
                if all_types:
                    top_type = all_types[0]
                    if top_type.section_type == SectionType.SKILLS:
                        skills_confidence = top_type.confidence
                    else:
                        # SKILLS+TECHNOLOGIES overlap (e.g. "Technical Stack" section
                        # classified TECHNOLOGIES (0.85) / SKILLS (0.72)): unlike
                        # RequirementProcessor's top-ranked-only rule, extraction here
                        # keys off SKILLS' own confidence, scanned from all_types,
                        # even when SKILLS isn't the #1-ranked type.
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

                # Combine title and content for processing
                text_to_process = ""
                if section.title:
                    text_to_process += section.title + " "
                if section.content:
                    text_to_process += section.content

                if not text_to_process.strip():
                    continue

                # Process text through spaCy
                try:
                    skill_doc = self.nlp(text_to_process)
                except Exception as e:
                    logger.error(f"Failed to process skills text: {e}")
                    continue

                # Find matches using matcher
                try:
                    matches = self.matcher(skill_doc, as_spans=True)

                    # Filter overlapping spans
                    unique_spans = filter_spans(matches)

                    # Extract skill text, normalize, and deduplicate
                    for span in unique_spans:
                        skill_text = span.text.replace("\n", " ").strip().lower()
                        if skill_text and skill_text not in seen_skills:
                            skills.append({"skill": skill_text, "confidence": 1.0})
                            seen_skills.add(skill_text)

                except Exception as e:
                    logger.error(f"Matcher extraction failed for section '{section.title}': {e}")
                    continue

            except Exception as e:
                logger.error(f"Error extracting skills from section '{section.title}': {e}")
                # Continue with next section
                continue

        # Store extracted skills in doc extension
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
