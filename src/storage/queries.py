"""SQL queries module (legacy).

This module is deprecated. Query functionality has been consolidated into
JobStore and AssessmentStore classes. Keeping this file for backward compatibility
with legacy imports, but all query classes have been removed.

See: src/storage/job_store.py and src/storage/assessment_store.py for current API.
"""

import warnings


class JobQueries:
    """Deprecated: Use JobStore instead.

    This class is kept for backward compatibility only. All functionality
    has been moved to src.storage.job_store.JobStore.
    """

    def __init__(self):
        warnings.warn(
            "JobQueries is deprecated. Use src.storage.job_store.JobStore instead.",
            DeprecationWarning,
            stacklevel=2,
        )


class CostQueries:
    """Deprecated: Use JobStore instead.

    This class is kept for backward compatibility only. All functionality
    has been moved to src.storage.job_store.JobStore.
    """

    def __init__(self):
        warnings.warn(
            "CostQueries is deprecated. Use src.storage.job_store.JobStore instead.",
            DeprecationWarning,
            stacklevel=2,
        )


class AssessmentQueries:
    """Deprecated: Use AssessmentStore instead.

    This class is kept for backward compatibility only. All functionality
    has been moved to src.storage.assessment_store.AssessmentStore.
    """

    def __init__(self):
        warnings.warn(
            "AssessmentQueries is deprecated. Use src.storage.assessment_store.AssessmentStore instead.",
            DeprecationWarning,
            stacklevel=2,
        )
