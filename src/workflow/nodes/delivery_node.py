"""Delivery node for delivering completed application packages."""

import uuid
import logging
from datetime import datetime
from typing import List, Dict

from sqlalchemy.orm import Session

from src.workflow.base_node import BaseNode
from src.workflow.base_context import JobSearchWorkflowContext
from src.database import (
    db_session,
    Run,
    MatchedJob,
    JobPosting,
    CompanyResearch,
    Artifact,
    UserProfile,
)
from src.delivery.nylas_service import NylasService
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DeliveryNode(BaseNode):
    """Node for triggering delivery of completed application packages."""

    def _validate_context(self, context: JobSearchWorkflowContext) -> bool:
        """Validate required context fields for delivery.

        Args:
            context: The workflow context

        Returns:
            True if valid, False otherwise
        """
        if not context.run_id:
            context.add_error("Run ID is required for delivery")
            return False
        return True

    def _load_data(self, context: JobSearchWorkflowContext, session: Session) -> None:
        """Load run and completed items for delivery.

        Args:
            context: The workflow context
            session: Database session
        """
        # Data will be loaded in _get_completed_items_for_delivery
        pass

    def _persist_data(
        self, context: JobSearchWorkflowContext, session: Session
    ) -> None:
        """Update run delivery status.

        Args:
            context: The workflow context
            session: Database session
        """
        # Persistence is handled by _trigger_delivery
        pass

    def _get_completed_items_for_delivery(
        self, session: Session, run_id: str
    ) -> List[Dict]:
        """Get all successfully completed items (research + fabrication) for delivery.

        Args:
            session: SQLAlchemy database session
            run_id: UUID of the run (as string)

        Returns:
            List of dictionaries containing job details, research, and cover letter
            Only includes items where both research and fabrication are completed
        """
        # Get matched jobs with both research and fabrication completed
        matched_jobs = (
            session.query(MatchedJob)
            .filter_by(
                run_id=uuid.UUID(run_id),
                research_status="completed",
                fabrication_status="completed",
            )
            .all()
        )

        completed_items = []

        for matched_job in matched_jobs:
            # Get job posting
            job_posting = (
                session.query(JobPosting)
                .filter_by(id=matched_job.job_posting_id)
                .first()
            )

            if not job_posting:
                continue

            # Get company research
            company_research = (
                session.query(CompanyResearch)
                .filter_by(job_posting_id=matched_job.job_posting_id)
                .first()
            )

            # Get artifact (contains both cover letter and CV)
            artifact = (
                session.query(Artifact).filter_by(matched_job_id=matched_job.id).first()
            )

            if not artifact or not artifact.cover_letter:
                continue

            # Extract cover letter and CV from artifact
            cover_letter_data = artifact.cover_letter
            cv_pdf_url = artifact.cv.get("pdf_url") if artifact.cv else None

            completed_items.append(
                {
                    "matched_job_id": str(matched_job.id),
                    "job_posting_id": str(job_posting.id),
                    "job_title": job_posting.title,
                    "company_name": job_posting.company_name,
                    "location": job_posting.location,
                    "job_description": job_posting.description,
                    "match_reason": matched_job.reason,
                    "application_link": matched_job.application_link,
                    "apply_options": job_posting.apply_options
                    if job_posting.apply_options
                    else [],
                    "research": {
                        "id": str(company_research.id) if company_research else None,
                        "results": company_research.research_results
                        if company_research
                        else None,
                        "citations": company_research.citations
                        if company_research
                        else None,
                    },
                    "cover_letter": {
                        "id": str(artifact.id),
                        "topic": cover_letter_data.get("topic"),
                        "content": cover_letter_data.get("content"),
                    },
                    "cv": {
                        "pdf_url": cv_pdf_url,
                    },
                }
            )

        return completed_items

    def _trigger_delivery(self, session: Session, run_id: str) -> Dict[str, any]:
        """Trigger delivery for all successfully completed items in a run.

        Sends email via Nylas with all application packages.

        Args:
            session: SQLAlchemy database session
            run_id: UUID of the run (as string)

        Returns:
            Dictionary with delivery summary
        """
        self.logger.info("=" * 80)
        self.logger.info("DELIVERING...")
        self.logger.info("=" * 80)

        # Get completed items
        completed_items = self._get_completed_items_for_delivery(session, run_id)

        if not completed_items:
            self.logger.warning("No completed items found for delivery")
            self.logger.info(
                "All items must have both research and fabrication completed"
            )
            return {
                "run_id": run_id,
                "items_delivered": 0,
                "status": "no_items",
            }

        # Resolve recipient from run's profile owner (if run has user_profile_id)
        run = session.query(Run).filter_by(id=uuid.UUID(run_id)).first()
        recipient_email = None
        if run and getattr(run, "user_profile_id", None):
            profile = (
                session.query(UserProfile).filter_by(id=run.user_profile_id).first()
            )
            if profile:
                recipient_email = profile.email

        # Send email via Nylas
        try:
            nylas_service = NylasService()
            send_result = nylas_service.send_job_application_email(
                session=session,
                completed_items=completed_items,
                recipient_email=recipient_email,
            )

            if send_result.get("success"):
                self.logger.info(
                    f"Email sent successfully to {send_result.get('recipient')}"
                )
                self.logger.info(f"Message ID: {send_result.get('message_id')}")

                # Update run delivery status (run already loaded above)
                if run:
                    run.delivery_triggered = True
                    run.delivery_triggered_at = datetime.utcnow()
                    session.commit()

                return {
                    "run_id": run_id,
                    "items_delivered": send_result.get(
                        "items_sent", len(completed_items)
                    ),
                    "status": "delivered",
                    "recipient": send_result.get("recipient"),
                    "message_id": send_result.get("message_id"),
                }
            else:
                error_msg = send_result.get("error", "Unknown error")
                self.logger.error(f"Failed to send email: {error_msg}")
                return {
                    "run_id": run_id,
                    "items_delivered": 0,
                    "status": "failed",
                    "error": error_msg,
                }

        except Exception as e:
            self.logger.error(f"Failed to send email via Nylas: {e}", exc_info=True)
            return {
                "run_id": run_id,
                "items_delivered": 0,
                "status": "failed",
                "error": str(e),
            }

    async def _execute(
        self, context: JobSearchWorkflowContext
    ) -> JobSearchWorkflowContext:
        """Trigger delivery for completed items.

        Args:
            context: The workflow context with run_id

        Returns:
            Updated context
        """
        self.logger.info("Starting delivery node")

        # Validate context
        if not self._validate_context(context):
            self.logger.error("Context validation failed")
            return context

        # Trigger delivery
        session_gen = self._get_db_session()
        session = next(session_gen)
        try:
            delivery_result = self._trigger_delivery(session, str(context.run_id))
            self.logger.info(
                f"Delivery triggered: {delivery_result['items_delivered']} item(s) delivered"
            )
        except Exception as e:
            self.logger.error(f"Failed to trigger delivery: {e}")
            context.add_error(f"Failed to trigger delivery: {e}")
        finally:
            try:
                next(session_gen, None)
            except StopIteration:
                pass

        self.logger.info("Delivery node completed")
        return context


# Export functions for backward compatibility with tests
def get_completed_items_for_delivery(session: Session, run_id: str) -> List[Dict]:
    """Get all successfully completed items for delivery.

    This is a wrapper function for backward compatibility with tests.
    Use DeliveryNode._get_completed_items_for_delivery() directly in new code.

    Args:
        session: SQLAlchemy database session
        run_id: UUID of the run (as string)

    Returns:
        List of dictionaries containing job details, research, and cover letter
    """
    node = DeliveryNode()
    return node._get_completed_items_for_delivery(session, run_id)


def trigger_delivery(session: Session, run_id: str) -> Dict[str, any]:
    """Trigger delivery for all successfully completed items in a run.

    This is a wrapper function for backward compatibility with tests.
    Use DeliveryNode._trigger_delivery() directly in new code.

    Args:
        session: SQLAlchemy database session
        run_id: UUID of the run (as string)

    Returns:
        Dictionary with delivery summary
    """
    node = DeliveryNode()
    return node._trigger_delivery(session, run_id)
