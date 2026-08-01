"""NLP-based requirement extraction for job descriptions.

WARNING: This module is EXPERIMENTAL and NOT integrated into the production pipeline.

Status:
- Branch: feat/issue-XXX-requirement-filtering (experimental, not merged to main)
- Test coverage: 0% (prototypes only, not integrated to pytest suite)
- Type safety: 11 mypy --strict errors (unresolved)
- CLI integration: None (not exposed in CLI)
- Production validation: Unverified (prototype tests only)

Do not use in production workflows without resolving blockers documented in
.claude/experimental/EXPERIMENTAL.md.

For production-ready NLP features, use the assess phase with Claude API instead.
"""

import warnings

warnings.warn(
    "The src.nlp module is experimental and not production-ready. "
    "See .claude/experimental/EXPERIMENTAL.md for blockers and next steps.",
    category=FutureWarning,
    stacklevel=2,
)

from src.nlp.ner import JobNERExtractor  # noqa: E402

__all__ = ["JobNERExtractor"]
