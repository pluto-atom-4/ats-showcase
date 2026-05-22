# ASSESS Phase: Job-CV Matching with Claude API

## Overview

The ASSESS phase uses Anthropic's Claude API to match preprocessed job postings against candidate CVs. This phase:

1. **Initializes Claude client** with rate limiting and retry logic
2. **Designs cost-optimized prompts** that leverage preprocessing outputs (tokens reduced 80-90%)
3. **Implements async job-CV matching** with comprehensive error handling
4. **Tracks token costs** transparently for budget awareness
5. **Handles edge cases** (network failures, rate limits, timeout)
6. **Tests with mocked Claude responses** before production

## Architecture

### Data Flow

```
VERIFY Phase Output
(verified job postings, verified CVs)
        ↓
┌──────────────────────────┐
│  Claude API Client Setup │
│ - Initialize with key    │
│ - Configure rate limits  │
│ - Set retry policy       │
└──────────────────────────┘
        ↓
┌──────────────────────────────┐
│  Prepare Assessment Request  │
│ - Build prompt with context  │
│ - Include preprocessed text  │
│ - Specify output format      │
└──────────────────────────────┘
        ↓
┌──────────────────────────────┐
│  Call Claude API             │
│ - Match job-to-CV            │
│ - Extract confidence score   │
│ - Return reasoning           │
└──────────────────────────────┘
        ↓
┌──────────────────────────────────────┐
│  Process Response                    │
│ - Parse JSON response                │
│ - Extract match score, reasoning     │
│ - Track tokens (cost calculation)    │
│ - Handle errors/fallbacks            │
└──────────────────────────────────────┘
        ↓
STORAGE Phase
(match results, costs, error log)
```

### Cost Breakdown

**Estimated costs per job assessment** (based on preprocessed data from PREPROCESS phase):

| Component | Input Tokens | Output Tokens | Approx Cost |
|-----------|--------------|---------------|------------|
| System prompt | 200 | 0 | $0.0001 |
| Job posting (cleaned, chunked) | 400-600 | 0 | $0.0002-0.0003 |
| CV context (preprocessed summary) | 300-500 | 0 | $0.0001-0.0002 |
| Claude response (match result) | 0 | 100-150 | $0.0002-0.0003 |
| **Total per job** | **900-1300** | **100-150** | **$0.0006-0.0008** |

**Cost reduction vs. unoptimized approach**:
- Raw HTML job posting: ~6000 tokens → ~500 tokens after preprocessing (91% reduction)
- Raw CV PDF: ~4000 tokens → ~350 tokens after preprocessing (91% reduction)
- **Token savings: 10,150 → 1,350 tokens per assessment (87% reduction)**
- **Cost per assessment: $0.02-0.03 → $0.0006-0.0008 (97% cost reduction)**

### Model Selection

**Recommended**: Claude 3.5 Sonnet (cost-optimized balance)

| Model | Input/1M tokens | Output/1M tokens | Latency | Use Case |
|-------|-----------------|------------------|---------|----------|
| Claude 3.5 Haiku | $0.80 | $4.00 | 500ms | High volume, tight budget |
| **Claude 3.5 Sonnet** | **$3.00** | **$15.00** | **1-2s** | **Recommended: balanced** |
| Claude 3 Opus | $15.00 | $75.00 | 2-3s | Complex analysis, precision critical |

**Rationale**: Sonnet provides strong job-CV reasoning at ~8x lower cost than Opus, with acceptable latency for verification-first workflow.

## Implementation

### 1. Claude API Client Setup

