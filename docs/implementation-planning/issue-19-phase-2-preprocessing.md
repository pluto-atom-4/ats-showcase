# Issue #19 Phase 2: Preprocessing & Cost Analysis 🔄

**Parent Issue**: #19 - POC: Test Crawl Workflow on Real Career Page
**Phase**: 2 of 5
**Status**: Planning
**Time Estimate**: 30–45 minutes

---

## Objective

Transform raw extracted job postings into clean, semantic chunks with token counts and cost estimates. Validate the 80–90% token reduction savings through preprocessing.

### Success Criteria
- ✅ All 26 extracted jobs cleaned and chunked
- ✅ Token count estimates generated for each job
- ✅ Actual cost estimates calculated (Claude 3.5 pricing)
- ✅ Semantic chunks validated (meaningful boundaries, no truncation)
- ✅ Token reduction verified (target: 80–90% vs raw HTML)
- ✅ Preprocessing pipeline integrated into CLI

---

## Background: Why Preprocessing Matters

**Cost Challenge**: Raw HTML job postings are 5,000–8,000 tokens each (excessive for LLM API calls)

**Solution**: Local preprocessing removes markup, splits into semantic chunks, reducing to 600–1,000 tokens per job

**Expected Savings**:
- Raw HTML per job: ~6,000 tokens × $0.003/1M = **$0.018**
- Cleaned & chunked: ~700 tokens × $0.003/1M = **$0.0021**
- **Savings per job: ~88% reduction**
- **Savings per 100 jobs: $1.80 → $0.21 = 88% cost cut**

---

## Phase 2 Tasks

### Task 2.1: Implement HTML Cleaning (Markup Removal)

**Objective**: Remove HTML tags, scripts, styles, and irrelevant content. Keep semantic text.

#### Implementation Strategy

**Primary Tool**: MarkItDown (Microsoft, HTML → Markdown → clean text)
- Preserves structure (headers, lists, emphasis)
- Removes scripts, styles, navigation
- Handles nested HTML gracefully
- Fallback: BeautifulSoup + lxml if MarkItDown unavailable

**Fallback Tool**: BeautifulSoup + lxml
- Extract text content
- Remove script/style tags
- Strip excess whitespace

#### Steps

1. **Check if MarkItDown is available**
   ```bash
   uv run python -c "import markitdown; print(markitdown.__version__)"
   ```

2. **Create HTML parsing module** (`src/parsers/html.py`)
   - Function: `clean_html(raw_html: str) -> str`
   - Try MarkItDown first, fallback to BeautifulSoup
   - Strip trailing whitespace, normalize newlines
   - Log which tool was used

3. **Test on sample job HTML**
   ```python
   from src.parsers.html import clean_html

   # Load sample raw HTML from extracted job
   with open('data/extracted_jobs/carbonrobotics_jobs.json') as f:
       jobs = json.load(f)
       raw_job = jobs[0]

   # For now, description field is empty in extracted jobs
   # Will need to fetch full job detail page if needed
   ```

4. **Expected Output**
   ```
   Input (raw HTML): <div class="job-post"><h2>Deep Learning...</h2><p>We are seeking...</p>...
   Output (clean text): Deep Learning Engineer

   We are seeking an experienced Deep Learning Engineer...

   Requirements:
   - Python, PyTorch, TensorFlow
   - 3+ years ML experience
   ...
   ```

#### Known Issues
- Extracted jobs have empty `description` field (only title + location extracted in Phase 1)
- May need to fetch full job detail pages separately, OR
- Use title + location as primary preprocessing input for now
- Document this limitation for Phase 3 (verification)

---

### Task 2.2: Implement Semantic Chunking (Sentence-based Splitting)

**Objective**: Split cleaned text into meaningful chunks (sentences/paragraphs), not fixed-size tokens.

#### Why Semantic Chunking?

