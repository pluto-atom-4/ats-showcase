"""Shared fixtures for tokenization tests."""

from unittest.mock import MagicMock, Mock

import pytest
import spacy


@pytest.fixture
def mock_spacy_model():
    """Mock spaCy model for testing without actual model download."""
    model = MagicMock()

    # Mock doc with sentences
    mock_sent1 = Mock()
    mock_sent1.text = "This is a sentence."

    mock_sent2 = Mock()
    mock_sent2.text = "This is another one."

    # Mock tokens for extract_entities
    def create_mock_token(text, pos, dep, lemma, is_stop=False, ent_type="", head=None):
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

    # Mock entities
    def create_mock_entity(text, label):
        ent = Mock()
        ent.text = text
        ent.label_ = label
        return ent

    # Create a callable that returns a doc with configurable sentences/tokens/entities
    def nlp_processor(text):
        doc = MagicMock()

        # Sentence segmentation
        sentences = text.split(". ")
        doc.sents = [
            Mock(text=sent.strip() + ("." if not sent.endswith(".") else ""))
            for sent in sentences
        ]

        # Tokens - split by space with more realistic POS/DEP tagging
        tokens = []
        words = text.split()

        for i, word in enumerate(words):
            # Assign realistic POS tags
            if word.lower() in (
                "python",
                "javascript",
                "react",
                "django",
                "flask",
                "fastapi",
            ):
                pos = "PROPN"
            elif word.lower() in (
                "developer",
                "engineer",
                "skill",
                "experience",
            ):
                pos = "NOUN"
            elif word.lower() in ("experienced", "senior", "junior", "motivated"):
                pos = "ADJ"
            else:
                pos = "NOUN"

            # Assign realistic DEP tags
            if word.lower() in (
                "machine",
                "learning",
                "web",
                "mobile",
                "cloud",
            ):
                dep = "compound"
            elif word == "needed" or word.lower() == "required":
                dep = "nmod"
            else:
                dep = "nmod"

            # Create parent token for compound dependencies
            parent = None
            if dep == "compound" and i + 1 < len(words):
                parent = create_mock_token(
                    words[i + 1].lower(), "NOUN", "nmod", words[i + 1].lower()
                )

            token = create_mock_token(
                word.lower(), pos, dep, word.lower(), head=parent
            )
            tokens.append(token)

        doc.__iter__ = Mock(return_value=iter(tokens))

        # Entities
        doc.ents = []
        if "python" in text.lower():
            doc.ents.append(create_mock_entity("Python", "PRODUCT"))
        if "javascript" in text.lower():
            doc.ents.append(create_mock_entity("JavaScript", "PRODUCT"))
        if "react" in text.lower():
            doc.ents.append(create_mock_entity("React", "PRODUCT"))
        if "postgresql" in text.lower():
            doc.ents.append(create_mock_entity("PostgreSQL", "PRODUCT"))
        if "mongodb" in text.lower():
            doc.ents.append(create_mock_entity("MongoDB", "PRODUCT"))
        if "redis" in text.lower():
            doc.ents.append(create_mock_entity("Redis", "PRODUCT"))
        if "aws" in text.lower():
            doc.ents.append(create_mock_entity("AWS", "PRODUCT"))
        if "gcp" in text.lower():
            doc.ents.append(create_mock_entity("GCP", "ORG"))
        if "google" in text.lower():
            doc.ents.append(create_mock_entity("Google", "ORG"))
        if "amazon" in text.lower():
            doc.ents.append(create_mock_entity("Amazon", "ORG"))

        return doc

    model.side_effect = nlp_processor
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