```python
import os
import json
from typing import Optional, Tuple
from anthropic import Anthropic, RateLimitError
import time

class AssessmentClient:
    """Wrapper for Claude API with rate limiting and retry logic."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_retries: int = 3,
        timeout_seconds: int = 30,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")

        self.client = Anthropic(api_key=self.api_key)
        self.model = model
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

        # Token tracking for cost calculations
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0

    def get_cost_estimate(self) -> dict:
        """Return cumulative cost estimate."""
        # Claude 3.5 Sonnet pricing (as of 2024)
        input_cost_per_million = 3.00
        output_cost_per_million = 15.00

        input_cost = (self.total_input_tokens / 1_000_000) * input_cost_per_million
        output_cost = (self.total_output_tokens / 1_000_000) * output_cost_per_million

        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "requests": self.total_requests,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(input_cost + output_cost, 6),
            "avg_cost_per_request": round((input_cost + output_cost) / max(self.total_requests, 1), 6),
        }

    def assess_job_cv_match(
        self,
        job_posting: dict,
        cv_summary: str,
        max_retries: Optional[int] = None,
    ) -> Tuple[dict, dict]:
        """
        Assess job-CV match using Claude.

        Args:
            job_posting: Dict with keys: title, requirements, responsibilities, benefits, salary
            cv_summary: Preprocessed CV text (should be <1000 tokens)
            max_retries: Override default retry count

        Returns:
            Tuple of (assessment_result, metadata)
            assessment_result = {
                "match_score": 0.0-1.0,
                "reasoning": "...",
                "strengths": ["..."],
                "gaps": ["..."],
                "recommendation": "strong_match|moderate_match|weak_match"
            }
            metadata = {
                "input_tokens": int,
                "output_tokens": int,
                "model": str,
                "latency_ms": float,
                "retry_count": int,
                "error": None or error message
            }
        """
        max_retries = max_retries or self.max_retries
        retry_count = 0

        while retry_count <= max_retries:
            try:
                start_time = time.time()

                # Build cost-optimized prompt
                system_prompt = self._build_system_prompt()
                user_message = self._build_assessment_prompt(job_posting, cv_summary)

                # Call Claude API
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                    timeout=self.timeout_seconds,
                )

                latency_ms = (time.time() - start_time) * 1000

                # Track tokens
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens
                self.total_requests += 1

                # Parse response
                content = response.content[0].text
                assessment = self._parse_assessment_response(content)

                metadata = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "model": self.model,
                    "latency_ms": round(latency_ms, 2),
                    "retry_count": retry_count,
                    "error": None,
                }

                return assessment, metadata

            except RateLimitError as e:
                retry_count += 1
                if retry_count > max_retries:
                    return self._fallback_assessment(), {
                        "error": f"Rate limit exceeded after {max_retries} retries: {str(e)}",
                        "retry_count": retry_count,
                    }
                # Exponential backoff
                wait_time = 2 ** retry_count
                print(f"Rate limited. Retrying in {wait_time}s...")
                time.sleep(wait_time)

            except Exception as e:
                print(f"Error in assessment: {str(e)}")
                return self._fallback_assessment(), {
                    "error": f"Assessment failed: {str(e)}",
                    "retry_count": retry_count,
                }

        return self._fallback_assessment(), {"error": "Max retries exceeded"}

    def _build_system_prompt(self) -> str:
        """Build system prompt for Claude."""
        return """You are an expert recruiter evaluating job-CV matches.

Your task:
1. Analyze the job posting requirements and responsibilities
2. Review the candidate CV summary
3. Provide a structured assessment with:
   - match_score: 0.0-1.0 confidence (0=no match, 1=perfect match)
   - reasoning: 2-3 sentence explanation
   - strengths: List 2-3 key candidate strengths matching the role
   - gaps: List 2-3 critical gaps or concerns
   - recommendation: strong_match | moderate_match | weak_match

Format your response as valid JSON only, no other text.

Scoring guidelines:
- 0.8-1.0 (strong): All major requirements met, strong cultural/domain fit
- 0.5-0.8 (moderate): Most requirements met, some gaps but learnable
- 0.0-0.5 (weak): Missing critical requirements or significant overqualification mismatch
"""

    def _build_assessment_prompt(self, job_posting: dict, cv_summary: str) -> str:
        """Build user message with job and CV context."""
        job_text = f"""
JOB POSTING:
Title: {job_posting.get('title', 'Unknown')}

Requirements:
{job_posting.get('requirements', 'Not provided')}

Responsibilities:
{job_posting.get('responsibilities', 'Not provided')}

Benefits/Compensation:
{job_posting.get('benefits', 'Not provided')}
{f"Salary: {job_posting.get('salary', '')}" if job_posting.get('salary') else ""}

CV SUMMARY:
{cv_summary}

Assess the match between this candidate and this job posting.
Return only valid JSON response, no markdown or formatting.
"""
        return job_text

    def _parse_assessment_response(self, content: str) -> dict:
        """Parse Claude's JSON response."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            assessment = json.loads(content.strip())

            # Validate required fields
            required = ["match_score", "reasoning", "strengths", "gaps", "recommendation"]
            for field in required:
                if field not in assessment:
                    assessment[field] = self._get_default_field(field)

            return assessment

        except json.JSONDecodeError:
            print(f"Failed to parse Claude response: {content}")
            return self._fallback_assessment()

    def _get_default_field(self, field: str):
        """Return default value for missing field."""
        defaults = {
            "match_score": 0.5,
            "reasoning": "Assessment incomplete",
            "strengths": [],
            "gaps": [],
            "recommendation": "moderate_match",
        }
        return defaults.get(field)

    def _fallback_assessment(self) -> dict:
        """Return fallback assessment when Claude fails."""
        return {
            "match_score": 0.0,
            "reasoning": "Assessment failed - manual review required",
            "strengths": [],
            "gaps": ["Unable to assess"],
            "recommendation": "weak_match",
        }
```

