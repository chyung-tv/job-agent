"""Fabrication node for generating cover letters and CVs for matched jobs."""

import uuid
from typing import Dict
import logging

from sqlalchemy.orm import Session

from src.workflow.base_node import BaseNode
from src.workflow.base_context import JobSearchWorkflowContext
from src.database import db_session, GenericRepository, MatchedJob
from src.fabrication.fab_cover_letter import fabricate_matched_jobs_for_run
from src.config import DEFAULT_MAX_RETRIES
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class FabricationNode(BaseNode):
    """Node for fabricating cover letters and CVs for matched jobs."""

    def __init__(
        self,
        model: str = "google-gla:gemini-2.5-flash",
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        """Initialize the fabrication node.

        Args:
            model: AI model to use for generation
            max_retries: Maximum number of retry attempts
        """
        super().__init__()
        self.model = model
        self.max_retries = max_retries

    def _validate_context(self, context: JobSearchWorkflowContext) -> bool:
        """Validate required context fields for fabrication.

        Args:
            context: The workflow context

        Returns:
            True if valid, False otherwise
        """
        if not context.run_id:
            context.add_error("Run ID is required for fabrication step")
            return False
        return True

    def _load_data(self, context: JobSearchWorkflowContext, session: Session) -> None:
        """Load matched jobs with completed research.

        Args:
            context: The workflow context
            session: Database session
        """
        # Matched jobs will be loaded in run() method
        pass

    def _persist_data(
        self, context: JobSearchWorkflowContext, session: Session
    ) -> None:
        """Persist fabrication results (handled by fabricate_matched_jobs_for_run).

        Args:
            context: The workflow context
            session: Database session
        """
        # Persistence is handled by fabricate_matched_jobs_for_run
        pass

    async def _execute(
        self, context: JobSearchWorkflowContext
    ) -> JobSearchWorkflowContext:
        """Fabricate cover letters and CVs for matched jobs.

        Args:
            context: The workflow context with run_id

        Returns:
            Updated context
        """
        self.logger.info("Starting fabrication node")

        # Validate context
        if not self._validate_context(context):
            self.logger.error("Context validation failed")
            return context

        # Use existing fabrication function
        session_gen = self._get_db_session()
        session = next(session_gen)
        try:
            fabrication_results = await fabricate_matched_jobs_for_run(
                session=session,
                run_id=str(context.run_id),
                model=self.model,
                max_retries=self.max_retries,
            )
            self.logger.info(
                f"Fabrication completed: {fabrication_results['successful']} successful, {fabrication_results['failed']} failed"
            )
        except Exception as e:
            self.logger.error(f"Failed to fabricate cover letters: {e}")
            context.add_error(f"Failed to fabricate cover letters: {e}")
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass

        self.logger.info("Fabrication node completed")
        return context
