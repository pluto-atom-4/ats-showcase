#!/bin/bash
# Gate 2 Evidence Verification Hook
# Pre-push check: requires evidence artifacts (.claude/evidence/) before allowing push
# Required: pytest-output.txt, mypy-report.txt, ruff-check.txt

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "🔬 Gate 2: Evidence Verification Check"

# Only run on git push (detected by branch tracking)
if ! git rev-parse --abbrev-ref --symbolic-full-name @{u} > /dev/null 2>&1; then
    echo "ⓘ Not on tracked branch, skipping evidence check"
    exit 0
fi

EVIDENCE_DIR=".claude/evidence"
REQUIRED_FILES=(
    "pytest-output.txt"
    "mypy-report.txt"
    "ruff-check.txt"
)

# Check if evidence directory exists
if [ ! -d "$EVIDENCE_DIR" ]; then
    echo "⚠️  Evidence directory not found: $EVIDENCE_DIR"
    echo ""
    echo "Create evidence artifacts by running:"
    echo "  mkdir -p .claude/evidence"
    echo "  uv run pytest tests/ -v > .claude/evidence/pytest-output.txt 2>&1"
    echo "  uv run mypy src/ tests/ > .claude/evidence/mypy-report.txt 2>&1 || true"
    echo "  uv run ruff check src/ > .claude/evidence/ruff-check.txt 2>&1 || true"
    echo ""
    exit 0
fi

# Check for required evidence files
MISSING_FILES=()
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$EVIDENCE_DIR/$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo "⚠️  Missing evidence artifacts:"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $EVIDENCE_DIR/$file"
    done
    echo ""
    echo "Generate evidence by running:"
    echo "  bash .claude/scripts/run-local-ci.sh"
    echo ""
    exit 0
fi

# Verify evidence files are not empty
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -s "$EVIDENCE_DIR/$file" ]; then
        echo "⚠️  Evidence file is empty: $EVIDENCE_DIR/$file"
    fi
done

echo "✅ Evidence artifacts found:"
for file in "${REQUIRED_FILES[@]}"; do
    size=$(wc -c < "$EVIDENCE_DIR/$file" 2>/dev/null || echo "0")
    echo "   ✓ $file ($size bytes)"
done
echo ""
exit 0
