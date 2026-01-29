"""Utility functions for Celery tasks."""

import logging
from datetime import datetime
from uuid import UUID

from src.database import db_session
from src.database.models import WorkflowExecution

logger = logging.getLogger(__name__)


def update_execution_status(
    execution_id: str,
    status: str,
    current_node: str = None,
    error_message: str = None,
    context_snapshot: dict = None,
) -> None:
    """Update workflow execution status in database.

    Args:
        execution_id: UUID string of the workflow execution
        status: New status (pending, processing, completed, failed)
        current_node: Name of current node being executed
        error_message: Error message if status is failed
        context_snapshot: Updated context snapshot
    """
    session_gen = db_session()
    session = next(session_gen)
    try:
        execution = (
            session.query(WorkflowExecution)
            .filter(WorkflowExecution.id == UUID(execution_id))
            .first()
        )

        if execution:
            execution.status = status
            if current_node:
                execution.current_node = current_node
            if error_message:
                execution.error_message = error_message
            if context_snapshot:
                execution.context_snapshot = context_snapshot

            # Update timestamps
            if status == "processing" and not execution.started_at:
                execution.started_at = datetime.utcnow()
            if status in ["completed", "failed"]:
                execution.completed_at = datetime.utcnow()

            execution.updated_at = datetime.utcnow()
            session.commit()
            logger.info(f"Updated execution {execution_id} status to {status}")
        else:
            logger.warning(f"Execution {execution_id} not found")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update execution status: {e}", exc_info=True)
        raise
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass
