"""Completion node for detecting workflow completion."""

import uuid
import logging
from datetime import datetime
from typing import List, Dict

from sqlalchemy.orm import Session

from src.workflow.base_node import BaseNode
from src.workflow.base_context import JobSearchWorkflowContext
from src.database import db_session, Run, MatchedJob, JobPosting, CompanyResearch, Artifact
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class CompletionNode(BaseNode):
    """Node for checking if a workflow run is complete."""
    
    def _validate_context(self, context: JobSearchWorkflowContext) -> bool:
        """Validate required context fields for completion check.
        
        Args:
            context: The workflow context
            
        Returns:
            True if valid, False otherwise
        """
        if not context.run_id:
            context.add_error("Run ID is required for completion check")
            return False
        return True
    
    def _load_data(self, context: JobSearchWorkflowContext, session: Session) -> None:
        """Load run and matched jobs for completion check.
        
        Args:
            context: The workflow context
            session: Database session
        """
        # Data will be loaded in _check_run_completion
        pass
    
    def _persist_data(self, context: JobSearchWorkflowContext, session: Session) -> None:
        """Update run status if complete.
        
        Args:
            context: The workflow context
            session: Database session
        """
        # Persistence is handled by _check_run_completion
        pass
    
    def _check_run_completion(self, session: Session, run_id: str) -> bool:
        """Check if all matched jobs in a run have finished (completed or failed).
        
        Args:
            session: SQLAlchemy database session
            run_id: UUID of the run (as string)
        
        Returns:
            True if run is complete, False otherwise
        """
        run = session.query(Run).filter_by(id=uuid.UUID(run_id)).first()
        
        if not run:
            return False
        
        # Get all matched jobs for this run
        matched_jobs = session.query(MatchedJob).filter_by(run_id=uuid.UUID(run_id)).all()
        
        if not matched_jobs:
            # No matched jobs means run is not complete yet (or invalid)
            return False
        
        # Check if all matched jobs have finished research (completed or failed)
        all_research_finished = all(
            matched_job.research_status in ['completed', 'failed']
            for matched_job in matched_jobs
        )
        
        # Check if all matched jobs have finished fabrication (completed or failed)
        all_fabrication_finished = all(
            matched_job.fabrication_status in ['completed', 'failed']
            for matched_job in matched_jobs
        )
        
        # Run is complete if all jobs have finished both research and fabrication
        is_complete = all_research_finished and all_fabrication_finished
        
        if is_complete and run.status != "completed":
            # Update run status
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            session.commit()
        
        return is_complete
    
    async def run(self, context: JobSearchWorkflowContext) -> JobSearchWorkflowContext:
        """Check if workflow run is complete.
        
        Args:
            context: The workflow context with run_id
            
        Returns:
            Updated context
        """
        self.logger.info("Starting completion node")
        
        # Validate context
        if not self._validate_context(context):
            self.logger.error("Context validation failed")
            return context
        
        # Check completion
        session_gen = self._get_db_session()
        session = next(session_gen)
        try:
            is_complete = self._check_run_completion(session, str(context.run_id))
            if is_complete:
                self.logger.info("Run is complete")
            else:
                self.logger.info("Run is not yet complete")
        except Exception as e:
            self.logger.error(f"Failed to check run completion: {e}")
            context.add_error(f"Failed to check run completion: {e}")
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass
        
        self.logger.info("Completion node completed")
        return context


# Export functions for backward compatibility with tests
def check_run_completion(session: Session, run_id: str) -> bool:
    """Check if all matched jobs in a run have finished (completed or failed).
    
    This is a wrapper function for backward compatibility with tests.
    Use CompletionNode._check_run_completion() directly in new code.
    
    Args:
        session: SQLAlchemy database session
        run_id: UUID of the run (as string)
    
    Returns:
        True if run is complete, False otherwise
    """
    node = CompletionNode()
    return node._check_run_completion(session, run_id)
