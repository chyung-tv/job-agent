"""Publish run status to Redis for real-time SSE streaming."""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_URL_DEFAULT = "redis://localhost:6379/0"


def get_redis_url() -> str:
    """Return Redis URL for pub/sub (same as Celery broker)."""
    return (
        os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL") or ""
    ).strip() or REDIS_URL_DEFAULT


def publish_run_status(
    run_id: str,
    status: str,
    *,
    node: Optional[str] = None,
    message: Optional[str] = None,
    completed_at: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Publish a status event to Redis channel run:status:{run_id}.

    Payload shape matches frontend Status (SSE) type. Used by workflows
    (node progress) and update_run_status (final completed/failed).
    Redis failures are logged and do not abort the workflow.

    Args:
        run_id: UUID string of the run
        status: status value (e.g. processing, completed, failed)
        node: optional node name (e.g. UserInputNode, CVProcessingNode)
        message: optional human-readable message for Progress Stepper
        completed_at: optional ISO timestamp when status is completed/failed
        error_message: optional error message when status is failed
    """
    payload = {"status": status}
    if node is not None:
        payload["node"] = node
    if message is not None:
        payload["message"] = message
    if completed_at is not None:
        payload["completed_at"] = completed_at
    if error_message is not None:
        payload["error_message"] = error_message

    channel = f"run:status:{run_id}"
    url = get_redis_url()
    try:
        import redis

        client = redis.Redis.from_url(url)
        subscribers = client.publish(channel, json.dumps(payload))
        client.close()
        logger.info(
            "Published run status to Redis (run_id=%s, channel=%s, subscribers=%d, payload=%s)",
            run_id,
            channel,
            subscribers,
            json.dumps(payload),
        )
    except Exception as e:
        logger.warning(
            "Failed to publish run status to Redis (run_id=%s, channel=%s, url=%s): %s",
            run_id,
            channel,
            url,
            e,
            exc_info=True,
        )
