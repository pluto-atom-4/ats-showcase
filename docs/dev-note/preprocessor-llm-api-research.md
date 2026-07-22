# Preprocessor + LLM API Best Practices

Research & implementation guide for optimal Claude API integration with preprocessed job data.

---

## Overview

Goal: Maximize token efficiency while maintaining assessment accuracy by leveraging preprocessed data (entities, sentences, stopword-removed text) in structured LLM prompts.

**Expected outcome:** 30-40% token reduction vs. raw HTML → Claude API.

---

## Part 1: Token Optimization Strategies

### 1.1 Chunking: Semantic vs. Token-Based

**Semantic Chunking (Recommended for Job Postings)**

Split at sentence boundaries, preserve complete thoughts:

```python
from src.tokenization.preprocessor import Preprocessor

preprocessor = Preprocessor()
job_html = fetch_job_description()  # Raw HTML
clean_text = parse_html(job_html)   # MarkItDown → ~400 tokens
sentences = preprocessor.segment_sentences(clean_text)
# sentences: ["Req 5+ years Python.", "Django experience required.", ...]

# Group sentences into logical chunks (100–600 tokens each)
chunks = []
current_chunk = []
current_tokens = 0

for sent in sentences:
    sent_tokens = count_tokens(sent)
    if current_tokens + sent_tokens > 400:
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        current_chunk = [sent]
        current_tokens = sent_tokens
    else:
        current_chunk.append(sent)
        current_tokens += sent_tokens

if current_chunk:
    chunks.append(" ".join(current_chunk))

return chunks
```

**Benefits:**
- Preserves semantic boundaries (skills, requirements stay together)
- No mid-sentence cuts (Claude reads naturally)
- Variable chunk sizes (100–600 tokens) OK; don't force uniformity

**Token-Based Chunking (Not Recommended for Job Postings)**

Fixed-size chunks, split mid-sentence if needed:

```python
def chunk_by_tokens(text: str, target_tokens: int = 500) -> List[str]:
    tokens = text.split()
    chunks = []
    current = []

    for token in tokens:
        if count_tokens(" ".join(current + [token])) > target_tokens:
            chunks.append(" ".join(current))
            current = [token]
        else:
            current.append(token)

    if current:
        chunks.append(" ".join(current))

    return chunks
```

**Problems:**
- Splits requirements mid-sentence ("5+ years Python, Django" → "5+ years Python," | "Django")
- Less natural context for Claude
- Same token count → fewer meaningful chunks

**Decision:** Use semantic chunking for job postings + CV matching.

---

### 1.2 Pre-Processing Data in Prompts

Structure preprocessed data for Claude comprehension:

```python
def build_assessment_prompt(
    cv_text: str,
    job_description: str,
    extracted_entities: tuple,
    chunks: list,
) -> str:
    """Build prompt using preprocessed data."""
    skills, tech, requirements = extracted_entities

    prompt = f"""
You are an expert recruiter assessing CV fit for a job opening.

## Candidate Profile

{cv_text}

## Job Requirements (Preprocessed)

**Skills Needed:** {", ".join(skills)}
**Tech Stack:** {", ".join(tech)}
**Other Requirements:** {", ".join(requirements)}

### Job Description

{chr(10).join(f"- {chunk}" for chunk in chunks)}

## Assessment

Evaluate CV fit (0-100) across:
1. **Technical Skills Match** - Do CV skills align with job tech stack?
2. **Seniority Alignment** - Does CV experience level match job level?
3. **Location & Fit** - Are CV location/availability compatible?
4. **Overall Match Score** - Weighted average of above

Return JSON:
{{
    "overall_score": 0-100,
    "tech_match": 0-100,
    "seniority_match": 0-100,
    "reasoning": "..."
}}
"""
    return prompt
```

**Token Savings:**

| Input Type | Tokens | Savings |
|---|---|---|
| Raw HTML | ~6,000 | — |
| Clean text | ~400 | 93% |
| Semantic chunks | ~600 | 90% |
| Preprocessed (entities + chunks) | ~450 | 92.5% |

---

## Part 2: Claude API Patterns

### 2.1 Non-Streaming (Simpler, Cost-Transparent)

Use for assessment where you need final score before persisting:

