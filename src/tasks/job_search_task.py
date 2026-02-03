"""Celery task for job search workflow."""

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


def _is_retryable(exc: BaseException) -> bool:
    """Return False for client errors and event-loop issues so we don't retry."""
    if isinstance(exc, ModelHTTPError):
        status = getattr(exc, "status_code", None) or 0
        if 400 <= status < 500:
            return False
    if isinstance(exc, RuntimeError) and "Event loop is closed" in str(exc):
        return False
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        return _is_retryable(cause)
    return True


def run_async(coro):
    """Run async coroutine from sync context (e.g. Celery task).

    When no event loop is running (typical in Celery workers), runs the
    coroutine in a **new** thread via asyncio.run() so each run (including
    retries) gets a fresh event loop. Reusing the same thread after a
    failure can leave httpx/genai clients bound to a closed loop, causing
    "Event loop is closed" on retry. When already inside a running loop
    (e.g. tests, Jupyter), uses nest_asyncio and run_until_complete.

    Handles "Event loop is closed" errors that occur during httpx/httpcore
    cleanup by wrapping them in a more informative exception that preserves
    the original error context.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        result_holder: list = []
        exc_holder: list = []

        def _run():
            try:
                result_holder.append(asyncio.run(coro))
            except RuntimeError as e:
                # Check if this is "Event loop is closed" during cleanup
                if "Event loop is closed" in str(e):
                    # This happens when httpx/httpcore tries to clean up
                    # connections after asyncio.run() has already closed the loop.
                    # Wrap it to provide context and mark as non-retryable.
                    import traceback

                    tb_str = "".join(
                        traceback.format_exception(type(e), e, e.__traceback__)
                    )
                    # Check if it's coming from cleanup code
                    is_cleanup_error = any(
                        marker in tb_str
                        for marker in [
                            "httpcore/_async/connection",
                            "httpx/_client.py",
                            "anyio/_backends",
                            "_close_connections",
                            "aclose()",
                            "transport_stream.aclose()",
                        ]
                    )
                    if is_cleanup_error:
                        # Wrap in a more informative exception
                        wrapped = RuntimeError(
                            "Event loop closed during httpx/httpcore connection cleanup. "
                            "This typically occurs when an async HTTP client tries to "
                            "close connections after the event loop has already been closed. "
                            "The underlying workflow may have failed or succeeded, but "
                            "cleanup failed. Check logs for the actual workflow result."
                        )
                        wrapped.__cause__ = e
                        wrapped.__suppress_context__ = True
                        exc_holder.append(wrapped)
                    else:
                        # Not clearly a cleanup error - preserve as-is
                        exc_holder.append(e)
                else:
                    exc_holder.append(e)
            except BaseException as e:
                exc_holder.append(e)

        t = threading.Thread(target=_run, name="run_async")
        t.start()
        t.join()
        if exc_holder:
            raise exc_holder[0]
        return result_holder[0]
    import nest_asyncio

    nest_asyncio.apply()
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, name="job_search_workflow")
@observe()
def execute_job_search_workflow(
    self,
    context_data: Dict[str, Any],
    run_id: str = None,
) -> Dict[str, Any]:
    """Execute job search workflow as Celery task.

    Args:
        context_data: Serialized JobSearchWorkflowContext data
        run_id: UUID string of the run record

    Returns:
        Serialized context with results
    """
    logger.info(
        "Starting job search workflow task (run_id: %s, task_id: %s)",
        run_id,
        self.request.id,
    )
    trace_context = create_workflow_trace_context(
        run_id=run_id,
        workflow_type="job_search",
        metadata={
            "celery_task_id": self.request.id,
            "celery_task_name": "job_search_workflow",
        },
    )
    with propagate_attributes(**trace_context):
        try:
            if run_id:
                update_run_status(run_id, "processing")

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
            if run_id:
                error_message = (
                    "; ".join(result.errors) if result.has_errors() else None
                )
                update_run_status(run_id, final_status, error_message=error_message)
                logger.info("Updated run status to: %s", final_status)

            logger.info(
                "Job search workflow task completed successfully (run_id: %s, matches: %s)",
                run_id,
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