❌ **Bad approach** (fixed-size token splits):
```
Chunk 1: "Requires 5+ years MES. Must know"
Chunk 2: "Wonderware. Experience with..." ← Broken requirement!
```

✅ **Good approach** (sentence-based):
```
Chunk 1: "Requires 5+ years MES experience."
Chunk 2: "Must know Wonderware software and related platforms."
```

#### Implementation Strategy

**Tool**: spaCy NLP (`en_core_web_md` model)
- Already installed in Phase 1
- Sentence segmentation is extremely fast (~10k sentences/sec)
- Handles contractions, abbreviations, etc.

#### Steps

1. **Create tokenization module** (`src/tokenization/chunking.py`)
   - Function: `chunk_by_sentences(text: str, target_chunk_size: int = 400) -> List[str]`
   - Use spaCy to find sentence boundaries
   - Combine consecutive sentences until approaching target_chunk_size
   - Ensure no chunk exceeds max size

2. **Algorithm Pseudo-code**
   ```python
   def chunk_by_sentences(text, target_size=400):
       doc = nlp(text)  # spaCy NLP
       chunks = []
       current_chunk = []
       current_tokens = 0

       for sent in doc.sents:
           sent_tokens = len(sent.text.split())
           if current_tokens + sent_tokens > target_size and current_chunk:
               # Finalize chunk
               chunks.append(" ".join(current_chunk))
               current_chunk = [sent.text]
               current_tokens = sent_tokens
           else:
               current_chunk.append(sent.text)
               current_tokens += sent_tokens

       if current_chunk:
           chunks.append(" ".join(current_chunk))

       return chunks
   ```

3. **Expected Output**
   ```
   Input text: "Deep Learning Engineer. We are seeking..."

   Chunk 1 (~380 tokens):
   "Deep Learning Engineer. We are seeking an experienced Deep Learning engineer
   to join our AI team. You will develop cutting-edge ML models for robotics
   applications."

   Chunk 2 (~420 tokens):
   "Requirements: 5+ years ML experience. Strong Python skills required.
   Experience with PyTorch or TensorFlow. Understanding of computer vision."

   Chunk 3 (~350 tokens):
   "Nice to have: CUDA/GPU optimization. Robotics domain experience.
   Published papers or open-source projects."
   ```

4. **Test with sample job**
   ```bash
   uv run python << 'EOF'
   from src.tokenization.chunking import chunk_by_sentences

   sample_text = "Deep Learning Engineer. Join our team..."
   chunks = chunk_by_sentences(sample_text)

   for i, chunk in enumerate(chunks, 1):
       print(f"Chunk {i} ({len(chunk.split())} words):\n{chunk}\n")
   EOF
   ```

---

### Task 2.3: Implement Token Counting & Cost Estimation

**Objective**: Use tiktoken to count tokens before API calls, estimate LLM costs upfront.

#### Implementation Strategy

**Tool**: tiktoken (OpenAI tokenizer, works for Claude too)
- Already installed
- Fast: ~1M tokens/sec
- Accurate for counting

#### Steps

1. **Create token counter module** (`src/tokenization/counter.py`)
   - Function: `count_tokens(text: str, model: str = "cl100k_base") -> int`
   - Use `cl100k_base` encoding (compatible with Claude 3.5)
   - Log token count for debugging

2. **Create cost estimator function**
   ```python
   def estimate_cost(token_count: int, model: str = "claude-3-5-sonnet") -> float:
       """Estimate cost for LLM assessment."""
       # Claude 3.5 Sonnet pricing (as of May 2026)
       input_price = 0.003  # $3 per 1M input tokens
       output_price = 0.015  # $15 per 1M output tokens (estimate)

       input_cost = (token_count / 1_000_000) * input_price
       output_cost = (token_count / 1_000_000) * output_price * 0.5  # Assume 50% output

       return input_cost + output_cost
   ```

