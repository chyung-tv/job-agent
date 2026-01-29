"""Central configuration for workflow constants and limits.

This module contains all configurable constants used throughout the workflow system.
Centralizing these values makes it easy to adjust limits and defaults without
searching through multiple files.
"""

# Job Search Workflow Limits (for API cost control)
DEFAULT_NUM_RESULTS = 10  # Default number of job results to fetch
DEFAULT_MAX_SCREENING = 5  # Default max jobs to screen/match (production)
TESTING_MAX_SCREENING = 3  # Testing limit - reduces Gemini API calls during development

# Discovery Settings
RESULTS_PER_PAGE = 10  # SerpAPI results per page (API limitation)

# Retry Settings
DEFAULT_MAX_RETRIES = 3  # Default retry attempts for research/fabrication nodes

# CV Processing Settings
DOWNLOAD_TIMEOUT_SEC = 30  # PDF download timeout in seconds
DOWNLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10MB max PDF size

# Profiling Settings
DEFAULT_NUM_JOB_TITLES = 3  # Default number of job titles to suggest in profiling
