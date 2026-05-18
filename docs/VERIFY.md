# VERIFY Phase: Interactive User Verification & Data Confirmation

**Goal**: Present preprocessed job chunks to user with token costs, allowing review/confirmation before expensive LLM calls.

**Why it matters**: User verification catches extraction errors early, prevents garbage data to Claude API, saves 10-30% of LLM costs by filtering invalid jobs.

---

## Architecture Overview

The VERIFY phase bridges PREPROCESS and ASSESS:

```
Preprocessed Chunks (from PREPROCESS)
    ↓
[Interactive CLI]
    ├─ Display job title & company
    ├─ Show chunks with token counts
    ├─ Display cost estimate for LLM
    ├─ Ask user: Approve / Reject / Edit
    ↓
[User Decision]
    ├─ ✅ Approve: Mark as "confirmed"
    ├─ ❌ Reject: Mark as "rejected" (skip LLM)
    └─ ✏️ Edit: User fixes typos/errors
    ↓
Confirmed Chunks → ASSESS Phase (Claude API)
Rejected Chunks → Skip LLM entirely
```

**Cost Impact**:
- Without verification: 100% of jobs sent to LLM (including garbage)
- With verification: 70-90% of jobs confirmed (10-30% filtered)
- Savings: $0.001-$0.003 per rejected job (token cost not wasted)

---

## 1. Verification Data Model

### Input: Processed Job Structure

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ProcessedChunk:
    """From PREPROCESS phase"""
    text: str
    chunk_type: str  # title, description, requirements, benefits, other
    token_count: int
    sentence_count: int
    chunk_index: int
    total_chunks: int

@dataclass
class ProcessedJob:
    """From PREPROCESS phase"""
    job_id: str
    company: str
    title: str
    original_tokens: int
    processed_tokens: int
    chunks: List[ProcessedChunk]
    
    @property
    def token_reduction_pct(self) -> float:
        return (1 - self.processed_tokens / self.original_tokens) * 100

@dataclass
class VerificationResult:
    """Output: User's decision"""
    job_id: str
    company: str
    title: str
    status: str  # confirmed, rejected, edited
    confirmed_chunks: List[ProcessedChunk]
    reason: Optional[str] = None  # Why rejected or edited
    timestamp: str = None  # ISO 8601
    
    def to_dict(self):
        return {
            'job_id': self.job_id,
            'company': self.company,
            'title': self.title,
            'status': self.status,
            'chunks': [c.__dict__ for c in self.confirmed_chunks],
            'reason': self.reason,
            'timestamp': self.timestamp,
        }
```

---

## 2. Interactive CLI with Typer

### High-Level Workflow

```python
import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer()
console = Console()

