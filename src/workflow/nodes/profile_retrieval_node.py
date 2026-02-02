"""Profile retrieval node for loading user profile from database."""

from typing import Optional
import logging
from datetime import datetime

from src.workflow.base_node import BaseNode
from src.workflow.base_context import JobSearchWorkflowContext
from src.database import GenericRepository, User


class ProfileRetrievalNode(BaseNode):
    """Node for retrieving user profile from database.

    This node loads an existing user from the database using user_id,
    and updates the job search workflow context.
    """

    def _validate_context(self, context: JobSearchWorkflowContext) -> bool:
        """Validate required context fields for profile retrieval.

        Args:
            context: The workflow context

        Returns:
            True if valid, False otherwise
        """
        if not context.user_id:
            context.add_error("user_id is required to retrieve user profile")
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
            user_repo = GenericRepository(session, User)
            user = user_repo.get(str(context.user_id))

            if user:
                context.user_profile = user.profile_text
                context.profile_was_cached = True
                # Update last_used_at
                user.last_used_at = datetime.utcnow()
                user_repo.update(user)
                self.logger.info(f"Retrieved user profile (ID: {context.user_id})")
            else:
                context.add_error(
                    f"User not found for user_id: {context.user_id}. "
                    "Please create a profile first using ProfilingWorkflow."
                )
                self.logger.error(
                    f"User not found for user_id: {context.user_id}"
                )
        except Exception as e:
            self.logger.error(f"Failed to load profile from database: {e}")
            context.add_error(f"Failed to retrieve profile: {e}")

    async def _execute(
        self, context: JobSearchWorkflowContext
    ) -> JobSearchWorkflowContext:
        """Retrieve user profile from database.

        Args:
            context: The workflow context with user_id

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