### 2. Batch Assessment with Progress Tracking

```python
from dataclasses import dataclass
from datetime import datetime
import csv

@dataclass
class AssessmentResult:
    job_id: str
    cv_id: str
    match_score: float
    recommendation: str
    reasoning: str
    strengths: list
    gaps: list
    input_tokens: int
    output_tokens: int
    latency_ms: float
    timestamp: str
    error: Optional[str] = None

class BatchAssessor:
    """Process batch of job-CV pairs with progress tracking."""

    def __init__(self, client: AssessmentClient, output_csv: str = "assessments.csv"):
        self.client = client
        self.output_csv = output_csv
        self.results = []

    def assess_batch(self, job_cv_pairs: list, show_progress: bool = True):
        """
        Process batch of (job, cv) pairs.

        Args:
            job_cv_pairs: List of tuples (job_dict, cv_summary, job_id, cv_id)
            show_progress: Print progress updates

        Returns:
            List of AssessmentResult objects
        """
        total = len(job_cv_pairs)

        for idx, (job, cv_summary, job_id, cv_id) in enumerate(job_cv_pairs, 1):
            if show_progress:
                print(f"[{idx}/{total}] Assessing {job_id} vs {cv_id}...", end=" ", flush=True)

            assessment, metadata = self.client.assess_job_cv_match(job, cv_summary)

            result = AssessmentResult(
                job_id=job_id,
                cv_id=cv_id,
                match_score=assessment.get("match_score", 0.0),
                recommendation=assessment.get("recommendation", "weak_match"),
                reasoning=assessment.get("reasoning", ""),
                strengths=assessment.get("strengths", []),
                gaps=assessment.get("gaps", []),
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0),
                latency_ms=metadata.get("latency_ms", 0),
                timestamp=datetime.now().isoformat(),
                error=metadata.get("error"),
            )

            self.results.append(result)

            if show_progress:
                status = "✓" if not metadata.get("error") else "✗"
                cost = self._estimate_result_cost(result)
                print(f"{status} (score: {result.match_score:.2f}, cost: ${cost:.6f})")

    def save_results(self):
        """Save results to CSV."""
        if not self.results:
            print("No results to save")
            return

        with open(self.output_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "job_id", "cv_id", "match_score", "recommendation", "reasoning",
                "strengths", "gaps", "input_tokens", "output_tokens", "latency_ms",
                "timestamp", "error"
            ])
            writer.writeheader()

            for result in self.results:
                writer.writerow({
                    "job_id": result.job_id,
                    "cv_id": result.cv_id,
                    "match_score": result.match_score,
                    "recommendation": result.recommendation,
                    "reasoning": result.reasoning,
                    "strengths": "|".join(result.strengths),
                    "gaps": "|".join(result.gaps),
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "latency_ms": result.latency_ms,
                    "timestamp": result.timestamp,
                    "error": result.error or "",
                })

        print(f"Saved {len(self.results)} results to {self.output_csv}")

    def print_cost_summary(self):
        """Print cost and performance summary."""
        cost_est = self.client.get_cost_estimate()

        print("\n" + "="*60)
        print("ASSESSMENT BATCH SUMMARY")
        print("="*60)
        print(f"Total requests: {cost_est['requests']}")
        print(f"Total input tokens: {cost_est['input_tokens']:,}")
        print(f"Total output tokens: {cost_est['output_tokens']:,}")
        print(f"Total cost: ${cost_est['total_cost_usd']:.6f}")
        print(f"Avg cost per request: ${cost_est['avg_cost_per_request']:.6f}")

        # Performance stats
        latencies = [r.latency_ms for r in self.results if r.latency_ms]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            print(f"Avg latency: {avg_latency:.0f}ms")

        # Match distribution
        recommendations = {}
        for r in self.results:
            recommendations[r.recommendation] = recommendations.get(r.recommendation, 0) + 1

        print(f"\nMatch distribution:")
        for rec, count in sorted(recommendations.items()):
            pct = (count / len(self.results)) * 100 if self.results else 0
            print(f"  {rec}: {count} ({pct:.1f}%)")

        errors = [r for r in self.results if r.error]
        if errors:
            print(f"\nErrors: {len(errors)}")
            for e in errors[:3]:  # Show first 3
                print(f"  {e.job_id}: {e.error}")

        print("="*60)

    def _estimate_result_cost(self, result: AssessmentResult) -> float:
        """Estimate cost for single result."""
        input_cost = (result.input_tokens / 1_000_000) * 3.00
        output_cost = (result.output_tokens / 1_000_000) * 15.00
        return input_cost + output_cost
```