3. **Integration with PreprocessedJob model**
   ```python
   from src.models.job import PreprocessedJob
   from src.tokenization.counter import count_tokens, estimate_cost

   preprocessed = PreprocessedJob(
       job_id="job_12345",
       clean_text=clean_text,
       chunks=chunks,
       token_count=count_tokens(clean_text),
       estimated_cost=estimate_cost(token_count)
   )
   ```

4. **Expected Output**
   ```
   Job: Deep Learning Engineer

   Raw text length: 1,200 words
   Token count: 1,456 tokens
   Estimated cost: $0.0044 (vs $0.018 if raw HTML sent)

   Savings: 75% fewer tokens
   ```

---

### Task 2.4: Implement Preprocess CLI Command

**Objective**: Wire everything together into `preprocess` CLI command.

#### Implementation Strategy

Update `src/cli.py` to implement `preprocess-jobs` command:

```python
@preprocess_app.command()
def preprocess_jobs(
    batch_size: int = typer.Option(10, help="Jobs per batch"),
    show_estimates: bool = typer.Option(False, help="Show token/cost estimates"),
) -> None:
    """Preprocess job postings (clean HTML, chunk, count tokens)."""
```

#### Steps

1. **Load extracted jobs from `data/extracted_jobs/`**
   - Recursively find all `.json` files
   - Load as JobPosting objects
   - Count total jobs

2. **For each job**:
   - Extract title + location (only available fields for now)
   - Clean HTML (if available)
   - Chunk by sentences
   - Count tokens
   - Estimate cost
   - Create PreprocessedJob object
   - Save to database or JSON

3. **Report results**
   ```
   ✅ Preprocessing complete!

   Total jobs: 26
   Successfully processed: 26
   Failed: 0

   📊 Token Statistics:
   - Average tokens per job: 412 tokens
   - Min: 120 tokens
   - Max: 980 tokens

   💰 Cost Estimates:
   - Total input cost: $0.08 (for all 26 jobs)
   - Savings vs raw HTML: 87%
   ```

4. **Optional: `--show-estimates` flag**
   - Show token count and cost for each job
   - Print first 3 chunks as examples

#### Expected Flow

```bash
$ uv run python -m src.cli preprocess preprocess-jobs --show-estimates

🔄 Preprocessing jobs from data/extracted_jobs/...

📋 Found 26 extracted jobs

Processing: Deep Learning Engineer
  ✓ Cleaned (removed HTML tags)
  ✓ Chunked (3 semantic chunks)
  ✓ Tokens: 412
  ✓ Cost: $0.0012

Processing: Electrical Engineer
  ✓ Cleaned
  ✓ Chunked (2 chunks)
  ✓ Tokens: 287
  ✓ Cost: $0.00086

...

✅ Preprocessing complete!

📊 Summary:
   Jobs processed: 26/26
   Total tokens: 10,712
   Total cost: $0.032
   Savings vs raw: 87%
```

---

### Task 2.5: Validation & Testing

**Objective**: Verify preprocessing pipeline works end-to-end with high quality.

#### Validation Checklist

- ✅ All 26 extracted jobs load without errors
- ✅ HTML cleaning produces readable text (no tags, excess whitespace)
- ✅ Semantic chunks have meaningful boundaries (sentences intact)
- ✅ Token count is reasonable (200–1000 tokens per job)
- ✅ Cost estimates are calculated correctly
- ✅ Preprocessing runs in reasonable time (<5 seconds for 26 jobs)
- ✅ Output can be stored and retrieved

#### Test Commands

```bash
# Run preprocessing
uv run python -m src.cli preprocess preprocess-jobs --show-estimates

# Verify output structure
python3 << 'EOF'
import json

# Check if preprocessed jobs were saved
# Expected: data/extracted_jobs/ contains preprocessed output

# Validate token counts make sense
# Expected: Average 400–600 tokens per job

# Check costs are calculated
# Expected: Total cost < $0.10 for all 26 jobs
EOF

# Run unit tests
uv run pytest tests/test_tokenization.py -v
uv run pytest tests/test_preprocessor.py -v
```

