#!/bin/bash
# Enforce feature branch workflow: block commits directly to main

BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ "$BRANCH" = "main" ]; then
  echo "❌ Direct commits to main are not allowed."
  echo ""
  echo "Workflow:"
  echo "  1. Create feature branch: git checkout -b feat/issue-XXX-description"
  echo "  2. Commit changes: git commit -m '...'"
  echo "  3. Push branch: git push -u origin feat/issue-XXX-description"
  echo "  4. Create PR on GitHub"
  echo "  5. Merge via PR"
  echo ""
  exit 1
fi

exit 0
