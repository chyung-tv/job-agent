"""Context classes for profiling workflow."""

from typing import Optional, List
from pathlib import Path
from uuid import UUID
from pydantic import BaseModel, Field

from src.workflow.base_context import BaseContext


class ProfilingWorkflowContext(BaseContext):
    """Context for profiling workflow.
    
    Carries state through the profiling pipeline from user input
    through CV processing to final profile creation.
    """
    
    # ========== Input Parameters ==========
    name: str
    email: str
    basic_info: Optional[str] = Field(
        default=None,
        description="Basic information about the user (optional)"
    )
    pdf_paths: Optional[List[Path]] = None
    data_dir: Optional[Path] = None
    
    # ========== Processing Output ==========
    raw_cv_text: Optional[str] = None
    
    # ========== Final Output ==========
    user_profile: Optional[str] = None
    profile_id: Optional[UUID] = None
    references: Optional[dict] = None
    
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
        if not self.pdf_paths and not self.data_dir:
            self.add_error("Either pdf_paths or data_dir is required for CV processing")
            return False
        return True
