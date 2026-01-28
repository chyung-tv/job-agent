"""Profile retrieval node for loading user profile from database."""

from typing import Optional
import logging
from datetime import datetime

from src.workflow.base_node import BaseNode
from src.workflow.base_context import JobSearchWorkflowContext
from src.database import GenericRepository, UserProfile


class ProfileRetrievalNode(BaseNode):
    """Node for retrieving user profile from database.
    
    This node loads an existing user profile from the database using
    profile_id, and updates the job search workflow context.
    """
    
    def _validate_context(self, context: JobSearchWorkflowContext) -> bool:
        """Validate required context fields for profile retrieval.
        
        Args:
            context: The workflow context
            
        Returns:
            True if valid, False otherwise
        """
        if not context.profile_id:
            context.add_error("profile_id is required to retrieve user profile")
            return False
        return True
    
    def _load_data(self, context: JobSearchWorkflowContext, session) -> None:
        """Load user profile from database.
        
        Args:
            context: The workflow context
            session: Database session
        """
        if not self._validate_context(context):
            return
        
        try:
            profile_repo = GenericRepository(session, UserProfile)
            profile = profile_repo.get(context.profile_id)
            
            if profile:
                context.user_profile = profile.profile_text
                context.profile_was_cached = True
                # Update last_used_at
                profile.last_used_at = datetime.utcnow()
                profile_repo.update(profile)
                self.logger.info(
                    f"Retrieved user profile (ID: {context.profile_id})"
                )
            else:
                context.add_error(
                    f"User profile not found for profile_id: {context.profile_id}. "
                    "Please create a profile first using ProfilingWorkflow."
                )
                self.logger.error(
                    f"Profile not found for profile_id: {context.profile_id}"
                )
        except Exception as e:
            self.logger.error(f"Failed to load profile from database: {e}")
            context.add_error(f"Failed to retrieve profile: {e}")
    
    async def run(self, context: JobSearchWorkflowContext) -> JobSearchWorkflowContext:
        """Retrieve user profile from database.
        
        Args:
            context: The workflow context with profile_id
            
        Returns:
            Updated context with profile information
        """
        self.logger.info("Starting profile retrieval")
        
        # Validate context
        if not self._validate_context(context):
            self.logger.error("Context validation failed")
            return context
        
        # Load profile from database
        session_gen = self._get_db_session()
        session = next(session_gen)
        try:
            self._load_data(context, session)
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Failed to retrieve profile: {e}")
            context.add_error(f"Failed to retrieve profile: {e}")
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass
        
        if context.user_profile:
            self.logger.info("Profile retrieved successfully")
        else:
            self.logger.warning("Profile retrieval completed but no profile was found")
        
        return context