@app.command()
def verify(
    input_file: str = typer.Argument(..., help="Preprocessed jobs JSON file"),
    output_file: Optional[str] = typer.Option(
        None, 
        "--output", 
        "-o",
        help="Save verified jobs (default: auto-generated)"
    ),
    batch_mode: bool = typer.Option(
        False,
        "--batch",
        "-b",
        help="Approve all without prompting (DANGEROUS, use carefully)"
    ),
    skip_rejected: bool = typer.Option(
        True,
        "--keep-rejected",
        help="Save rejected jobs separately for review"
    ),
):
    """
    Interactive verification: Review preprocessed jobs before LLM assessment.
    
    Workflow:
    1. Load preprocessed jobs from JSON
    2. For each job:
       - Display title, company, token cost
       - Show chunks (5 at a time)
       - Ask: Approve (A) / Reject (R) / Edit (E) / Show More (M)?
    3. Save confirmed jobs for ASSESS phase
    4. Optionally save rejected jobs for later review
    
    Example:
        uv run python main.py verify data/extracted_jobs/Company_jobs.json
        uv run python main.py verify data/extracted_jobs/Company_jobs.json --output data/verified_jobs/
    """
    
    # Load preprocessed jobs
    jobs = load_preprocessed_jobs(input_file)
    console.print(f"[bold blue]Loaded {len(jobs)} preprocessed jobs[/bold blue]")
    
    # Initialize results
    confirmed = []
    rejected = []
    
    # Process each job
    for idx, job in enumerate(jobs, 1):
        console.print(f"\n[bold cyan]Job {idx}/{len(jobs)}[/bold cyan]")
        
        # Display job summary
        display_job_summary(job)
        
        # Get user decision
        if batch_mode:
            decision = 'approve'
        else:
            decision = prompt_user_decision(job)
        
        # Handle decision
        if decision == 'approve':
            result = VerificationResult(
                job_id=job.job_id,
                company=job.company,
                title=job.title,
                status='confirmed',
                confirmed_chunks=job.chunks,
                timestamp=datetime.now().isoformat(),
            )
            confirmed.append(result)
            console.print("[green]✅ Confirmed[/green]")
        
        elif decision == 'reject':
            reason = typer.prompt("Why reject? (optional)")
            result = VerificationResult(
                job_id=job.job_id,
                company=job.company,
                title=job.title,
                status='rejected',
                confirmed_chunks=[],
                reason=reason or "User rejected",
                timestamp=datetime.now().isoformat(),
            )
            rejected.append(result)
            console.print("[red]❌ Rejected[/red]")
        
        elif decision == 'edit':
            edited_chunks = edit_chunks_interactive(job.chunks)
            result = VerificationResult(
                job_id=job.job_id,
                company=job.company,
                title=job.title,
                status='edited',
                confirmed_chunks=edited_chunks,
                reason="User edited chunks",
                timestamp=datetime.now().isoformat(),
            )
            confirmed.append(result)
            console.print("[yellow]✏️  Edited and confirmed[/yellow]")
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  ✅ Confirmed: {len(confirmed)}")
    console.print(f"  ❌ Rejected: {len(rejected)}")
    console.print(f"  📊 Acceptance rate: {len(confirmed) / len(jobs) * 100:.1f}%")
    
    # Save results
    output_path = output_file or f"data/verified_jobs/{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_verified_jobs(confirmed, output_path)
    console.print(f"\n[green]✅ Saved {len(confirmed)} confirmed jobs to: {output_path}[/green]")
    
    if skip_rejected and rejected:
        rejected_path = output_path.replace('verified_jobs', 'rejected_jobs')
        save_rejected_jobs(rejected, rejected_path)
        console.print(f"[yellow]⚠️  Saved {len(rejected)} rejected jobs to: {rejected_path}[/yellow]")
