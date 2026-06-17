# ATS Playground CLI - Step-by-Step Workflow Guide

Complete reference for using the ATS Playground command-line interface to run the intelligent job assessment workflow.

---

## Quick Start (5 Minutes)

Run everything in one command:

```bash
uv run python -m src.cli all --cv data/cv.json --config config/companies.json
```

For multiple company config directories:

```bash
uv run python -m src.cli all --cv data/cv.json --config-dir ./config
```

---

## Full Workflow (8 Commands)

### Phase 0: Prerequisites

Before running any commands, ensure:

```bash
# Setup environment
uv sync                                          # Install deps
uv run python -m spacy download en_core_web_md # NLP model
uv run playwright install                       # Browser
cp .env.example .env                            # Config
# Edit .env and add: export ANTHROPIC_API_KEY="..."
```

Verify dependencies:

```bash
# Check Python version (must be 3.12+)
python --version

# Check API key is set
echo $ANTHROPIC_API_KEY
```

---

## Phase 1: CRAWL - Extract Job Postings

### Command

```bash
uv run python -m src.cli crawl \
  --config config/companies.json \
  --headless true \
  --timeout 30000
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--config` | `config/companies.json` | Path to single JSON config file |
| `--config-dir` | None | Directory with multiple JSON config files |
| `--headless` | `true` | Run browser in headless mode (no UI) |
| `--timeout` | `30000` | Browser timeout in milliseconds |
| `--mock` | `false` | Mock crawling without launching browser (testing) |

### Config File Format

```json
{
  "companies": {
    "CompanyName": {
      "enabled": true,
      "name": "Company Name",
      "url": "https://example.com/careers",
      "job_selector": ".job-posting",
      "title_selector": ".job-title",
      "location_selector": ".job-location",
      "description_selector": ".job-description"
    }
  }
}
```

### Output

Saves job postings to: `data/extracted_jobs/{company_name}_jobs.json`

Example output:

```
🌐 Crawling in progress...

📋 Found 2 companies from file: config/companies.json
✅ Processing 2 enabled companies

✅ Crawl complete! Extracted 45 total jobs

   • CompanyA: 26 jobs
      Saved to: data/extracted_jobs/companya_jobs.json
   • CompanyB: 19 jobs
      Saved to: data/extracted_jobs/companyb_jobs.json

⏱️  Phase 1 took 42.15s
```

### Troubleshooting

**Browser crashes:**
```bash
uv run playwright install chromium
```

**Timeout errors:**
Increase `--timeout` (in milliseconds): `--timeout 60000` (60 seconds)

**No jobs found:**
- Check CSS selectors in config file
- Visit company careers page manually to verify structure
- Use browser DevTools to inspect HTML

---

## Phase 2: PREPROCESS - Clean, Chunk, Count Tokens

### Command

```bash
uv run python -m src.cli preprocess \
  --batch-size 10 \
  --show-estimates
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--batch-size` | `10` | Number of jobs per batch (for memory management) |
| `--show-estimates` | `false` | Display token/cost estimates for first 3 jobs |

### What It Does

1. **Cleans HTML** - Removes markup, normalizes text
2. **Chunks text** - Splits into semantic chunks (sentence-based)
3. **Counts tokens** - Estimates Claude API tokens using tiktoken
4. **Estimates costs** - Calculates API cost per job

### Output

Saves preprocessed jobs to: `data/extracted_jobs/preprocessed_jobs.json`

Example output:

```
🔄 Preprocessing jobs...

📂 Processing companya_jobs.json...
   Job 1: Software Engineer - San Francisco...
      Tokens: 342 | Cost: $0.0021
   Job 2: Senior DevOps Engineer - Austin...
      Tokens: 456 | Cost: $0.0028

✅ Preprocessing complete!

📊 Summary:
   Total jobs: 45
   Processed: 45
   Failed: 0
   Total tokens: 15,420
   Total cost: $0.0924
   Avg tokens/job: 343

💾 Saving preprocessed jobs...
   ✓ Saved to: data/extracted_jobs/preprocessed_jobs.json
```

### Key Metrics

- **Token reduction**: ~88% vs raw HTML (saves API costs)
- **Time**: <2 seconds for typical crawls
- **Cost accuracy**: ±5% vs actual Claude API usage

