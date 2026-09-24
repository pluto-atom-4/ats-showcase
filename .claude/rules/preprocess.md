# Preprocess Phase Rules

MarkItDown HTML cleaning, spaCy semantic chunking, token counting via tiktoken.

## HTML Cleaning Strategy

**Primary API (Issue #230 Phase 1):**

Use `clean_html()` for consolidated HTML preprocessing with 70+ boilerplate patterns:

```python
from src.parsers.html_to_markdown import clean_html

# Clean HTML, remove boilerplate, preserve important sections
clean_text = clean_html(
    raw_html,
    include_section_headers=True,       # Keep synthesized headers
    skip_boilerplate_categories={'salary_benefits', 'legal'}
)
```

**Boilerplate Categories (7 total):**
- `legal` – Legal disclaimers, EEO statements, compliance notices
- `section_headers` – Navigation headers, redundant section labels
- `company_info` – Company taglines, about blurbs (not job-specific)
- `time_refs` – Posted dates, application deadlines, timestamps
- `salary_benefits` – Salary ranges, benefits details (optional removal)
- `formatting` – Extra whitespace, CSS classes, metadata attributes
- `navigation` – Page navigation, breadcrumbs, menus

**Example output comparison:**
```
Before (raw HTML, ~6,000 tokens):
  <div class="job-post">
    <h2>Senior Python Developer</h2>
    ...
    <p>© 2026 Company Inc. All rights reserved. Equal Opportunity Employer...</p>
    <nav><a href="/careers">Back to jobs</a></nav>
  </div>

After clean_html() (boilerplate removed, ~400 tokens):
  ## Senior Python Developer

  [job description and requirements, no legal/nav]
```

**Performance benefit:** 70+ pre-compiled regex patterns (10x faster than sequential regex per job). Backward compat: old jobs without boilerplate removal still queryable.

**HTML→Markdown normalization (Issue #228, Phase 4 – IMPLEMENTED):** crawl stores raw extracted description as-is; `_build_preprocess_clean_text` (`src/cli.py` line 323) calls `src.parsers.html_to_markdown.clean_html()` — HTML→Markdown conversion + synthesized `##`/`###` section headers + `---` dividers + boilerplate removal (7 categories) — as the first step of preprocess, before chunking. Replaces deprecated `normalize_description()`. This used to run inline in `Crawler` at crawl time; it does not anymore.

**3-Tier Fallback Chain (Issue #231):**
1. **MarkItDown** (primary) – Preserves structure, ~50ms/job
2. **BeautifulSoup + lxml** (fallback) – Basic text extraction, ~100ms/job
3. **Original HTML** (safe) – Worst case, ~6K tokens, never fails

```python
from src.parsers.html_to_markdown import html_to_markdown

clean_text = html_to_markdown(raw_html)
# Automatically uses fallback chain: MarkItDown → BeautifulSoup → Original HTML
```

Robustness: Preprocessing never fails catastrophically (tests: `test_exception_fallback_returns_original_html`, `test_malformed_html_does_not_raise`).

## Semantic Chunking (Sentences, Not Tokens)

Split at semantic boundaries: "Requires 5+ years MES. Must know Wonderware." stays together. Chunks vary 100–600 tokens (intentional).

```python
from src.tokenization.chunking import chunk_by_sentences

chunks = chunk_by_sentences(clean_text, target_tokens=400)
```

Target: ~400 tokens/chunk (safe for LLM).

## Token Counting & Cost Transparency

Always count before API calls.

```python
from src.tokenization.counter import count_tokens

tokens = count_tokens(text)
cost_usd = tokens * 0.000003  # Claude 3.5 Sonnet input rate
```

Show estimate before assessment. Track actual vs estimated in cost_tracking table.

## Key Non-Obvious Behavior

- **Boilerplate removal (Issue #230)**: 70+ patterns pre-compiled across 7 categories (legal, headers, company, time, salary, formatting, navigation). Removes ~30% of text while preserving job requirements. Backward compatible: old jobs queryable via `preprocessing_version` column (Phase 2 feature).
- **Chunk sizes vary intentionally**: Semantic boundaries, not token-aligned. Don't force uniform counts.
- **Cost estimates pre-API**: tiktoken estimates differ slightly from Claude's actual token count.
- **Fallback parsing (Issue #231)**: 3-tier chain: MarkItDown → BeautifulSoup → Original HTML. Preprocessing never fails, worst-case returns unmodified HTML (~6K tokens vs ~400 expected).
- **Section skip-list (Issue #221)**: `Preprocessor.SKIP_SECTIONS` (`preprocessor.py`) excludes benefits/legal/hiring-process sections (e.g. `e-verify`, `union`, `technical assessment`, `contingent upon award`) from entity extraction. `technical assessment` closes a real gap: it contains "technical", one of `skills_section_keywords`, so without an explicit skip entry such a section risked being misrouted into skills instead of skipped.

## Implementation Details (Phases 5–7)

Technical keyword expansion (Issue #192), boilerplate removal (Issue #193), company name filtering (Issue #194) documented in [DESIGN.md](../../DESIGN.md).

## Phase 2: Preprocessing Version Tracking (Issue #230 Phase 2)

**Purpose:** Track which preprocessing pipeline processed each job, enable selective re-preprocessing with new versions.

**Schema:** `preprocessing_version TEXT DEFAULT 'v2.0'` column in `job_reviews` table.

**Versions:**
- `v1.0` (legacy) – No boilerplate removal; raw HTML extraction
- `v2.0` (new) – 70+ boilerplate patterns removed; 3-tier fallback chain

### Selective Re-Preprocessing Workflow

Query jobs by version, re-process old jobs with new pipeline:

```bash
# Show preprocessing status
uv run python -m src.cli preprocess --show-version-stats

# Re-preprocess only v1.0 jobs to v2.0
uv run python -m src.cli preprocess \
  --cv data/cv.json \
  --re-preprocess-only-v1

# Force specific version
uv run python -m src.cli preprocess \
  --cv data/cv.json \
  --preprocessing-version 2.0
```

### API Usage (JobStore)

```python
from src.storage.job_store import JobStore

store = JobStore("data/ats_playground.db")

# Get version stats
stats = store.get_version_stats()
print(f"v1.0 jobs: {stats.get('1.0', 0)}, v2.0 jobs: {stats.get('2.0', 0)}")

# Get jobs by version
v1_jobs = store.get_jobs_by_version("v1.0")

# Update version after re-processing
for job in v1_jobs:
    # Re-process with new pipeline...
    store.update_preprocessing_version(job["job_id"], "v2.0")
```

### Cost Analysis

Compare token usage across versions:

```python
# Query cost_tracking table for version comparison
# SELECT preprocessing_version, AVG(actual_tokens), SUM(actual_cost)
# FROM jobs j
# JOIN cost_tracking c ON j.id = c.job_id
# GROUP BY preprocessing_version
```

Expected benefit: v2.0 produces ~30% fewer tokens vs v1.0 (boilerplate removed).

## Requirement Extraction (Phase 8a, Issue #252)

**CLI:** `--extract-requirements` (default), `--no-extract-requirements`, `--export-requirements-json <file>`

**Trigger Patterns:** 18 patterns (Tier 1-3, confidence 0.40-0.95). See `docs/dev-note/phase8/patterns.md` for details.

**Database:** Nullable `requirements` column (JSON array). <50ms overhead per job, <5% token increase.

## Span Extraction (Phase 8b, Issue #253-257)

**Purpose:** Expand Phase 8a partial spans to full multi-token boundaries, classify as atomic/compound, preserve in chunking.

**Boundary Rules:** Hard stops (`.`, `;`, `!`) always split. Soft stops (`,`) may split unless conjunction follows. Conjunctions (`and`, `or`) extend span.

**CLI:** `--preserve-requirement-spans` (default, prevents chunk splits), `--no-preserve-requirement-spans` (faster).

**Chunking:** With preservation enabled, chunks 5-10% larger to keep spans intact. No span crosses boundary. <2% latency overhead.

**Database:** `requirement_spans` JSONB column (array of span dicts with text, token boundaries, type, conjunct_count).

**Strategies (Issue #278):** rules and strategy are injectable; `requirement_spans` dict shape stays frozen.

```python
from src.preprocessing.span_categorizer import create_span_categorizer
from src.preprocessing.custom_span_categorizer import load_patterns
from src.preprocessing.span_types import BoundaryRules

nlp_cat = create_span_categorizer("nlp", rules=BoundaryRules())        # POS/DEP, callable on Doc
custom = create_span_categorizer("custom", patterns=load_patterns("patterns.json"))  # regex, writes doc._.custom_spans
```

- `custom` requires `patterns`; patterns are validated (500-char cap, nested-quantifier ReDoS heuristic) and input text is capped at 200k chars.
- `CustomSpanCategorizer(patterns).categorize(text)` is spaCy-free. The spaCy wrapper is not registered as a pipeline factory yet (#381); no CLI flag yet (#380).
- Tests for the strategies are model-free; 11 older spaCy-model tests need `en_core_web_md` (#383).

See `docs/dev-note/phase8/span_algorithm.md` for algorithm pseudocode, boundary rules, edge cases.

## Verification Commands

See [Preprocessing Commands](./_common.md#preprocessing-token-estimates) for token estimates, queries, and test commands.
