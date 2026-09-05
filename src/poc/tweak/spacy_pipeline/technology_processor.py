"""Technology extraction processor for spaCy pipeline.

Implements entity-based technology detection using spaCy's entity_ruler.
Extracts technologies from SKILLS or KNOWLEDGE section types (B2 decision - Issue #321).

Processes spaCy Doc with classified sections (doc._.classified_sections) and
entity ruler matches (doc.ents), extracting technologies into doc._.technologies
extension.

Classes:
    TechnologyProcessor: spaCy pipeline component for technology extraction

Usage:
    >>> import spacy
    >>> from src.poc.tweak.spacy_pipeline import TechnologyProcessor
    >>>
    >>> nlp = spacy.load("en_core_web_md")
    >>> # Ensure entity_ruler is registered (done in batch_processor.py)
    >>> processor = TechnologyProcessor(nlp, "technology_processor")
    >>> nlp.add_pipe("technology_processor", last=True)
    >>>
    >>> doc = nlp("Experience with Python, Docker, and AWS")
    >>> doc._.technologies
    [{"tech": "python", "confidence": 1.0}, {"tech": "docker", "confidence": 1.0}]

Issue #321: Implement technology processor for batch pipeline.
"""

import logging
from typing import Any, Dict, List

from spacy.language import Language
from spacy.tokens import Doc

from src.poc.tweak.patterns import SectionType
from src.poc.tweak.spacy_pipeline.patterns import TECH_TERMS

logger = logging.getLogger(__name__)


def _generate_patterns():
    """Generate entity ruler patterns for technology terms.

    Converts TECH_TERMS into spaCy entity_ruler patterns with case-insensitive
    matching.

    Returns:
        List of pattern dicts with label="TECH" and pattern=token specs
    """
    patterns = []
    for term in TECH_TERMS:
        # Check if it's a multi-word phrase
        if " " in term:
            # Phrase pattern: Case-insensitive by using LOWER
            # 'computer vision' -> [{'LOWER': 'computer'}, {'LOWER': 'vision'}]
            tokens = term.lower().split()
            patterns.append({"label": "TECH", "pattern": [{"LOWER": t} for t in tokens]})
        else:
            # Single word pattern: Simple case-insensitive token match
            # 'PyTorch' -> {'LOWER': 'pytorch'}
            patterns.append({"label": "TECH", "pattern": [{"LOWER": term.lower()}]})
    return patterns


class TechnologyProcessor:
    """spaCy pipeline component for technology extraction.

    Reads classified sections from doc._.classified_sections and extracts
    technologies from sections classified as SKILLS or KNOWLEDGE types.

    Uses pre-registered entity_ruler (D5 decision) to identify technology
    entities (doc.ents with label="TECH").

    Attributes:
        nlp: spaCy Language object
        _name: Component identifier for logging
    """

    def __init__(self, nlp: Language, name: str) -> None:
        """Initialize TechnologyProcessor.

        Ensures entity_ruler is present in pipeline and registers doc._.technologies
        extension if not already present.

        Args:
            nlp: spaCy Language object (required by factory pattern)
            name: Component name for logging (typically 'technology_processor')

        Raises:
            ValueError: If name is None or empty
        """
        if not name:
            raise ValueError("Component name cannot be None or empty")

        self.nlp = nlp
        self._name = name

        # Ensure entity_ruler exists (D5 decision: explicit pre-registration in batch_processor.py)
        # This check is defensive; actual registration happens in run_batch()
        if "entity_ruler" not in nlp.pipe_names:
            logger.warning(
                "entity_ruler not found in pipeline. "
                "TechnologyProcessor expects entity_ruler to be pre-registered. "
                "See batch_processor.py run_batch() for setup."
            )

        # Register Doc extension for technologies if not present
        if not Doc.has_extension("technologies"):
            Doc.set_extension("technologies", default=[])

    def __call__(self, doc: Doc) -> Doc:
        """Process a spaCy Doc and extract technologies.

        Reads doc._.classified_sections and extracts technologies from sections
        classified as SKILLS or KNOWLEDGE types.

        Returns dict list: [{"tech": str, "confidence": 1.0}, ...]

        Handles edge cases gracefully:
        - If doc._.classified_sections is None: treats as empty list
        - If doc._.classified_sections is empty: doc._.technologies = []
        - Extraction errors are logged but do not halt processing

        Args:
            doc: spaCy Doc to process

        Returns:
            Modified doc with doc._.technologies populated

        Raises:
            TypeError: If doc is not a spaCy Doc
        """
        # Get classified sections from doc extension (handle None/missing gracefully)
        classified_sections = doc._.classified_sections if doc._.classified_sections else []

        # Extract technologies from sections
        technologies: List[Dict[str, Any]] = []
        seen_techs: set = set()  # Deduplicate technologies

        for section, classification in classified_sections:
            try:
                # Filter to SKILLS or KNOWLEDGE section types (B2 decision)
                # Technologies are typically listed in skills or knowledge sections
                if (
                    SectionType.SKILLS not in classification.labels
                    and SectionType.KNOWLEDGE not in classification.labels
                ):
                    continue

                # Extract TECH entities from doc (already processed by entity_ruler in pipeline)
                # We filter by section here by checking the entity text position in section content
                if section.content:
                    try:
                        section_doc = self.nlp(section.content)
                    except Exception as e:
                        logger.error(f"Failed to process section content: {e}")
                        continue

                    # Extract all TECH entities and normalize to lowercase for deduplication
                    for ent in section_doc.ents:
                        if ent.label_ == "TECH":
                            tech_text = ent.text.lower()
                            if tech_text and tech_text not in seen_techs:
                                technologies.append({"tech": tech_text, "confidence": 1.0})
                                seen_techs.add(tech_text)

            except Exception as e:
                logger.error(f"Error extracting technologies from section '{section.title}': {e}")
                # Continue with next section
                continue

        # Store extracted technologies in doc extension
        doc._.technologies = technologies

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
