"""Shared fixtures for tokenization tests."""

from unittest.mock import MagicMock, Mock

import pytest
import spacy


def _create_mock_token(text, pos, dep, lemma, is_stop=False, ent_type="", head=None):
    """Helper to create mock token with realistic attributes."""
    token = Mock()
    token.text = text
    token.pos_ = pos
    token.dep_ = dep
    token.lemma_ = lemma
    token.is_stop = is_stop
    token.ent_type_ = ent_type
    token.is_punct = text in ".,!?;"
    if head is None:
        token.head = Mock(pos_="NOUN")
    else:
        token.head = head
    return token


def _create_mock_entity(text, label):
    """Helper to create mock entity."""
    ent = Mock()
    ent.text = text
    ent.label_ = label
    return ent


def _get_pos_tag(word):
    """Assign realistic POS tag based on word."""
    tech_words = ("python", "javascript", "react", "django", "flask", "fastapi")
    noun_words = ("developer", "engineer", "skill", "experience")
    adj_words = ("experienced", "senior", "junior", "motivated")

    if word.lower() in tech_words:
        return "PROPN"
    elif word.lower() in noun_words:
        return "NOUN"
    elif word.lower() in adj_words:
        return "ADJ"
    return "NOUN"


def _get_dep_tag(word):
    """Assign realistic DEP tag based on word."""
    compound_words = ("machine", "learning", "web", "mobile", "cloud")
    if word.lower() in compound_words:
        return "compound"
    return "nmod"


def _extract_entities_from_text(text):
    """Extract entities from text for mocking."""
    entities = []
    entity_map = {
        "python": ("Python", "PRODUCT"),
        "javascript": ("JavaScript", "PRODUCT"),
        "react": ("React", "PRODUCT"),
        "postgresql": ("PostgreSQL", "PRODUCT"),
        "mongodb": ("MongoDB", "PRODUCT"),
        "redis": ("Redis", "PRODUCT"),
        "aws": ("AWS", "PRODUCT"),
        "gcp": ("GCP", "ORG"),
        "google": ("Google", "ORG"),
        "amazon": ("Amazon", "ORG"),
    }
    for keyword, (name, label) in entity_map.items():
        if keyword in text.lower():
            entities.append(_create_mock_entity(name, label))
    return entities


def _create_tokens_from_text(text, words):
    """Create mock tokens with POS/DEP tags."""
    tokens = []
    for i, word in enumerate(words):
        pos = _get_pos_tag(word)
        dep = _get_dep_tag(word)

        parent = None
        if dep == "compound" and i + 1 < len(words):
            parent = _create_mock_token(
                words[i + 1].lower(), "NOUN", "nmod", words[i + 1].lower()
            )

        token = _create_mock_token(word.lower(), pos, dep, word.lower(), head=parent)
        tokens.append(token)
    return tokens


def _process_text_to_doc(text):
    """Convert text to mock spaCy doc with sentences, tokens, entities."""
    doc = MagicMock()

    # Sentence segmentation
    sentences = text.split(". ")
    doc.sents = [
        Mock(text=sent.strip() + ("." if not sent.endswith(".") else ""))
        for sent in sentences
    ]

    # Tokens
    words = text.split()
    tokens = _create_tokens_from_text(text, words)
    doc.__iter__ = Mock(return_value=iter(tokens))

    # Entities
    doc.ents = _extract_entities_from_text(text)

    return doc


@pytest.fixture
def mock_spacy_model():
    """Mock spaCy model for testing without actual model download."""
    model = MagicMock()
    model.side_effect = _process_text_to_doc
    return model


@pytest.fixture
def preprocessor_with_mock(monkeypatch, mock_spacy_model):
    """Preprocessor fixture with mocked spaCy model."""
    from src.tokenization.preprocessor import Preprocessor

    monkeypatch.setattr("spacy.load", lambda model: mock_spacy_model)

    return Preprocessor(model="en_core_web_md")


@pytest.fixture
def mock_spacy_model_with_exceptions():
    """Mock spaCy model that can raise exceptions for testing error paths."""
    model = MagicMock()

    def nlp_processor_with_error(text):
        if text == "__RAISE_EXCEPTION__":
            raise RuntimeError("Simulated spaCy processing error")

        # Normal processing
        doc = MagicMock()
        doc.sents = [Mock(text="Test sentence.")]

        tokens = []
        for word in text.split():
            token = Mock()
            token.text = word.lower()
            token.pos_ = "NOUN"
            token.dep_ = "nmod"
            token.lemma_ = word.lower()
            token.is_stop = False
            token.ent_type_ = ""
            token.is_punct = False
            token.head = Mock()
            tokens.append(token)

        doc.__iter__ = Mock(return_value=iter(tokens))
        doc.ents = []
        return doc

    model.side_effect = nlp_processor_with_error
    return model


@pytest.fixture
def preprocessor_with_exceptions(monkeypatch, mock_spacy_model_with_exceptions):
    """Preprocessor with exception-raising mock for error testing."""
    from src.tokenization.preprocessor import Preprocessor

    monkeypatch.setattr("spacy.load", lambda model: mock_spacy_model_with_exceptions)

    return Preprocessor(model="en_core_web_md")
