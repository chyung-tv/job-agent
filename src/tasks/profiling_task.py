"""Celery task for profiling workflow."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
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
from src.workflow.profiling_context import ProfilingWorkflowContext
from src.workflow.profiling_workflow import ProfilingWorkflow

# Configure logging to capture all workflow/node logs
# This ensures all Python loggers (including workflow nodes) are visible in Celery logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,  # Override any existing configuration
)

logger = logging.getLogger(__name__)
_langfuse_config = LangfuseConfig.from_env()

# One thread pool for running async workflows; avoids "Event loop is closed"
# when Celery retries or runs multiple tasks in the same process.
_run_async_executor = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="run_async",
)


def run_async(coro):
    """Run async coroutine from sync context (e.g. Celery task).

    When no event loop is running (typical in Celery workers), runs the
    coroutine in a dedicated thread via asyncio.run() so the loop is
    isolated from the main thread. This avoids "Event loop is closed" and
    "cannot reuse already awaited coroutine" when Celery retries or when
    libraries (e.g. google-genai httpx) hold references to a closed loop.
    When already inside a running loop (e.g. tests, Jupyter), uses
    nest_asyncio and run_until_complete.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (Celery worker, script). Run in a separate thread
        # so each task gets a fresh loop and no closed-loop references leak.
        def _run():
            return asyncio.run(coro)

        future = _run_async_executor.submit(_run)
        return future.result()
    # Already inside an event loop (e.g. Jupyter, nested call)
    import nest_asyncio

    nest_asyncio.apply()
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, name="profiling_workflow")
@observe()
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
        "Starting profiling workflow task (execution_id: %s, task_id: %s)",
        execution_id,
        self.request.id,
    )
    trace_context = create_workflow_trace_context(
        execution_id=execution_id,
        workflow_type="profiling",
        metadata={
            "celery_task_id": self.request.id,
            "celery_task_name": "profiling_workflow",
        },
    )
    with propagate_attributes(**trace_context):
        try:
            if execution_id:
                update_execution_status(
                    execution_id, "processing", current_node="ProfilingWorkflow"
                )

            context = ProfilingWorkflowContext(**context_data)
            logger.info(
                "Reconstructed context for %s (%s)", context.name, context.email
            )

            logger.info("Executing profiling workflow...")
            workflow = ProfilingWorkflow()
            result = run_async(workflow.run(context))
            logger.info(
                "Workflow execution completed. Has errors: %s", result.has_errors()
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

            profile_id = result.profile_id if hasattr(result, "profile_id") else "N/A"
            logger.info(
                "Profiling workflow task completed successfully (execution_id: %s, profile_id: %s)",
                execution_id,
                profile_id,
            )

            if _langfuse_config.enabled:
                langfuse = get_langfuse_client()
                if langfuse:
                    try:
                        langfuse.update_current_trace(
                            output={
                                "status": final_status,
                                "profile_id": profile_id,
                                "has_errors": result.has_errors(),
                            }
                        )
                    except Exception as e:
                        logger.warning("Failed to update Langfuse trace: %s", e)

            return result.model_dump(mode="json")

        except Exception as exc:
            logger.error("Profiling workflow failed: %s", exc, exc_info=True)
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
