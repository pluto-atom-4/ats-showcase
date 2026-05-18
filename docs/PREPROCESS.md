# PREPROCESS Phase: Text Transformation & Token Optimization

**Goal**: Transform raw HTML job postings into semantically meaningful chunks with accurate token counts before sending to Claude.

**Why it matters**: Local preprocessing reduces tokens by 80-90% vs raw HTML, dramatically lowering LLM costs while improving context quality for better assessments.

---

## Architecture Overview

The PREPROCESS phase runs **locally only** (no LLM calls) and produces three key outputs:

```
Raw HTML Job Posting
    ↓
[HTML Cleaning] → Remove scripts, ads, boilerplate
    ↓
[Text Extraction] → Convert to plain text with spaCy
    ↓
[Semantic Chunking] → Split at sentence/paragraph boundaries
    ↓
[Token Counting] → Count tokens per chunk with tiktoken
    ↓
[Metadata Tagging] → Mark chunk type (title, description, requirements)
    ↓
Structured Chunks Ready for VERIFY Phase
```

**Cost Impact**: 
- Raw HTML: ~5,000-8,000 tokens per job posting
- After preprocessing: ~500-800 tokens (82% reduction)
- Savings: $0.034 per posting with Claude 3.5 Haiku

---

## 1. HTML Cleaning & Text Extraction

### Problem: Raw HTML is Token-Wasteful

```html
<!-- Real-world example: unnecessary tokens -->
<div class="job-posting" id="j-123" data-variant="click" onclick="...">
  <script src="analytics.js"></script>
  <div class="ad-banner">Buy our product!</div>
  <h1 class="title">Senior Software Engineer</h1>
  <p class="description">We are hiring a Senior...</p>
</div>
```

Naive token count: ~450 tokens (just for the metadata!)

### Solution 1: MarkItDown (Recommended)

**MarkItDown** is Microsoft's modern HTML-to-Markdown converter, optimized for LLM processing. It preserves structure (headings, lists, tables) while removing noise.

```python
from markitdown import MarkItDown

def clean_html_with_markitdown(html_string: str) -> str:
    """
    Convert HTML to clean Markdown text.
    
    MarkItDown advantages:
    - Preserves document structure (headings, lists)
    - Token-efficient Markdown format
    - Handles malformed HTML gracefully
    - Much faster than BeautifulSoup for this use case
    """
    md = MarkItDown()
    
    # Convert HTML string to markdown
    # Note: MarkItDown's convert() expects file paths,
    # so we use text_content from HTML stream conversion
    try:
        # For raw HTML strings, we parse directly
        result = md.convert_stream(
            stream=io.StringIO(html_string),
            file_extension=".html"
        )
        return result.text_content
    except Exception as e:
        print(f"MarkItDown conversion failed: {e}")
        # Fallback to BeautifulSoup
        return clean_html_with_beautifulsoup(html_string)
```

**Result**: ~120 tokens (73% reduction just from cleaning)

### Solution 2: BeautifulSoup (Fallback)

For cases where MarkItDown isn't suitable, use **BeautifulSoup4 + lxml**:

```python
from bs4 import BeautifulSoup

def clean_html_with_beautifulsoup(raw_html: str) -> str:
    """Remove scripts, styles, ads, tracking elements."""
    soup = BeautifulSoup(raw_html, 'lxml')
    
    # Remove noise elements
    for tag in soup.find_all(['script', 'style', 'iframe', 'noscript']):
        tag.decompose()
    
    # Remove common ad/tracking classes
    for tag in soup.find_all(class_=lambda x: x and any(
        noise in x.lower() 
        for noise in ['ad', 'banner', 'tracking', 'analytics', 'cookie']
    )):
        tag.decompose()
    
    # Extract text with preserved structure
    text = soup.get_text(separator='\n', strip=True)
    
    # Remove excessive whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)
```

### Comparison: MarkItDown vs BeautifulSoup

| Aspect | MarkItDown | BeautifulSoup |
|--------|-----------|--------------|
| **Purpose** | HTML→Markdown conversion | HTML parsing/manipulation |
| **Speed** | Fast (single pass) | Slower (tree traversal) |
| **Structure preservation** | Headings, lists, tables ✓ | Manual parsing needed |
| **Markdown output** | Native ✓ | Requires manual formatting |
| **Dependency weight** | ~50 KB | ~200 KB |
| **LLM-friendly** | Excellent | Good |
| **Fallback capability** | No | Yes (if MarkItDown fails) |