```

---

## 3. Display & User Interface

### Job Summary Display

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

def display_job_summary(job: ProcessedJob):
    """Show job header with key info."""
    console = Console()
    
    # Header
    header = f"[bold cyan]{job.title}[/bold cyan]\n"
    header += f"[dim]{job.company}[/dim]"
    console.print(Panel(header, title="Job Posting", expand=False))
    
    # Token cost breakdown
    table = Table(title="Token Cost Estimate", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_column("Cost", justify="right", style="yellow")
    
    processed_tokens = job.processed_tokens
    original_tokens = job.original_tokens
    token_counter = TokenCounter()
    
    input_cost = token_counter.estimate_cost(processed_tokens, 'input')
    output_cost = token_counter.estimate_cost(processed_tokens * 0.2, 'output')  # Estimate 20% output
    total_cost = input_cost + output_cost
    
    table.add_row(
        "Processed tokens",
        str(processed_tokens),
        f"${input_cost:.4f}"
    )
    table.add_row(
        "Est. output tokens (20%)",
        str(int(processed_tokens * 0.2)),
        f"${output_cost:.4f}"
    )
    table.add_row(
        "[bold]Total estimated cost[/bold]",
        "[bold]—[/bold]",
        f"[bold yellow]${total_cost:.4f}[/bold yellow]"
    )
    table.add_row(
        "Token reduction",
        f"{job.token_reduction_pct:.1f}%",
        f"Saved: ${token_counter.estimate_cost(original_tokens - processed_tokens):.4f}"
    )
    
    console.print(table)

def display_chunks(chunks: List[ProcessedChunk], start_idx: int = 0, per_page: int = 5):
    """Show chunks paginated, 5 at a time."""
    console = Console()
    
    table = Table(title=f"Chunks {start_idx+1} to {min(start_idx+per_page, len(chunks))} of {len(chunks)}")
    table.add_column("Idx", style="dim", width=3)
    table.add_column("Type", style="magenta", width=12)
    table.add_column("Text Preview", width=70)
    table.add_column("Tokens", justify="right", style="yellow")
    
    for i in range(start_idx, min(start_idx + per_page, len(chunks))):
        chunk = chunks[i]
        preview = chunk.text[:65] + "..." if len(chunk.text) > 65 else chunk.text
        
        # Color code by type
        type_color = {
            'title': '[cyan]',
            'description': '[blue]',
            'requirements': '[yellow]',
            'benefits': '[green]',
            'other': '[dim]'
        }.get(chunk.chunk_type, '[white]')
        
        table.add_row(
            str(i + 1),
            f"{type_color}{chunk.chunk_type}[/]",
            preview,
            str(chunk.token_count)
        )
    
    console.print(table)
    
    if start_idx + per_page < len(chunks):
        console.print(f"[dim]... {len(chunks) - (start_idx + per_page)} more chunks[/dim]")

def prompt_user_decision(job: ProcessedJob) -> str:
    """Interactive decision prompt."""
    console = Console()
    
    while True:
        console.print("\n[bold]What do you want to do?[/bold]")
        console.print("[cyan](A)[/cyan] Approve as-is and send to LLM")
        console.print("[yellow](M)[/yellow] Show more chunks (page through all)")
        console.print("[red](R)[/red] Reject - don't send to LLM")
        console.print("[magenta](E)[/magenta] Edit chunks before confirming")
        console.print("[dim](S)[/dim] Skip to next job")
        
        choice = typer.prompt("Enter choice").upper()
        
        if choice in ['A', 'M', 'R', 'E', 'S']:
            if choice == 'A':
                return 'approve'
            elif choice == 'M':
                show_all_chunks_interactive(job.chunks)
                continue
            elif choice == 'R':
                return 'reject'
            elif choice == 'E':
                return 'edit'
            elif choice == 'S':
                return 'skip'
        else:
            console.print("[red]Invalid choice, try again[/red]")

def show_all_chunks_interactive(chunks: List[ProcessedChunk]):
    """Paginated chunk browsing."""
    console = Console()
    
    idx = 0
    while idx < len(chunks):
        display_chunks(chunks, start_idx=idx)
        
        if idx + 5 < len(chunks):
            choice = typer.prompt("[dim](N)ext, (P)revious, or (Q)uit paging?[/dim]").upper()
            if choice == 'N':
                idx += 5
            elif choice == 'P':
                idx = max(0, idx - 5)
            elif choice == 'Q':
                break
        else:
            typer.prompt("[dim]End of chunks. Press Enter to continue...[/dim]")
            break

def edit_chunks_interactive(chunks: List[ProcessedChunk]) -> List[ProcessedChunk]:
    """Allow user to edit or remove problematic chunks."""
    console = Console()
    
    modified_chunks = list(chunks)
    
    while True:
        console.print(f"\n[bold cyan]{len(modified_chunks)} chunks total[/bold cyan]")
        display_chunks(modified_chunks, start_idx=0, per_page=10)
        
        console.print("\n[bold]Edit options:[/bold]")
        console.print("[red](D)[/red] Delete a chunk by number")
        console.print("[magenta](E)[/magenta] Edit a chunk's text")
        console.print("[green](D)[/green] Done editing")
        
        choice = typer.prompt("Enter choice").upper()
        
        if choice == 'D':
            chunk_num = int(typer.prompt("Chunk number to delete (1-indexed)")) - 1
            if 0 <= chunk_num < len(modified_chunks):
                deleted = modified_chunks.pop(chunk_num)
                console.print(f"[red]Deleted chunk {chunk_num + 1}[/red]")
            else:
                console.print("[red]Invalid chunk number[/red]")
        
        elif choice == 'E':
            chunk_num = int(typer.prompt("Chunk number to edit (1-indexed)")) - 1
            if 0 <= chunk_num < len(modified_chunks):
                chunk = modified_chunks[chunk_num]
                console.print(f"[cyan]Current text:[/cyan]\n{chunk.text}\n")
                new_text = typer.prompt("New text (or press Enter to cancel)")
                if new_text:
                    chunk.text = new_text
                    console.print(f"[green]Updated chunk {chunk_num + 1}[/green]")
            else:
                console.print("[red]Invalid chunk number[/red]")
        
        elif choice == 'D':
            break
    
    return modified_chunks
```