#### Success Metrics

| Metric | Target | Note |
|--------|--------|------|
| Jobs processed | 26/26 | 100% success rate |
| Avg tokens per job | 400–600 | Reasonable range |
| Token reduction | 80–90% | vs raw HTML |
| Processing time | <5 sec | For 26 jobs |
| Cost per job | $0.0008–$0.002 | Stays under $0.002 |

---

## Known Limitations & Unknowns

### Limitation 1: Empty Job Descriptions
**Issue**: Extracted jobs only contain title + location; description field is empty

**Reason**: Phase 1 crawler only extracted from job listing table, not full detail pages

**Options**:
1. **Accept limitation**: Preprocess only title + location for now, revisit in Phase 3
2. **Enhance crawler**: Fetch full job detail pages (requires additional Playwright navigation)
3. **Skip preprocessing**: Wait until Phase 3 verification to get full descriptions

**Recommended**: Option 1 (accept for now) — full descriptions can be fetched later if needed

### Limitation 2: Token Count vs Reality
**Issue**: tiktoken estimates may not exactly match Claude's actual token count

**Reason**: Special tokens, prompt overhead, model-specific handling

**Mitigation**: Track actual tokens from Claude API calls in Phase 4, compare with estimates

### Unknown 1: Semantic Chunking Quality
**Unknown**: Will spaCy sentence boundaries preserve meaning for technical content?

**Test**: Manual review of first 3 chunks to ensure boundaries are sensible

### Unknown 2: Performance at Scale
**Unknown**: Will preprocessing stay <5sec for hundreds of jobs?

**Test**: Time the pipeline with 26 jobs, extrapolate to 100+ jobs

---

## File Structure After Phase 2

```
src/
  tokenization/
    chunking.py         # chunk_by_sentences()
    counter.py          # count_tokens(), estimate_cost()
  parsers/
    html.py             # clean_html()
  cli.py                # Updated with preprocess-jobs command

tests/
  test_tokenization.py  # New tests for chunking, token counting
  test_preprocessor.py  # New tests for full preprocessing pipeline

data/
  extracted_jobs/
    carbonrobotics_jobs.json         # (from Phase 1)
    carbonrobotics_jobs_preprocessed.json  # (generated Phase 2)

docs/
  implementation-planning/
    issue-19-phase-2-preprocessing.md  # This file
```

---

## Implementation Order

1. **Task 2.1**: HTML cleaning module (html.py)
2. **Task 2.2**: Semantic chunking module (chunking.py)
3. **Task 2.3**: Token counting module (counter.py)
4. **Task 2.4**: CLI preprocess command (cli.py)
5. **Task 2.5**: Tests and validation
6. **Commit**: Feature branch with all changes

---

## Acceptance Criteria

Phase 2 is complete when:

- ✅ All 26 extracted jobs successfully preprocessed
- ✅ Token reduction 80–90% verified (with metrics)
- ✅ Semantic chunks have meaningful boundaries
- ✅ CLI command works end-to-end without errors
- ✅ Unit tests passing (100% on tokenization tests)
- ✅ Code formatted (black) and linting passes (ruff)
- ✅ Documentation updated
- ✅ Changes committed to feature branch

---

## Next Phase (Phase 3)

After preprocessing succeeds, Phase 3 will:
- Run interactive user verification (`review` command)
- Confirm/reject each job before expensive LLM calls
- Fetch full job descriptions if needed
- Mark approved jobs as "confirmed"

---

## References

- **PREPROCESS.md**: Deep dive on MarkItDown, spaCy, semantic chunking, token math
- **TOKENIZATION.md**: (if exists) Token counting strategies
- **Model Schema**: `src/models/job.py::PreprocessedJob`
- **CLI Reference**: `docs/CLI.md`
