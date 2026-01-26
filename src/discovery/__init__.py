"""Discovery module for job search."""

from .serpapi_service import SerpApiJobsService
from .serpapi_models import (
    SerpApiJobsResponse,
    JobResult,
    SearchMetadata,
    SearchParameters,
    Filter,
    FilterOption,
    DetectedExtensions,
    JobHighlight,
    ApplyOption,
    SerpApiPagination,
)

__all__ = [
    "SerpApiJobsService",
    "SerpApiJobsResponse",
    "JobResult",
    "SearchMetadata",
    "SearchParameters",
    "Filter",
    "FilterOption",
    "DetectedExtensions",
    "JobHighlight",
    "ApplyOption",
    "SerpApiPagination",
]