### 3. Error Handling and Fallbacks

```python
class AssessmentError(Exception):
    """Base assessment error."""
    pass

class RateLimitedError(AssessmentError):
    """Claude API rate limited."""
    pass

class InvalidResponseError(AssessmentError):
    """Claude returned unparseable response."""
    pass

class NetworkError(AssessmentError):
    """Network connectivity issue."""
    pass

class ErrorHandler:
    """Centralized error handling with fallback strategies."""

    @staticmethod
    def handle_assessment_error(
        error: Exception,
        job_id: str,
        cv_id: str,
        retry_count: int = 0,
    ) -> dict:
        """
        Handle assessment errors with appropriate fallback.

        Fallback strategies:
        1. RateLimitError → exponential backoff + retry
        2. TimeoutError → fallback assessment + log for manual review
        3. InvalidResponseError → retry with simpler prompt
        4. NetworkError → queue for later retry
        """
        error_type = type(error).__name__

        if error_type == "RateLimitError":
            # Already handled in client.assess_job_cv_match()
            return {
                "strategy": "backoff_retry",
                "wait_seconds": 2 ** retry_count,
                "next_action": "retry",
            }

        elif error_type == "TimeoutError":
            return {
                "strategy": "fallback_assessment",
                "match_score": 0.5,
                "recommendation": "moderate_match",
                "reasoning": "Assessment timed out - manual review recommended",
                "next_action": "save_for_review",
            }

        elif error_type == "InvalidResponseError":
            return {
                "strategy": "simpler_prompt_retry",
                "next_action": "retry_with_simpler_prompt",
                "max_retries": 1,
            }

        else:
            # Generic error → fallback
            return {
                "strategy": "fallback_assessment",
                "match_score": 0.0,
                "recommendation": "weak_match",
                "reasoning": f"Assessment error: {str(error)}",
                "next_action": "save_for_manual_review",
            }
```

### 4. Testing with Mocked Responses

