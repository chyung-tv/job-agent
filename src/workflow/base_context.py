"""Base context classes for workflow state management."""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from src.discovery.serpapi_models import JobResult
from src.matcher.matcher import JobScreeningOutput
from src.config import DEFAULT_NUM_RESULTS, TESTING_MAX_SCREENING


class BaseContext(BaseModel):
    """Base context class for all workflows.

    Provides common fields and methods for state management across workflow nodes.
    """

    # Common fields
    run_id: Optional[UUID] = None
    errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def add_error(self, error: str) -> None:
        """Add an error message to the context.

        Args:
            error: Error message to add
        """
        self.errors.append(error)

    def has_errors(self) -> bool:
        """Check if context has any errors.

        Returns:
            True if there are any errors, False otherwise
        """
        return len(self.errors) > 0

    def validate(self) -> bool:
        """Base validation method. Override in subclasses.

        Returns:
            True if valid, False otherwise
        """
        return True


class JobSearchWorkflowContext(BaseContext):
    """Context for job search workflow.

    Carries all state through the job search pipeline from discovery
    through matching, research, fabrication, and delivery.
    """

    # ========== Input Parameters ==========
    query: str
    location: str
    num_results: int = DEFAULT_NUM_RESULTS
    max_screening: int = TESTING_MAX_SCREENING
    profile_id: Optional[UUID] = None
    google_domain: str = "google.com"
    hl: str = "en"
    gl: str = "us"

    # ========== Discovery Step Output ==========
    jobs: List[JobResult] = Field(default_factory=list)
    job_search_id: Optional[UUID] = None

    # ========== Profile Retrieval Output ==========
    user_profile: Optional[str] = None
    profile_was_cached: bool = False

    # ========== Matching Step Output ==========
    matched_results: List[JobScreeningOutput] = Field(default_factory=list)
    all_screening_results: List[JobScreeningOutput] = Field(default_factory=list)

    def get_summary(self) -> dict:
        """Get a summary of the workflow state.

        Returns:
            Dictionary with summary statistics
        """
        return {
            "query": self.query,
            "location": self.location,
            "jobs_found": len(self.jobs),
            "jobs_screened": len(self.all_screening_results),
            "matches_found": len(self.matched_results),
            "profile_cached": self.profile_was_cached,
            "has_errors": self.has_errors(),
        }

    def validate(self) -> bool:
        """Validate that context has required fields.

        Returns:
            True if valid, False otherwise (errors added to context)
        """
        if not self.query or not self.query.strip():
            self.add_error("Query is required")
            return False
        if not self.location or not self.location.strip():
            self.add_error("Location is required")
            return False
        if not self.profile_id:
            self.add_error("profile_id is required to retrieve user profile")
            return False
        return True
