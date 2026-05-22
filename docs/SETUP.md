# NLP & Text Processing Setup Guide (Issue #7)

**Status**: ✅ Complete
**Python Version**: 3.12.x recommended
**Components**: spaCy 3.8.14, MarkItDown, tiktoken, Pydantic v2

---

## Quick Start (5 minutes)

### 1. Pin Python to 3.12 (Recommended)
```bash
# This creates .python-version file
uv python pin 3.12

# Verify
uv python list | grep "in use"
```

### 2. Install Dependencies
```bash
# Install all core and dev dependencies
uv sync --all-extras

# Or install core only
uv sync
```

### 3. Download NLP Model
```bash
# Download spaCy en_core_web_md model (~32 MB)
python -m spacy download en_core_web_md

# Verify installation
python -c "import spacy; nlp = spacy.load('en_core_web_md'); print('✅ Model loaded')"
```

### 4. Validate Setup
```bash
# Run comprehensive validation
python -m src.setup.validate_nlp_setup

# Expected output: ✅ ALL CRITICAL COMPONENTS OK
```

---

## Detailed Setup Instructions

### Python Version Strategy

**Recommended**: Python 3.12.x (bugfix phase, EOL 2028-10)
**Alternative**: Python 3.13+ (security-only, newer features)
**Not Recommended**: Python 3.11 (legacy, performance slower)

| Version | Status | EOL | Recommendation |
|---------|--------|-----|-----------------|
| 3.11 | Legacy | 2027-10 | ❌ Avoid |
| **3.12** | Bugfix | 2028-10 | ✅ **Recommended** |
| 3.13 | Security | 2029-10 | ⚠️ OK for dev |

#### Install Python 3.12 (if not available)

**Using uv** (recommended):
```bash
# Auto-download Python 3.12
uv python install 3.12

# Or download specific version
uv python install 3.12.12
```

**Using pyenv** (macOS/Linux):
```bash
# Install Python 3.12.12
pyenv install 3.12.12

# Set as project version
pyenv local 3.12.12
```

**Using Homebrew** (macOS):
```bash
brew install python@3.12
# Set in .python-version or environment
```

