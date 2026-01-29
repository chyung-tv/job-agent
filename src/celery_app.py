"""Celery application configuration for job-agent."""

import os

from celery import Celery


# Get Redis URLs from environment (fall back to local defaults for dev)
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", BROKER_URL)


celery_app = Celery(
    "job_agent",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        "src.tasks.profiling_task",
        "src.tasks.job_search_task",
    ],
)


celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