### Understanding Token Counts

```
Raw HTML job posting:     ~6,000 tokens
Cleaned + chunked:        ~700 tokens
Cost reduction:           88% ✅

Per-job cost:
  Raw approach:           $0.018
  ATS Playground:         $0.002
  Savings:                89% per job
```

---

## Phase 3: REVIEW - Interactive Job Filtering

### Command

```bash
uv run python -m src.cli review \
  --extracted data/extracted_jobs/companya_jobs.json \
  --preprocessed data/extracted_jobs/preprocessed_jobs.json
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--extracted` | `data/extracted_jobs/carbonrobotics_jobs.json` | Path to extracted jobs JSON |
| `--preprocessed` | `data/extracted_jobs/preprocessed_jobs.json` | Path to preprocessed jobs JSON |

### Interactive Flow

For each job, you'll see:

```
[1/26] Software Engineer - San Francisco
  Company: Carbon Robotics
  Location: San Francisco, CA
  Token count: 342
  Estimated cost: $0.0021

Confirm? (y/n/skip):
```

### Actions

- **y** (yes) - Confirm job, will be assessed by Claude
- **n** (no) - Reject job, skip LLM assessment
- **skip** - Skip for now (can review later)

### Output

Updates job status in preprocessed JSON:

```json
{
  "job_id": "companya_1",
  "title": "Software Engineer",
  "status": "confirmed",  // or "rejected"
  "chunks": [...],
  "token_count": 342
}
```

Example output:

```
👀 Reviewing extracted jobs...

[1/26] Software Engineer - San Francisco
  Company: Carbon Robotics
  Location: San Francisco, CA
  Tokens: 342 | Cost: $0.0021
Confirm? (y/n/skip): y

[2/26] Product Manager - Austin
  Company: Carbon Robotics
  Location: Austin, TX
  Tokens: 398 | Cost: $0.0024
Confirm? (y/n/skip): n

...

✅ Review complete: 22 confirmed, 4 rejected
```

### Why Review Jobs?

- **Save money** - Skip irrelevant jobs before LLM assessment
- **Save time** - Skip positions you're not interested in
- **Improve results** - Assess only relevant opportunities

---

## Phase 4: ASSESS - AI Evaluation with Claude

### Command

```bash
uv run python -m src.cli assess \
  --cv data/cv.json \
  --confirmed-only true
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--cv` | *required* | Path to CV file (JSON or TXT) |
| `--confirmed-only` | `true` | Only assess jobs with status="confirmed" |

### CV File Format

**JSON format:**

```json
{
  "text": "Your complete CV text here...",
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+1-555-0000",
  "summary": "5 years of software engineering experience...",
  "skills": ["Python", "Go", "Kubernetes", "ML"],
  "experience": [...]
}
```

**Plain text format:** Just use a `.txt` file with your CV content

### What It Does

For each confirmed job, Claude evaluates:

1. **Overall CV Match** (0-100) - How well does your CV fit?
2. **Technical Skills** (0-100) - Do you have required skills?
3. **Seniority Level** (0-100) - Does your experience level match?
4. **Location Preference** (0-100) - Is location acceptable?
5. **Recommendations** (text) - Should you apply?

### Output

Saves assessments to: `data/ats_playground.db` (SQLite)

Example output:

```
📄 Loaded CV from: data/cv.json

🤖 Starting CV assessment for 22 confirmed jobs

✅ Job 1/22: Software Engineer - San Francisco
   Tech: 85/100 | Seniority: 75/100 | Location: 80/100 | Overall: 80/100
   Cost: $0.0006 | Tokens: 1,247

✅ Job 2/22: Senior Backend Engineer - New York
   Tech: 92/100 | Seniority: 88/100 | Location: 60/100 | Overall: 80/100
   Cost: $0.0007 | Tokens: 1,356

✅ Job 3/22: DevOps Engineer - Austin
   Tech: 78/100 | Seniority: 72/100 | Location: 90/100 | Overall: 80/100
   Cost: $0.0006 | Tokens: 1,198

...

════════════════════════════════════════════════════════════════════════════════
📊 Assessment Summary:
   Total assessed: 22/22
   Avg overall score: 76.3/100
   Total cost: $0.0147
   Total tokens: 26,534

🏆 Top Matches:
   1. Senior Backend Engineer - Overall: 92/100
   2. ML Engineer - Overall: 88/100
   3. Software Engineer (Python) - Overall: 85/100

✅ Assessment complete!
```

