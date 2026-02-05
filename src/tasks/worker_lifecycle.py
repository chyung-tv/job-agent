"""Worker lifecycle management for async Celery tasks.

This module implements the Worker Lifespan Pattern to solve the "Event loop is closed"
error that occurs when running async code (pydantic-ai/google-genai with httpx) in Celery.

The pattern:
1. Creates a long-lived event loop when each worker process starts
2. Reuses this loop for all task executions
3. Properly closes the loop (allowing httpx cleanup) when the worker shuts down
"""

import asyncio
import logging
import threading

from celery.signals import worker_process_init, worker_process_shutdown

logger = logging.getLogger(__name__)

# Global event loop for this worker process
_worker_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None


def _run_loop_forever(loop: asyncio.AbstractEventLoop):
    """Run the event loop in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


@worker_process_init.connect
def init_worker_loop(**kwargs):
    """Initialize a long-lived event loop when worker process starts."""
    global _worker_loop, _loop_thread

    _worker_loop = asyncio.new_event_loop()
    _loop_thread = threading.Thread(
        target=_run_loop_forever,
        args=(_worker_loop,),
        daemon=True,
        name="worker-event-loop",
    )
    _loop_thread.start()
    logger.info("Worker event loop initialized (thread: %s)", _loop_thread.name)


@worker_process_shutdown.connect
def shutdown_worker_loop(**kwargs):
    """Gracefully shutdown the event loop when worker stops."""
    global _worker_loop, _loop_thread

    if _worker_loop is None:
        return

    logger.info("Shutting down worker event loop...")

    # Stop the loop (this will cause run_forever to return)
    _worker_loop.call_soon_threadsafe(_worker_loop.stop)

    # Wait for the loop thread to finish
    if _loop_thread and _loop_thread.is_alive():
        _loop_thread.join(timeout=5.0)

    # Close the loop after it stops
    if not _worker_loop.is_closed():
        _worker_loop.close()

    logger.info("Worker event loop closed")
    _worker_loop = None
    _loop_thread = None


def run_in_worker_loop(coro):
    """Run a coroutine in the worker's long-lived event loop.

    This function schedules the coroutine on the worker's event loop thread
    and blocks until the result is available.

    Args:
        coro: The coroutine to execute

    Returns:
        The result of the coroutine

    Raises:
        RuntimeError: If the worker event loop is not initialized
        Exception: Any exception raised by the coroutine
    """
    if _worker_loop is None:
        raise RuntimeError(
            "Worker event loop not initialized. "
            "This function should only be called from within a Celery task."
        )

    future = asyncio.run_coroutine_threadsafe(coro, _worker_loop)
    return future.result()  # Block until complete
