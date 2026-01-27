"""Database module for job-agent application."""

from src.database.session import Base, SessionLocal, db_session, engine, with_db_session, get_connection_string
from src.database.repository import (
    GenericRepository,
    save_job_search_from_context,
    save_job_postings_from_context,
    save_matched_jobs_from_context,
    update_job_search_stats_from_context,
    load_user_profile_from_context,
    save_user_profile_from_context,
    find_job_posting_by_screening_output,
)
from src.database.models import JobSearch, JobPosting, MatchedJob, UserProfile

__all__ = [
    "Base",
    "SessionLocal",
    "db_session",
    "engine",
    "with_db_session",
    "get_connection_string",
    "GenericRepository",
    "JobSearch",
    "JobPosting",
    "MatchedJob",
    "UserProfile",
    "save_job_search_from_context",
    "save_job_postings_from_context",
    "save_matched_jobs_from_context",
    "update_job_search_stats_from_context",
    "load_user_profile_from_context",
    "save_user_profile_from_context",
    "find_job_posting_by_screening_output",
]