```python
import anthropic
from src.tokenization.counter import count_tokens

def assess_job_non_streaming(cv_text: str, job_text: str, model: str = "claude-3-5-sonnet-20241022") -> dict:
    """Assess job fit (non-streaming)."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Preprocess
    preprocessor = Preprocessor()
    clean_text = parse_html(job_text)
    chunks = chunk_semantic(clean_text)
    skills, tech, reqs = preprocessor.extract_entities(clean_text)

    # Build prompt
    prompt = build_assessment_prompt(cv_text, job_text, (skills, tech, reqs), chunks)

    # Count tokens upfront
    input_tokens = count_tokens(prompt)
    estimated_output = 200  # JSON response ~200 tokens
    estimated_cost = (input_tokens + estimated_output) * 0.000003  # Sonnet input rate

    print(f"Estimated: {input_tokens} input + {estimated_output} output = ${estimated_cost:.6f}")

    # Call API
    message = client.messages.create(
        model=model,
        max_tokens=500,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    # Parse response
    response_text = message.content[0].text
    assessment = json.loads(response_text)

    # Log actual usage
    actual_input = message.usage.input_tokens
    actual_output = message.usage.output_tokens
    actual_cost = (actual_input + actual_output) * 0.000003

    return {
        "assessment": assessment,
        "cost_tracking": {
            "estimated_input": input_tokens,
            "estimated_output": estimated_output,
            "actual_input": actual_input,
            "actual_output": actual_output,
            "estimated_cost": estimated_cost,
            "actual_cost": actual_cost,
        }
    }
```

**When to use:**
- ✅ Assessment phase (need final score to save)
- ✅ Cost tracking (easy to compare estimate vs. actual)
- ✅ Simple error handling (just retry on 5xx)

### 2.2 Streaming (Real-Time Feedback)

Use for review phase UX (show reasoning as it streams):

```python
def assess_job_streaming(cv_text: str, job_text: str, callback=None):
    """Assess with streaming output."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    preprocessor = Preprocessor()
    clean_text = parse_html(job_text)
    chunks = chunk_semantic(clean_text)
    skills, tech, reqs = preprocessor.extract_entities(clean_text)

    prompt = build_assessment_prompt(cv_text, job_text, (skills, tech, reqs), chunks)

    with client.messages.stream(
        model="claude-3-5-sonnet-20241022",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        full_response = ""
        for text in stream.text_stream:
            full_response += text
            if callback:
                callback(text)  # Update UI in real-time

    return full_response
```

**When to use:**
- ✅ Review panel (show assessment reasoning live)
- ✅ Interactive workflows (user sees progress)
- ❌ NOT for batch assessment (harder to handle errors)

**Cost caveat:** Streaming still charges for input + output tokens. No savings vs. non-streaming. Use for UX, not cost.

---

## Part 3: Rate Limiting & Retries

Claude API limits:
- **RPM (Requests Per Minute):** ~10 (varies by plan)
- **TPM (Tokens Per Minute):** ~50K (varies by plan)

### 3.1 Exponential Backoff

```python
import time
import anthropic

def call_with_backoff(prompt: str, max_retries: int = 3) -> str:
    """Call Claude API with exponential backoff."""
    client = anthropic.Anthropic()

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

        except anthropic.RateLimitError as e:
            if attempt == max_retries - 1:
                raise

            backoff_seconds = 2 ** attempt  # 2, 4, 8 seconds
            logger.warning(f"Rate limited. Retry in {backoff_seconds}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(backoff_seconds)

        except anthropic.APIStatusError as e:
            if e.status_code in (500, 502, 503):  # Transient server errors
                if attempt == max_retries - 1:
                    raise

                backoff_seconds = 2 ** attempt
                logger.warning(f"Server error {e.status_code}. Retry in {backoff_seconds}s")
                time.sleep(backoff_seconds)
            else:
                raise  # Don't retry on client errors (4xx)

        except anthropic.AuthenticationError:
            logger.error("Invalid API key. Check ANTHROPIC_API_KEY.")
            raise
```

### 3.2 Queue-Based Batch Processing

For assessing 100+ jobs without hitting rate limits:

```python
import asyncio
from asyncio import Semaphore

async def assess_jobs_batch(jobs: list, cv_text: str, max_concurrent: int = 3):
    """Assess multiple jobs with rate limiting."""
    semaphore = Semaphore(max_concurrent)  # Max 3 concurrent requests

    async def assess_with_semaphore(job):
        async with semaphore:
            return await assess_job_async(cv_text, job)

    results = await asyncio.gather(*[assess_with_semaphore(job) for job in jobs])
    return results
```