**Windows**: Download from [python.org](https://www.python.org/downloads/)

### System Dependencies

#### Ubuntu/Debian
```bash
# Required for lxml (C bindings)
sudo apt-get update
sudo apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    python3-dev \
    build-essential

# Verify
python3-config --includes  # Should show paths
```

#### macOS
```bash
# Install via Homebrew
brew install libxml2 libxslt

# If compilation fails, use custom paths:
export LDFLAGS="-L$(brew --prefix libxml2)/lib"
export CPPFLAGS="-I$(brew --prefix libxml2)/include"
uv pip install lxml
```

#### Windows
```bash
# No action needed - pre-built wheels auto-install
pip install lxml  # Should work without compilation
```

### Core Dependencies

All dependencies automatically installed with `uv sync`:

| Package | Version | Purpose | Status |
|---------|---------|---------|--------|
| **spacy** | >=3.8.0 | NLP preprocessing, NER | ✅ |
| **markitdown** | >=0.1.5 | HTML → Markdown cleaning | ✅ |
| **beautifulsoup4** | >=4.12.0 | HTML fallback parser | ✅ |
| **lxml** | >=4.9.0 | Fast C-based parser (optional) | ✅ |
| **tiktoken** | >=0.8.0 | Token counting for Claude API | ✅ |
| **pydantic** | >=2.5.0 | Data validation (v2 required) | ✅ |
| **anthropic** | >=0.25.0 | Claude API client | ✅ |
| **playwright** | >=1.48.0 | Browser automation | ✅ |

### spaCy Model Installation

**Recommended Model**: `en_core_web_md` (balanced speed/accuracy)

```bash
# Download specific model
python -m spacy download en_core_web_md

# Alternative models
python -m spacy download en_core_web_sm  # Small, fast (not recommended)
python -m spacy download en_core_web_lg  # Large, accurate (slower)

# Verify
python -c "import spacy; nlp = spacy.load('en_core_web_md'); print(nlp('Test').ents)"
```

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| en_core_web_sm | 12 MB | Very Fast | Good | Testing/dev |
| **en_core_web_md** | 41 MB | Balanced | Better | ✅ **Recommended** |
| en_core_web_lg | 551 MB | Slow | Best | High-precision NER |

### Validation & Testing

#### Run Validation Script
```bash
python -m src.setup.validate_nlp_setup

# Output shows:
# ✅ Python version check
# ✅ spaCy installation & model
# ✅ Pydantic v2 compatibility
# ✅ tiktoken token counting
# ✅ MarkItDown HTML cleaning
# ✅ lxml C bindings (optional)
# ✅ System dependencies
```

#### Run Full Test Suite
```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_preprocessor.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

#### Quick Integration Test
```python
# Test spaCy + NER
python << 'EOF'
import spacy
nlp = spacy.load("en_core_web_md")
doc = nlp("Senior Python developer needed at Microsoft in Seattle")
print(f"Entities: {[(ent.text, ent.label_) for ent in doc.ents]}")
EOF

# Expected output: Entities with PERSON, ORG, GPE, etc.
```

---

## Troubleshooting

### spaCy Model Not Found

**Error**: `[E050] Can't find model 'en_core_web_md'`

**Solutions**:
```bash
# Download model
python -m spacy download en_core_web_md

# Check installed models
python -m spacy info

# Verify environment
python -c "import spacy; print(spacy.util.get_model_path('en_core_web_md'))"
```

### lxml Missing

**Error**: `ImportError: lxml is not available`

**Symptoms**: HTML processing slow (3-5x slower with html.parser)

**Solutions**:

*Ubuntu/Debian*:
```bash
sudo apt-get install libxml2-dev libxslt-dev python3-dev
pip install lxml
```

*macOS*:
```bash
brew install libxml2 libxslt
# If still fails:
LDFLAGS="-L$(brew --prefix libxml2)/lib" \
CPPFLAGS="-I$(brew --prefix libxml2)/include" \
pip install lxml
```

**Fallback**: Script automatically falls back to `html.parser` if lxml unavailable (slower but works)

### MarkItDown Installation Fails

**Error**: `ModuleNotFoundError: No module named 'markitdown'`

**Solutions**:
```bash
# Install minimal (HTML only, recommended)
uv pip install markitdown

# Install full (includes PDF, Office support)
uv pip install "markitdown[all]"  # ~100MB additional

# Test
python -c "import markitdown; print('✅ MarkItDown OK')"
```

### Python Version Mismatch

**Error**: `Python 3.X found, but 3.12+ required`

**Solutions**:
```bash
# Pin Python 3.12
uv python pin 3.12

# Or set manually
echo "3.12" > .python-version

# Verify
python --version  # Should show 3.12.x
```

### Playwright Chromium Not Found

**Error**: Playwright browser fails to start

**Solutions**:
```bash
# Pre-download Chromium binary
python -m playwright install chromium

# Or with verbose output
python -m playwright install chromium -v

# Set proxy if behind firewall
export HTTP_PROXY=http://proxy.example.com:8080
python -m playwright install chromium

# Verify
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); print('✅ Playwright OK'); b.close(); p.stop()"
```

### Token Count Mismatch

**Note**: tiktoken estimates ±1% variance from actual Claude tokens (normal)

**Tracking**:
```python
# In cost_tracking table:
# - estimated_tokens: From tiktoken pre-calculation
# - actual_tokens: From Claude API response
# - variance: Difference (usually <1%)

# Check variance
db.query("""
    SELECT
        AVG(ABS(actual_tokens - estimated_tokens) * 100.0 / actual_tokens) as variance_pct
    FROM cost_tracking
""")
```

---

## Performance Benchmarks

Expected performance on Python 3.12:

| Operation | Time | Notes |
|-----------|------|-------|
| Python startup | ~0.5s | First import |
| spaCy model load | ~1-2s | One-time per process |
| Token counting (100 tokens) | <1ms | tiktoken |
| HTML processing (100 jobs) | <30s | Semantic chunking |
| Test suite (16 tests) | 0.06s | All core tests |
| Validation script | <1s | Full environment check |

---

## Environment Variables

Optional configuration in `.env`:

```bash
# spaCy configuration
SPACY_HOME=~/.spacy/models          # Where to store models
SPACY_DOWNLOAD_LOGLEVEL=INFO        # Verbose output

# Proxy configuration (if behind corporate firewall)
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=https://proxy.example.com:8443
NO_PROXY=localhost,127.0.0.1

# Python behavior
PYTHONUNBUFFERED=1                  # Unbuffered output
PYTHONDONTWRITEBYTECODE=1           # No .pyc files

# Token counting
TIKTOKEN_CACHE_DIR=~/.cache/tiktoken  # Where to cache encodings
```

---

## Next Steps

1. **Validate Setup**: `python -m src.setup.validate_nlp_setup` ✅
2. **Run Tests**: `pytest tests/ -v` ✅
3. **Test NLP Pipeline**: `python -m src.cli preprocess --show-estimates`
4. **Review Documentation**: See `docs/COMPATIBILITY.md` for detailed dependency matrix

---

## Related Documentation

- **Issue #7**: GitHub Issue #7 – NLP & Text Processing Setup
- **Implementation Plan**: `docs/implementation-planning/issue-7-nlp-setup-implementation.md`
- **Dependency Matrix**: `docs/COMPATIBILITY.md` (§ Dependency Conflict Matrix)
- **Validation Script**: `src/setup/validate_nlp_setup.py`
- **Dev Notes**: `docs/dev-note/issue-7-implementation-progress.md`

---

## Support

For issues:

1. **Check Validation Script**: `python -m src.setup.validate_nlp_setup` provides diagnostics
2. **Review Logs**: `tail -f logs/app.log` for detailed error messages
3. **Check Compatibility**: See `docs/COMPATIBILITY.md` for known issues
4. **File Issue**: Include validation script output when filing bugs

---

**Last Updated**: 2026-05-20
**Status**: Complete ✅
**Python**: 3.12.12 verified
