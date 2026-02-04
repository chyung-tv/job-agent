"""FastAPI endpoints for job search workflow."""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path if running directly
# This allows the script to work both as a module and when run directly
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from http import HTTPStatus
import logging
import os
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from src.config import get_api_key
from src.workflow.status_publisher import get_redis_url
from src.workflow.job_search_workflow import JobSearchWorkflow
from src.workflow.profiling_workflow import ProfilingWorkflow
from src.workflow.base_context import JobSearchWorkflowContext
from src.database import (
    db_session,
    GenericRepository,
    User,
    Run,
)
from src.config import DEFAULT_NUM_RESULTS, TESTING_MAX_SCREENING
from src.tasks.profiling_task import execute_profiling_workflow
from src.tasks.job_search_task import execute_job_search_workflow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Job Agent API", version="1.0.0")

# CORS: allow frontend origin(s) for direct browser → API requests (e.g. VPS app domain).
# SSE stream is proxied through Next.js so it does not hit the backend from the browser.
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def verify_api_key(request: Request) -> None:
    """Validate API key from X-API-Key or Authorization: Bearer. Always required (no skip when empty)."""
    expected = get_api_key()
    if not expected:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="API key not configured on server",
        )
    # Prefer X-API-Key, then Authorization: Bearer <key>
    auth_header = request.headers.get("Authorization")
    api_key_header = request.headers.get("X-API-Key")
    provided = api_key_header
    if not provided and auth_header and auth_header.lower().startswith("bearer "):
        provided = auth_header[7:].strip()
    if not provided or provided != expected:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="API key missing or invalid",
        )


# Request/Response models for new endpoint
class JobSearchFromProfileRequest(BaseModel):
    """Request model for job search from profile endpoint."""

    user_id: UUID = Field(..., description="UUID of the user")
    num_results: Optional[int] = Field(
        default=DEFAULT_NUM_RESULTS,
        description="Number of job results to fetch per search",
    )
    max_screening: Optional[int] = Field(
        default=TESTING_MAX_SCREENING,
        description="Maximum number of jobs to screen/match per search (limits API calls)",
    )


class JobSearchFromProfileResponse(BaseModel):
    """Response model for job search from profile endpoint."""

    message: str
    user_id: UUID
    location: str
    job_titles_count: int
    job_titles: list[str]


def send_job_search_completion_email(
    user_id: UUID,
    job_titles: list[str],
    results: dict,
) -> None:
    """Send email notification when job searches complete.

    This is a placeholder for future email implementation.
    For now, it just logs the completion.

    Args:
        user_id: UUID of the user
        job_titles: List of job titles that were searched
        results: Dictionary with search results summary
    """
    logger.info(
        f"Job searches completed for user {user_id}. "
        f"Titles: {job_titles}. Results: {results}"
    )
    # TODO: Implement actual email sending


@app.post("/workflow/job-search", status_code=HTTPStatus.ACCEPTED)
async def run_job_search_workflow(
    context: JobSearchWorkflow.Context,
    _: None = Depends(verify_api_key),
):
    """Run the job search workflow asynchronously using Celery.

    Args:
        context: Job search workflow context with input parameters

    Returns:
        202 Accepted with run_id, execution_id, task_id, status, status_url, and estimated_completion_time
    """
    logger.info("Received job search workflow request")

    session_gen = db_session()
    session = next(session_gen)
    try:
        # Create Run record (tie to user when user_id provided for delivery email)
        user_id = getattr(context, "user_id", None)
        run = Run(status="pending", user_id=str(user_id) if user_id else None)
        session.add(run)
        session.commit()
        session.refresh(run)

        # Set run_id in context
        context.run_id = run.id

        # Enqueue Celery task
        task = execute_job_search_workflow.delay(
            context_data=context.model_dump(mode="json"),
            run_id=str(run.id),
        )

        # Store task_id on run
        run.task_id = task.id
        session.commit()

        logger.info(f"Enqueued job search workflow task {task.id} for run {run.id}")

        # Return 202 Accepted with metadata
        return JSONResponse(
            status_code=HTTPStatus.ACCEPTED,
            content={
                "run_id": str(run.id),
                "task_id": task.id,
                "status": "pending",
                "status_url": f"/workflow/status/{run.id}",
                "estimated_completion_time": "5-10 minutes",
            },
        )
    except Exception as e:
        logger.error(f"Failed to enqueue job search workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue job search workflow: {str(e)}",
        )
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass


