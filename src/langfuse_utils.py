"""Langfuse utility functions for workflow tracking."""

import logging
from typing import Any, Dict, Optional

from langfuse import Langfuse, get_client, observe, propagate_attributes

from src.config import LangfuseConfig

logger = logging.getLogger(__name__)
langfuse_config = LangfuseConfig.from_env()


def get_langfuse_client() -> Optional[Langfuse]:
    """Get Langfuse client if enabled.

    Returns:
        Langfuse client instance or None if disabled
    """
    if not langfuse_config.enabled:
        return None

    try:
        return get_client()
    except Exception as e:
        logger.warning("Failed to get Langfuse client: %s", e)
        return None


def create_workflow_trace_context(
    execution_id: Optional[str] = None,
    run_id: Optional[str] = None,
    workflow_type: Optional[str] = None,
    node_name: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create context attributes for Langfuse trace propagation.

    Args:
        execution_id: Optional; deprecated in favor of run_id
        run_id: Run ID (and/or task_id in metadata)
        workflow_type: Type of workflow (profiling, job_search)
        node_name: Current node name
        user_id: User identifier (if available)
        metadata: Additional metadata

    Returns:
        Dictionary of attributes for propagate_attributes
    """
    tags = []
    if workflow_type:
        tags.append(workflow_type)
    if node_name:
        tags.append(node_name)

    meta = dict(metadata or {})
    if execution_id is not None:
        meta["execution_id"] = execution_id
    if run_id is not None:
        meta["run_id"] = run_id
    if workflow_type is not None:
        meta["workflow_type"] = workflow_type
    if node_name is not None:
        meta["node_name"] = node_name

    attrs: Dict[str, Any] = {
        "tags": tags,
        "metadata": meta,
    }
    if user_id is not None:
        attrs["user_id"] = user_id

    return attrs


__all__ = [
    "get_langfuse_client",
    "create_workflow_trace_context",
    "observe",
    "propagate_attributes",
]
