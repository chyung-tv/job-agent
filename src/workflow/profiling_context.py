"""Context classes for profiling workflow."""

from typing import Optional, List, Union
from uuid import UUID
from pydantic import Field, field_serializer

from src.workflow.base_context import BaseContext


class ProfilingWorkflowContext(BaseContext):
    """Context for profiling workflow.

    Carries state through the profiling pipeline from user input
    through CV processing to final profile creation.
    """

    # ========== Input Parameters ==========
    name: str
    email: str
    location: str = Field(
        ..., description="Preferred job search location (e.g., 'Hong Kong')"
    )
    basic_info: Optional[str] = Field(
        default=None, description="Basic information about the user (optional)"
    )
    cv_urls: List[str] = Field(..., description="List of URLs to CV/PDF documents")

    # ========== Processing Output ==========
    raw_cv_text: Optional[str] = None

    # ========== Final Output ==========
    user_profile: Optional[str] = None
    # Set by CVProcessingNode from User.id; Better Auth uses string ids (not necessarily UUID).
    user_id: Optional[Union[UUID, str]] = None
    references: Optional[dict] = None
    suggested_job_titles: Optional[List[str]] = Field(
        default=None,
        description="List of AI-suggested job titles for this profile",
    )

    @field_serializer("user_id")
    def _serialize_user_id(self, value: Optional[Union[UUID, str]]) -> Optional[str]:
        """Serialize user_id to string for JSON (DB and Better Auth use string ids)."""
        if value is None:
            return None
        return str(value)

    def validate(self) -> bool:
        """Validate that context has required fields.

        Returns:
            True if valid, False otherwise (errors added to context)
        """
        if not self.name or not self.name.strip():
            self.add_error("Name is required")
            return False
        if not self.email or not self.email.strip():
            self.add_error("Email is required")
            return False
        if not self.location or not self.location.strip():
            self.add_error("Location is required")
            return False
        if not self.cv_urls or len(self.cv_urls) == 0:
            self.add_error("At least one CV URL is required")
            return False
        for url in self.cv_urls:
            u = (url or "").strip()
            if not u:
                self.add_error("CV URL cannot be empty")
                return False
            if not (u.startswith("http://") or u.startswith("https://")):
                self.add_error(f"CV URL must be http or https: {u[:50]}...")
                return False
        return True