---

## 4. Cost Transparency & Reporting

### Cost Display

```python
class VerificationCostReport:
    """Track verification decisions and their cost impact."""
    
    def __init__(self):
        self.confirmed = []
        self.rejected = []
        self.token_counter = TokenCounter()
    
    def add_confirmed(self, job: ProcessedJob):
        """Track confirmed job."""
        self.confirmed.append({
            'job_id': job.job_id,
            'company': job.company,
            'tokens': job.processed_tokens,
            'cost': self.token_counter.estimate_cost(job.processed_tokens),
        })
    
    def add_rejected(self, job: ProcessedJob, reason: str = "User rejected"):
        """Track rejected job."""
        saved_cost = self.token_counter.estimate_cost(job.processed_tokens)
        self.rejected.append({
            'job_id': job.job_id,
            'company': job.company,
            'tokens': job.processed_tokens,
            'saved_cost': saved_cost,
            'reason': reason,
        })
    
    def print_summary(self):
        """Display verification summary with cost impact."""
        console = Console()
        
        total_confirmed = sum(j['cost'] for j in self.confirmed)
        total_saved = sum(j['saved_cost'] for j in self.rejected)
        total_would_have_cost = total_confirmed + total_saved
        
        table = Table(title="Verification Cost Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Cost", justify="right", style="yellow")
        
        table.add_row(
            "Confirmed (will send to LLM)",
            str(len(self.confirmed)),
            str(sum(j['tokens'] for j in self.confirmed)),
            f"${total_confirmed:.4f}"
        )
        table.add_row(
            "Rejected (saved from LLM)",
            str(len(self.rejected)),
            str(sum(j['tokens'] for j in self.rejected)),
            f"${total_saved:.4f} saved"
        )
        table.add_row(
            "[bold]Total (hypothetical all sent)[/bold]",
            str(len(self.confirmed) + len(self.rejected)),
            str(sum(j['tokens'] for j in self.confirmed + self.rejected)),
            f"[bold yellow]${total_would_have_cost:.4f}[/bold yellow]"
        )
        table.add_row(
            "[bold]Actual cost (only confirmed)[/bold]",
            "[dim]—[/dim]",
            "[dim]—[/dim]",
            f"[bold green]${total_confirmed:.4f}[/bold green]"
        )
        
        console.print(table)
        
        if self.rejected:
            console.print(f"\n[bold green]💰 Cost savings from rejection: ${total_saved:.4f}[/bold green]")
            console.print(f"[dim]({len(self.rejected)} jobs prevented from going to LLM)[/dim]")

def print_verification_stats(confirmed: List[VerificationResult], rejected: List[VerificationResult]):
    """Print verification workflow statistics."""
    console = Console()
    
    total = len(confirmed) + len(rejected)
    acceptance_rate = len(confirmed) / total * 100 if total > 0 else 0
    
    console.print(f"\n[bold cyan]═══ Verification Statistics ═══[/bold cyan]")
    console.print(f"✅ Confirmed: {len(confirmed)} ({acceptance_rate:.1f}%)")
    console.print(f"❌ Rejected: {len(rejected)} ({100-acceptance_rate:.1f}%)")
    console.print(f"📊 Total processed: {total}")
    
    # Rejection reasons
    if rejected:
        console.print(f"\n[dim]Top rejection reasons:[/dim]")
        from collections import Counter
        reasons = Counter(r.reason for r in rejected)
        for reason, count in reasons.most_common(3):
            console.print(f"  • {reason}: {count}")
```