### Scoring Interpretation

| Score | Interpretation | Action |
|-------|-----------------|--------|
| 90-100 | Excellent match | Definitely apply |
| 75-89 | Good fit | Apply |
| 60-74 | Moderate fit | Consider applying |
| 0-59 | Poor fit | Skip |

### Rate Limiting

Claude API has built-in rate limits:

- **Max requests**: 10 per minute
- **Max tokens**: 50,000 per minute
- **Backoff**: Auto-retry with exponential backoff

For 100 jobs: ~10 minutes

### Troubleshooting

**"ANTHROPIC_API_KEY not set"**
```bash
export ANTHROPIC_API_KEY="..."
```

**API rate limit exceeded:**
CLI auto-retries. Wait 1 minute and rerun the command (restarts from where it failed).

**No confirmed jobs found:**
Run `review` command first to confirm jobs.

---

## Phase 5: EXPORT - Generate Markdown Report

### Command

```bash
uv run python -m src.cli export \
  --output data/assessments/report.md \
  --min-score 75 \
  --max-score 100 \
  --sort-by score \
  --template detailed \
  --include-recommendations true \
  --include-stats true
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output` | `data/assessments/report.md` | Output file path |
| `--min-score` | `0` | Minimum score filter (0-100) |
| `--max-score` | `100` | Maximum score filter (0-100) |
| `--sort-by` | `score` | Sort by: `score`, `company`, or `location` |
| `--template` | `detailed` | Template: `detailed` or `summary` |
| `--include-recommendations` | `true` | Include Claude recommendations |
| `--include-stats` | `true` | Include analytics section |

### Filter Examples

Show only top matches (80+):

```bash
uv run python -m src.cli export --min-score 80
```

Show only poor fits (<60):

```bash
uv run python -m src.cli export --max-score 59
```

Sort by location:

```bash
uv run python -m src.cli export --sort-by location
```

### Output

Generates Markdown file: `data/assessments/report.md`

Example output:

```
📊 Generating report (score 75-100)...
✅ Exported 18/22 jobs to data/assessments/report.md
   File size: 42.3 KB
   Template: detailed
```

### Report Structure

```markdown
# ATS Assessment Report

**Generated:** 2026-06-16
**Total jobs:** 22
**Filtered:** 18 (75-100)

---

## Top Matches

1. **Senior Backend Engineer** (92/100)
   - Company: TechCorp
   - Location: New York, NY
   - Tech: 92/100 | Seniority: 88/100 | Overall: 92/100

...

---

## Job Details

### 1. Senior Backend Engineer
- **Company:** TechCorp
- **Location:** New York, NY
- **Score:** 92/100
- **Tech Skills:** 92/100
- **Seniority:** 88/100
- **Location Fit:** 60/100
- **Recommendation:** Excellent match - Python + 5 years experience aligns well

...

---

## Analytics

**Total Jobs:** 22
**Assessed:** 22
**Average Score:** 76.3/100
**Total Cost:** $0.0147
**Token Usage:** 26,534 tokens

**Score Distribution:**
- 90-100 (Excellent): 3 jobs
- 75-89 (Good): 12 jobs
- 60-74 (Moderate): 7 jobs
- 0-59 (Poor): 0 jobs
```

---

## Utility Commands

### Search Assessments by Keyword

```bash
uv run python -m src.cli query \
  --keyword "python" \
  --min-score 75 \
  --max-score 100 \
  --limit 10 \
  --json-output false
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--keyword` | *required* | Search term |
| `--min-score` | None | Minimum score filter |
| `--max-score` | None | Maximum score filter |
| `--limit` | `10` | Maximum results |
| `--json-output` | `false` | Output as JSON (true/false) |

### Example Usage

Search for Python jobs:

```bash
uv run python -m src.cli query --keyword "python"
```

Search for high-scoring ML jobs:

```bash
uv run python -m src.cli query --keyword "machine learning" --min-score 85
```