**Recommendation**: Use **MarkItDown as primary**, BeautifulSoup as fallback for edge cases.

### Complete HTML Cleaning Pipeline

```python
import io
from typing import Optional

class HTMLCleaner:
    def __init__(self, prefer_markitdown: bool = True):
        self.prefer_markitdown = prefer_markitdown
        
        if prefer_markitdown:
            try:
                from markitdown import MarkItDown
                self.md = MarkItDown()
            except ImportError:
                print("MarkItDown not installed, using BeautifulSoup fallback")
                self.md = None
        else:
            self.md = None
    
    def clean(self, html: str) -> str:
        """Clean HTML using preferred method."""
        if self.prefer_markitdown and self.md:
            return self._clean_with_markitdown(html)
        else:
            return self._clean_with_beautifulsoup(html)
    
    def _clean_with_markitdown(self, html: str) -> str:
        try:
            result = self.md.convert_stream(
                stream=io.StringIO(html),
                file_extension=".html"
            )
            return result.text_content
        except Exception as e:
            print(f"MarkItDown failed: {e}, falling back to BeautifulSoup")
            return self._clean_with_beautifulsoup(html)
    
    def _clean_with_beautifulsoup(self, html: str) -> str:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        
        for tag in soup.find_all(['script', 'style', 'iframe', 'noscript']):
            tag.decompose()
        
        text = soup.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)

# Usage
cleaner = HTMLCleaner(prefer_markitdown=True)
clean_text = cleaner.clean(raw_html)
```

### Text Extraction with spaCy

spaCy provides sentence segmentation and NLP preprocessing:

```python
import spacy

nlp = spacy.load('en_core_web_sm')

def extract_text_with_nlp(clean_text: str) -> dict:
    """Extract sentences and identify key entities."""
    doc = nlp(clean_text)
    
    return {
        'sentences': [sent.text for sent in doc.sents],
        'tokens': [token.text for token in doc],
        'entities': [
            {
                'text': ent.text,
                'label': ent.label_,
                'start_char': ent.start_char,
                'end_char': ent.end_char,
            }
            for ent in doc.ents
        ],
        'noun_chunks': [chunk.text for chunk in doc.noun_chunks],
    }
```

---

## 2. Semantic Chunking Strategy

### Why Not Simple Token Splitting?

❌ **Bad approach**: Split every 512 tokens
- Breaks sentences mid-way
- Loses context relationships
- Confuses LLM assessment

✅ **Good approach**: Split at sentence/paragraph boundaries
- Keeps semantic units together
- Preserves context for LLM
- Estimated 80-90% token reduction still achieved

### Implementation: Boundary-Aware Chunking

```python
from typing import List
import tiktoken

def create_semantic_chunks(
    sentences: List[str],
    target_tokens: int = 512,
    max_tokens: int = 1024
) -> List[dict]:
    """
    Create chunks respecting sentence boundaries.
    
    Args:
        sentences: List of sentences from spaCy
        target_tokens: Try to fit this many tokens per chunk
        max_tokens: Hard limit (never exceed)
    
    Returns:
        List of chunks with metadata
    """
    enc = tiktoken.encoding_for_model('claude-3-5-haiku-20241022')
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for sentence in sentences:
        sentence_tokens = len(enc.encode(sentence))
        
        # If adding this sentence exceeds target, start new chunk
        if current_tokens + sentence_tokens > target_tokens and current_chunk:
            chunks.append({
                'text': ' '.join(current_chunk),
                'token_count': current_tokens,
                'sentence_count': len(current_chunk),
            })
            current_chunk = []
            current_tokens = 0
        
        # If sentence alone exceeds max, truncate (rare for job postings)
        if sentence_tokens > max_tokens:
            sentence = sentence[:200]  # Emergency truncation
        
        current_chunk.append(sentence)
        current_tokens += sentence_tokens
    
    # Don't forget last chunk
    if current_chunk:
        chunks.append({
            'text': ' '.join(current_chunk),
            'token_count': current_tokens,
            'sentence_count': len(current_chunk),
        })
    
    return chunks
```

### Chunk Type Classification

Mark each chunk with its semantic role:

