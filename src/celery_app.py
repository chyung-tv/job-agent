"""Celery application configuration for job-agent."""

import os

from celery import Celery

from src.config import LangfuseConfig

# Initialize Langfuse before creating agents (must run before any Agent is imported)
_langfuse_config = LangfuseConfig.from_env()
_langfuse_client = None
if (
    _langfuse_config.enabled
    and _langfuse_config.public_key
    and _langfuse_config.secret_key
):
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=_langfuse_config.public_key,
            secret_key=_langfuse_config.secret_key,
            host=_langfuse_config.host,
        )
        if _langfuse_client.auth_check():
            from pydantic_ai import Agent

            Agent.instrument_all()
        else:
            _langfuse_client = None
    except Exception as e:
        _langfuse_client = None
        print(f"Langfuse initialization failed: {e} - continuing without tracing")

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
