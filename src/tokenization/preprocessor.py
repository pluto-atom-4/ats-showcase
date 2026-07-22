"""NLP preprocessing for job postings using spaCy."""

import logging
from typing import List, Optional, Tuple

import spacy
from spacy.language import Language

logger = logging.getLogger(__name__)


class Preprocessor:
    """Preprocess text using spaCy for NLP tasks."""

    def __init__(self, model: str = "en_core_web_md"):
        """Initialize preprocessor with spaCy model.

        Args:
            model: spaCy model name (e.g., en_core_web_md)
        """
        self.model_name = model
        self.nlp: Optional[Language] = None
        self._load_model()

    def _load_model(self) -> None:
        """Load spaCy model with error handling.

        Raises:
            OSError: If model cannot be loaded or is not installed.
        """
        try:
            logger.info(f"Loading spaCy model: {self.model_name}")
            self.nlp = spacy.load(self.model_name)
            logger.info(f"Successfully loaded spaCy model: {self.model_name}")
        except OSError as e:
            logger.error(
                f"Failed to load spaCy model '{self.model_name}': {e}. "
                "Ensure it's installed: python -m spacy download en_core_web_md"
            )
            raise

    def segment_sentences(self, text: str) -> List[str]:
        """Split text into sentences using spaCy sentence segmentation.

        Handles edge cases: abbreviations (Dr., Inc.), multiple punctuation.

        Args:
            text: Input text to segment

        Returns:
            List of sentence strings
        """
        if not self.nlp:
            logger.warning("spaCy model not loaded, returning empty list")
            return []

        if not text or not text.strip():
            return []

        try:
            doc = self.nlp(text)
            sentences = [sent.text.strip() for sent in doc.sents]
            logger.debug(f"Segmented text into {len(sentences)} sentences")
            return sentences
        except Exception as e:
            logger.error(f"Error segmenting sentences: {e}")
            return []

    def extract_entities(self, text: str) -> Tuple[List[str], List[str], List[str]]:
        """Extract named entities (skills, technologies, requirements).

        Uses spaCy NER for named entities and POS/DEP tagging for skills/tech.

        Args:
            text: Input text to extract entities from

        Returns:
            Tuple of (skills, technologies, requirements) as unique strings
        """
        if not self.nlp:
            logger.warning("spaCy model not loaded, returning empty lists")
            return [], [], []

        if not text or not text.strip():
            return [], [], []

        skills: set[str] = set()
        technologies: set[str] = set()
        requirements: set[str] = set()

        try:
            doc = self.nlp(text)
            tech_keywords = self._get_tech_keywords()

            # Extract from NER (named entities)
            self._extract_from_ner(doc, tech_keywords, technologies, requirements)

            # Extract from POS tags and noun compounds
            self._extract_from_tokens(doc, tech_keywords, skills, technologies)

            logger.debug(
                f"Extracted {len(skills)} skills, "
                f"{len(technologies)} technologies, "
                f"{len(requirements)} requirements"
            )

            return (
                sorted(skills),
                sorted(technologies),
                sorted(requirements),
            )

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return [], [], []

    @staticmethod
    def _get_tech_keywords() -> set:
        """Get common technology keywords."""
        return {
            "python",
            "javascript",
            "typescript",
            "java",
            "c#",
            "csharp",
            "go",
            "rust",
            "php",
            "ruby",
            "react",
            "vue",
            "angular",
            "node",
            "express",
            "django",
            "flask",
            "fastapi",
            "spring",
            "postgresql",
            "mysql",
            "mongodb",
            "redis",
            "elasticsearch",
            "kafka",
            "aws",
            "gcp",
            "azure",
            "docker",
            "kubernetes",
            "git",
            "sql",
            "html",
            "css",
            "json",
            "xml",
            "rest",
            "graphql",
            "api",
            "ml",
            "ai",
            "tensorflow",
            "pytorch",
            "sklearn",
        }

    @staticmethod
    def _extract_from_ner(doc, tech_keywords, technologies, requirements):
        """Extract entities from named entity recognition."""
        for ent in doc.ents:
            entity_text = ent.text.strip()
            if not entity_text or ent.label_ not in ("PRODUCT", "ORG"):
                continue

            if any(
                keyword in entity_text.lower() for keyword in tech_keywords
            ):
                technologies.add(entity_text)
            else:
                requirements.add(entity_text)

    @staticmethod
    def _extract_from_tokens(doc, tech_keywords, skills, technologies):
        """Extract skills and tech from tokens."""
        exclude_skills = {"senior", "junior", "required", "optional", "available"}

        for token in doc:
            token_text = token.text.strip()
            if not token_text:
                continue

            # Check if token matches tech keywords
            if token_text.lower() in tech_keywords:
                technologies.add(token_text)
            elif token.lemma_.lower() in tech_keywords:
                technologies.add(token.text)

            # Extract noun compounds as skills
            if (
                token.pos_ in ("NOUN", "PROPN")
                and token.dep_ in ("compound", "nmod", "attr")
                and len(token_text) > 3
            ):
                parent = token.head
                if parent.pos_ in ("NOUN", "PROPN"):
                    phrase = " ".join(
                        child.text
                        for child in doc
                        if child.head == parent or child == parent
                    )
                    if len(phrase) > 3 and "job" not in phrase.lower():
                        skills.add(phrase)

            # Extract adjectives
            if token.pos_ == "ADJ" and len(token_text) > 4:
                if token_text.lower() not in exclude_skills:
                    skills.add(token_text)

    def remove_stopwords(self, text: str) -> str:
        """Remove common English stopwords while preserving important terms.

        Uses spaCy's built-in stopwords list. Preserves technical terms
        and important entities.

        Args:
            text: Input text

        Returns:
            Text with stopwords removed
        """
        if not self.nlp:
            logger.warning("spaCy model not loaded, returning original text")
            return text

        if not text or not text.strip():
            return ""

        try:
            doc = self.nlp(text)

            # Terms to preserve (never remove as stopwords)
            preserve_terms = {
                "require",
                "required",
                "must",
                "should",
                "will",
                "ability",
                "experience",
                "skill",
                "knowledge",
                "understanding",
            }

            filtered_tokens = []
            for token in doc:
                # Keep if:
                # 1. Not a stopword
                # 2. Is a stopword but in preserve list
                # 3. Is named entity
                # 4. Is punctuation (keep for structure)
                if (
                    not token.is_stop
                    or token.lemma_.lower() in preserve_terms
                    or token.ent_type_
                    or token.is_punct
                ):
                    filtered_tokens.append(token.text)

            result = " ".join(filtered_tokens).strip()
            logger.debug(
                f"Removed stopwords: {len(doc)} tokens → {len(filtered_tokens)} tokens"
            )
            return result

        except Exception as e:
            logger.error(f"Error removing stopwords: {e}")
            return text
