# Implementation Guide: Celery + Redis + FastAPI

This document provides detailed implementation guidance for integrating Celery, Redis, and FastAPI into the job-agent application.

## Table of Contents

1. [Setup & Configuration](#setup--configuration)
2. [FastAPI Integration](#fastapi-integration)
3. [Celery Task Implementation](#celery-task-implementation)
4. [Database Models](#database-models)
5. [API Endpoints](#api-endpoints)
6. [Error Handling & Retries](#error-handling--retries)
7. [Monitoring & Observability](#monitoring--observability)
8. [Testing Strategy](#testing-strategy)

---

## Setup & Configuration

### 1. Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies
    "celery>=5.3.0",
    "redis>=5.0.0",
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "python-multipart>=0.0.6",  # For file uploads
]
```

### 2. Environment Variables

Add to `.env`:

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

### 3. Celery Configuration

Create `src/celery_app.py`:

```python
"""Celery application configuration."""
from celery import Celery
from kombu import Queue
import os
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "job_agent",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=[
        "src.tasks.profiling",
        "src.tasks.discovery",
        "src.tasks.matching",
        "src.tasks.job_processing",
    ]
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task routing (separate queues for different task types)
    task_routes={
        "src.tasks.profiling.*": {"queue": "profiling"},
        "src.tasks.discovery.*": {"queue": "discovery"},
        "src.tasks.matching.*": {"queue": "matching"},
        "src.tasks.job_processing.*": {"queue": "job_processing"},
    },
    
    # Queue definitions
    task_queues=(
        Queue("profiling", routing_key="profiling"),
        Queue("discovery", routing_key="discovery"),
        Queue("matching", routing_key="matching"),
        Queue("job_processing", routing_key="job_processing"),
    ),
    
    # Rate limiting (prevent API overload)
    task_annotations={
        "src.tasks.profiling.build_profile_task": {"rate_limit": "10/m"},  # 10 per minute
        "src.tasks.discovery.search_jobs_task": {"rate_limit": "5/m"},
        "src.tasks.matching.screen_jobs_task": {"rate_limit": "20/m"},
        "src.tasks.job_processing.process_job_task": {"rate_limit": "5/m"},
    },
    
    # Result expiration (cleanup old results)
    result_expires=3600,  # 1 hour
    
    # Worker configuration
    worker_prefetch_multiplier=1,  # Fair task distribution
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,  # Reject if worker dies
    
    # Retry configuration
    task_default_retry_delay=60,  # 1 minute default
    task_max_retries=3,
)
```

---

## FastAPI Integration

### 1. FastAPI Application Setup

Create `src/api/main.py`:

```python
"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import profiling, discovery, matching, job_processing

app = FastAPI(
    title="Job Agent API",
    description="API for job search automation and application material generation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(profiling.router, prefix="/api/v1/profiling", tags=["profiling"])
app.include_router(discovery.router, prefix="/api/v1/discovery", tags=["discovery"])
app.include_router(matching.router, prefix="/api/v1/matching", tags=["matching"])
app.include_router(job_processing.router, prefix="/api/v1/jobs", tags=["job_processing"])

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
```

### 2. Database Session Dependency

Create `src/api/dependencies.py`:

```python
"""FastAPI dependencies."""
from fastapi import Depends
from sqlalchemy.orm import Session
from src.database.session import SessionLocal

def get_db() -> Session:
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## Celery Task Implementation

### 1. Profile Building Task

Create `src/tasks/profiling.py`:

```python
"""Celery tasks for user profile building."""
from celery import Task
from typing import List, Optional
import uuid
from datetime import datetime
from src.celery_app import celery_app
from src.database.session import SessionLocal
from src.database.models import UserProfile
from src.profiling.profile import build_profile_from_pdfs

class DatabaseTask(Task):
    """Base task class with database session management."""
    
    def __call__(self, *args, **kwargs):
        """Execute task with database session."""
        with SessionLocal() as session:
            return super().__call__(session, *args, **kwargs)

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),  # Retry on any exception
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def build_profile_task(
    self,
    session: SessionLocal,
    profile_id: str,
    pdf_paths: List[str],
    webhook_url: Optional[str] = None
) -> str:
    """Build user profile from PDFs.
    
    Args:
        session: Database session (injected by DatabaseTask)
        profile_id: UUID of UserProfile record
        pdf_paths: List of PDF file paths to process
        webhook_url: Optional webhook URL to call on completion
        
    Returns:
        profile_id (for result tracking)
        
    Raises:
        Retry: If transient error occurs
        Exception: If permanent error occurs
    """
    try:
        # Load profile from database
        profile = session.query(UserProfile).filter_by(id=uuid.UUID(profile_id)).first()
        if not profile:
            raise ValueError(f"Profile {profile_id} not found")
        
        # Idempotency check
        if profile.status == "completed":
            return str(profile.id)
        
        # Update status to processing
        profile.status = "processing"
        profile.started_at = datetime.utcnow()
        session.commit()
        
        # Build profile (actual business logic)
        profile_text = build_profile_from_pdfs(pdf_paths)
        
        # Save result to database
        profile.profile_text = profile_text
        profile.status = "completed"
        profile.completed_at = datetime.utcnow()
        session.commit()
        
        # Call webhook if provided
        if webhook_url:
            try:
                import requests
                requests.post(
                    webhook_url,
                    json={
                        "profile_id": profile_id,
                        "status": "completed",
                        "completed_at": profile.completed_at.isoformat()
                    },
                    timeout=5
                )
            except Exception as e:
                # Log webhook failure but don't fail task
                print(f"Webhook call failed: {e}")
        
        return str(profile.id)
        
    except Exception as exc:
        # Update database on failure
        if 'profile' in locals():
            profile.status = "failed"
            profile.error_message = str(exc)
            profile.failed_at = datetime.utcnow()
            session.commit()
        
        # Retry if retryable error
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        else:
            # Max retries reached, don't retry again
            raise
```

### 2. Job Discovery Task

Create `src/tasks/discovery.py`:

```python
"""Celery tasks for job discovery."""
from celery import Task
from typing import Optional
import uuid
from datetime import datetime
from src.celery_app import celery_app
from src.database.session import SessionLocal
from src.database.models import JobSearch
from src.discovery.serpapi_service import SerpApiJobsService

class DatabaseTask(Task):
    """Base task class with database session management."""
    
    def __call__(self, *args, **kwargs):
        with SessionLocal() as session:
            return super().__call__(session, *args, **kwargs)

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def search_jobs_task(
    self,
    session: SessionLocal,
    job_search_id: str,
    query: str,
    location: str,
    num_results: int = 30,
    webhook_url: Optional[str] = None
) -> str:
    """Search for jobs using SerpAPI.
    
    Args:
        session: Database session
        job_search_id: UUID of JobSearch record
        query: Job search query
        location: Location for search
        num_results: Number of results to fetch
        webhook_url: Optional webhook URL
        
    Returns:
        job_search_id
    """
    try:
        job_search = session.query(JobSearch).filter_by(id=uuid.UUID(job_search_id)).first()
        if not job_search:
            raise ValueError(f"JobSearch {job_search_id} not found")
        
        if job_search.status == "completed":
            return str(job_search.id)
        
        job_search.status = "processing"
        job_search.started_at = datetime.utcnow()
        session.commit()
        
        # Search jobs
        service = SerpApiJobsService.create()
        jobs = service.search(query, location, num_results)
        
        # Save jobs to database (implementation depends on your service)
        # ... save logic here ...
        
        job_search.status = "completed"
        job_search.completed_at = datetime.utcnow()
        session.commit()
        
        # Call webhook
        if webhook_url:
            # ... webhook logic ...
            pass
        
        return str(job_search.id)
        
    except Exception as exc:
        if 'job_search' in locals():
            job_search.status = "failed"
            job_search.error_message = str(exc)
            session.commit()
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        else:
            raise
```

---

## Database Models

### 1. Update UserProfile Model

Add to `src/database/models.py`:

```python
class UserProfile(Base):
    # ... existing fields ...
    
    # Celery integration fields
    celery_task_id = Column(String(255), nullable=True, doc="Celery task ID for correlation")
    status = Column(String(50), nullable=False, default="pending")
    # pending, processing, completed, failed
    
    # Progress tracking
    progress_percent = Column(Integer, default=0, doc="Progress 0-100")
    
    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Webhook
    webhook_url = Column(String(500), nullable=True)
```

### 2. Update JobSearch Model

Similar fields for JobSearch:

```python
class JobSearch(Base):
    # ... existing fields ...
    
    celery_task_id = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    progress_percent = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    webhook_url = Column(String(500), nullable=True)
```

---

## API Endpoints

### 1. Profiling Endpoints

Create `src/api/routes/profiling.py`:

```python
"""Profiling API endpoints."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import os
from pathlib import Path
from src.api.dependencies import get_db
from src.database.models import UserProfile
from src.tasks.profiling import build_profile_task

router = APIRouter()

@router.post("", status_code=202)
async def create_profile(
    pdf_files: List[UploadFile] = File(...),
    webhook_url: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a profile processing task.
    
    Returns immediately with profile_id and status URL.
    """
    # Save uploaded files
    upload_dir = Path("/tmp/uploads")
    upload_dir.mkdir(exist_ok=True)
    
    pdf_paths = []
    for file in pdf_files:
        file_id = uuid.uuid4()
        file_path = upload_dir / f"{file_id}_{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        pdf_paths.append(str(file_path))
    
    # Create database record
    profile = UserProfile(
        id=uuid.uuid4(),
        status="pending",
        source_pdfs=pdf_paths,
        webhook_url=webhook_url
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    
    # Trigger Celery task
    task = build_profile_task.delay(
        profile_id=str(profile.id),
        pdf_paths=pdf_paths,
        webhook_url=webhook_url
    )
    
    # Store task ID for correlation
    profile.celery_task_id = task.id
    db.commit()
    
    return {
        "profile_id": str(profile.id),
        "status": "pending",
        "status_url": f"/api/v1/profiling/{profile.id}/status",
        "result_url": f"/api/v1/profiling/{profile.id}"
    }

@router.get("/{profile_id}/status")
async def get_profile_status(
    profile_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get profile processing status."""
    profile = db.query(UserProfile).filter_by(id=profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    response = {
        "profile_id": str(profile.id),
        "status": profile.status,
        "created_at": profile.created_at.isoformat(),
    }
    
    if profile.status == "processing":
        response["progress"] = profile.progress_percent or 0
    
    if profile.status == "completed":
        response["completed_at"] = profile.completed_at.isoformat()
        response["result_url"] = f"/api/v1/profiling/{profile.id}"
    
    if profile.status == "failed":
        response["error"] = profile.error_message
        response["failed_at"] = profile.failed_at.isoformat() if profile.failed_at else None
    
    return response

@router.get("/{profile_id}")
async def get_profile(
    profile_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get completed profile result."""
    profile = db.query(UserProfile).filter_by(id=profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if profile.status != "completed":
        raise HTTPException(
            status_code=202,
            detail=f"Profile not ready. Status: {profile.status}"
        )
    
    return {
        "profile_id": str(profile.id),
        "profile_text": profile.profile_text,
        "completed_at": profile.completed_at.isoformat()
    }
```

---

## Error Handling & Retries

### 1. Retry Strategy

Configure retries based on error type:

```python
from celery.exceptions import Retry

@celery_app.task(
    bind=True,
    autoretry_for=(RateLimitError, TimeoutError),  # Only retry these
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
)
def api_call_task(self, ...):
    try:
        # API call
        result = external_api.call()
        return result
    except RateLimitError as exc:
        # Retry with backoff
        raise self.retry(exc=exc, countdown=60)
    except ValueError as exc:
        # Don't retry - permanent error
        raise
```

### 2. Dead Letter Queue

For permanent failures:

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    reject_on_worker_lost=True,
)
def process_task(self, ...):
    try:
        # Process
        pass
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            # Max retries reached - send to dead letter queue
            # Update database status to 'failed'
            # Log error
            raise
        raise self.retry(exc=exc)
```

---

## Monitoring & Observability

### 1. Flower (Celery Monitoring)

Install and run Flower:

```bash
pip install flower
celery -A src.celery_app flower --port=5555
```

Access at `http://localhost:5555`

### 2. Database Queries for Status

Create monitoring endpoints:

```python
@router.get("/admin/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get system statistics."""
    pending = db.query(UserProfile).filter_by(status="pending").count()
    processing = db.query(UserProfile).filter_by(status="processing").count()
    completed = db.query(UserProfile).filter_by(status="completed").count()
    failed = db.query(UserProfile).filter_by(status="failed").count()
    
    return {
        "profiles": {
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
        }
    }
```

---

## Testing Strategy

### 1. Unit Tests for Tasks

```python
import pytest
from src.tasks.profiling import build_profile_task

def test_build_profile_task_success(mocker, db_session):
    """Test successful profile building."""
    # Create test profile
    profile = UserProfile(id=uuid.uuid4(), status="pending")
    db_session.add(profile)
    db_session.commit()
    
    # Mock PDF processing
    mocker.patch("src.tasks.profiling.build_profile_from_pdfs", return_value="profile text")
    
    # Execute task
    result = build_profile_task(
        db_session,
        profile_id=str(profile.id),
        pdf_paths=["/tmp/test.pdf"]
    )
    
    # Verify
    assert result == str(profile.id)
    db_session.refresh(profile)
    assert profile.status == "completed"
    assert profile.profile_text == "profile text"
```

### 2. Integration Tests for API

```python
import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_create_profile_endpoint(mocker):
    """Test profile creation endpoint."""
    # Mock Celery task
    mocker.patch("src.api.routes.profiling.build_profile_task.delay")
    
    # Upload file
    files = [("pdf_files", ("test.pdf", b"fake pdf content", "application/pdf"))]
    response = client.post("/api/v1/profiling", files=files)
    
    assert response.status_code == 202
    data = response.json()
    assert "profile_id" in data
    assert data["status"] == "pending"
    assert "status_url" in data
```

---

## Running the Application

### 1. Start Redis

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### 2. Start Celery Worker

```bash
celery -A src.celery_app worker --loglevel=info --queues=profiling,discovery,matching,job_processing
```

### 3. Start FastAPI

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Start Flower (Optional)

```bash
celery -A src.celery_app flower --port=5555
```

---

## Best Practices Summary

1. ✅ **Database is source of truth** - Always query DB for status
2. ✅ **Return resource IDs** - Not Celery task IDs
3. ✅ **HTTP 202 for async** - Return immediately, provide status URL
4. ✅ **Idempotent tasks** - Safe to retry
5. ✅ **Update DB on failure** - Store error messages
6. ✅ **Use webhooks** - Better than polling for production
7. ✅ **Rate limiting** - Prevent API overload
8. ✅ **Monitoring** - Flower + database queries
9. ✅ **Proper error handling** - Retry transient, fail permanent
10. ✅ **Task correlation** - Store task_id in DB for debugging