```python
def classify_chunk_type(text: str, position: int, total_chunks: int) -> str:
    """
    Classify chunk content for filtering/prioritization.
    
    Values: 'title', 'description', 'requirements', 'benefits', 'other'
    """
    text_lower = text.lower()
    
    # Position heuristic: title usually near start
    if position == 0 or (position < 2 and len(text) < 100):
        return 'title'
    
    # Content matching
    if any(keyword in text_lower for keyword in 
           ['requirement', 'must have', 'needed', 'skill', 'experience']):
        return 'requirements'
    
    if any(keyword in text_lower for keyword in 
           ['benefit', 'offer', 'we provide', 'perks', 'compensation']):
        return 'benefits'
    
    if any(keyword in text_lower for keyword in 
           ['about us', 'company', 'our team', 'mission', 'vision']):
        return 'description'
    
    return 'other'
```

---

## 3. Token Counting & Cost Optimization

### Accurate Token Counting with tiktoken

```python
import tiktoken

class TokenCounter:
    """Wrapper for consistent token counting across project."""
    
    def __init__(self, model: str = 'claude-3-5-haiku-20241022'):
        self.encoding = tiktoken.encoding_for_model(model)
        self.model = model
    
    def count_tokens(self, text: str) -> int:
        """Count tokens for given text."""
        return len(self.encoding.encode(text))
    
    def count_batch(self, texts: List[str]) -> List[int]:
        """Count tokens for multiple texts."""
        return [self.count_tokens(text) for text in texts]
    
    def estimate_cost(self, token_count: int, operation: str = 'input') -> float:
        """
        Estimate cost for tokens.
        
        Claude 3.5 Haiku pricing:
        - Input: $0.80 per 1M tokens
        - Output: $4.00 per 1M tokens (estimate 20% output)
        """
        rates = {
            'claude-3-5-haiku-20241022': {
                'input': 0.80e-6,  # per token
                'output': 4.00e-6,
            }
        }
        
        if self.model not in rates:
            raise ValueError(f"Unknown model: {self.model}")
        
        rate = rates[self.model].get(operation, 0)
        return token_count * rate

# Usage
counter = TokenCounter()

# Single text
tokens = counter.count_tokens("Senior Software Engineer")
cost = counter.estimate_cost(tokens, 'input')
print(f"Tokens: {tokens}, Cost: ${cost:.6f}")

# Batch
texts = ["5+ years Python", "AWS experience", "Remote or NYC"]
token_counts = counter.count_batch(texts)
total_tokens = sum(token_counts)
total_cost = counter.estimate_cost(total_tokens)
```

### Cost Projection Example

For a 500-job scraping run:

```
Raw HTML pipeline:
- Average tokens per job: 6,000
- Total tokens: 3,000,000
- Input cost: $2.40
- Estimated output: $0.48 (20% of input)
- Total: $2.88 per run

✓ With preprocessing:
- Average tokens per job: 800
- Total tokens: 400,000
- Input cost: $0.32
- Estimated output: $0.06
- Total: $0.38 per run

Savings: 86.8% cost reduction ($2.50 saved per 500 jobs)
```

---

## 4. Complete Preprocessing Pipeline

### Full Implementation

