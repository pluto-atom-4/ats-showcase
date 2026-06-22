# Issue: Missing `.env` File Loading in CLI Entry Point

## Problem Statement

The `.env` file is not being loaded by the CLI application, causing the `ANTHROPIC_API_KEY` environment variable to be unavailable downstream when `LLMProvider()` is initialized. This results in the following error:

```
❌ LLM setup failed: ANTHROPIC_API_KEY not set and api_key not provided
   Set ANTHROPIC_API_KEY environment variable
```

### Evidence from Assessment Log

From `assess.log`:
```
📄 Loaded CV from: data/cv.json

❌ LLM setup failed: ANTHROPIC_API_KEY not set and api_key not provided
   Set ANTHROPIC_API_KEY environment variable
Workflow failed: 1
...
ValueError: ANTHROPIC_API_KEY not set and api_key not provided
```

## Root Cause Analysis

### Current State

1. **CLI Entry Point** (`src/cli.py`):
   - No `.env` loading mechanism in `main()` function (lines 1241-1243)
   - Directly calls `app()` from Typer without environment initialization
   - Passes through to Typer app with no environment pre-loading

2. **LLM Provider** (`src/llm/provider.py`, line 84):
   - Reads from environment: `self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")`
   - No fallback to load `.env` if variable isn't set
   - Raises `ValueError` if `ANTHROPIC_API_KEY` is missing

3. **Environment Setup**:
   - `.env` file exists with configuration (`ANTHROPIC_API_KEY`, `DATABASE_PATH`, `SPACY_MODEL`, etc.)
   - `.env.example` exists as template
   - **But `.env` is never loaded** when CLI runs

4. **Python Search Path**:
   - `python -m src.cli --all ...` requires `PYTHONPATH` or proper module setup
   - Current setup uses `pyproject.toml` with entry point: `ats-cli = "src.cli:main"`
   - Running via `python -m` or `uv run python -m src.cli` doesn't trigger `.env` loading

## Impact

- **Users cannot run the CLI workflow** without manually exporting `ANTHROPIC_API_KEY` to their shell
- **Inconsistent with documentation** (README suggests `.env` file is sufficient)
- **Breaks reproducibility** across environments and sessions
- **Defeats purpose of `.env` file** in development and deployment

## Solution Required

Add `.env` file loading to the CLI entry point using `python-dotenv`:

### Changes Needed

1. **Install `python-dotenv`** (if not already installed):
   ```bash
   uv pip install python-dotenv
   # or add to pyproject.toml dependencies
   ```

2. **Update `src/cli.py` main function** (lines 1241-1243):
   ```python
   from dotenv import load_dotenv

   def main() -> None:
       """Main entry point."""
       load_dotenv()  # Load .env file before Typer app
       app()
   ```

3. **Optional: Add to Typer callback** for more explicit control:
   ```python
   @app.callback()
   def init_env():
       """Initialize environment from .env file."""
       load_dotenv()
   ```

## Affected Workflows

- ✅ `uv run python -m src.cli --all --cv data/cv.json --config config/companies.json`
- ✅ `uv run python -m src.cli assess --cv data/cv.json`
- ✅ `ats-cli --all --cv data/cv.json --config config/companies.json` (via entry point)
- ✅ All other CLI commands that require downstream access to environment variables

## Success Criteria

- [ ] `ANTHROPIC_API_KEY` loaded from `.env` file automatically on CLI startup
- [ ] No change required to user environment variables when `.env` file exists
- [ ] Error message clearly indicates if `.env` is missing or `ANTHROPIC_API_KEY` not set
- [ ] `python-dotenv` dependency added to `pyproject.toml`
- [ ] Documentation updated to reflect automatic `.env` loading
- [ ] All existing tests pass
- [ ] Workflow can complete without manual `export ANTHROPIC_API_KEY=...`

## Testing

```bash
# Current failure scenario (reproduces the issue)
cd /path/to/ats-playground
uv run python -m src.cli --all --cv data/cv.json --config config/companies.json
# Result: ANTHROPIC_API_KEY not set error

# Expected after fix
uv run python -m src.cli --all --cv data/cv.json --config config/companies.json
# Result: Workflow proceeds, uses ANTHROPIC_API_KEY from .env
```

## Related Files

- `src/cli.py` - Main entry point (main function, lines 1241-1243)
- `src/llm/provider.py` - LLMProvider initialization (line 84)
- `pyproject.toml` - Entry point configuration
- `.env` - Configuration file (not loaded)
- `.env.example` - Template
- `assess.log` - Error evidence

## Priority

**High** - Blocks critical functionality (LLM assessment workflow)

## Notes

- `.env` file is already present and correctly configured
- The fix is a simple 1-2 line addition to the main entry point
- `python-dotenv` is a standard, zero-dependency library already in use by similar projects
- This aligns with Python development best practices (12-factor app pattern)
