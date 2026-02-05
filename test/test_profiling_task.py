"""Unit tests for profiling Celery task."""

import pytest


def test_profiling_task_module_imports():
    """Verify profiling_task module imports without errors."""
    from src.tasks.profiling_task import execute_profiling_workflow, _is_retryable

    # Verify the task is a Celery task
    assert hasattr(execute_profiling_workflow, "delay")
    assert hasattr(execute_profiling_workflow, "apply_async")

    # Verify _is_retryable is callable
    assert callable(_is_retryable)


def test_job_search_task_module_imports():
    """Verify job_search_task module imports without errors."""
    from src.tasks.job_search_task import execute_job_search_workflow, _is_retryable

    # Verify the task is a Celery task
    assert hasattr(execute_job_search_workflow, "delay")
    assert hasattr(execute_job_search_workflow, "apply_async")

    # Verify _is_retryable is callable
    assert callable(_is_retryable)
