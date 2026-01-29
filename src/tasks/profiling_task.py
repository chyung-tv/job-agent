"""Celery task for profiling workflow."""

import asyncio
import logging
from typing import Dict, Any

from src.celery_app import celery_app
from src.workflow.profiling_workflow import ProfilingWorkflow
from src.workflow.profiling_context import ProfilingWorkflowContext
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


@celery_app.task(bind=True, name="profiling_workflow")
def execute_profiling_workflow(
    self,
    context_data: Dict[str, Any],
    execution_id: str = None,
) -> Dict[str, Any]:
    """Execute profiling workflow as Celery task.

    Args:
        context_data: Serialized ProfilingWorkflowContext data
        execution_id: UUID string of the workflow execution record

    Returns:
        Serialized context with results
    """
    logger.info(
        f"Starting profiling workflow task (execution_id: {execution_id}, task_id: {self.request.id})"
    )

    try:
        # Update status to processing
        if execution_id:
            update_execution_status(
                execution_id, "processing", current_node="ProfilingWorkflow"
            )

        # Reconstruct context from dict
        context = ProfilingWorkflowContext(**context_data)
        logger.info(f"Reconstructed context for {context.name} ({context.email})")

        # Execute workflow (async)
        logger.info("Executing profiling workflow...")
        workflow = ProfilingWorkflow()
        result = run_async(workflow.run(context))
        logger.info(f"Workflow execution completed. Has errors: {result.has_errors()}")

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

        profile_id = result.profile_id if hasattr(result, "profile_id") else "N/A"
        logger.info(
            f"Profiling workflow task completed successfully (execution_id: {execution_id}, profile_id: {profile_id})"
        )

        # Return serialized result
        return result.model_dump(mode="json")

    except Exception as exc:
        logger.error(f"Profiling workflow failed: {exc}", exc_info=True)

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