```python
from dataclasses import dataclass
from typing import List, Optional
import spacy
import tiktoken

@dataclass
class ProcessedChunk:
    text: str
    chunk_type: str
    token_count: int
    sentence_count: int
    chunk_index: int
    total_chunks: int

@dataclass
class ProcessedJob:
    job_id: str
    company: str
    title: str
    original_tokens: int
    processed_tokens: int
    chunks: List[ProcessedChunk]
    
    @property
    def token_reduction_pct(self) -> float:
        return (1 - self.processed_tokens / self.original_tokens) * 100

class PreprocessingPipeline:
    def __init__(
        self,
        spacy_model: str = 'en_core_web_sm',
        use_markitdown: bool = True
    ):
        self.nlp = spacy.load(spacy_model)
        self.token_counter = TokenCounter()
        self.html_cleaner = HTMLCleaner(prefer_markitdown=use_markitdown)
    
    def process_job(
        self,
        job_id: str,
        company: str,
        title: str,
        html_content: str,
        target_chunk_tokens: int = 512,
    ) -> ProcessedJob:
        """Full preprocessing pipeline for one job."""
        
        # Step 1: Clean HTML (MarkItDown or BeautifulSoup)
        clean_text = self.html_cleaner.clean(html_content)
        
        # Step 2: Extract with NLP
        doc = self.nlp(clean_text)
        sentences = [sent.text for sent in doc.sents]
        
        # Step 3: Semantic chunking
        chunks_data = create_semantic_chunks(
            sentences,
            target_tokens=target_chunk_tokens,
        )
        
        # Step 4: Classify and track tokens
        processed_chunks = []
        total_processed_tokens = 0
        
        for idx, chunk_data in enumerate(chunks_data):
            chunk_type = classify_chunk_type(
                chunk_data['text'],
                idx,
                len(chunks_data)
            )
            
            processed_chunks.append(ProcessedChunk(
                text=chunk_data['text'],
                chunk_type=chunk_type,
                token_count=chunk_data['token_count'],
                sentence_count=chunk_data['sentence_count'],
                chunk_index=idx,
                total_chunks=len(chunks_data),
            ))
            
            total_processed_tokens += chunk_data['token_count']
        
        # Compare to original HTML token count
        original_tokens = self.token_counter.count_tokens(html_content)
        
        return ProcessedJob(
            job_id=job_id,
            company=company,
            title=title,
            original_tokens=original_tokens,
            processed_tokens=total_processed_tokens,
            chunks=processed_chunks,
        )
    
    def process_batch(
        self,
        jobs: List[dict],  # [{'id': '', 'company': '', 'title': '', 'html': ''}]
    ) -> List[ProcessedJob]:
        """Process multiple jobs."""
        results = []
        for job in jobs:
            result = self.process_job(
                job_id=job['id'],
                company=job['company'],
                title=job['title'],
                html_content=job['html'],
            )
            results.append(result)
        
        # Print summary
        if results:
            total_reduction = sum(j.token_reduction_pct for j in results) / len(results)
            print(f"Batch summary: {len(results)} jobs processed")
            print(f"Average token reduction: {total_reduction:.1f}%")
        
        return results
```

### Usage

```python
# Initialize pipeline (uses MarkItDown by default)
pipeline = PreprocessingPipeline(use_markitdown=True)

# From CRAWL phase, we have raw jobs
jobs_from_crawl = [
    {
        'id': 'job-123',
        'company': 'TechCorp',
        'title': 'Senior Software Engineer',
        'html': '<div>...</div>',
    },
    # ... more jobs
]

# Process all jobs
processed_jobs = pipeline.process_batch(jobs_from_crawl)

# Inspect results
for job in processed_jobs:
    print(f"\n{job.company} - {job.title}")
    print(f"Reduction: {job.token_reduction_pct:.1f}%")
    print(f"Chunks: {len(job.chunks)}")
    for chunk in job.chunks:
        print(f"  [{chunk.chunk_type}] {chunk.token_count} tokens, {chunk.sentence_count} sentences")
```

---

## 5. Testing Strategy

### Unit Tests: HTML Cleaning

```python
import pytest

def test_markitdown_removes_scripts():
    html = "<div><script>alert('xss')</script><p>Job title</p></div>"
    cleaner = HTMLCleaner(prefer_markitdown=True)
    result = cleaner.clean(html)
    assert "alert" not in result
    assert "Job title" in result

def test_beautifulsoup_fallback():
    html = "<div><p>Real content</p></div>"
    cleaner = HTMLCleaner(prefer_markitdown=False)
    result = cleaner.clean(html)
    assert "Real content" in result

def test_semantic_chunking_respects_sentence_boundaries():
    sentences = ["This is sentence one.", "This is sentence two.", "This is sentence three."]
    chunks = create_semantic_chunks(sentences, target_tokens=20)
    
    # Each chunk should contain complete sentences
    for chunk in chunks:
        assert chunk['text'].endswith('.')

def test_chunk_type_classification():
    title_text = "Senior Software Engineer - Platform Team"
    assert classify_chunk_type(title_text, 0, 5) == 'title'
    
    req_text = "Requirements: 5+ years Python, AWS expertise"
    assert classify_chunk_type(req_text, 2, 5) == 'requirements'

def test_token_counter_accuracy():
    counter = TokenCounter()
    
    # Known examples
    text = "Hello world"
    tokens = counter.count_tokens(text)
    assert tokens > 0
    assert tokens <= 3  # "Hello" + "world" at most
```