**Alternative: Queue + Single Worker**

```python
from queue import Queue
import threading

job_queue = Queue()
results = {}

def worker():
    while True:
        job_id, cv_text, job_text = job_queue.get()
        try:
            result = assess_job_non_streaming(cv_text, job_text)
            results[job_id] = result
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
        finally:
            job_queue.task_done()

# Start worker
thread = threading.Thread(target=worker, daemon=True)
thread.start()

# Queue jobs
for job_id, cv, job_text in jobs_to_assess:
    job_queue.put((job_id, cv, job_text))

# Wait for completion
job_queue.join()
```

**Decision:** Single-worker queue for simplicity; async for performance.

---

## Part 4: Error Handling

### 4.1 Retry Strategy Decision Tree

```
API Call
│
├─ Success (200) → Return response
│
├─ 401 Unauthorized
│   └─ Log "Invalid API key"
│   └─ Fail immediately (don't retry)
│
├─ 429 Rate Limit
│   └─ Backoff 2^N seconds (exponential)
│   └─ Retry up to 3 times
│
├─ 500, 502, 503 (Server Error)
│   └─ Backoff 2^N seconds
│   └─ Retry up to 3 times
│
└─ Other 4xx (Bad Request, etc.)
    └─ Log error details
    └─ Fail immediately
```

### 4.2 Logging Template

```python
import logging

logger = logging.getLogger(__name__)

def assess_with_logging(cv_text: str, job_text: str, job_id: str):
    """Assess with comprehensive logging."""
    logger.info(f"Starting assessment for job {job_id}")

    try:
        preprocessor = Preprocessor()
        clean_text = parse_html(job_text)
        skills, tech, reqs = preprocessor.extract_entities(clean_text)

        logger.debug(f"Extracted: {len(skills)} skills, {len(tech)} tech, {len(reqs)} reqs")

        prompt = build_assessment_prompt(cv_text, job_text, (skills, tech, reqs), [])
        input_tokens = count_tokens(prompt)

        logger.debug(f"Input tokens: {input_tokens}")

        response = call_with_backoff(prompt)
        assessment = json.loads(response)

        logger.info(f"Assessment complete: score={assessment['overall_score']}")
        return assessment

    except anthropic.RateLimitError as e:
        logger.warning(f"Rate limited on job {job_id}: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse response for job {job_id}: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error for job {job_id}: {e}")
        raise
```

---

## Part 5: Prompt Engineering for Job Assessment

### 5.1 System Prompt

```python
SYSTEM_PROMPT = """You are an expert recruiter and technical interviewer.

Your task: Assess how well a candidate's CV matches a job posting.

Guidelines:
1. Be objective - focus on skill/experience match, not subjective fit
2. Look for both required and nice-to-have skills
3. Consider seniority level alignment (junior/mid/senior)
4. Factor in transferable skills (e.g., language-agnostic concepts)
5. Be balanced - acknowledge both strengths and gaps

Return JSON format (no markdown, just raw JSON):
{
    "overall_score": <0-100 int>,
    "tech_match": <0-100 int>,
    "seniority_match": <0-100 int>,
    "location_match": <yes/no/unknown>,
    "top_strengths": ["strength1", "strength2", ...],
    "gaps": ["gap1", "gap2", ...],
    "reasoning": "Brief explanation of scoring"
}
"""
```

### 5.2 Few-Shot Examples (Optional Token Investment)

Include 1-2 examples for complex assessments:

```python
def build_prompt_with_examples(cv_text: str, job_text: str, chunks: list) -> str:
    examples = [
        {
            "cv": "5 years Python, Django, PostgreSQL. React basics.",
            "job": "Senior Python developer. Needs Django, PostgreSQL, Redis.",
            "assessment": {"overall_score": 75, "tech_match": 85, "reasoning": "..."}
        }
    ]

    prompt = f"""
{SYSTEM_PROMPT}

## Example

CV: {examples[0]['cv']}
Job: {examples[0]['job']}
Assessment: {json.dumps(examples[0]['assessment'], indent=2)}

---

## Actual Assessment

CV: {cv_text}

Job: {job_text}

Job Requirements (Extracted):
{chr(10).join(chunks)}

Assessment:
"""
    return prompt
```

**Cost:** Examples add ~200 tokens upfront, save ~100 tokens in reasoning clarity. Net cost increase but better accuracy.

