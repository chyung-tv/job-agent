# Celery Migration Guide: From FastAPI BackgroundTasks to Celery + Redis

**Status**: Planning  
**Last Updated**: 2026-01-29  
**Author**: Development Team

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Merits of Switching to Celery + Redis](#2-merits-of-switching-to-celery--redis)
3. [Docker Setup for Development](#3-docker-setup-for-development)
4. [Dockerfile for Application](#4-dockerfile-for-application)
5. [Docker Compose Configuration](#5-docker-compose-configuration)
6. [Hot Reload Setup](#6-hot-reload-setup)
7. [Deployment Considerations](#7-deployment-considerations)
8. [Migration Steps](#8-migration-steps)
9. [Clarifying Questions](#9-clarifying-questions)

---

## 1. Current State Analysis

### Current Implementation

Your application currently uses **FastAPI BackgroundTasks** for asynchronous workflow execution:

- **Location**: `src/api/api.py`
- **Pattern**: `background_tasks.add_task(execute_job_searches_from_profile, ...)`
- **Limitations**:
  - Tasks run in the same process as the FastAPI server
  - No task persistence (server crash = lost tasks)
  - No retry mechanism
  - No task prioritization or queuing
  - Cannot scale horizontally (multiple workers)
  - No built-in monitoring or status tracking
  - Tasks block the server process during execution

### Workflow Characteristics

Based on your codebase:
- **Profiling Workflow**: Processes CVs, generates profiles (2-5 minutes)
- **Job Search Workflow**: Multiple steps (discovery, matching, research, fabrication) (5-10 minutes)
- **Multi-run Pattern**: Can trigger multiple job searches in parallel
- **Status Tracking**: Already has `WorkflowExecution` model in database

---

## 2. Merits of Switching to Celery + Redis

### 2.1 Reliability & Persistence

**Current (FastAPI BackgroundTasks)**:
- ❌ Tasks lost if server crashes or restarts
- ❌ No task persistence
- ❌ Tasks tied to server process lifecycle

**With Celery + Redis**:
- ✅ Tasks persisted in Redis message broker
- ✅ Tasks survive server restarts
- ✅ Tasks can be retried automatically on failure
- ✅ Tasks can be scheduled for future execution
- ✅ Tasks can be prioritized (high/low priority queues)

### 2.2 Scalability

**Current (FastAPI BackgroundTasks)**:
- ❌ Single process execution
- ❌ Cannot scale workers independently
- ❌ Long-running tasks block API server
- ❌ Limited concurrency (one task at a time per server)

**With Celery + Redis**:
- ✅ Horizontal scaling: Add more Celery workers as needed
- ✅ API server stays responsive (workers handle tasks separately)
- ✅ Multiple workers can process tasks in parallel
- ✅ Can scale workers independently from API server
- ✅ Better resource utilization (dedicated worker processes)

### 2.3 Monitoring & Observability

**Current (FastAPI BackgroundTasks)**:
- ❌ No built-in monitoring
- ❌ Difficult to track task progress
- ❌ No visibility into task queue
- ❌ Hard to debug failed tasks

**With Celery + Redis**:
- ✅ **Flower**: Web-based monitoring tool for Celery
- ✅ Real-time task status tracking
- ✅ Task history and statistics
- ✅ Queue length monitoring
- ✅ Worker status and health checks
- ✅ Task retry tracking
- ✅ Integration with existing `WorkflowExecution` model

### 2.4 Task Management Features

**Current (FastAPI BackgroundTasks)**:
- ❌ No task prioritization
- ❌ No task scheduling (cron-like)
- ❌ No task chaining or workflows
- ❌ No rate limiting per task type

**With Celery + Redis**:
- ✅ Task prioritization (high/low priority queues)
- ✅ Scheduled tasks (periodic tasks, cron-like)
- ✅ Task chaining (task A → task B → task C)
- ✅ Rate limiting per task type
- ✅ Task routing to specific workers
- ✅ Task result backend (store task results)

### 2.5 Production Readiness

**Current (FastAPI BackgroundTasks)**:
- ⚠️ Suitable for small-scale applications
- ⚠️ Limited error handling
- ⚠️ No built-in retry logic
- ⚠️ Difficult to monitor in production

**With Celery + Redis**:
- ✅ Industry-standard solution (used by Instagram, Pinterest, etc.)
- ✅ Robust error handling and retry mechanisms
- ✅ Production-tested at scale
- ✅ Rich ecosystem (monitoring, tooling, documentation)
- ✅ Better suited for VPS deployment

### 2.6 Cost-Benefit Analysis

**Additional Infrastructure**:
- Redis server (can run in Docker, minimal resource usage)
- Celery worker processes (can run on same VPS as API server)

**Benefits**:
- Better reliability (fewer lost tasks)
- Better scalability (handle more concurrent workflows)
- Better monitoring (easier debugging and optimization)
- Better user experience (faster API responses, better status tracking)

**Verdict**: The benefits significantly outweigh the minimal infrastructure overhead, especially for production deployment.

---

## 3. Docker Setup for Development

### 3.1 Architecture Overview

```
┌─────────────────┐
│   FastAPI API   │  (Port 8000)
│   (Hot Reload)  │
└────────┬────────┘
         │
         │ Enqueues tasks
         ▼
┌─────────────────┐
│     Redis       │  (Port 6379)
│  (Message Broker)│
└────────┬────────┘
         │
         │ Distributes tasks
         ▼
┌─────────────────┐
│ Celery Worker   │  (Background)
│  (Processes)    │
└─────────────────┘
```

### 3.2 Services Needed

1. **PostgreSQL** (existing) - Database
2. **Redis** (new) - Message broker for Celery
3. **FastAPI App** (new) - API server with hot reload
4. **Celery Worker** (new) - Background task processor
5. **Flower** (optional) - Celery monitoring dashboard

---

## 4. Dockerfile for Application

### 4.1 Multi-Stage Dockerfile

Create `Dockerfile` in project root:

```dockerfile
# Stage 1: Build stage
FROM python:3.13-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (if using uv) or pip
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

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.2 Development-Optimized Dockerfile (Hot Reload)

For development with hot reload, create `Dockerfile.dev`:

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

# Expose port
EXPOSE 8000

# Development command with hot reload
CMD ["uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

**Note**: In docker-compose, we'll mount the source code as a volume, so changes reflect immediately.

---

## 5. Docker Compose Configuration

### 5.1 Complete docker-compose.yml

Update your `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:16-alpine
    container_name: job-agent-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-job_agent}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - job-agent-network

  # Redis Message Broker
  redis:
    image: redis:7-alpine
    container_name: job-agent-redis
    restart: unless-stopped
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - job-agent-network

  # FastAPI Application (with hot reload for development)
  api:
    build:
      context: .
      dockerfile: Dockerfile.dev
    container_name: job-agent-api
    restart: unless-stopped
    ports:
      - "${API_PORT:-8000}:8000"
    environment:
      # Database
      DATABASE_URL: postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-job_agent}
      # Redis
      REDIS_URL: redis://redis:6379/0
      # Celery
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      # Other environment variables
      PYTHONPATH: /app
    volumes:
      # Mount source code for hot reload
      - ./src:/app/src
      - ./test:/app/test
      - ./docs:/app/docs
      - ./pyproject.toml:/app/pyproject.toml
      # Exclude node_modules, .git, etc. (handled by .dockerignore)
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - job-agent-network
    command: >
      sh -c "
        uvicorn src.api.api:app 
        --host 0.0.0.0 
        --port 8000 
        --reload 
        --reload-dir /app/src
      "

  # Celery Worker
  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile.dev
    container_name: job-agent-celery-worker
    restart: unless-stopped
    environment:
      # Database
      DATABASE_URL: postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-job_agent}
      # Redis
      REDIS_URL: redis://redis:6379/0
      # Celery
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      PYTHONPATH: /app
    volumes:
      # Mount source code for hot reload
      - ./src:/app/src
      - ./test:/app/test
      - ./pyproject.toml:/app/pyproject.toml
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      api:
        condition: service_started
    networks:
      - job-agent-network
    command: >
      sh -c "
        celery -A src.celery_app worker 
        --loglevel=info 
        --concurrency=2
        --reload
      "

  # Flower - Celery Monitoring (Optional)
  flower:
    build:
      context: .
      dockerfile: Dockerfile.dev
    container_name: job-agent-flower
    restart: unless-stopped
    ports:
      - "${FLOWER_PORT:-5555}:5555"
    environment:
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      PYTHONPATH: /app
    depends_on:
      redis:
        condition: service_healthy
      celery-worker:
        condition: service_started
    networks:
      - job-agent-network
    command: >
      sh -c "
        celery -A src.celery_app flower 
        --port=5555 
        --broker=redis://redis:6379/0
      "

volumes:
  postgres_data:
  redis_data:

networks:
  job-agent-network:
    driver: bridge
```

### 5.2 Environment Variables

Create `.env` file (add to `.gitignore`):

```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=job_agent
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# API
API_PORT=8000

# Flower (Optional)
FLOWER_PORT=5555

# Add your other environment variables here
# SERPAPI_KEY=...
# OPENAI_API_KEY=...
# etc.
```

### 5.3 .dockerignore

Ensure `.dockerignore` exists:

```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info
dist
build
.git
.gitignore
.env
.venv
venv/
env/
*.log
.DS_Store
.vscode
.idea
node_modules
```

---

## 6. Hot Reload Setup

### 6.1 How Hot Reload Works

With the Docker Compose configuration above:

1. **Source Code Mounting**: Your `src/` directory is mounted as a volume
2. **Uvicorn `--reload`**: Watches for file changes in `/app/src`
3. **Celery `--reload`**: Restarts worker when code changes
4. **Immediate Reflection**: Changes to Python files trigger automatic reload

### 6.2 Development Workflow

```bash
# Start all services
docker-compose up

# Or start in background
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f celery-worker

# Make code changes in your editor
# → Changes automatically reflected in containers

# Stop services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

### 6.3 Hot Reload Limitations

- **Database migrations**: May need to restart containers
- **New dependencies**: Need to rebuild images (`docker-compose build`)
- **Environment variables**: May need container restart
- **Celery task code**: Worker reloads automatically, but may take a few seconds

### 6.4 Testing Hot Reload

1. Start containers: `docker-compose up`
2. Make a change to `src/api/api.py` (e.g., add a print statement)
3. Save the file
4. Check logs: `docker-compose logs api` - you should see reload message
5. Test API endpoint - changes should be live

---

## 7. Deployment Considerations

### 7.1 Production Dockerfile

For production, use the multi-stage Dockerfile (Section 4.1) without hot reload:

```dockerfile
# Use production Dockerfile
docker-compose -f docker-compose.prod.yml up
```

### 7.2 Production docker-compose.prod.yml

Create `docker-compose.prod.yml` for production:

```yaml
version: '3.8'

services:
  postgres:
    # ... same as dev, but consider managed database instead

  redis:
    # ... same as dev, but consider managed Redis (e.g., Redis Cloud)

  api:
    build:
      context: .
      dockerfile: Dockerfile  # Use production Dockerfile
    restart: always
    environment:
      # Use production environment variables
    # Remove volume mounts (code baked into image)
    command: >
      uvicorn src.api.api:app 
      --host 0.0.0.0 
      --port 8000 
      --workers 4  # Multiple workers for production
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    # Remove volume mounts
    command: >
      celery -A src.celery_app worker 
      --loglevel=info 
      --concurrency=4  # More workers for production
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
    # Can scale workers: docker-compose up --scale celery-worker=3

  flower:
    # ... same as dev, but consider authentication
```

### 7.3 VPS Deployment Steps

1. **Prepare VPS**:
   ```bash
   # Install Docker and Docker Compose
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```

2. **Clone Repository**:
   ```bash
   git clone <your-repo>
   cd job-agent
   ```

3. **Set Environment Variables**:
   ```bash
   cp .env.example .env
   # Edit .env with production values
   ```

4. **Build and Start**:
   ```bash
   docker-compose -f docker-compose.prod.yml build
   docker-compose -f docker-compose.prod.yml up -d
   ```

5. **Set Up Reverse Proxy** (Nginx):
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

6. **Set Up SSL** (Let's Encrypt):
   ```bash
   certbot --nginx -d your-domain.com
   ```

### 7.4 Monitoring in Production

- **Flower**: Access at `http://your-vps:5555` (add authentication!)
- **Logs**: `docker-compose logs -f`
- **Health Checks**: Use `/health` endpoint
- **Resource Monitoring**: `docker stats`

### 7.5 Scaling Workers

```bash
# Scale Celery workers
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=3

# Scale API workers (use multiple API containers or uvicorn workers)
# Option 1: Multiple containers
docker-compose -f docker-compose.prod.yml up -d --scale api=2

# Option 2: Use uvicorn workers (in Dockerfile CMD)
CMD ["uvicorn", "src.api.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## 8. Migration Steps

### Phase 1: Add Dependencies

Update `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies ...
    "celery>=5.3.0",
    "redis>=5.0.0",
    "flower>=2.0.0",  # Optional, for monitoring
]
```

### Phase 2: Create Celery App

Create `src/celery_app.py`:

```python
"""Celery application configuration."""
from celery import Celery
import os

# Get Redis URL from environment
redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "job_agent",
    broker=redis_url,
    backend=redis_url,
    include=["src.tasks.profiling_task", "src.tasks.job_search_task"],
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)
```

### Phase 3: Create Celery Tasks

Create `src/tasks/__init__.py` (empty file)

Create `src/tasks/profiling_task.py`:

```python
"""Celery task for profiling workflow."""
from src.celery_app import celery_app
from src.workflow.profiling_workflow import ProfilingWorkflow
from src.workflow.profiling_context import ProfilingWorkflowContext
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="profiling_workflow")
def execute_profiling_workflow(self, context_data: dict):
    """Execute profiling workflow as Celery task.
    
    Args:
        context_data: Serialized ProfilingWorkflowContext data
        
    Returns:
        Serialized context with results
    """
    try:
        # Reconstruct context from dict
        context = ProfilingWorkflowContext(**context_data)
        
        # Execute workflow
        workflow = ProfilingWorkflow()
        result = await workflow.run(context)
        
        # Return serialized result
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Profiling workflow failed: {e}", exc_info=True)
        # Retry task
        raise self.retry(exc=e, countdown=60, max_retries=3)
```

Create `src/tasks/job_search_task.py`:

```python
"""Celery task for job search workflow."""
from src.celery_app import celery_app
from src.workflow.job_search_workflow import JobSearchWorkflow
from src.workflow.base_context import JobSearchWorkflowContext
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="job_search_workflow")
def execute_job_search_workflow(self, context_data: dict):
    """Execute job search workflow as Celery task.
    
    Args:
        context_data: Serialized JobSearchWorkflowContext data
        
    Returns:
        Serialized context with results
    """
    try:
        # Reconstruct context from dict
        context = JobSearchWorkflowContext(**context_data)
        
        # Execute workflow
        workflow = JobSearchWorkflow()
        result = await workflow.run(context)
        
        # Return serialized result
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Job search workflow failed: {e}", exc_info=True)
        # Retry task
        raise self.retry(exc=e, countdown=60, max_retries=3)
```

### Phase 4: Update API Endpoints

Update `src/api/api.py`:

```python
from src.celery_app import celery_app
from src.tasks.profiling_task import execute_profiling_workflow
from src.tasks.job_search_task import execute_job_search_workflow

@app.post("/workflow/profiling")
async def run_profiling_workflow(context: ProfilingWorkflow.Context):
    """Run profiling workflow asynchronously."""
    # Create run_id and execution record (status: pending)
    # ... existing code ...
    
    # Enqueue Celery task
    task = execute_profiling_workflow.delay(context.model_dump(mode="json"))
    
    # Return 202 Accepted with run_id
    return JSONResponse(
        status_code=HTTPStatus.ACCEPTED,
        content={
            "run_id": str(context.run_id),
            "execution_id": str(execution_id),
            "task_id": task.id,
            "status": "pending",
            "status_url": f"/workflow/status/{context.run_id}",
        }
    )

@app.get("/workflow/status/{run_id}")
async def get_workflow_status(run_id: UUID):
    """Get workflow execution status."""
    # Query WorkflowExecution from database
    # Return status, current_node, progress, etc.
    # ... implementation ...
```

### Phase 5: Test Migration

1. Start Docker Compose: `docker-compose up`
2. Test profiling endpoint: `POST /workflow/profiling`
3. Check task in Flower: `http://localhost:5555`
4. Poll status endpoint: `GET /workflow/status/{run_id}`
5. Verify workflow completes successfully

---

## 9. Clarifying Questions

Before proceeding with the migration, I'd like to clarify a few points:

### 9.1 Infrastructure & Deployment

1. **VPS Provider**: Which VPS provider are you planning to use? (DigitalOcean, AWS EC2, Linode, etc.)
   - This affects recommended instance sizes and setup steps

   i am going to use hertzner cloud

2. **Database**: Are you planning to:
   - Keep PostgreSQL in Docker on the VPS? Yes
   - Use a managed database service (e.g., AWS RDS, DigitalOcean Managed Database)? No
   - This affects backup strategies and scaling

3. **Redis**: Are you planning to:
   - Run Redis in Docker on the VPS? Yes    
   - Use a managed Redis service (e.g., Redis Cloud, AWS ElastiCache)? No
   - Managed services provide better reliability but add cost

4. **Domain & SSL**: Do you have a domain name? Will you use Let's Encrypt for SSL? i am going to use caddy for domain routing, it should handle the ssl certificate for me.

### 9.2 Workflow & Task Design

5. **Task Priority**: Do you need task prioritization?
   - E.g., premium users get higher priority queues
   - Or all tasks are equal priority yess

6. **Task Scheduling**: Do you need scheduled/recurring tasks?
   - E.g., daily job search runs, periodic profile updates, yes i plan to use cron-like scheduling for daily job search runs.
   - Celery supports cron-like scheduling

7. **Task Results**: Do you need to store task results?
   - Currently, results are stored in database via `WorkflowExecution`
   - Celery can also store results in Redis (optional) i think db is enuf unless you think otherwise. i dont see the need to store results in redis.

8. **Error Handling**: What should happen when a task fails after max retries?
   - Send email notification? no
   - Log to error tracking service (Sentry)? yes, and what is flower for if we use sentry?
   - Update database status? yes

### 9.3 Development Workflow

9. **Hot Reload Preference**: Do you want hot reload for:
   - API server only? yes
   - Celery workers too? i guess yes at least for development.
   - Both (as configured above)?

10. **Local Development**: Will developers run:
    - Everything in Docker?
    - Some services locally (e.g., PostgreSQL locally, API in Docker)? i currently run everything in docker, thats better for deploymoent and dev both
    - This affects docker-compose configuration

### 9.4 Monitoring & Observability

11. **Monitoring Tools**: Besides Flower, do you want:
    - Application performance monitoring (APM)? no
    - Error tracking (Sentry)?
    - Log aggregation (ELK stack, Loki)? no
    - Metrics (Prometheus, Grafana)? no

12. **Alerting**: Do you need alerts for:
    - Failed tasks? yes
    - Queue length thresholds? if you mean hitting the rate limit, yes i think we should have that.
    - Worker health? yes

### 9.5 Migration Strategy

13. **Migration Approach**: Do you want to:
    - Migrate all workflows at once? yes
    - Migrate incrementally (profiling first, then job search)?no
    - Keep both systems running during transition? no

14. **Backward Compatibility**: Do you need to support:
    - Old API clients that expect synchronous responses? no
    - Gradual migration of existing integrations? no

---

## Summary

**Key Takeaways**:

1. **Celery + Redis provides significant benefits** over FastAPI BackgroundTasks:
   - Better reliability, scalability, monitoring, and production readiness

2. **Docker Compose setup** includes:
   - PostgreSQL, Redis, FastAPI API, Celery Worker, Flower (optional)
   - Hot reload for development
   - Production-ready configuration

3. **Hot reload works** by:
   - Mounting source code as volumes
   - Using `--reload` flags in uvicorn and celery
   - Changes reflect immediately in containers

4. **Deployment to VPS** requires:
   - Production Dockerfile (no hot reload)
   - Production docker-compose.yml
   - Reverse proxy (Nginx)
   - SSL certificate (Let's Encrypt)

5. **Migration path**:
   - Add dependencies → Create Celery app → Create tasks → Update API → Test

**Next Steps**:
1. Answer clarifying questions above
2. Review and adjust Docker configuration
3. Implement Celery tasks
4. Test locally with Docker Compose
5. Deploy to VPS

---

**Document Status**: Ready for Review  
**Next Action**: Answer clarifying questions and proceed with implementation
