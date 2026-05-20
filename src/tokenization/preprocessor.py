"""NLP preprocessing for job postings using spaCy."""

from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class Preprocessor:
    """Preprocess text using spaCy for NLP tasks."""
    
    def __init__(self, model: str = "en_core_web_md"):
        """
        Initialize preprocessor with spaCy model.
        
        Args:
            model: spaCy model name (e.g., en_core_web_md)
        """
        self.model_name = model
        self.nlp = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load spaCy model."""
        # TODO: Implement model loading with error handling
        logger.info(f"Loading spaCy model: {self.model_name}")
    
    def segment_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using spaCy sentence segmentation.
        
        Args:
            text: Input text
        
        Returns:
            List of sentences
        """
        # TODO: Implement sentence segmentation
        return []
    
    def extract_entities(self, text: str) -> Tuple[List[str], List[str], List[str]]:
        """
        Extract named entities (skills, technologies, requirements).
        
        Args:
            text: Input text
        
        Returns:
            Tuple of (skills, technologies, requirements)
        """
        # TODO: Implement entity extraction
        return [], [], []
    
    def remove_stopwords(self, text: str) -> str:
        """
        Remove common stopwords from text.
        
        Args:
            text: Input text
        
        Returns:
            Text with stopwords removed
        """
        # TODO: Implement stopword removal
        return text