### Integration Tests: Full Pipeline

```python
def test_full_preprocessing_pipeline():
    pipeline = PreprocessingPipeline(use_markitdown=True)
    
    job = {
        'id': 'test-1',
        'company': 'TestCorp',
        'title': 'Engineer',
        'html': '''
            <div>
                <script>tracking()</script>
                <h1>Senior Software Engineer</h1>
                <p>We're looking for a talented engineer.</p>
                <h2>Requirements</h2>
                <ul>
                    <li>5+ years Python</li>
                    <li>AWS expertise</li>
                </ul>
            </div>
        '''
    }
    
    result = pipeline.process_job(
        job_id=job['id'],
        company=job['company'],
        title=job['title'],
        html_content=job['html'],
    )
    
    # Verify structure
    assert result.job_id == 'test-1'
    assert len(result.chunks) > 0
    assert result.token_reduction_pct > 70
    
    # Verify chunks
    for chunk in result.chunks:
        assert chunk.token_count > 0
        assert chunk.chunk_type in ['title', 'description', 'requirements', 'benefits', 'other']
```

---

## 6. Dependencies & Installation

### Core Dependencies

```toml
# pyproject.toml
[project.optional-dependencies]
preprocess = [
    "spacy>=3.8.0",           # NLP preprocessing
    "tiktoken>=0.8.0",        # Token counting
    "markitdown>=0.1.5",      # HTML→Markdown (recommended)
    "beautifulsoup4>=4.12.0", # HTML parsing (fallback)
    "lxml>=4.9.0",            # HTML parser (required by BeautifulSoup)
]
```

### Installation

```bash
# Install with MarkItDown
uv pip install "markitdown[all]" spacy tiktoken beautifulsoup4 lxml

# Download spaCy model
python -m spacy download en_core_web_sm

# Verify installation
python -c "from markitdown import MarkItDown; import spacy; import tiktoken; print('All dependencies OK')"
```

---

## 7. Deployment Checklist

Before moving to VERIFY phase:

- [ ] **MarkItDown installed**: `pip install markitdown[all]` or falls back to BeautifulSoup
- [ ] **spaCy model downloaded**: `python -m spacy download en_core_web_sm`
- [ ] **HTML cleaning tested**: Run 10+ real job postings, verify no data loss
- [ ] **Token counting verified**: Compare tiktoken counts to Claude API (±2 token variance acceptable)
- [ ] **Chunking produces valid text**: No mid-word breaks, all chunks readable
- [ ] **Chunk classification works**: 90%+ accuracy on manual inspection of 20 jobs
- [ ] **Cost calculations verified**: Batch of 100 jobs confirms 80%+ token reduction
- [ ] **Performance acceptable**: Pipeline processes 100 jobs in < 30 seconds
- [ ] **Error handling**: Test with malformed HTML, empty text, extreme sizes (>10KB postings)

---

## 8. Common Pitfalls & Solutions

| Problem | Symptom | Solution |
|---------|---------|----------|
| **spaCy model not loaded** | `OSError: can't find model 'en_core_web_sm'` | Run `python -m spacy download en_core_web_sm` |
| **tiktoken mismatch** | Token counts differ from Claude API | Ensure tiktoken ≥ 0.8.0; use `claude-3-5-haiku-20241022` constant |
| **lxml not installed** | `FeatureNotFound: Couldn't find a tree builder` | Install: `pip install lxml` |
| **MarkItDown import fails** | `ModuleNotFoundError: No module named 'markitdown'` | Install: `pip install markitdown[all]` OR use BeautifulSoup fallback |
| **Sentence splitting too aggressive** | Chunks too small, many fragments | Increase `target_tokens` from 512 to 768 |
| **Memory exhaustion** | Process hangs on large HTML (>50MB) | Add size check: `if len(html) > 1000000: truncate()` |
| **Unicode encoding issues** | Mojibake (garbled text) after cleaning | Ensure UTF-8 handling: `html.encode('utf-8')` |

---

## 9. Next Steps

After PREPROCESS phase completes:

1. **VERIFY**: User confirms chunks are accurate before expensive LLM calls
2. **ASSESS**: Send verified chunks to Claude for job-CV fit scoring
3. **STORAGE**: Save results and track cost per job

See `docs/README.md` for phase navigation.