Get JSON output:

```bash
uv run python -m src.cli query --keyword "kubernetes" --json-output true
```

### Output

```
🔍 Searching for 'python' (score 0-100, limit 10)...

Found 8 results:

Rank │ Company          │ Title                    │ Score │ Tech │ Senior
─────┼──────────────────┼──────────────────────────┼───────┼──────┼───────
  1  │ TechCorp         │ Senior Python Engineer   │  92   │  95  │  88
  2  │ DataInc          │ ML Engineer (Python)     │  88   │  90  │  85
  3  │ CloudSys         │ Backend Engineer (Py)    │  80   │  85  │  75

📊 Average score: 86.7
💡 Tip: Use 'export --min-score 85' to get a full report
```

### Display Statistics

```bash
uv run python -m src.cli stats \
  --show-token-usage false
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--show-token-usage` | `false` | Include token usage breakdown |

---

## Advanced Workflows

### Workflow 1: Quick POC (15 minutes)

```bash
# 1. Crawl
uv run python -m src.cli crawl --config config/companies.json
# Output: 26 jobs extracted

# 2. Preprocess (check token savings)
uv run python -m src.cli preprocess --show-estimates
# Output: 88% token reduction

# 3. Assess (auto-confirm in 'all' command)
# (covered by next step)

# 4. Run everything
uv run python -m src.cli all --cv data/cv.json --config config/companies.json
```

Expected time: 10-15 minutes

### Workflow 2: Incremental Assessment

```bash
# Crawl many companies
uv run python -m src.cli crawl --config-dir ./config

# Preprocess
uv run python -m src.cli preprocess --show-estimates

# Review jobs (manual filtering)
uv run python -m src.cli review

# Assess only confirmed
uv run python -m src.cli assess --cv data/cv.json

# Export top matches
uv run python -m src.cli export --min-score 80
```

### Workflow 3: Repeated Assessment

```bash
# Update CV
vim data/cv.json

# Re-assess (skips jobs already assessed, assesses new ones)
uv run python -m src.cli assess --cv data/cv.json

# Export new report
uv run python -m src.cli export --output data/assessments/report_v2.md
```

### Workflow 4: Search and Filter

```bash
# Export full report
uv run python -m src.cli export

# Search for specific skills
uv run python -m src.cli query --keyword "kubernetes"
uv run python -m src.cli query --keyword "python"
uv run python -m src.cli query --keyword "remote"

# Export filtered report
uv run python -m src.cli export --min-score 85 --sort-by location
```

---

## Common Patterns

### Pattern 1: Single Command (Easiest)

```bash
uv run python -m src.cli all --cv data/cv.json --config config/companies.json
```

**Pros:** One command, automatic workflow
**Cons:** Less control, must confirm all jobs

### Pattern 2: Phase-by-Phase (Recommended)

```bash
uv run python -m src.cli crawl --config config/companies.json
uv run python -m src.cli preprocess --show-estimates
uv run python -m src.cli review
uv run python -m src.cli assess --cv data/cv.json
uv run python -m src.cli export --min-score 75
```

**Pros:** Full control, can inspect outputs
**Cons:** More commands to run

### Pattern 3: Batch Processing

```bash
# Process multiple company directories
uv run python -m src.cli crawl --config-dir ./config/tech-companies
uv run python -m src.cli crawl --config-dir ./config/finance-companies

# Preprocess all at once
uv run python -m src.cli preprocess

# Review and assess
uv run python -m src.cli review
uv run python -m src.cli assess --cv data/cv.json

# Generate separate reports
uv run python -m src.cli export --output data/assessments/tech_report.md
uv run python -m src.cli export --output data/assessments/finance_report.md
```

---

## Data Flow & Files

