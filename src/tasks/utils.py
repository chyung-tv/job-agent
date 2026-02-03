"""Utility functions for Celery tasks."""

import logging
from datetime import datetime
from uuid import UUID

from src.database import db_session
from src.database.models import Run
from src.workflow.status_publisher import publish_run_status

logger = logging.getLogger(__name__)


def update_run_status(
    run_id: str,
    status: str,
    error_message: str = None,
) -> None:
    """Update run status in database.

    Args:
        run_id: UUID string of the run
        status: New status (pending, processing, completed, failed)
        error_message: Error message if status is failed
    """
    session_gen = db_session()
    session = next(session_gen)
    try:
        run = session.query(Run).filter(Run.id == UUID(run_id)).first()

        if run:
            run.status = status
            if error_message:
                run.error_message = error_message
            if status == "completed" or status == "failed":
                run.completed_at = datetime.utcnow()
            run.updated_at = datetime.utcnow()
            session.commit()
            logger.info(f"Updated run {run_id} status to {status}")

            completed_at_iso = None
            if status in ("completed", "failed"):
                completed_at_iso = (
                    run.completed_at.isoformat() + "Z"
                    if run.completed_at
                    else datetime.utcnow().isoformat() + "Z"
                )
            publish_run_status(
                run_id,
                status,
                error_message=error_message,
                completed_at=completed_at_iso,
            )
        else:
            logger.warning(f"Run {run_id} not found")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update run status: {e}", exc_info=True)
        raise
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass
