"""Central configuration for workflow constants and limits.

This module contains all configurable constants used throughout the workflow system.
Centralizing these values makes it easy to adjust limits and defaults without
searching through multiple files.
"""

import os
from dataclasses import dataclass


@dataclass
class LangfuseConfig:
    """Langfuse observability configuration."""

    enabled: bool = True
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"

    @classmethod
    def from_env(cls) -> "LangfuseConfig":
        """Load configuration from environment variables."""
        public_key = (os.getenv("LANGFUSE_PUBLIC_KEY") or "").strip()
        secret_key = (os.getenv("LANGFUSE_SECRET_KEY") or "").strip()
        host = (os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").strip()
        enabled_str = (os.getenv("LANGFUSE_ENABLED") or "true").strip().lower()
        enabled = enabled_str == "true" and bool(public_key and secret_key)
        return cls(
            enabled=enabled,
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )


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

# Static API key for protected routes. Copy this value into your .env as API_KEY for local/testing.
JOB_LAND_API_KEY = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def get_api_key() -> str:
    """Return the static API key (required for protected routes)."""
    return JOB_LAND_API_KEY
