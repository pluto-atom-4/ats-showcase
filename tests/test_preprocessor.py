"""Tests for preprocessing functionality."""

import pytest

from tokenization.chunker import SemanticChunker
from tokenization.counter import TokenCounter
from tokenization.preprocessor import Preprocessor


@pytest.mark.unit
def test_preprocessor_initialization():
    """Test preprocessor with spaCy model."""
    # Skip if model not installed
    try:
        preprocessor = Preprocessor()
        assert preprocessor.model_name == "en_core_web_md"
    except Exception as e:
        pytest.skip(f"spaCy model not available: {e}")


@pytest.mark.unit
def test_semantic_chunker():
    """Test semantic chunking."""
    chunker = SemanticChunker(target_chunk_size=400)

    sentences = [
        "This is sentence one.",
        "This is sentence two.",
        "This is sentence three.",
        "This is sentence four.",
    ]

    chunks = chunker.chunk("test text", sentences)
    # Should chunk into semantic groups
    assert isinstance(chunks, list)


@pytest.mark.unit
def test_token_counter():
    """Test token counting."""
    counter = TokenCounter()

    # Test cost estimation
    cost = counter.estimate_cost(input_tokens=1000, output_tokens=100)
    assert cost > 0
    assert cost < 0.01  # Should be less than a cent for these tokens


@pytest.mark.unit
def test_token_pricing():
    """Verify token pricing constants."""
    counter = TokenCounter()

    # Check pricing is set
    assert counter.CLAUDE_PRICING["input"] > 0
    assert counter.CLAUDE_PRICING["output"] > 0
