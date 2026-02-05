"""Celery task for profiling workflow."""

import logging
from typing import Dict, Any

from pydantic_ai.exceptions import ModelHTTPError

from src.tasks.worker_lifecycle import run_in_worker_loop

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
    """Return False for client errors so we don't retry."""
    if isinstance(exc, ModelHTTPError):
        # 4xx client errors (e.g. 400 FAILED_PRECONDITION) are not retryable
        status = getattr(exc, "status_code", None) or 0
        if 400 <= status < 500:
            return False
    # Unwrap cause (e.g. ModelHTTPError wraps google.genai.errors.ClientError)
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        return _is_retryable(cause)
    return True


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
            result = run_in_worker_loop(workflow.run(context))
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
