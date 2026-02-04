"""Unit tests for profiling Celery task async runner and soft-success handling."""

import types

import pytest

from src.tasks.profiling_task import (
    _is_httpx_cleanup_event_loop_error,
    _SOFT_SUCCESS_WARNING,
)


def _make_cleanup_runtime_error() -> RuntimeError:
    """Create a RuntimeError that mimics httpx/httpcore cleanup stack."""

    def inner():
        raise RuntimeError("Event loop is closed")

    try:
        inner()
    except RuntimeError as e:  # pragma: no cover - setup helper
        return e


def test_is_httpx_cleanup_event_loop_error_matches_httpx_markers():
    """Heuristic should return True when tb contains httpx/httpcore markers."""
    exc = _make_cleanup_runtime_error()
    fake_tb = "httpx/_client.py\nanyio/_backends\n_close_connections"

    assert _is_httpx_cleanup_event_loop_error(exc, fake_tb) is True


def test_is_httpx_cleanup_event_loop_error_ignores_unrelated_errors():
    """Heuristic should return False for non-cleanup RuntimeErrors."""
    exc = RuntimeError("Event loop is closed")
    fake_tb = "some/other/module.py\nunrelated_function"

    assert _is_httpx_cleanup_event_loop_error(exc, fake_tb) is False


def test_soft_success_warning_message_is_stable():
    """Soft-success warning string should remain stable for frontend matching."""
    assert isinstance(_SOFT_SUCCESS_WARNING, str)
    # Important substring used by the frontend to detect soft-success.
    assert (
        "async HTTP client cleanup error (event loop closed during httpx/httpcore cleanup)"
        in _SOFT_SUCCESS_WARNING
    )

