"""Celery task for job search workflow."""

import asyncio
import logging
from typing import Dict, Any

from src.celery_app import celery_app
from src.workflow.job_search_workflow import JobSearchWorkflow
from src.workflow.base_context import JobSearchWorkflowContext
from src.tasks.utils import update_execution_status

# Configure logging to capture all workflow/node logs
# This ensures all Python loggers (including workflow nodes) are visible in Celery logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,  # Override any existing configuration
)

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async function in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, use nest_asyncio
            import nest_asyncio

            nest_asyncio.apply()
            return asyncio.run(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create a new one
        return asyncio.run(coro)


@celery_app.task(bind=True, name="job_search_workflow")
def execute_job_search_workflow(
    self,
    context_data: Dict[str, Any],
    execution_id: str = None,
) -> Dict[str, Any]:
    """Execute job search workflow as Celery task.

    Args:
        context_data: Serialized JobSearchWorkflowContext data
        execution_id: UUID string of the workflow execution record

    Returns:
        Serialized context with results
    """
    logger.info(
        f"Starting job search workflow task (execution_id: {execution_id}, task_id: {self.request.id})"
    )

    try:
        # Update status to processing
        if execution_id:
            update_execution_status(
                execution_id, "processing", current_node="JobSearchWorkflow"
            )

        # Reconstruct context from dict
        context = JobSearchWorkflowContext(**context_data)
        logger.info(
            f"Reconstructed context for query: '{context.query}' in {context.location}"
        )

        # Execute workflow (async)
        logger.info("Executing job search workflow...")
        workflow = JobSearchWorkflow()
        result = run_async(workflow.run(context))
        matches_count = len(result.matched_results) if result.matched_results else 0
        logger.info(
            f"Workflow execution completed. Has errors: {result.has_errors()}, Matches found: {matches_count}"
        )

        # Update status to completed
        if execution_id:
            final_status = "failed" if result.has_errors() else "completed"
            error_message = "; ".join(result.errors) if result.has_errors() else None
            update_execution_status(
                execution_id,
                final_status,
                error_message=error_message,
                context_snapshot=result.model_dump(mode="json"),
            )
            logger.info(f"Updated execution status to: {final_status}")

        logger.info(
            f"Job search workflow task completed successfully (execution_id: {execution_id}, matches: {matches_count})"
        )

        # Return serialized result
        return result.model_dump(mode="json")

    except Exception as exc:
        logger.error(f"Job search workflow failed: {exc}", exc_info=True)

        # Update status to failed
        if execution_id:
            try:
                update_execution_status(
                    execution_id,
                    "failed",
                    error_message=str(exc),
                )
            except Exception as update_error:
                logger.error(
                    f"Failed to update execution status: {update_error}", exc_info=True
                )

        # Retry task on failure
        raise self.retry(exc=exc, countdown=60, max_retries=3)