---

## 5. Batch Operations & Shortcuts

### Batch Verification (Advanced)

```python
@app.command()
def verify_batch(
    input_dir: str = typer.Argument(..., help="Directory of preprocessed jobs"),
    approval_threshold: float = typer.Option(
        0.0,
        "--threshold",
        "-t",
        help="Auto-approve jobs with >X% confidence"
    ),
):
    """
    Batch verification with auto-approval rules.
    
    Use cases:
    - Auto-approve jobs with high extraction confidence
    - Approve all jobs from trusted companies
    - Reject obvious spam patterns
    """
    # Implementation: Apply rules without user interaction
    pass

@app.command()
def verify_company(
    company_name: str = typer.Argument(..., help="Company to verify jobs for"),
    approval_mode: str = typer.Option(
        "interactive",
        "--mode",
        help="interactive, auto_approve, or auto_reject"
    ),
):
    """Verify all jobs from a single company."""
    # Implementation: Filter by company, run verification
    pass

@app.command()
def verify_resume_session(
    session_file: str = typer.Argument(..., help="Saved verification session"),
):
    """Resume interrupted verification session."""
    # Implementation: Load checkpoint, continue from last job
    pass
```

---

## 6. Testing Strategy

### Unit Tests: Display & Formatting

```python
import pytest
from rich.console import Console
from io import StringIO

def test_display_chunks():
    chunks = [
        ProcessedChunk(
            text="Senior Software Engineer role",
            chunk_type="title",
            token_count=5,
            sentence_count=1,
            chunk_index=0,
            total_chunks=3,
        ),
        ProcessedChunk(
            text="Must have 5+ years Python experience.",
            chunk_type="requirements",
            token_count=9,
            sentence_count=1,
            chunk_index=1,
            total_chunks=3,
        ),
    ]
    
    # Capture output
    output = StringIO()
    console = Console(file=output, force_terminal=True)
    
    # Display shouldn't error
    display_chunks(chunks)
    
    # Verify output contains chunk content
    assert "Senior Software Engineer" in output.getvalue()

def test_cost_transparency():
    job = ProcessedJob(
        job_id="test-1",
        company="TestCorp",
        title="Engineer",
        original_tokens=5000,
        processed_tokens=500,
        chunks=[],
    )
    
    report = VerificationCostReport()
    report.add_confirmed(job)
    
    # Verify cost calculation
    cost = report.confirmed[0]['cost']
    assert cost > 0
    assert cost < 0.01  # Should be < 1 cent for 500 tokens

def test_cost_savings_from_rejection():
    job = ProcessedJob(
        job_id="test-1",
        company="TestCorp",
        title="Engineer",
        original_tokens=5000,
        processed_tokens=500,
        chunks=[],
    )
    
    report = VerificationCostReport()
    report.add_rejected(job, "Spam")
    
    saved = report.rejected[0]['saved_cost']
    assert saved > 0
```

### Integration Tests: User Interaction

```python
def test_verify_workflow_confirm(monkeypatch):
    """Test confirm workflow."""
    # Mock user input: Approve
    responses = iter(['A'])  # Approve
    monkeypatch.setattr('typer.prompt', lambda *args, **kwargs: next(responses))
    
    job = create_test_job()
    decision = prompt_user_decision(job)
    
    assert decision == 'approve'

def test_verify_workflow_reject(monkeypatch):
    """Test reject workflow."""
    responses = iter(['R', 'Spam job'])  # Reject, reason
    monkeypatch.setattr('typer.prompt', lambda *args, **kwargs: next(responses))
    
    job = create_test_job()
    decision = prompt_user_decision(job)
    
    assert decision == 'reject'

def test_verify_workflow_edit(monkeypatch):
    """Test edit workflow."""
    responses = iter(['E'])  # Edit
    monkeypatch.setattr('typer.prompt', lambda *args, **kwargs: next(responses))
    
    job = create_test_job()
    decision = prompt_user_decision(job)
    
    assert decision == 'edit'
```

---

## 7. Deployment Checklist

