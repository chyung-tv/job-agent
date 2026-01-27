"""Workflow context object for carrying state through the pipeline."""

from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path
import uuid
from datetime import datetime

from src.discovery.serpapi_models import JobResult
from src.matcher.matcher import JobScreeningOutput


@dataclass
class WorkflowContext:
    """Context object carrying all workflow state through the pipeline.
    
    This implements the "Bucket of Water" pattern where a single object
    carries all context needed by multiple steps in a workflow, eliminating
    long parameter lists and improving modularity.
    
    Example:
        context = WorkflowContext(query="software engineer", location="Hong Kong")
        context = discovery_step(context)
        context = profiling_step(context)
        context = matching_step(context)
        return context.matched_results
    """
    
    # ========== Input Parameters ==========
    query: str
    location: str
    num_results: int = 30
    max_screening: int = 5
    pdf_paths: Optional[List[Path]] = None
    data_dir: Optional[Path] = None
    google_domain: str = "google.com"
    hl: str = "en"
    gl: str = "us"
    
    # ========== Discovery Step Output ==========
    jobs: List[JobResult] = field(default_factory=list)
    job_search_id: Optional[uuid.UUID] = None
    
    # ========== Profiling Step Output ==========
    user_profile: Optional[str] = None
    profile_was_cached: bool = False
    profile_name: Optional[str] = None
    profile_email: Optional[str] = None
    
    # ========== Matching Step Output ==========
    matched_results: List[JobScreeningOutput] = field(default_factory=list)
    all_screening_results: List[JobScreeningOutput] = field(default_factory=list)
    
    # ========== Metadata ==========
    created_at: datetime = field(default_factory=datetime.utcnow)
    errors: List[str] = field(default_factory=list)
    
    # ========== Helper Methods ==========
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
    
    def validate_for_discovery(self) -> bool:
        """Validate that context has required fields for discovery step.
        
        Returns:
            True if valid, False otherwise (errors added to context)
        """
        if not self.query or not self.query.strip():
            self.add_error("Query is required for discovery step")
            return False
        if not self.location or not self.location.strip():
            self.add_error("Location is required for discovery step")
            return False
        return True
    
    def validate_for_profiling(self) -> bool:
        """Validate that context has required fields for profiling step.
        
        Returns:
            True if valid, False otherwise (errors added to context)
        """
        if not self.pdf_paths and not self.data_dir:
            self.add_error("Either pdf_paths or data_dir is required for profiling step")
            return False
        return True
    
    def validate_for_matching(self) -> bool:
        """Validate that context has required fields for matching step.
        
        Returns:
            True if valid, False otherwise (errors added to context)
        """
        if not self.user_profile:
            self.add_error("User profile is required for matching step")
            return False
        if not self.jobs:
            self.add_error("Jobs list is required for matching step")
            return False
        return True
