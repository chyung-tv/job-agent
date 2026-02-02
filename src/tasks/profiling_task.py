"""Celery task for profiling workflow."""

import asyncio
import logging
import threading
from typing import Dict, Any

from pydantic_ai.exceptions import ModelHTTPError

from src.celery_app import celery_app
from src.config import LangfuseConfig
from src.langfuse_utils import (
    create_workflow_trace_context,
    get_langfuse_client,
    observe,
    propagate_attributes,
)
from src.tasks.utils import update_run_status
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

def _is_retryable(exc: BaseException) -> bool:
    """Return False for client errors and event-loop issues so we don't retry."""
    if isinstance(exc, ModelHTTPError):
        # 4xx client errors (e.g. 400 FAILED_PRECONDITION) are not retryable
        status = getattr(exc, "status_code", None) or 0
        if 400 <= status < 500:
            return False
    if isinstance(exc, RuntimeError) and "Event loop is closed" in str(exc):
        return False
    # Unwrap cause (e.g. ModelHTTPError wraps google.genai.errors.ClientError)
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        return _is_retryable(cause)
    return True


def run_async(coro):
    """Run async coroutine from sync context (e.g. Celery task).

    When no event loop is running (typical in Celery workers), runs the
    coroutine in a **new** thread via asyncio.run() so each run (including
    retries) gets a fresh event loop. Reusing the same thread pool thread
    after a failure can leave httpx/genai clients bound to a closed loop,
    causing "Event loop is closed" on retry. Using a new thread per call
    avoids that. When already inside a running loop (e.g. tests, Jupyter),
    uses nest_asyncio and run_until_complete.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (Celery worker, script). Run in a new thread so
        # each task/retry gets a fresh loop and no closed-loop references.
        result_holder: list = []
        exc_holder: list = []

        def _run():
            try:
                result_holder.append(asyncio.run(coro))
            except BaseException as e:
                exc_holder.append(e)

        t = threading.Thread(target=_run, name="run_async")
        t.start()
        t.join()
        if exc_holder:
            raise exc_holder[0]
        return result_holder[0]
    # Already inside an event loop (e.g. Jupyter, nested call)
    import nest_asyncio

    nest_asyncio.apply()
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, name="profiling_workflow")
@observe()
def execute_profiling_workflow(
    self,
    context_data: Dict[str, Any],
    run_id: str = None,
) -> Dict[str, Any]:
    """Execute profiling workflow as Celery task.

    Args:
        context_data: Serialized ProfilingWorkflowContext data
        run_id: UUID string of the run record

    Returns:
        Serialized context with results
    """
    logger.info(
        "Starting profiling workflow task (run_id: %s, task_id: %s)",
        run_id,
        self.request.id,
    )
    trace_context = create_workflow_trace_context(
        run_id=run_id,
        workflow_type="profiling",
        metadata={
            "celery_task_id": self.request.id,
            "celery_task_name": "profiling_workflow",
        },
    )
    with propagate_attributes(**trace_context):
        try:
            if run_id:
                update_run_status(run_id, "processing")

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
            if run_id:
                error_message = (
                    "; ".join(result.errors) if result.has_errors() else None
                )
                update_run_status(run_id, final_status, error_message=error_message)
                logger.info("Updated run status to: %s", final_status)

            user_id_result = getattr(result, "user_id", "N/A")
            logger.info(
                "Profiling workflow task completed successfully (run_id: %s, user_id: %s)",
                run_id,
                user_id_result,
            )

            if _langfuse_config.enabled:
                langfuse = get_langfuse_client()
                if langfuse:
                    try:
                        langfuse.update_current_trace(
                            output={
                                "status": final_status,
                                "user_id": str(user_id_result) if user_id_result != "N/A" else None,
                                "has_errors": result.has_errors(),
                            }
                        )
                    except Exception as e:
                        logger.warning("Failed to update Langfuse trace: %s", e)

            return result.model_dump(mode="json")

        except Exception as exc:
            logger.error("Profiling workflow failed: %s", exc, exc_info=True)
            if run_id:
                try:
                    update_run_status(run_id, "failed", error_message=str(exc))
                except Exception as update_error:
                    logger.error(
                        "Failed to update execution status: %s",
                        update_error,
                        exc_info=True,
                    )
            if not _is_retryable(exc):
                raise
            raise self.retry(exc=exc, countdown=60, max_retries=3)
