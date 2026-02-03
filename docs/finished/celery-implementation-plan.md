# Celery Migration: Comprehensive Phased Implementation Plan

**Status**: Implementation Plan  
**Last Updated**: 2026-01-29  
**Based on**: Clarifications from `docs/celery.md`  
**Target**: Hetzner Cloud VPS with Caddy, Docker-based deployment

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 0: Preparation & Environment Setup](#phase-0-preparation--environment-setup)
3. [Phase 1: Docker Infrastructure](#phase-1-docker-infrastructure)
4. [Phase 2: Celery Core Setup](#phase-2-celery-core-setup)
5. [Phase 3: Task Implementation](#phase-3-task-implementation)
6. [Phase 4: API Migration](#phase-4-api-migration)
7. [Phase 5: Status Endpoint & Workflow Tracking](#phase-5-status-endpoint--workflow-tracking)
8. [Phase 6: Task Prioritization & Scheduling](#phase-6-task-prioritization--scheduling)
9. [Phase 7: Error Handling & Sentry Integration](#phase-7-error-handling--sentry-integration)
10. [Phase 8: Testing & Validation](#phase-8-testing--validation)
11. [Phase 9: Production Deployment](#phase-9-production-deployment)
12. [Phase 10: Post-Deployment & Monitoring](#phase-10-post-deployment--monitoring)

---

## Overview

### Migration Strategy
- **Approach**: Migrate all workflows at once (no gradual migration)
- **Backward Compatibility**: Not required
- **Infrastructure**: Hetzner Cloud VPS, Docker Compose, Caddy reverse proxy
- **Monitoring**: Sentry for error tracking, Flower for Celery monitoring
- **Development**: Hot reload for both API and Celery workers

### Key Requirements
- ✅ Task prioritization (premium users)
- ✅ Cron-like scheduling for daily job searches
- ✅ Database storage for results (no Redis result backend)
- ✅ Sentry integration for error tracking
- ✅ Alerts for failed tasks, rate limits, worker health
- ✅ Hot reload in development

### Timeline Estimate
- **Total Duration**: 2-3 weeks
- **Development Phases**: 1-2 weeks
- **Testing & Deployment**: 1 week

---

## Phase 0: Preparation & Environment Setup

**Duration**: 2-4 hours  
**Dependencies**: None  
**Objective**: Set up development environment and review current codebase

### Tasks

#### 0.1 Review Current Codebase
- [ ] Review `src/api/api.py` - understand current BackgroundTasks usage
- [ ] Review `src/workflow/base_workflow.py` - understand workflow execution
- [ ] Review `src/database/models.py` - understand WorkflowExecution model
- [ ] Document current workflow execution flow
- [ ] Identify all endpoints that need migration

#### 0.2 Set Up Development Branch
```bash
git checkout -b feature/celery-migration
git push -u origin feature/celery-migration
```

#### 0.3 Create Backup
```bash
# Create backup of current working state
git tag pre-celery-migration
git push origin pre-celery-migration
```

#### 0.4 Environment Variables Audit
- [ ] List all required environment variables
- [ ] Document current `.env` structure
- [ ] Plan new environment variables needed:
  - `CELERY_BROKER_URL`
  - `CELERY_RESULT_BACKEND`
  - `REDIS_URL`
  - `SENTRY_DSN` (for Phase 7)

### Success Criteria
- ✅ Current codebase fully understood
- ✅ Development branch created
- ✅ Backup tag created
- ✅ Environment variables documented

---

## Phase 1: Docker Infrastructure

**Duration**: 4-6 hours  
**Dependencies**: Phase 0  
**Objective**: Set up Docker Compose with Redis, update Dockerfiles, configure hot reload

### Tasks

#### 1.1 Update Dependencies
**File**: `pyproject.toml`

```toml
dependencies = [
    # ... existing dependencies ...
    "celery>=5.3.0",
    "redis>=5.0.0",
    "flower>=2.0.0",  # For monitoring
    "sentry-sdk>=2.0.0",  # For error tracking (Phase 7)
]
```

**Action**:
- [ ] Add Celery, Redis, Flower dependencies
- [ ] Run `uv pip install` or `pip install -e .` to install dependencies

#### 1.2 Create Development Dockerfile
**File**: `Dockerfile.dev`

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml uv.lock* ./
RUN pip install --upgrade pip && \
    pip install uv && \
    uv pip install --system -r pyproject.toml || \
    pip install -e .

# Copy application code (will be mounted as volume in docker-compose)
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose ports
EXPOSE 8000 5555

# Default command (overridden in docker-compose)
CMD ["uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

**Action**:
- [ ] Create `Dockerfile.dev`
- [ ] Verify it builds successfully

#### 1.3 Create Production Dockerfile
**File**: `Dockerfile`

```dockerfile
# Stage 1: Build stage
FROM python:3.13-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY pyproject.toml uv.lock* ./
RUN pip install --upgrade pip && \
    pip install uv && \
    uv pip install --system -r pyproject.toml || \
    pip install -e .

# Stage 2: Runtime stage
FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Production command (no reload)
CMD ["uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

**Action**:
- [ ] Create `Dockerfile`
- [ ] Verify it builds successfully

#### 1.4 Update Docker Compose
**File**: `docker-compose.yml`

Update with Redis, Celery worker, and Flower services (see `docs/celery.md` Section 5.1 for full configuration).

**Key Changes**:
- [ ] Add Redis service
- [ ] Add Celery worker service with hot reload
- [ ] Add Flower service (monitoring)
- [ ] Update API service with Redis environment variables
- [ ] Configure volume mounts for hot reload
- [ ] Set up health checks

**Action**:
- [ ] Update `docker-compose.yml` with all services
- [ ] Create `.env.example` file with all required variables
- [ ] Update `.dockerignore` if needed

#### 1.5 Test Docker Setup
```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify services are running
docker-compose ps

# Test hot reload
# Make a change to src/api/api.py
# Check logs to see reload message
```

**Action**:
- [ ] Verify all services start successfully
- [ ] Verify hot reload works for API
- [ ] Verify Redis is accessible
- [ ] Verify PostgreSQL connection works

### Success Criteria
- ✅ All Docker images build successfully
- ✅ All services start and are healthy
- ✅ Hot reload works for API server
- ✅ Redis is accessible from API container
- ✅ Database connection works

---

## Phase 2: Celery Core Setup

**Duration**: 3-4 hours  
**Dependencies**: Phase 1  
**Objective**: Create Celery application configuration and base task infrastructure

### Tasks

#### 2.1 Create Celery App Configuration
**File**: `src/celery_app.py`

```python
"""Celery application configuration."""
import os
from celery import Celery
from celery.schedules import crontab

# Get Redis URL from environment
redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "job_agent",
    broker=redis_url,
    backend=redis_url,  # Using Redis for result backend (but storing results in DB)
    include=[
        "src.tasks.profiling_task",
        "src.tasks.job_search_task",
        "src.tasks.scheduled_tasks",  # For Phase 6
    ],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    task_acks_late=True,  # Acknowledge after task completion
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (memory leak prevention)
    
    # Retry configuration
    task_autoretry_for=(Exception,),
    task_retry_backoff=True,
    task_retry_backoff_max=600,  # Max 10 minutes
    task_max_retries=3,
    
    # Result backend (we'll store results in DB, but use Redis for task status)
    result_expires=3600,  # Results expire after 1 hour
    
    # Task routing (for prioritization - Phase 6)
    task_routes={
        "profiling_workflow": {"queue": "default"},
        "job_search_workflow": {"queue": "default"},
        "profiling_workflow.priority": {"queue": "high_priority"},
        "job_search_workflow.priority": {"queue": "high_priority"},
    },
    
    # Queue configuration
    task_default_queue="default",
    task_default_exchange="tasks",
    task_default_exchange_type="direct",
    task_default_routing_key="default",
    
    # Beat schedule (for Phase 6 - cron-like scheduling)
    beat_schedule={
        "daily-job-search": {
            "task": "src.tasks.scheduled_tasks.daily_job_search",
            "schedule": crontab(hour=9, minute=0),  # 9 AM UTC daily
        },
    },
)
```

**Action**:
- [ ] Create `src/celery_app.py`
- [ ] Configure task routing for prioritization
- [ ] Set up beat schedule structure (will be populated in Phase 6)
- [ ] Test Celery app can be imported

#### 2.2 Create Tasks Directory Structure
```bash
mkdir -p src/tasks
touch src/tasks/__init__.py
```

**Action**:
- [ ] Create `src/tasks/` directory
- [ ] Create `__init__.py` file

#### 2.3 Create Base Task Utilities
**File**: `src/tasks/utils.py`

```python
"""Utility functions for Celery tasks."""
import logging
from typing import Dict, Any
from src.database import db_session
from src.database.models import WorkflowExecution

logger = logging.getLogger(__name__)


def update_execution_status(
    execution_id: str,
    status: str,
    current_node: str = None,
    error_message: str = None,
    context_snapshot: Dict[str, Any] = None,
) -> None:
    """Update workflow execution status in database.
    
    Args:
        execution_id: UUID of the workflow execution
        status: New status (pending, processing, completed, failed)
        current_node: Name of current node being executed
        error_message: Error message if status is failed
        context_snapshot: Updated context snapshot
    """
    session_gen = db_session()
    session = next(session_gen)
    try:
        execution = session.query(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id
        ).first()
        
        if execution:
            execution.status = status
            if current_node:
                execution.current_node = current_node
            if error_message:
                execution.error_message = error_message
            if context_snapshot:
                execution.context_snapshot = context_snapshot
            
            session.commit()
            logger.info(f"Updated execution {execution_id} status to {status}")
        else:
            logger.warning(f"Execution {execution_id} not found")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update execution status: {e}", exc_info=True)
        raise
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass
```

**Action**:
- [ ] Create `src/tasks/utils.py`
- [ ] Implement `update_execution_status` function

#### 2.4 Test Celery App Setup
```bash
# Start Redis
docker-compose up -d redis

# Test Celery app import
python -c "from src.celery_app import celery_app; print('Celery app loaded successfully')"

# Test Celery worker can start (dry run)
celery -A src.celery_app worker --loglevel=info --dry-run
```

**Action**:
- [ ] Verify Celery app can be imported
- [ ] Verify worker can start (dry run)
- [ ] Check for any import errors

### Success Criteria
- ✅ Celery app created and configured
- ✅ Task utilities created
- ✅ Celery app can be imported without errors
- ✅ Worker can start (dry run)

---

## Phase 3: Task Implementation

**Duration**: 6-8 hours  
**Dependencies**: Phase 2  
**Objective**: Implement Celery tasks for profiling and job search workflows

### Tasks

#### 3.1 Implement Profiling Task
**File**: `src/tasks/profiling_task.py`

```python
"""Celery task for profiling workflow."""
import asyncio
import logging
from typing import Dict, Any
from src.celery_app import celery_app
from src.workflow.profiling_workflow import ProfilingWorkflow
from src.workflow.profiling_context import ProfilingWorkflowContext
from src.tasks.utils import update_execution_status

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async function in sync context."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If loop is already running, create new task
        import nest_asyncio
        nest_asyncio.apply()
    return asyncio.run(coro)


@celery_app.task(bind=True, name="profiling_workflow")
def execute_profiling_workflow(
    self,
    context_data: Dict[str, Any],
    execution_id: str = None,
) -> Dict[str, Any]:
    """Execute profiling workflow as Celery task.
    
    Args:
        context_data: Serialized ProfilingWorkflowContext data
        execution_id: UUID of the workflow execution record
        
    Returns:
        Serialized context with results
    """
    try:
        # Update status to processing
        if execution_id:
            update_execution_status(execution_id, "processing", current_node="ProfilingWorkflow")
        
        # Reconstruct context from dict
        context = ProfilingWorkflowContext(**context_data)
        
        # Execute workflow (async)
        workflow = ProfilingWorkflow()
        result = run_async(workflow.run(context))
        
        # Update status to completed
        if execution_id:
            final_status = "failed" if result.has_errors() else "completed"
            error_message = "; ".join(result.errors) if result.has_errors() else None
            update_execution_status(
                execution_id,
                final_status,
                error_message=error_message,
                context_snapshot=result.model_dump(mode="json"),
            )
        
        # Return serialized result
        return result.model_dump(mode="json")
        
    except Exception as e:
        logger.error(f"Profiling workflow failed: {e}", exc_info=True)
        
        # Update status to failed
        if execution_id:
            update_execution_status(
                execution_id,
                "failed",
                error_message=str(e),
            )
        
        # Retry task
        raise self.retry(exc=e, countdown=60, max_retries=3)
```

**Note**: For async support, we may need `nest-asyncio` or use `celery[async]`. We'll handle this in testing.

**Action**:
- [ ] Create `src/tasks/profiling_task.py`
- [ ] Implement `execute_profiling_workflow` task
- [ ] Handle async workflow execution
- [ ] Add error handling and retry logic

#### 3.2 Implement Job Search Task
**File**: `src/tasks/job_search_task.py`

```python
"""Celery task for job search workflow."""
import asyncio
import logging
from typing import Dict, Any
from src.celery_app import celery_app
from src.workflow.job_search_workflow import JobSearchWorkflow
from src.workflow.base_context import JobSearchWorkflowContext
from src.tasks.utils import update_execution_status

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async function in sync context."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
    return asyncio.run(coro)


@celery_app.task(bind=True, name="job_search_workflow")
def execute_job_search_workflow(
    self,
    context_data: Dict[str, Any],
    execution_id: str = None,
) -> Dict[str, Any]:
    """Execute job search workflow as Celery task.
    
    Args:
        context_data: Serialized JobSearchWorkflowContext data
        execution_id: UUID of the workflow execution record
        
    Returns:
        Serialized context with results
    """
    try:
        # Update status to processing
        if execution_id:
            update_execution_status(execution_id, "processing", current_node="JobSearchWorkflow")
        
        # Reconstruct context from dict
        context = JobSearchWorkflowContext(**context_data)
        
        # Execute workflow (async)
        workflow = JobSearchWorkflow()
        result = run_async(workflow.run(context))
        
        # Update status to completed
        if execution_id:
            final_status = "failed" if result.has_errors() else "completed"
            error_message = "; ".join(result.errors) if result.has_errors() else None
            update_execution_status(
                execution_id,
                final_status,
                error_message=error_message,
                context_snapshot=result.model_dump(mode="json"),
            )
        
        # Return serialized result
        return result.model_dump(mode="json")
        
    except Exception as e:
        logger.error(f"Job search workflow failed: {e}", exc_info=True)
        
        # Update status to failed
        if execution_id:
            update_execution_status(
                execution_id,
                "failed",
                error_message=str(e),
            )
        
        # Retry task
        raise self.retry(exc=e, countdown=60, max_retries=3)
```

**Action**:
- [ ] Create `src/tasks/job_search_task.py`
- [ ] Implement `execute_job_search_workflow` task
- [ ] Handle async workflow execution
- [ ] Add error handling and retry logic

#### 3.3 Handle Async Execution
We need to handle async workflows in sync Celery tasks. Two options:

**Option A**: Use `nest-asyncio` (simpler)
```bash
# Add to pyproject.toml
"nest-asyncio>=1.6.0",
```

**Option B**: Use `celery[async]` (more complex, but better)

**Decision**: Start with Option A, migrate to Option B if needed.

**Action**:
- [ ] Add `nest-asyncio` to dependencies
- [ ] Test async execution in tasks

#### 3.4 Test Tasks
```bash
# Start Celery worker
docker-compose up -d celery-worker

# Check worker logs
docker-compose logs -f celery-worker

# Test task import
python -c "from src.tasks.profiling_task import execute_profiling_workflow; print('Task imported')"
python -c "from src.tasks.job_search_task import execute_job_search_workflow; print('Task imported')"
```

**Action**:
- [ ] Verify tasks can be imported
- [ ] Verify worker can load tasks
- [ ] Check for any import errors

### Success Criteria
- ✅ Profiling task implemented
- ✅ Job search task implemented
- ✅ Async execution handled
- ✅ Tasks can be imported without errors
- ✅ Worker can load tasks

---

## Phase 4: API Migration

**Duration**: 6-8 hours  
**Dependencies**: Phase 3  
**Objective**: Migrate API endpoints from BackgroundTasks to Celery

### Tasks

#### 4.1 Update Profiling Endpoint
**File**: `src/api/api.py`

**Current Implementation** (to be replaced):
```python
@app.post("/workflow/profiling")
async def run_profiling_workflow(context: ProfilingWorkflow.Context):
    # ... synchronous execution ...
```

**New Implementation**:
```python
from src.celery_app import celery_app
from src.tasks.profiling_task import execute_profiling_workflow
from src.database import db_session
from src.database.models import Run, WorkflowExecution
from uuid import uuid4

@app.post("/workflow/profiling", status_code=HTTPStatus.ACCEPTED)
async def run_profiling_workflow(context: ProfilingWorkflow.Context):
    """Run profiling workflow asynchronously using Celery.
    
    Returns 202 Accepted with run_id and status URL.
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
        
        # Create WorkflowExecution record (status: pending)
        execution = WorkflowExecution(
            run_id=run.id,
            workflow_type="profiling",
            status="pending",
            context_snapshot=context.model_dump(mode="json"),
        )
        session.add(execution)
        session.commit()
        session.refresh(execution)
        
        # Enqueue Celery task
        task = execute_profiling_workflow.delay(
            context_data=context.model_dump(mode="json"),
            execution_id=str(execution.id),
        )
        
        logger.info(f"Enqueued profiling workflow task {task.id} for run {run.id}")
        
        # Return 202 Accepted
        return JSONResponse(
            status_code=HTTPStatus.ACCEPTED,
            content={
                "run_id": str(run.id),
                "execution_id": str(execution.id),
                "task_id": task.id,
                "status": "pending",
                "status_url": f"/workflow/status/{run.id}",
                "estimated_completion_time": "2-5 minutes",
            },
        )
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to enqueue profiling workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue workflow: {str(e)}",
        )
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass
```

**Action**:
- [ ] Update `/workflow/profiling` endpoint
- [ ] Create Run and WorkflowExecution records
- [ ] Enqueue Celery task
- [ ] Return 202 Accepted response

#### 4.2 Update Job Search Endpoint
**File**: `src/api/api.py`

Similar to profiling endpoint:

```python
from src.tasks.job_search_task import execute_job_search_workflow

@app.post("/workflow/job-search", status_code=HTTPStatus.ACCEPTED)
async def run_job_search_workflow(context: JobSearchWorkflow.Context):
    """Run job search workflow asynchronously using Celery.
    
    Returns 202 Accepted with run_id and status URL.
    """
    logger.info("Received job search workflow request")
    
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
        
        # Create WorkflowExecution record (status: pending)
        execution = WorkflowExecution(
            run_id=run.id,
            workflow_type="job_search",
            status="pending",
            context_snapshot=context.model_dump(mode="json"),
        )
        session.add(execution)
        session.commit()
        session.refresh(execution)
        
        # Enqueue Celery task
        task = execute_job_search_workflow.delay(
            context_data=context.model_dump(mode="json"),
            execution_id=str(execution.id),
        )
        
        logger.info(f"Enqueued job search workflow task {task.id} for run {run.id}")
        
        # Return 202 Accepted
        return JSONResponse(
            status_code=HTTPStatus.ACCEPTED,
            content={
                "run_id": str(run.id),
                "execution_id": str(execution.id),
                "task_id": task.id,
                "status": "pending",
                "status_url": f"/workflow/status/{run.id}",
                "estimated_completion_time": "5-10 minutes",
            },
        )
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to enqueue job search workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue workflow: {str(e)}",
        )
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass
```

**Action**:
- [ ] Update `/workflow/job-search` endpoint
- [ ] Create Run and WorkflowExecution records
- [ ] Enqueue Celery task
- [ ] Return 202 Accepted response

#### 4.3 Update Job Search from Profile Endpoint
**File**: `src/api/api.py`

Replace `background_tasks.add_task` with Celery task enqueuing:

```python
from src.tasks.job_search_task import execute_job_search_workflow

@app.post("/workflow/job-search/from-profile", status_code=HTTPStatus.ACCEPTED)
async def run_job_search_from_profile(
    request: JobSearchFromProfileRequest,
) -> JobSearchFromProfileResponse:
    """Trigger multiple job searches from a profile's suggested job titles.
    
    Enqueues a Celery task for each job title.
    """
    logger.info(f"Received job search from profile request for profile_id: {request.profile_id}")
    
    session_gen = db_session()
    session = next(session_gen)
    try:
        # Load profile
        profile_repo = GenericRepository(session, UserProfile)
        profile = profile_repo.get(str(request.profile_id))
        
        if not profile:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Profile with id {request.profile_id} not found",
            )
        
        location = profile.location
        if not location:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Profile is missing location.",
            )
        
        suggested_job_titles = profile.suggested_job_titles or []
        if not suggested_job_titles:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Profile has no suggested job titles.",
            )
        
        # Enqueue a task for each job title
        task_ids = []
        for job_title in suggested_job_titles:
            context = JobSearchWorkflowContext(
                query=job_title,
                location=location,
                profile_id=request.profile_id,
                num_results=request.num_results,
                max_screening=request.max_screening,
            )
            
            # Create Run and Execution records
            run = Run(status="pending")
            session.add(run)
            session.commit()
            session.refresh(run)
            
            context.run_id = run.id
            
            execution = WorkflowExecution(
                run_id=run.id,
                workflow_type="job_search",
                status="pending",
                context_snapshot=context.model_dump(mode="json"),
            )
            session.add(execution)
            session.commit()
            session.refresh(execution)
            
            # Enqueue task
            task = execute_job_search_workflow.delay(
                context_data=context.model_dump(mode="json"),
                execution_id=str(execution.id),
            )
            task_ids.append(task.id)
        
        logger.info(f"Enqueued {len(task_ids)} job search tasks for profile {request.profile_id}")
        
        return JobSearchFromProfileResponse(
            message="Job searches initiated in background",
            profile_id=request.profile_id,
            location=location,
            job_titles_count=len(suggested_job_titles),
            job_titles=suggested_job_titles,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to initiate job searches: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate job searches: {str(e)}",
        )
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass
```

**Action**:
- [ ] Update `/workflow/job-search/from-profile` endpoint
- [ ] Replace BackgroundTasks with Celery tasks
- [ ] Create Run and Execution records for each job search
- [ ] Enqueue tasks for each job title

#### 4.4 Remove BackgroundTasks Import
**File**: `src/api/api.py`

- [ ] Remove `from fastapi import BackgroundTasks`
- [ ] Remove `background_tasks: BackgroundTasks` parameter from endpoints
- [ ] Remove `execute_job_searches_from_profile` function (replaced by Celery tasks)

#### 4.5 Test API Endpoints
```bash
# Start all services
docker-compose up -d

# Test profiling endpoint
curl -X POST http://localhost:8000/workflow/profiling \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "email": "test@example.com", "cv_urls": []}'

# Should return 202 with run_id

# Test job search endpoint
curl -X POST http://localhost:8000/workflow/job-search \
  -H "Content-Type: application/json" \
  -d '{"query": "Software Engineer", "location": "Hong Kong", "profile_id": "..."}'

# Should return 202 with run_id
```

**Action**:
- [ ] Test profiling endpoint returns 202
- [ ] Test job search endpoint returns 202
- [ ] Verify tasks are enqueued in Redis
- [ ] Check worker logs for task execution

### Success Criteria
- ✅ All endpoints return 202 Accepted
- ✅ Tasks are enqueued successfully
- ✅ Run and WorkflowExecution records created
- ✅ No BackgroundTasks usage remaining
- ✅ Worker processes tasks successfully

---

## Phase 5: Status Endpoint & Workflow Tracking

**Duration**: 4-6 hours  
**Dependencies**: Phase 4  
**Objective**: Implement status endpoint and improve workflow tracking

### Tasks

#### 5.1 Implement Status Endpoint
**File**: `src/api/api.py`

```python
from src.database.models import WorkflowExecution, Run
from src.celery_app import celery_app

@app.get("/workflow/status/{run_id}")
async def get_workflow_status(run_id: UUID):
    """Get workflow execution status.
    
    Returns current status, progress, and results (if completed).
    """
    session_gen = db_session()
    session = next(session_gen)
    try:
        # Get workflow execution
        execution = session.query(WorkflowExecution).filter(
            WorkflowExecution.run_id == run_id
        ).order_by(WorkflowExecution.created_at.desc()).first()
        
        if not execution:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Workflow execution not found for run_id: {run_id}",
            )
        
        # Get task status from Celery (if task_id available)
        task_status = None
        if hasattr(execution, 'task_id') and execution.task_id:
            task = celery_app.AsyncResult(execution.task_id)
            task_status = task.state  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
        
        # Calculate progress (rough estimate based on workflow type and current node)
        progress_percent = calculate_progress(execution)
        
        # Build response
        response = {
            "run_id": str(execution.run_id),
            "execution_id": str(execution.id),
            "workflow_type": execution.workflow_type,
            "status": execution.status,  # pending, processing, completed, failed
            "current_node": execution.current_node,
            "progress_percent": progress_percent,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "has_errors": execution.status == "failed",
            "error_message": execution.error_message,
        }
        
        # Add result if completed
        if execution.status == "completed" and execution.context_snapshot:
            response["result"] = execution.context_snapshot
        
        # Add Celery task status if available
        if task_status:
            response["task_status"] = task_status
        
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow status: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow status: {str(e)}",
        )
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass


def calculate_progress(execution: WorkflowExecution) -> int:
    """Calculate progress percentage based on workflow type and current node.
    
    Args:
        execution: WorkflowExecution record
        
    Returns:
        Progress percentage (0-100)
    """
    if execution.status == "completed":
        return 100
    elif execution.status == "failed":
        return 0
    
    # Node-based progress estimation
    if execution.workflow_type == "profiling":
        nodes = ["UserInputNode", "CVProcessingNode"]
    elif execution.workflow_type == "job_search":
        nodes = [
            "ProfileRetrievalNode",
            "DiscoveryNode",
            "MatchingNode",
            "ResearchNode",
            "FabricationNode",
            "CompletionNode",
            "DeliveryNode",
        ]
    else:
        return 50  # Unknown workflow type
    
    if execution.current_node:
        try:
            current_index = nodes.index(execution.current_node)
            return int((current_index + 1) / len(nodes) * 100)
        except ValueError:
            return 50  # Unknown node
    
    return 0  # Not started
```

**Action**:
- [ ] Implement `/workflow/status/{run_id}` endpoint
- [ ] Query WorkflowExecution from database
- [ ] Calculate progress percentage
- [ ] Return status, progress, and results

#### 5.2 Update Workflow Execution Tracking
**File**: `src/workflow/base_workflow.py`

Ensure `_update_workflow_execution` updates `current_node` properly:

```python
def _update_workflow_execution(
    self,
    context: "BaseContext",
    current_node: Optional[str] = None,
    status: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update workflow execution record."""
    if not self._execution_id:
        return
    
    session_gen = db_session()
    session = next(session_gen)
    try:
        execution = session.query(WorkflowExecution).filter(
            WorkflowExecution.id == self._execution_id
        ).first()
        
        if execution:
            if current_node:
                execution.current_node = current_node
            if status:
                execution.status = status
            if error_message:
                execution.error_message = error_message
            
            # Update context snapshot
            execution.context_snapshot = json.loads(context.model_dump_json())
            
            # Update timestamps
            if status == "processing" and not execution.started_at:
                execution.started_at = datetime.utcnow()
            if status in ["completed", "failed"]:
                execution.completed_at = datetime.utcnow()
            
            session.commit()
    except Exception as e:
        session.rollback()
        self.logger.error(f"Failed to update workflow execution: {e}")
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass
```

**Action**:
- [ ] Verify `_update_workflow_execution` updates `current_node`
- [ ] Ensure timestamps are updated correctly
- [ ] Test node execution tracking

#### 5.3 Test Status Endpoint
```bash
# Start workflow
curl -X POST http://localhost:8000/workflow/profiling ...

# Get run_id from response

# Poll status endpoint
curl http://localhost:8000/workflow/status/{run_id}

# Should return status, progress, etc.
```

**Action**:
- [ ] Test status endpoint returns correct status
- [ ] Verify progress calculation works
- [ ] Test with completed workflow
- [ ] Test with failed workflow

### Success Criteria
- ✅ Status endpoint implemented
- ✅ Progress calculation works
- ✅ Current node tracking works
- ✅ Status endpoint returns correct data
- ✅ Timestamps updated correctly

---

## Phase 6: Task Prioritization & Scheduling

**Duration**: 4-6 hours  
**Dependencies**: Phase 5  
**Objective**: Implement task prioritization and cron-like scheduling

### Tasks

#### 6.1 Update Celery Configuration for Priority Queues
**File**: `src/celery_app.py`

Already configured in Phase 2, but verify:

```python
# Task routing (for prioritization)
task_routes={
    "profiling_workflow": {"queue": "default"},
    "job_search_workflow": {"queue": "default"},
    "profiling_workflow.priority": {"queue": "high_priority"},
    "job_search_workflow.priority": {"queue": "high_priority"},
},
```

**Action**:
- [ ] Verify priority queue configuration
- [ ] Update task names if needed

#### 6.2 Create Priority Task Versions
**File**: `src/tasks/profiling_task.py`

```python
@celery_app.task(bind=True, name="profiling_workflow.priority")
def execute_profiling_workflow_priority(
    self,
    context_data: Dict[str, Any],
    execution_id: str = None,
) -> Dict[str, Any]:
    """Execute profiling workflow with high priority."""
    # Same implementation as regular task
    return execute_profiling_workflow(context_data, execution_id)
```

**File**: `src/tasks/job_search_task.py`

```python
@celery_app.task(bind=True, name="job_search_workflow.priority")
def execute_job_search_workflow_priority(
    self,
    context_data: Dict[str, Any],
    execution_id: str = None,
) -> Dict[str, Any]:
    """Execute job search workflow with high priority."""
    # Same implementation as regular task
    return execute_job_search_workflow(context_data, execution_id)
```

**Action**:
- [ ] Create priority task versions
- [ ] Update API endpoints to use priority tasks for premium users (if applicable)

#### 6.3 Update Docker Compose for Priority Queues
**File**: `docker-compose.yml`

Update Celery worker to consume from multiple queues:

```yaml
celery-worker:
  # ... existing config ...
  command: >
    sh -c "
      celery -A src.celery_app worker 
      --loglevel=info 
      --concurrency=2
      --queues=high_priority,default
      --reload
    "
```

**Action**:
- [ ] Update worker command to consume from multiple queues
- [ ] Verify priority queue works

#### 6.4 Implement Scheduled Tasks
**File**: `src/tasks/scheduled_tasks.py`

```python
"""Scheduled Celery tasks (cron-like)."""
import logging
from src.celery_app import celery_app
from src.database import db_session
from src.database.models import UserProfile
from src.tasks.job_search_task import execute_job_search_workflow
from src.workflow.base_context import JobSearchWorkflowContext

logger = logging.getLogger(__name__)


@celery_app.task(name="daily_job_search")
def daily_job_search():
    """Run daily job searches for all profiles with suggested job titles.
    
    This task runs daily (configured in celery_app.py beat_schedule).
    """
    logger.info("Starting daily job search task")
    
    session_gen = db_session()
    session = next(session_gen)
    try:
        # Get all profiles with suggested job titles and location
        profiles = session.query(UserProfile).filter(
            UserProfile.suggested_job_titles.isnot(None),
            UserProfile.location.isnot(None),
        ).all()
        
        logger.info(f"Found {len(profiles)} profiles for daily job search")
        
        # Enqueue job search for each profile
        for profile in profiles:
            try:
                for job_title in profile.suggested_job_titles:
                    context = JobSearchWorkflowContext(
                        query=job_title,
                        location=profile.location,
                        profile_id=profile.id,
                        num_results=10,  # Default
                        max_screening=5,  # Default
                    )
                    
                    # Create Run and Execution records
                    from src.database.models import Run, WorkflowExecution
                    run = Run(status="pending")
                    session.add(run)
                    session.commit()
                    session.refresh(run)
                    
                    context.run_id = run.id
                    
                    execution = WorkflowExecution(
                        run_id=run.id,
                        workflow_type="job_search",
                        status="pending",
                        context_snapshot=context.model_dump(mode="json"),
                    )
                    session.add(execution)
                    session.commit()
                    session.refresh(execution)
                    
                    # Enqueue task
                    execute_job_search_workflow.delay(
                        context_data=context.model_dump(mode="json"),
                        execution_id=str(execution.id),
                    )
                    
            except Exception as e:
                logger.error(f"Failed to enqueue job search for profile {profile.id}: {e}")
                continue
        
        logger.info("Daily job search task completed")
        
    except Exception as e:
        logger.error(f"Daily job search task failed: {e}", exc_info=True)
        raise
    finally:
        try:
            next(session_gen, None)
        except StopIteration:
            pass
```

**Action**:
- [ ] Create `src/tasks/scheduled_tasks.py`
- [ ] Implement `daily_job_search` task
- [ ] Update `celery_app.py` to include scheduled tasks

#### 6.5 Add Celery Beat Service
**File**: `docker-compose.yml`

```yaml
celery-beat:
  build:
    context: .
    dockerfile: Dockerfile.dev
  container_name: job-agent-celery-beat
  restart: unless-stopped
  environment:
    DATABASE_URL: postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-job_agent}
    CELERY_BROKER_URL: redis://redis:6379/0
    CELERY_RESULT_BACKEND: redis://redis:6379/0
    PYTHONPATH: /app
  volumes:
    - ./src:/app/src
    - ./pyproject.toml:/app/pyproject.toml
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  networks:
    - job-agent-network
  command: >
    sh -c "
      celery -A src.celery_app beat 
      --loglevel=info
    "
```

**Action**:
- [ ] Add Celery Beat service to docker-compose.yml
- [ ] Test scheduled tasks run correctly

#### 6.6 Test Priority Queues and Scheduling
```bash
# Test priority queue
# Enqueue a priority task and verify it runs before default tasks

# Test scheduled task
# Wait for scheduled time or manually trigger beat
celery -A src.celery_app beat --loglevel=info
```

**Action**:
- [ ] Test priority queues work
- [ ] Test scheduled tasks run
- [ ] Verify daily job search enqueues tasks

### Success Criteria
- ✅ Priority queues configured
- ✅ Priority tasks implemented
- ✅ Scheduled tasks implemented
- ✅ Celery Beat service running
- ✅ Daily job search works

---

## Phase 7: Error Handling & Sentry Integration

**Duration**: 4-6 hours  
**Dependencies**: Phase 6  
**Objective**: Integrate Sentry for error tracking and implement comprehensive error handling

### Tasks

#### 7.1 Add Sentry SDK
**File**: `pyproject.toml`

Already added in Phase 1, verify:
```toml
"sentry-sdk>=2.0.0",
```

#### 7.2 Initialize Sentry
**File**: `src/config.py` or `src/sentry_config.py`

```python
"""Sentry configuration."""
import os
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

def init_sentry():
    """Initialize Sentry SDK."""
    sentry_dsn = os.getenv("SENTRY_DSN")
    if not sentry_dsn:
        return
    
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            CeleryIntegration(),
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of transactions
        environment=os.getenv("ENVIRONMENT", "development"),
        release=os.getenv("RELEASE_VERSION", "unknown"),
    )
```

**Action**:
- [ ] Create Sentry initialization function
- [ ] Import and call in `src/api/api.py` and Celery app

#### 7.3 Integrate Sentry in API
**File**: `src/api/api.py`

```python
from src.sentry_config import init_sentry

# Initialize Sentry at module level
init_sentry()

# Sentry will automatically capture exceptions
```

**Action**:
- [ ] Initialize Sentry in API
- [ ] Test error capture

#### 7.4 Integrate Sentry in Celery App
**File**: `src/celery_app.py`

```python
from src.sentry_config import init_sentry

# Initialize Sentry
init_sentry()

# Sentry CeleryIntegration will automatically capture task failures
```

**Action**:
- [ ] Initialize Sentry in Celery app
- [ ] Test task error capture

#### 7.5 Add Custom Error Handling in Tasks
**File**: `src/tasks/profiling_task.py`

```python
import sentry_sdk

@celery_app.task(bind=True, name="profiling_workflow")
def execute_profiling_workflow(self, ...):
    try:
        # ... existing code ...
    except Exception as e:
        # Capture exception in Sentry with context
        sentry_sdk.set_context("workflow", {
            "type": "profiling",
            "execution_id": execution_id,
            "context_data": context_data,
        })
        sentry_sdk.capture_exception(e)
        
        # ... existing error handling ...
```

**Action**:
- [ ] Add Sentry context to task errors
- [ ] Capture exceptions with context

#### 7.6 Implement Alerting Logic
**File**: `src/tasks/utils.py` or new `src/monitoring/alerts.py`

```python
"""Alerting utilities."""
import logging
import sentry_sdk

logger = logging.getLogger(__name__)


def alert_failed_task(execution_id: str, error_message: str, workflow_type: str):
    """Send alert for failed task.
    
    Args:
        execution_id: UUID of failed execution
        error_message: Error message
        workflow_type: Type of workflow
    """
    # Sentry will automatically capture, but we can add custom context
    sentry_sdk.set_context("task_failure", {
        "execution_id": execution_id,
        "workflow_type": workflow_type,
        "error_message": error_message,
    })
    sentry_sdk.capture_message(
        f"Workflow {workflow_type} failed: {error_message}",
        level="error",
    )
    logger.error(f"Alerted for failed task {execution_id}")


def alert_rate_limit(queue_name: str, queue_length: int, threshold: int = 100):
    """Alert when queue length exceeds threshold.
    
    Args:
        queue_name: Name of the queue
        queue_length: Current queue length
        threshold: Alert threshold
    """
    if queue_length > threshold:
        sentry_sdk.set_context("rate_limit", {
            "queue_name": queue_name,
            "queue_length": queue_length,
            "threshold": threshold,
        })
        sentry_sdk.capture_message(
            f"Queue {queue_name} length ({queue_length}) exceeds threshold ({threshold})",
            level="warning",
        )
        logger.warning(f"Rate limit alert: {queue_name} has {queue_length} tasks")


def alert_worker_health(worker_name: str, status: str):
    """Alert when worker health issues detected.
    
    Args:
        worker_name: Name of the worker
        status: Worker status
    """
    if status != "online":
        sentry_sdk.set_context("worker_health", {
            "worker_name": worker_name,
            "status": status,
        })
        sentry_sdk.capture_message(
            f"Worker {worker_name} status: {status}",
            level="warning",
        )
        logger.warning(f"Worker health alert: {worker_name} is {status}")
```

**Action**:
- [ ] Create alerting utilities
- [ ] Integrate alerts in task error handling
- [ ] Add queue monitoring (can use Flower API or Redis)

#### 7.7 Add Queue Monitoring
**File**: `src/monitoring/queue_monitor.py` (optional)

```python
"""Queue monitoring utilities."""
from celery import Celery
from src.celery_app import celery_app

def check_queue_lengths():
    """Check queue lengths and alert if needed."""
    inspect = celery_app.control.inspect()
    active_queues = inspect.active_queues()
    
    # Get queue lengths from Redis
    # This is a simplified version - you may need to use Redis directly
    for worker, queues in active_queues.items():
        for queue in queues:
            queue_name = queue.get("name", "unknown")
            # Check length and alert if needed
            # Implementation depends on Redis setup
```

**Action**:
- [ ] Implement queue monitoring (optional)
- [ ] Add periodic queue checks

#### 7.8 Update Environment Variables
**File**: `.env.example`

```bash
# Sentry
SENTRY_DSN=your_sentry_dsn_here
ENVIRONMENT=development
RELEASE_VERSION=1.0.0
```

**Action**:
- [ ] Add Sentry environment variables
- [ ] Document Sentry setup

#### 7.9 Test Sentry Integration
```bash
# Trigger an error in a task
# Check Sentry dashboard for error

# Test alerting
# Verify alerts are sent to Sentry
```

**Action**:
- [ ] Test error capture in Sentry
- [ ] Verify alerts work
- [ ] Test queue monitoring (if implemented)

### Success Criteria
- ✅ Sentry initialized
- ✅ Errors captured in Sentry
- ✅ Alerts implemented
- ✅ Task failures alert correctly
- ✅ Queue monitoring works (if implemented)

---

## Phase 8: Testing & Validation

**Duration**: 1-2 days  
**Dependencies**: Phase 7  
**Objective**: Comprehensive testing of all functionality

### Tasks

#### 8.1 Unit Tests
**File**: `test/test_celery_tasks.py`

```python
"""Tests for Celery tasks."""
import pytest
from src.tasks.profiling_task import execute_profiling_workflow
from src.tasks.job_search_task import execute_job_search_workflow

def test_profiling_task():
    # Test profiling task execution
    pass

def test_job_search_task():
    # Test job search task execution
    pass
```

**Action**:
- [ ] Write unit tests for tasks
- [ ] Write unit tests for API endpoints
- [ ] Write unit tests for status endpoint

#### 8.2 Integration Tests
**File**: `test/test_integration.py`

```python
"""Integration tests for Celery workflow."""
import pytest
from fastapi.testclient import TestClient
from src.api.api import app

client = TestClient(app)

def test_profiling_workflow_integration():
    # Test full profiling workflow
    response = client.post("/workflow/profiling", json={...})
    assert response.status_code == 202
    
    run_id = response.json()["run_id"]
    
    # Poll status endpoint
    status_response = client.get(f"/workflow/status/{run_id}")
    assert status_response.status_code == 200
    
    # Wait for completion (or mock)
    # Verify final status
```

**Action**:
- [ ] Write integration tests
- [ ] Test full workflow execution
- [ ] Test error scenarios

#### 8.3 Load Testing
```bash
# Use tools like Apache Bench or Locust
ab -n 100 -c 10 http://localhost:8000/workflow/profiling
```

**Action**:
- [ ] Perform load testing
- [ ] Verify worker scaling
- [ ] Check queue handling under load

#### 8.4 End-to-End Testing
```bash
# Test complete user flow:
# 1. Create profile
# 2. Trigger job search
# 3. Check status
# 4. Verify results
```

**Action**:
- [ ] Test complete user flows
- [ ] Verify all workflows work end-to-end
- [ ] Test error recovery

#### 8.5 Test Priority Queues
```bash
# Enqueue low priority task
# Enqueue high priority task
# Verify high priority runs first
```

**Action**:
- [ ] Test priority queue ordering
- [ ] Verify priority tasks execute first

#### 8.6 Test Scheduled Tasks
```bash
# Manually trigger beat or wait for schedule
# Verify daily job search runs
```

**Action**:
- [ ] Test scheduled tasks
- [ ] Verify daily job search works

#### 8.7 Test Error Handling
```bash
# Trigger various error scenarios
# Verify errors are captured in Sentry
# Verify retries work
```

**Action**:
- [ ] Test error scenarios
- [ ] Verify Sentry captures errors
- [ ] Test retry logic

### Success Criteria
- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ Load testing successful
- ✅ End-to-end tests pass
- ✅ Priority queues work
- ✅ Scheduled tasks work
- ✅ Error handling works

---

## Phase 9: Production Deployment

**Duration**: 1-2 days  
**Dependencies**: Phase 8  
**Objective**: Deploy to Hetzner Cloud VPS with Caddy

### Tasks

#### 9.1 Create Production Docker Compose
**File**: `docker-compose.prod.yml`

Based on `docs/celery.md` Section 7.2, create production configuration:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - job-agent-network

  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redis_data:/data
    networks:
      - job-agent-network

  api:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      SENTRY_DSN: ${SENTRY_DSN}
      ENVIRONMENT: production
    depends_on:
      - postgres
      - redis
    networks:
      - job-agent-network
    command: >
      uvicorn src.api.api:app 
      --host 0.0.0.0 
      --port 8000 
      --workers 2

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      SENTRY_DSN: ${SENTRY_DSN}
      ENVIRONMENT: production
    depends_on:
      - postgres
      - redis
    networks:
      - job-agent-network
    command: >
      celery -A src.celery_app worker 
      --loglevel=info 
      --concurrency=4
      --queues=high_priority,default

  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      SENTRY_DSN: ${SENTRY_DSN}
      ENVIRONMENT: production
    depends_on:
      - postgres
      - redis
    networks:
      - job-agent-network
    command: >
      celery -A src.celery_app beat 
      --loglevel=info

  flower:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    ports:
      - "5555:5555"
    environment:
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      FLOWER_BASIC_AUTH: ${FLOWER_USER}:${FLOWER_PASSWORD}
    depends_on:
      - redis
    networks:
      - job-agent-network
    command: >
      celery -A src.celery_app flower 
      --port=5555

volumes:
  postgres_data:
  redis_data:

networks:
  job-agent-network:
    driver: bridge
```

**Action**:
- [ ] Create `docker-compose.prod.yml`
- [ ] Configure production settings
- [ ] Add Flower authentication

#### 9.2 Set Up Hetzner Cloud VPS
```bash
# SSH into VPS
ssh root@your-vps-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt-get update
apt-get install docker-compose-plugin

# Clone repository
git clone <your-repo>
cd job-agent

# Set up environment variables
cp .env.example .env
# Edit .env with production values
```

**Action**:
- [ ] Set up Hetzner VPS
- [ ] Install Docker and Docker Compose
- [ ] Clone repository
- [ ] Configure environment variables

#### 9.3 Configure Caddy
**File**: `Caddyfile` (on VPS)

```caddyfile
your-domain.com {
    reverse_proxy api:8000
    
    # Optional: Add Flower monitoring endpoint
    handle /flower* {
        reverse_proxy flower:5555
    }
}
```

**Action**:
- [ ] Install Caddy on VPS
- [ ] Configure Caddyfile
- [ ] Set up domain DNS
- [ ] Test SSL certificate generation

#### 9.4 Deploy Application
```bash
# Build and start services
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Verify services
docker-compose -f docker-compose.prod.yml ps
```

**Action**:
- [ ] Build production images
- [ ] Start all services
- [ ] Verify services are running
- [ ] Test API endpoints

#### 9.5 Set Up Monitoring
```bash
# Set up log rotation
# Configure systemd for auto-restart
# Set up backup for PostgreSQL
```

**Action**:
- [ ] Configure log rotation
- [ ] Set up database backups
- [ ] Configure auto-restart on failure

#### 9.6 Verify Deployment
```bash
# Test API
curl https://your-domain.com/health

# Test workflow endpoints
curl -X POST https://your-domain.com/workflow/profiling ...

# Check Flower
curl https://your-domain.com/flower

# Check Sentry for errors
```

**Action**:
- [ ] Test all endpoints
- [ ] Verify workflows work
- [ ] Check monitoring tools
- [ ] Verify SSL certificate

### Success Criteria
- ✅ VPS set up and configured
- ✅ Caddy configured with SSL
- ✅ All services running
- ✅ API endpoints accessible
- ✅ Workflows execute successfully
- ✅ Monitoring tools accessible

---

## Phase 10: Post-Deployment & Monitoring

**Duration**: Ongoing  
**Dependencies**: Phase 9  
**Objective**: Monitor, optimize, and maintain production system

### Tasks

#### 10.1 Monitor System Health
- [ ] Set up Sentry alerts for critical errors
- [ ] Monitor Flower dashboard daily
- [ ] Check queue lengths regularly
- [ ] Monitor worker health

#### 10.2 Optimize Performance
- [ ] Tune Celery worker concurrency
- [ ] Optimize database queries
- [ ] Monitor and optimize Redis usage
- [ ] Scale workers as needed

#### 10.3 Set Up Backups
```bash
# PostgreSQL backup script
pg_dump -U postgres job_agent > backup_$(date +%Y%m%d).sql

# Set up cron for daily backups
```

**Action**:
- [ ] Set up database backups
- [ ] Configure backup retention
- [ ] Test backup restoration

#### 10.4 Document Operations
- [ ] Document deployment process
- [ ] Document troubleshooting steps
- [ ] Document scaling procedures
- [ ] Create runbooks

#### 10.5 Continuous Improvement
- [ ] Review error logs weekly
- [ ] Optimize based on usage patterns
- [ ] Add new features as needed
- [ ] Update dependencies regularly

### Success Criteria
- ✅ System monitoring in place
- ✅ Backups configured
- ✅ Documentation complete
- ✅ System running smoothly

---

## Summary

### Implementation Checklist

**Phase 0**: Preparation ✅
- [ ] Codebase review
- [ ] Branch creation
- [ ] Backup creation

**Phase 1**: Docker Infrastructure ✅
- [ ] Dependencies added
- [ ] Dockerfiles created
- [ ] Docker Compose updated
- [ ] Hot reload tested

**Phase 2**: Celery Core Setup ✅
- [ ] Celery app created
- [ ] Task utilities created
- [ ] Configuration complete

**Phase 3**: Task Implementation ✅
- [ ] Profiling task implemented
- [ ] Job search task implemented
- [ ] Async handling resolved

**Phase 4**: API Migration ✅
- [ ] Profiling endpoint migrated
- [ ] Job search endpoint migrated
- [ ] BackgroundTasks removed

**Phase 5**: Status Endpoint ✅
- [ ] Status endpoint implemented
- [ ] Progress calculation
- [ ] Workflow tracking

**Phase 6**: Prioritization & Scheduling ✅
- [ ] Priority queues configured
- [ ] Scheduled tasks implemented
- [ ] Celery Beat running

**Phase 7**: Error Handling & Sentry ✅
- [ ] Sentry integrated
- [ ] Alerts implemented
- [ ] Error tracking working

**Phase 8**: Testing ✅
- [ ] Unit tests written
- [ ] Integration tests written
- [ ] Load testing completed
- [ ] End-to-end tests passed

**Phase 9**: Production Deployment ✅
- [ ] VPS configured
- [ ] Caddy set up
- [ ] Services deployed
- [ ] SSL working

**Phase 10**: Post-Deployment ✅
- [ ] Monitoring in place
- [ ] Backups configured
- [ ] Documentation complete

---

## Notes

### About Flower vs Sentry

**Flower** is for **Celery-specific monitoring**:
- Task queue status
- Worker health
- Task execution history
- Real-time task monitoring

**Sentry** is for **error tracking and alerting**:
- Application errors
- Exception tracking
- Performance monitoring
- Alert notifications

They serve different purposes and complement each other.

### Async Task Execution

Celery tasks are synchronous by default. To run async workflows, we use `nest-asyncio` or `celery[async]`. Start with `nest-asyncio` for simplicity, migrate to `celery[async]` if needed.

### Priority Queues

Priority queues require:
1. Multiple queues configured (`high_priority`, `default`)
2. Worker consuming from multiple queues
3. Tasks routed to appropriate queue
4. Worker processes high priority queue first

---

**Document Status**: Implementation Plan Complete  
**Next Action**: Begin Phase 0 - Preparation & Environment Setup