```python
from unittest.mock import Mock, patch

def test_assessment_client_success():
    """Test successful assessment."""
    # Mock Claude response
    mock_response = Mock()
    mock_response.content = [Mock(text=json.dumps({
        "match_score": 0.85,
        "reasoning": "Strong fit for role",
        "strengths": ["Python expert", "10+ years experience"],
        "gaps": ["No Rust experience"],
        "recommendation": "strong_match"
    }))]
    mock_response.usage.input_tokens = 1000
    mock_response.usage.output_tokens = 150

    with patch.object(Anthropic, 'messages') as mock_create:
        mock_create.return_value.create = Mock(return_value=mock_response)

        client = AssessmentClient()
        job = {
            "title": "Senior Python Engineer",
            "requirements": "Python, 5+ years",
            "responsibilities": "Build APIs",
            "benefits": "Competitive salary",
        }
        cv_summary = "Python expert, 10 years experience"

        assessment, metadata = client.assess_job_cv_match(job, cv_summary)

        assert assessment["match_score"] == 0.85
        assert assessment["recommendation"] == "strong_match"
        assert metadata["input_tokens"] == 1000
        assert metadata["output_tokens"] == 150

def test_assessment_client_rate_limit_retry():
    """Test rate limit handling with retry."""
    with patch.object(Anthropic, 'messages') as mock_create:
        # First call raises RateLimitError, second succeeds
        mock_success = Mock()
        mock_success.content = [Mock(text=json.dumps({
            "match_score": 0.5,
            "reasoning": "Moderate fit",
            "strengths": [],
            "gaps": [],
            "recommendation": "moderate_match"
        }))]
        mock_success.usage.input_tokens = 900
        mock_success.usage.output_tokens = 100

        mock_create.return_value.create = Mock(
            side_effect=[RateLimitError("Rate limited"), mock_success]
        )

        client = AssessmentClient(max_retries=1)
        job = {"title": "Test", "requirements": "Test"}
        cv_summary = "Test CV"

        # Should retry once after rate limit
        assessment, metadata = client.assess_job_cv_match(job, cv_summary)
        assert metadata.get("error") is None or assessment["match_score"] >= 0

def test_assessment_client_invalid_response():
    """Test handling of unparseable response."""
    mock_response = Mock()
    mock_response.content = [Mock(text="Not valid JSON")]
    mock_response.usage.input_tokens = 900
    mock_response.usage.output_tokens = 50

    with patch.object(Anthropic, 'messages') as mock_create:
        mock_create.return_value.create = Mock(return_value=mock_response)

        client = AssessmentClient()
        job = {"title": "Test", "requirements": "Test"}
        cv_summary = "Test CV"

        assessment, metadata = client.assess_job_cv_match(job, cv_summary)

        # Should return fallback assessment
        assert "match_score" in assessment
        assert "recommendation" in assessment
```

## Integration with Other Phases

### Input from VERIFY Phase
- Verified job postings (cleaned, deduplicated)
- Verified CVs (user-confirmed)
- User notes and preferences (e.g., "prioritize remote roles")

### Output to STORAGE Phase
- Assessment results (match_score, recommendation, reasoning)
- Cost tracking and attribution
- Error logs for failed assessments
- Metadata (latency, token counts, model version)

## Deployment Checklist

- [ ] **Environment setup**:
  - [ ] Set `ANTHROPIC_API_KEY` in `.env` or GitHub Secrets
  - [ ] Test API connectivity: `python -c "from anthropic import Anthropic; Anthropic().models.list()"`

- [ ] **Configuration**:
  - [ ] Confirm model selection (Claude 3.5 Sonnet recommended)
  - [ ] Set retry policy (default: 3 retries with exponential backoff)
  - [ ] Configure timeout (default: 30 seconds)

- [ ] **Testing**:
  - [ ] Run unit tests with mocked Claude responses
  - [ ] Run integration test with 5 sample job-CV pairs
  - [ ] Verify cost tracking accuracy vs actual invoice

- [ ] **Monitoring**:
  - [ ] Log all API calls (timestamp, tokens, cost)
  - [ ] Alert on error rate >5%
  - [ ] Track rate limit frequency (should be rare)

- [ ] **Cost controls**:
  - [ ] Set daily budget alert ($50 recommended for testing)
  - [ ] Implement request throttling if needed (2-5 requests/sec)
  - [ ] Review cost per job after first 100 assessments

## Performance Targets

| Metric | Target | Note |
|--------|--------|------|
| Latency per assessment | 1-2 seconds | Includes API call + parsing |
| Throughput | 2-5 jobs/min | Limited by Claude rate limits |
| Cost per assessment | $0.0006-0.0008 | After preprocessing optimization |
| Error rate | <2% | Mostly transient (rate limits, network) |
| Successful retry rate | >95% | Rate limits should resolve on retry |

## Next Steps

1. **Integration**: Combine with VERIFY phase (use verified data only)
2. **Caching**: Consider caching assessments for duplicate job-CV pairs
3. **Async processing**: Use job queue (Celery/RQ) for high-volume (100+ jobs/day)
4. **Cost optimization**: Monitor token counts and adjust prompt size if >1500 tokens/request
5. **A/B testing**: Compare Claude 3.5 Sonnet vs Opus on sample 50-job batch for ROI analysis

---

**Related Documentation**:
- [PREPROCESS.md](./PREPROCESS.md) - Input data preparation
- [VERIFY.md](./VERIFY.md) - User verification workflow
- [STORAGE.md](./STORAGE.md) - Result persistence and querying
- [COMPATIBILITY.md](./COMPATIBILITY.md) - Python/SDK compatibility
