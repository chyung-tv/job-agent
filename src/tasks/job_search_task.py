"""Celery task for job search workflow."""

import asyncio
import logging
from typing import Dict, Any

from src.celery_app import celery_app
from src.config import LangfuseConfig
from src.langfuse_utils import (
    create_workflow_trace_context,
    get_langfuse_client,
    observe,
    propagate_attributes,
)
from src.tasks.utils import update_execution_status
from src.workflow.base_context import JobSearchWorkflowContext
from src.workflow.job_search_workflow import JobSearchWorkflow

# Configure logging to capture all workflow/node logs
# This ensures all Python loggers (including workflow nodes) are visible in Celery logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,  # Override any existing configuration
)

logger = logging.getLogger(__name__)
_langfuse_config = LangfuseConfig.from_env()


def run_async(coro):
    """Run async coroutine from sync context (e.g. Celery task).

    Uses asyncio.run() when no loop is running (normal in Celery workers),
    so each run gets a fresh event loop and we avoid "no current event loop"
    and "event loop is closed" in Python 3.10+. If already inside a running
    loop (e.g. tests), uses nest_asyncio and run_until_complete.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (Celery worker, script) - create and close a new one
        return asyncio.run(coro)
    # Already inside an event loop (e.g. Jupyter, nested call)
    import nest_asyncio

    nest_asyncio.apply()
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, name="job_search_workflow")
@observe()
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
        "Starting job search workflow task (execution_id: %s, task_id: %s)",
        execution_id,
        self.request.id,
    )
    trace_context = create_workflow_trace_context(
        execution_id=execution_id,
        workflow_type="job_search",
        metadata={
            "celery_task_id": self.request.id,
            "celery_task_name": "job_search_workflow",
        },
    )
    with propagate_attributes(**trace_context):
        try:
            if execution_id:
                update_execution_status(
                    execution_id, "processing", current_node="JobSearchWorkflow"
                )

            context = JobSearchWorkflowContext(**context_data)
            logger.info(
                "Reconstructed context for query: '%s' in %s",
                context.query,
                context.location,
            )

            logger.info("Executing job search workflow...")
            workflow = JobSearchWorkflow()
            result = run_async(workflow.run(context))
            matches_count = len(result.matched_results) if result.matched_results else 0
            logger.info(
                "Workflow execution completed. Has errors: %s, Matches found: %s",
                result.has_errors(),
                matches_count,
            )

            final_status = "failed" if result.has_errors() else "completed"
            if execution_id:
                error_message = (
                    "; ".join(result.errors) if result.has_errors() else None
                )
                update_execution_status(
                    execution_id,
                    final_status,
                    error_message=error_message,
                    context_snapshot=result.model_dump(mode="json"),
                )
                logger.info("Updated execution status to: %s", final_status)

            logger.info(
                "Job search workflow task completed successfully (execution_id: %s, matches: %s)",
                execution_id,
                matches_count,
            )

            if _langfuse_config.enabled:
                langfuse = get_langfuse_client()
                if langfuse:
                    try:
                        langfuse.update_current_trace(
                            output={
                                "status": final_status,
                                "matches_count": matches_count,
                                "has_errors": result.has_errors(),
                            }
                        )
                    except Exception as e:
                        logger.warning("Failed to update Langfuse trace: %s", e)

            return result.model_dump(mode="json")

        except Exception as exc:
            logger.error("Job search workflow failed: %s", exc, exc_info=True)
            if execution_id:
                try:
                    update_execution_status(
                        execution_id,
                        "failed",
                        error_message=str(exc),
                    )
                except Exception as update_error:
                    logger.error(
                        "Failed to update execution status: %s",
                        update_error,
                        exc_info=True,
                    )
            raise self.retry(exc=exc, countdown=60, max_retries=3)
