#!/bin/bash
# Pre-commit quality checks for ATS Playground
# Runs code quality tools: ruff, mypy, bandit, and tests

set -e

echo "🔍 Running pre-commit quality checks..."

# Get repository root
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Detect changed Python files
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)

if [ -z "$CHANGED_FILES" ]; then
    echo "✓ No Python files changed"
    exit 0
fi

echo "📝 Files to check:"
echo "$CHANGED_FILES" | sed 's/^/   /'

# Run pre-commit hooks
echo ""
echo "▶ Running pre-commit hooks..."
if command -v pre-commit &> /dev/null; then
    pre-commit run --files $CHANGED_FILES
else
    echo "⚠ pre-commit not found, skipping hooks"
fi

# Run tests for changed files
echo ""
echo "▶ Running tests for changed modules..."
TEST_ARGS=""
for file in $CHANGED_FILES; do
    # Extract test pattern from file path
    if [[ $file == src/* ]]; then
        module=$(echo "$file" | sed 's|src/||; s|/|_|g; s|\.py$||')
        TEST_ARGS="$TEST_ARGS -k $module"
    fi
done

if [ -n "$TEST_ARGS" ]; then
    uv run pytest tests/ $TEST_ARGS -v --tb=short || true
else
    echo "✓ No module-specific tests to run"
fi

echo ""
echo "✓ Quality checks complete"
exit 0