@app.get("/")
async def read_root(_: None = Depends(verify_api_key)):
    """Root endpoint."""
    return {"message": "Job Agent API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


SSE_HEARTBEAT_INTERVAL_SEC = 15


async def _sse_run_status_stream(run_id: UUID) -> AsyncGenerator[str, None]:
    """Subscribe to Redis run:status:{run_id} and yield SSE events. Heartbeat every 15s."""
    channel = f"run:status:{run_id}"
    url = get_redis_url()
    client = Redis.from_url(url)
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(channel)
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=SSE_HEARTBEAT_INTERVAL_SEC,
            )
            if message is None:
                yield ": keep-alive\n\n"
            elif message.get("type") == "message" and message.get("data"):
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                yield f"data: {data}\n\n"
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for run_id=%s", run_id)
        raise
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await client.aclose()
        except Exception as e:
            logger.warning("Error closing Redis pubsub for run_id=%s: %s", run_id, e)


@app.get("/workflow/status/{run_id}/stream")
async def stream_run_status(
    run_id: UUID,
    _: None = Depends(verify_api_key),
) -> StreamingResponse:
    """Stream run status via SSE. Subscribe to Redis run:status:{run_id}; heartbeat every 15s."""
    return StreamingResponse(
        _sse_run_status_stream(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/workflow/status/{run_id}")
async def get_run_status(
    run_id: UUID,
    _: None = Depends(verify_api_key),
) -> JSONResponse:
    """Get run status via GET request (fallback when SSE is unavailable).

    Returns all Run fields matching the RunStatusResponse schema.
    Returns 404 if run not found.
    """
    session_gen = db_session()
    session = next(session_gen)
    try:
        run_repo = GenericRepository(session, Run)
        run = run_repo.get(str(run_id))

        if not run:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Run with id {run_id} not found",
            )

        # Convert datetime fields to ISO strings
        completed_at_iso = (
            run.completed_at.isoformat() + "Z" if run.completed_at else None
        )
        delivery_triggered_at_iso = (
            run.delivery_triggered_at.isoformat() + "Z"
            if run.delivery_triggered_at
            else None
        )
        created_at_iso = run.created_at.isoformat() + "Z" if run.created_at else None
        updated_at_iso = run.updated_at.isoformat() + "Z" if run.updated_at else None

        return JSONResponse(
            content={
                "run_id": str(run.id),
                "task_id": run.task_id,
                "status": run.status,
                "error_message": run.error_message,
                "completed_at": completed_at_iso,
                "user_id": run.user_id,
                "job_search_id": str(run.job_search_id) if run.job_search_id else None,
                "total_matched_jobs": run.total_matched_jobs,
                "research_completed_count": run.research_completed_count,
                "fabrication_completed_count": run.fabrication_completed_count,
                "research_failed_count": run.research_failed_count,
                "fabrication_failed_count": run.fabrication_failed_count,
                "delivery_triggered": run.delivery_triggered,
                "delivery_triggered_at": delivery_triggered_at_iso,
                "created_at": created_at_iso,
                "updated_at": updated_at_iso,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get run status: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to get run status: {str(e)}",
        )
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass


@app.post("/workflow/profiling", status_code=HTTPStatus.ACCEPTED)
async def run_profiling_workflow(
    context: ProfilingWorkflow.Context,
    _: None = Depends(verify_api_key),
):
    """Run the profiling workflow asynchronously using Celery.

    Args:
        context: Profiling workflow context with name, email, cv_urls (list of CV/PDF URLs),
            and optional basic_info. The backend downloads and parses PDFs from the URLs.

    Returns:
        202 Accepted with run_id, task_id, status, status_url, and estimated_completion_time
    """
    logger.info("Received profiling workflow request")

    session_gen = db_session()
    session = next(session_gen)
    try:
        # Create Run record
        run = Run(status="pending")
        session.add(run)
        session.commit()
        session.refresh(run)

        # Set run_id in context
        context.run_id = run.id

        # Enqueue Celery task
        task = execute_profiling_workflow.delay(
            context_data=context.model_dump(mode="json"),
            run_id=str(run.id),
        )

        # Store task_id on run
        run.task_id = task.id
        session.commit()

        logger.info(f"Enqueued profiling workflow task {task.id} for run {run.id}")

        # Return 202 Accepted with metadata
        return JSONResponse(
            status_code=HTTPStatus.ACCEPTED,
            content={
                "run_id": str(run.id),
                "task_id": task.id,
                "status": "pending",
                "status_url": f"/workflow/status/{run.id}",
                "estimated_completion_time": "3-5 minutes",
            },
        )
    except Exception as e:
        logger.error(f"Failed to enqueue profiling workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue profiling workflow: {str(e)}",
        )
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass


@app.post("/workflow/job-search/from-profile", status_code=HTTPStatus.ACCEPTED)
async def run_job_search_from_profile(
    request: JobSearchFromProfileRequest,
    _: None = Depends(verify_api_key),
) -> JobSearchFromProfileResponse:
    """Trigger multiple job searches from a profile's suggested job titles.

    This endpoint:
    1. Loads the user profile from the database
    2. Extracts suggested_job_titles and location
    3. Enqueues Celery tasks to execute job searches for each title
    4. Returns immediately with 202 Accepted

    Each job search becomes its own independent Celery task with its own Run record.

    Args:
        request: Request containing user_id and optional search parameters

    Returns:
        202 Accepted with profile information and job titles

    Raises:
        404: If profile not found
        400: If profile has no suggested job titles or missing location
    """
    logger.info(
        f"Received job search from profile request for user_id: {request.user_id}"
    )

    # Load user from database
    session_gen = db_session()
    session = next(session_gen)
    try:
        user_repo = GenericRepository(session, User)
        user = user_repo.get(str(request.user_id))

        if not user:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"User with id {request.user_id} not found",
            )

        # Extract location and suggested job titles
        location = user.location
        if not location:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="User profile is missing location. Please update the profile with a location.",
            )

        suggested_job_titles = user.suggested_job_titles or []
        if not suggested_job_titles or len(suggested_job_titles) == 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="User has no suggested job titles. Please run profiling workflow first.",
            )

        # Enqueue Celery tasks for each job title
        task_ids = []
        for job_title in suggested_job_titles:
            try:
                # Create context for this job search
                context = JobSearchWorkflowContext(
                    query=job_title,
                    location=location,
                    user_id=request.user_id,
                    num_results=request.num_results,
                    max_screening=request.max_screening,
                )

                # Create Run record (tie to user for delivery email)
                run = Run(status="pending", user_id=str(request.user_id))
                session.add(run)
                session.commit()
                session.refresh(run)

                # Set run_id in context
                context.run_id = run.id

                # Enqueue Celery task
                task = execute_job_search_workflow.delay(
                    context_data=context.model_dump(mode="json"),
                    run_id=str(run.id),
                )

                # Store task_id on run
                run.task_id = task.id
                session.commit()
                task_ids.append(task.id)

                logger.info(
                    f"Enqueued job search task {task.id} for '{job_title}' (run {run.id})"
                )
            except Exception as e:
                logger.error(
                    f"Failed to enqueue job search for '{job_title}': {e}",
                    exc_info=True,
                )
                # Continue with other job titles even if one fails

        logger.info(
            f"Initiated {len(task_ids)} job searches for user {request.user_id} "
            f"via Celery. Location: {location}. Task IDs: {task_ids}"
        )

        return JobSearchFromProfileResponse(
            message="Job searches initiated via Celery",
            user_id=request.user_id,
            location=location,
            job_titles_count=len(suggested_job_titles),
            job_titles=suggested_job_titles,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to initiate job searches from profile: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate job searches: {str(e)}",
        )
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