---

## Part 6: Token Counting & Cost Prediction

### 6.1 Pre-Call Estimation

```python
from src.tokenization.counter import count_tokens

def estimate_cost(cv_text: str, job_text: str) -> dict:
    """Estimate cost before API call."""
    cv_tokens = count_tokens(cv_text)
    job_tokens = count_tokens(job_text)
    prompt_overhead = 50  # System prompt, examples

    estimated_input = cv_tokens + job_tokens + prompt_overhead
    estimated_output = 200  # JSON response

    # Claude 3.5 Sonnet: $3/1M input, $15/1M output
    input_cost = estimated_input * (3 / 1_000_000)
    output_cost = estimated_output * (15 / 1_000_000)
    total_cost = input_cost + output_cost

    return {
        "estimated_input_tokens": estimated_input,
        "estimated_output_tokens": estimated_output,
        "estimated_cost": total_cost,
        "cost_per_job": f"${total_cost:.6f}",
    }
```

### 6.2 Post-Call Tracking

```python
def track_assessment_cost(job_id: str, message_response):
    """Log actual vs. estimated."""
    actual_input = message_response.usage.input_tokens
    actual_output = message_response.usage.output_tokens
    actual_cost = (actual_input + actual_output) * 0.000003  # Average rate

    logger.info(
        f"Job {job_id}: {actual_input} input + {actual_output} output = ${actual_cost:.6f}"
    )

    # Store in cost_tracking table
    db.insert_cost_tracking({
        "job_id": job_id,
        "actual_input_tokens": actual_input,
        "actual_output_tokens": actual_output,
        "actual_cost": actual_cost,
    })
```

---

## Part 7: Implementation Roadmap

### Phase 1: Non-Streaming Baseline (Week 1)

- [ ] Implement `assess_job_non_streaming()` with exponential backoff
- [ ] Build `build_assessment_prompt()` with entity extraction
- [ ] Add cost tracking to database
- [ ] Test on 10 job samples

**Acceptance:** 90%+ assessment accuracy on golden set, cost tracking ≥95% accurate vs. API.

### Phase 2: Semantic Chunking (Week 2)

- [ ] Implement `chunk_semantic()` with sentence-boundary preservation
- [ ] Validate chunk sizes (100–600 tokens)
- [ ] Compare token usage vs. raw HTML
- [ ] Optimize for edge cases (long requirements, multiple paragraphs)

**Acceptance:** 30–40% token reduction vs. raw HTML.

### Phase 3: Queue-Based Batch Processing (Week 2)

- [ ] Implement single-worker queue pattern
- [ ] Add concurrent request limiting (3 parallel max)
- [ ] Test rate limit handling with mock API
- [ ] Assess 100+ jobs without hitting limits

**Acceptance:** Process 100 jobs in <10 min without 429 errors.

### Phase 4: Streaming + Review Panel (Week 3)

- [ ] Implement streaming assessment for review phase
- [ ] Show reasoning in real-time in UI
- [ ] Add progress tracking (X of Y jobs)
- [ ] Test on 50 jobs with review workflow

**Acceptance:** Reasoning visible within 2 seconds of start.

---

## Appendix: Useful Code Templates

### Template 1: Simple Assessment

```python
def quick_assess(cv_path: str, job_html: str) -> dict:
    """Quick assessment with minimal setup."""
    with open(cv_path) as f:
        cv_text = f.read()

    clean_job = parse_html(job_html)
    prompt = f"CV:\n{cv_text}\n\nJob:\n{clean_job}\n\nScore this match 0-100."

    response = anthropic.Anthropic().messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )

    return {"score": int(response.content[0].text)}
```

### Template 2: Batch with Retries

```python
def assess_batch(jobs: list, cv_text: str) -> list:
    """Assess multiple jobs with built-in retries."""
    results = []
    for job_id, job_html in jobs:
        try:
            result = assess_job_non_streaming(cv_text, job_html)
            results.append({"job_id": job_id, "status": "success", "data": result})
        except anthropic.RateLimitError:
            results.append({"job_id": job_id, "status": "rate_limited"})
        except Exception as e:
            results.append({"job_id": job_id, "status": "error", "error": str(e)})
    return results
```

---

**Last Updated:** 2026-07-22
**Status:** Ready for implementation (Phase 1–4 tasks)
**Next:** Task 4 (Review Panel Enhancement)
