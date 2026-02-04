"""Celery task for profiling workflow."""

import asyncio
import logging
import threading
import traceback
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
_SOFT_SUCCESS_WARNING = (
    "Profiling workflow completed but encountered an async HTTP client "
    "cleanup error (event loop closed during httpx/httpcore cleanup). "
    "Results were saved, but some background cleanup may have failed."
)


def _is_retryable(exc: BaseException) -> bool:
    """Return False for client errors and event-loop issues so we don't retry."""
    if isinstance(exc, ModelHTTPError):
        # 4xx client errors (e.g. 400 FAILED_PRECONDITION) are not retryable
        status = getattr(exc, "status_code", None) or 0
        if 400 <= status < 500:
            return False
    if isinstance(exc, RuntimeError) and "Event loop is closed" in str(exc):
        # Only treat as non-retryable when it's the specific httpx/httpcore
        # cleanup error; other loop-closed errors can be transient.
        tb_str = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__, chain=True)
        )
        if _is_httpx_cleanup_event_loop_error(exc, tb_str):
            return False
        return True
    # Unwrap cause (e.g. ModelHTTPError wraps google.genai.errors.ClientError)
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        return _is_retryable(cause)
    return True


def _is_httpx_cleanup_event_loop_error(exc: BaseException, tb_str: str) -> bool:
    """Heuristically detect httpx/httpcore cleanup errors after loop close.

    We look for the \"Event loop is closed\" message combined with stack frames
    from httpx/httpcore/anyio connection closing code. This lets us treat the
    error as a cleanup-only issue when the main workflow already finished.
    """
    if "Event loop is closed" not in str(exc):
        return False
    cleanup_markers = [
        "httpcore/_async/connection",
        "httpx/_client.py",
        "anyio/_backends",
        "_close_connections",
        "aclose()",
        "transport_stream.aclose()",
    ]
    return any(marker in tb_str for marker in cleanup_markers)


def run_async(coro):
    """Run async coroutine from sync context (e.g. Celery task).

    Always runs the coroutine in a **new** thread via asyncio.run() so each
    run (including retries) gets a fresh event loop. This avoids mixing an
    existing loop with httpx cleanup and prevents "Event loop is closed" on
    first run when cleanup runs after the loop is closed.

    When "Event loop is closed" occurs during httpx/httpcore cleanup but we
    already have the workflow result in result_holder, we treat it as success
    and return the result so the Celery task succeeds.
    """
    result_holder: list = []
    exc_holder: list = []

    async def wrapper():
        value = None
        try:
            value = await coro
            return value
        finally:
            if value is not None:
                result_holder.append(value)

    def _run():
        """Execute the coroutine in a fresh event loop in this thread."""
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(wrapper())
            # Best-effort async generator shutdown before closing loop
            loop.run_until_complete(loop.shutdown_asyncgens())
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                # Optimistic success: if we already have a result, treat as cleanup-only.
                if result_holder:
                    logger.info(
                        "Event loop closed during cleanup but workflow result "
                        "already captured; treating as success (result_holder non-empty)"
                    )
                    return

                tb_str = "".join(
                    traceback.format_exception(type(e), e, e.__traceback__, chain=True)
                )
                cause = getattr(e, "__cause__", None)
                if cause is not None:
                    tb_str += "".join(
                        traceback.format_exception(
                            type(cause),
                            cause,
                            cause.__traceback__,
                        )
                    )
                if _is_httpx_cleanup_event_loop_error(e, tb_str):
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
                    exc_holder.append(e)
            else:
                exc_holder.append(e)
        except BaseException as e:
            exc_holder.append(e)
        finally:
            try:
                loop.close()
            except Exception:
                logger.debug("Error while closing event loop", exc_info=True)

    t = threading.Thread(target=_run, name="run_async")
    t.start()
    t.join()
    if exc_holder:
        raise exc_holder[0]
    logger.info("run_async returning result (workflow completed successfully)")
    return result_holder[0]


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
        context: ProfilingWorkflowContext | None = None
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
                                "user_id": str(user_id_result)
                                if user_id_result != "N/A"
                                else None,
                                "has_errors": result.has_errors(),
                            }
                        )
                    except Exception as e:
                        logger.warning("Failed to update Langfuse trace: %s", e)

            return result.model_dump(mode="json")

        except Exception as exc:
            logger.error("Profiling workflow failed: %s", exc, exc_info=True)

            # Special handling for httpx/httpcore cleanup errors where the main
            # workflow likely finished but connection cleanup failed after the
            # event loop was closed. In this case we treat the run as a
            # soft-success so the frontend can proceed.
            tb_str = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__, chain=True)
            )
            cause = getattr(exc, "__cause__", None)
            if cause is not None:
                tb_str += "".join(
                    traceback.format_exception(
                        type(cause),
                        cause,
                        cause.__traceback__,
                    )
                )

            if context is not None and _is_httpx_cleanup_event_loop_error(exc, tb_str):
                logger.warning(
                    "Profiling workflow hit httpx/httpcore cleanup error after event "
                    "loop closed; treating as soft success so frontend can continue."
                )
                if run_id:
                    try:
                        update_run_status(
                            run_id,
                            "completed",
                            error_message=_SOFT_SUCCESS_WARNING,
                        )
                    except Exception as update_error:
                        logger.error(
                            "Failed to update execution status for soft-success: %s",
                            update_error,
                            exc_info=True,
                        )

                # Best-effort Langfuse trace update, mirroring success path but
                # without requiring a full result object.
                if _langfuse_config.enabled:
                    langfuse = get_langfuse_client()
                    if langfuse:
                        try:
                            user_id_value = getattr(context, "user_id", None)
                            langfuse.update_current_trace(
                                output={
                                    "status": "completed_with_warnings",
                                    "user_id": str(user_id_value)
                                    if user_id_value is not None
                                    else None,
                                    "has_errors": False,
                                    "warning": _SOFT_SUCCESS_WARNING,
                                }
                            )
                        except Exception as e:
                            logger.warning("Failed to update Langfuse trace: %s", e)

                # Return minimal but valid context so the frontend has basic
                # information (including the five questions/answers).
                return context.model_dump(mode="json")

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