```
CONFIG FILES:
  config/companies.json ─────┐
  config/other.json ─────────┤
                             ↓
PHASE 1 (CRAWL):
  ┌──────────────────────────────────┐
  │ Browser Automation               │
  │ (Playwright)                     │
  └──────────────────────────────────┘
                             ↓
  data/extracted_jobs/
  ├── companya_jobs.json ◄── 26 raw jobs
  ├── companyb_jobs.json ◄── 19 raw jobs
  └── ...

PHASE 2 (PREPROCESS):
  ┌──────────────────────────────────┐
  │ Clean HTML                       │
  │ Chunk Text (semantic)            │
  │ Count Tokens (tiktoken)          │
  └──────────────────────────────────┘
                             ↓
  data/extracted_jobs/
  └── preprocessed_jobs.json ◄── 45 chunked jobs

PHASE 3 (REVIEW):
  ┌──────────────────────────────────┐
  │ Interactive CLI Review           │
  │ User confirms/rejects            │
  └──────────────────────────────────┘
                             ↓
  data/extracted_jobs/
  └── preprocessed_jobs.json ◄── status=confirmed/rejected

CV INPUT:
  data/cv.json ──────────────┐
  data/cv.txt ───────────────┤
                             ↓
PHASE 4 (ASSESS):
  ┌──────────────────────────────────┐
  │ Claude 3.5 Sonnet API            │
  │ Multi-category scoring           │
  │ Cost tracking                    │
  └──────────────────────────────────┘
                             ↓
  data/ats_playground.db ◄── SQLite assessments

PHASE 5 (EXPORT):
  ┌──────────────────────────────────┐
  │ Generate Markdown Report         │
  │ Filter, sort, analytics          │
  └──────────────────────────────────┘
                             ↓
  data/assessments/
  ├── report.md ◄── Full report
  ├── report_summary.md
  └── ...

SEARCH:
  data/ats_playground.db ──┐
                           ↓
                    ┌──────────────────┐
                    │ Keyword search   │
                    │ Score filtering  │
                    └──────────────────┘
                           ↓
                      Table output
                      JSON output
```

---

## Cost & Performance

### Typical Costs

| Phase | Cost | Time |
|-------|------|------|
| Crawl 26 jobs | Free | 30-60s |
| Preprocess 26 | Free | <2s |
| Review 26 | Free | 2-3m |
| Assess 26 | $0.02 | 5-10m |
| Export | Free | <1s |
| **TOTAL** | **$0.02** | **10-15m** |

vs. Traditional approach: **$0.47** (89% savings)

### Token Usage

```
Per job:
  Raw HTML:          6,000 tokens
  Preprocessed:      700 tokens
  Assessment:        1,200 tokens
  Total:             1,900 tokens

26 jobs:
  Total tokens:      49,400
  Cost at $0.003/1K: $0.15
  (Claude 3.5 Sonnet pricing)
```

---

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY="..."

# Optional (defaults shown)
LOG_LEVEL="INFO"
DB_PATH="data/ats_playground.db"
```

Set in `.env` file:

```bash
cp .env.example .env
# Edit and add:
# export ANTHROPIC_API_KEY="..."
```

---

## Error Handling

### Common Errors & Fixes

**Error: "Config file not found"**
```bash
# Fix: Use correct path
uv run python -m src.cli crawl --config config/companies.json
```

**Error: "No companies found"**
```bash
# Fix: Check config file format
cat config/companies.json | grep "companies"
```

**Error: "SQLite locked"**
```bash
# Fix: Only one assess process at a time
# Wait for other processes to finish
```

**Error: "Rate limit exceeded"**
```bash
# Fix: Auto-retries. Wait 1 minute and re-run
# (Restarts from where it failed)
```

**Error: "spaCy model not found"**
```bash
uv run python -m spacy download en_core_web_md
```

---

## Testing Commands

Verify setup without using API:

```bash
# Test crawl (mock mode)
uv run python -m src.cli crawl --mock true

# Test preprocessing
uv run python -m src.cli preprocess --show-estimates

# Test export (with existing data)
uv run python -m src.cli export --min-score 80
```

---

## Tips & Best Practices

1. **Use `--config-dir`** for multiple companies (easier to manage)
2. **Always review jobs** before assessment (saves money)
3. **Use `--min-score`** when exporting (focus on good matches)
4. **Check token estimates** with `--show-estimates` (predict costs)
5. **Save API key in `.env`** (don't pass on command line)
6. **Monitor `.db` file size** (deletes old data if >100MB)

---

## Document Version

- **Version:** 1.0
- **Last Updated:** 2026-06-16
- **Status:** Complete
- **Coverage:** All 8 CLI commands with options, examples, workflows