Before ASSESS phase:

- [ ] **Rich library installed**: `pip show rich` or in dependencies
- [ ] **Typer CLI tested**: `uv run python main.py verify --help` shows menu
- [ ] **Cost calculations verified**: Compare manual vs automated cost estimates
- [ ] **Display formatting**: Run on sample data, verify readability
- [ ] **User interaction tested**: Test all paths (approve, reject, edit, skip)
- [ ] **Batch operations**: Test resume, company filters
- [ ] **Output files created**: Verify JSON structure matches ASSESS input
- [ ] **Performance acceptable**: 100+ jobs verified in < 5 minutes
- [ ] **Error handling**: Test with malformed chunks, invalid JSON, large files

---

## 8. Integration with Prior & Next Phases

### Input from PREPROCESS

```python
# PREPROCESS produces:
preprocessed_jobs = [
    ProcessedJob(
        job_id="job-123",
        company="TechCorp",
        title="Senior Engineer",
        original_tokens=6000,
        processed_tokens=600,
        chunks=[
            ProcessedChunk(...),  # title
            ProcessedChunk(...),  # description
            ProcessedChunk(...),  # requirements
        ]
    ),
    # ... more jobs
]
```

### Output to ASSESS

```python
# VERIFY produces:
verified_jobs = [
    VerificationResult(
        job_id="job-123",
        company="TechCorp",
        title="Senior Engineer",
        status="confirmed",
        confirmed_chunks=[...],  # Ready for Claude
        timestamp="2026-05-18T16:00:00Z"
    ),
    # ... more verified jobs
]

# ASSESS phase reads confirmed_chunks and sends to Claude API
```

---

## 9. Common Verification Patterns

### Pattern 1: High-Confidence Auto-Approval

For jobs with obvious structure:

```python
def should_auto_approve(job: ProcessedJob) -> bool:
    """Heuristic: auto-approve well-formed jobs."""
    # Has title chunk
    has_title = any(c.chunk_type == 'title' for c in job.chunks)
    
    # Has requirements chunk
    has_requirements = any(c.chunk_type == 'requirements' for c in job.chunks)
    
    # Reasonable token count (not garbage)
    reasonable_size = 100 < job.processed_tokens < 10000
    
    return has_title and has_requirements and reasonable_size
```

### Pattern 2: Spam Detection

```python
def detect_spam(job: ProcessedJob) -> Optional[str]:
    """Detect obvious spam/low-quality jobs."""
    if job.processed_tokens < 50:
        return "Too short (< 50 tokens)"
    
    if job.title and len(job.title.split()) > 20:
        return "Title too long (>20 words)"
    
    if not any(c.chunk_type in ['requirements', 'description'] for c in job.chunks):
        return "No actual job content"
    
    return None
```

### Pattern 3: Company-Specific Rules

```python
TRUSTED_COMPANIES = ['Google', 'Meta', 'Microsoft', 'Amazon']  # Auto-approve
SUSPICIOUS_COMPANIES = ['MLM', 'Crypto Scam']  # Auto-reject

def apply_company_rules(job: ProcessedJob) -> Optional[str]:
    """Return action (approve, reject) or None for user choice."""
    if job.company in TRUSTED_COMPANIES:
        return "approve"  # Auto-approve trusted companies
    
    if any(sus in job.company for sus in SUSPICIOUS_COMPANIES):
        return "reject"  # Auto-reject suspicious
    
    return None  # Ask user
```

---

## 10. Next Steps

After VERIFY phase completes:

1. **ASSESS**: Send confirmed chunks to Claude API for job-CV matching
2. **STORAGE**: Save verification decisions and LLM results
3. **EXPORT**: Generate markdown reports with verified + assessed jobs

See `docs/README.md` for phase navigation.

---

## Performance Expectations

- **User decision time per job**: 5-30 seconds (depends on job complexity)
- **Throughput**: 10-20 jobs/hour with active user reviewing
- **Cost per verified job**: $0 (no LLM cost until ASSESS)
- **Acceptance rate typical**: 70-90% (10-30% filtered as low quality)
