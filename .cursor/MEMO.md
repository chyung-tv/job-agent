# MEMO.md — Long-Term Memory Bank

> **Purpose:** This is the project's "institutional memory" — a living document that captures hard-won lessons, architectural decisions, and gotchas that must survive across development sessions. Consult this before making architectural changes.

---

## Table of Contents

1. [Historical Context & Regressions](#1-historical-context--regressions)
2. [Architecture & "Vibe" Decisions](#2-architecture--vibe-decisions)
3. [Gotchas & Constraints](#3-gotchas--constraints)
4. [Project Evolution Timeline](#4-project-evolution-timeline)
5. [Critical Lessons Summary](#5-critical-lessons-summary)

---

## 1. Historical Context & Regressions

### 1.1 The Event Loop Fix (Worker Lifespan Pattern)

**Bug:** "Event loop is closed" errors during job matching.

**Symptoms:**
- Celery workers would log `Failed to match job ... Event loop is closed`
- Some jobs would fail to match while others succeeded
- Non-deterministic failures across different ForkPoolWorkers
- httpx clients (used by pydantic-ai/google-genai) failing to clean up properly

**Root Cause:** Async/await mismatch when running async Pydantic AI agents inside synchronous Celery tasks. Using `asyncio.run()` creates and closes an event loop per task. When the loop closes, httpx connections attached to it cannot clean up properly. Subsequent tasks trying to reuse those connections encounter "Event loop is closed" errors.

**Solution:** **Worker Lifespan Pattern** — Create a long-lived event loop per worker process that survives across all tasks.

**Implementation (`src/tasks/worker_lifecycle.py`):**

```python
import asyncio
import threading
from celery.signals import worker_process_init, worker_process_shutdown

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
    _worker_loop.call_soon_threadsafe(_worker_loop.stop)
    if _loop_thread and _loop_thread.is_alive():
        _loop_thread.join(timeout=5.0)
    if not _worker_loop.is_closed():
        _worker_loop.close()
    _worker_loop = None
    _loop_thread = None

def run_in_worker_loop(coro):
    """Run a coroutine in the worker's long-lived event loop."""
    if _worker_loop is None:
        raise RuntimeError("Worker event loop not initialized")
    future = asyncio.run_coroutine_threadsafe(coro, _worker_loop)
    return future.result()  # Block until complete
```

**Usage in Celery tasks:**

```python
from src.tasks.worker_lifecycle import run_in_worker_loop

@celery_app.task(bind=True, name="job_search_workflow")
def execute_job_search_workflow(self, context_data, run_id=None):
    workflow = JobSearchWorkflow()
    # CRITICAL: Use run_in_worker_loop, NOT asyncio.run()
    result = run_in_worker_loop(workflow.run(context))
    return result.model_dump(mode="json")
```

**Why it works:**
1. Event loop is created once when worker process starts (`worker_process_init` signal)
2. Loop runs in a background daemon thread (`run_forever()`)
3. All tasks use `asyncio.run_coroutine_threadsafe()` to schedule work on the shared loop
4. httpx clients created by pydantic-ai/google-genai all attach to the same loop
5. Connections can properly clean up between tasks because the loop stays alive
6. Loop gracefully closes when worker shuts down (`worker_process_shutdown` signal)

**Files affected:**
- `src/tasks/worker_lifecycle.py` (new module)
- `src/celery_app.py` (imports worker_lifecycle to register signals)
- `src/tasks/profiling_task.py` (uses `run_in_worker_loop`)
- `src/tasks/job_search_task.py` (uses `run_in_worker_loop`)

**Key insight:** The problem was never about "allowing nested loops" — it was about the loop's **lifetime**. The loop must live as long as the worker process, not per-task.

---

### 1.2 WorkflowExecution Table Removal

**Bug:** Duplicate state tracking between `WorkflowExecution` and Celery/Flower.

**Problem:** `WorkflowExecution` stored `status`, `current_node`, `context_snapshot` — all of which Celery/Flower already track. This created:
- Duplicate writes on every status change
- Confusion about which source of truth to query
- Extra database roundtrips

**Solution:** Remove `WorkflowExecution` entirely. Add `task_id` to `Run` model. Use:
- `Run.status` and `Run.error_message` for business state
- `Run.task_id` to link to Flower for live task status
- Celery/Flower for node-level progress

**Files affected:** All workflow nodes, `api.py`, `base_workflow.py`, `tasks/utils.py`

---

### 1.3 UserProfile → Single `user` Table

**Bug:** Fragmented user identity across `user` (auth) and `user_profiles` (domain).

**Problem:** Two tables for "person" caused:
- JOIN complexity when querying user data
- Unclear ownership of fields like `email`, `name`
- Migration headaches for Better Auth integration

**Solution:** Single `user` table (Better Auth default name) with:
- **Auth columns:** id, name, email, emailVerified, image, createdAt, updatedAt
- **Profile columns:** location, profile_text, suggested_job_titles, source_pdfs, references, last_used_at

All FKs now reference `user.id`. The `user_profiles` table is dropped.

---

### 1.4 Prisma Migration Disaster (Prevented)

**Near-miss:** Running `prisma migrate` would have dropped production tables.

**Why:** Prisma compares its schema to the database and tries to "fix" differences. Since SQLAlchemy created the tables, Prisma would see "orphan" tables and attempt to drop them.

**Prevention:**
1. **Two Postgres users:** `job_agent_ui` has NO `CREATE`, `ALTER`, or `DROP` privileges
2. **Documentation:** Prominent warnings in all frontend docs
3. **Workflow:** Only `prisma db pull` (introspect) and `prisma generate` are allowed

---

## 2. Architecture & "Vibe" Decisions

### 2.1 SQLAlchemy as Schema Master

| Layer | Tool | Responsibility |
|-------|------|----------------|
| DDL (schema changes) | SQLAlchemy + Alembic | Single source of truth |
| DRL (reads/writes) | Prisma (frontend), SQLAlchemy (backend) | Runtime access |
| Migrations | Alembic only | Never Prisma |

**Rationale:** "One chef in the kitchen." Prisma's migration system is powerful but conflicts with Alembic. By making SQLAlchemy the master, we avoid schema drift.

---

### 2.2 Server Actions for Workflow Triggers

**Pattern:** All workflow triggers (`POST /workflow/profiling`, etc.) go through Next.js Server Actions.

```
Browser → Server Action → FastAPI Backend
                ↓
         Adds X-API-Key header
```

**Rationale:**
- `API_KEY` never exposed to browser DevTools
- Consistent auth pattern
- Type-safe with Zod schemas

**Files:** `frontend/actions/workflow.ts`

---

### 2.3 SSE for Real-Time Status

**Pattern:** Server-Sent Events via Redis pub/sub for workflow progress.

```
Celery Worker → Redis (run:status:{run_id}) → FastAPI SSE → Browser EventSource
```

**Requirements:**
1. **15-second heartbeat:** Yield `: keep-alive\n\n` to prevent connection drops
2. **Caddy timeout:** `read_timeout 600s` in reverse_proxy config
3. **Next.js proxy:** `/api/workflow/status/[runId]/stream` adds API key server-side

---

### 2.4 Zustand with sessionStorage Persist

**Pattern:** Onboarding state survives page refresh.

```typescript
// store/useOnboardingStore.ts
const useOnboardingStore = create(
  persist(
    (set) => ({
      name: "",
      email: "",
      location: "",
      basic_info: "",
      cv_urls: [],
      addCvUrl: (url) => set((state) => ({ cv_urls: [...state.cv_urls, url] })),
    }),
    {
      name: "onboarding-store",
      storage: createJSONStorage(() => sessionStorage),
    }
  )
);
```

**Rationale:** Users completing the AI "Vibe Check" chat would lose their Cultural Persona summary on accidental refresh. sessionStorage persists within the tab's lifetime.

---

### 2.5 Better Auth Behind Caddy

**Requirement:** Set `advanced: { trustHost: true }` in Better Auth config.

**Why:** Without this, Better Auth generates redirect URLs using `localhost:3000` instead of the public domain. Caddy terminates TLS, but Better Auth doesn't know the original request was HTTPS.

```typescript
// lib/auth.ts
export const auth = betterAuth({
  // ...
  advanced: {
    trustHost: true,
  },
});
```

---

### 2.6 Celery Over BackgroundTasks

**Decision:** Replace FastAPI `BackgroundTasks` with Celery + Redis.

| Feature | BackgroundTasks | Celery |
|---------|-----------------|--------|
| Task persistence | ❌ Lost on crash | ✅ Redis-backed |
| Retry mechanism | ❌ None | ✅ Configurable |
| Monitoring | ❌ None | ✅ Flower |
| Horizontal scaling | ❌ Single process | ✅ Multiple workers |
| Priority queues | ❌ None | ✅ Supported |

---

## 3. Gotchas & Constraints

### 3.1 Docker & Deployment

| Gotcha | Details |
|--------|---------|
| **BuildKit required** | Frontend Dockerfile uses `--mount=type=cache` for npm. Enable with `DOCKER_BUILDKIT=1` |
| **Postgres host port** | Production binds to `127.0.0.1:5433` (not 5432) to avoid conflicts |
| **Volume permissions** | Postgres init scripts only run on empty volume |
| **Container restart** | Use `restart: unless-stopped` for all services |
| **Multi-stage build cache** | `docker compose run` may use stale cached images; use `--no-cache` for first-time setup |
| **Verify packages in Dockerfile** | Add `RUN python -c "import pkg; print('OK')"` after install to fail fast if packages missing |
| **Frontend public/ directory** | Multi-stage `COPY --from=builder` fails silently if source doesn't exist; add `frontend/public/.gitkeep` |
| **NEXT_PUBLIC_* in Docker** | Must be ARG/ENV at build time, not runtime environment; see Lesson 7 |

### 3.2 Database

| Gotcha | Details |
|--------|---------|
| **Two Postgres users** | `job_agent_admin` for migrations, `job_agent_ui` for frontend |
| **Connection pooling** | Use Prisma global singleton to prevent connection exhaustion |
| **Better Auth column names** | Must use camelCase: `emailVerified`, `createdAt`, not snake_case |
| **Alembic search_path** | Hardcode schema in `env.py` if using non-default schema |

### 3.3 Frontend (Next.js 16+)

| Gotcha | Details |
|--------|---------|
| **proxy.ts not middleware.ts** | Next.js 16+ deprecated middleware; use `proxy.ts` with `export function proxy()` |
| **Session cookie name** | Better Auth uses `better-auth.session-token` |
| **Zustand hydration** | Use `useEffect` or `useHasHydrated` to avoid SSR mismatch |
| **PDF iframe sandbox** | Use `sandbox="allow-scripts allow-same-origin"` for security |

### 3.4 Caddy & Networking

| Gotcha | Details |
|--------|---------|
| **SSE read timeout** | Set `read_timeout 600s` in reverse_proxy for long-lived connections |
| **CORS_ORIGINS** | Must include `https://app.yourdomain.com` in production |
| **X-Forwarded-Proto** | Caddy sets this by default; Better Auth needs it for HTTPS detection |
| **Flower Basic Auth** | Generate hash with `caddy hash-password` or `htpasswd -nbB` |

### 3.5 API & Authentication

| Gotcha | Details |
|--------|---------|
| **API_KEY header** | Send as `X-API-Key` or `Authorization: Bearer` |
| **Health endpoint** | `/health` is public (no API key) for load balancer probes |
| **UploadThing** | No domain allowlisting needed; token-based auth only |
| **Google OAuth redirect URIs** | Must configure both dev (`localhost:3000`) and prod in Google Cloud Console |

---

## 4. Project Evolution Timeline

### Phase 1: Backend Foundation
- FastAPI + SQLAlchemy + Alembic
- Celery + Redis for async workflows
- Pydantic AI agents for job matching
- Two Postgres users for security

### Phase 2: Frontend Integration
- Next.js 16+ with App Router
- Better Auth with Google OAuth
- Prisma for read-only data access
- Server Actions for workflow triggers

### Phase 3: Production Deployment
- Docker Compose with Caddy
- Hetzner Cloud VPS
- Domain routing (app., api., flower.)
- SSE for real-time status updates

### Phase 4: Observability (Planned)
- Langfuse for AI tracing
- Sentry for error tracking
- Structured logging

---

## 5. Critical Lessons Summary

### Lesson 1: Worker Lifespan Pattern for Async Celery Tasks

> **Use a long-lived event loop per worker process, NOT `asyncio.run()` per task.**

When running async code (pydantic-ai, httpx) in Celery workers:
1. Create an event loop when the worker starts (`worker_process_init` signal)
2. Run it in a background thread with `run_forever()`
3. Schedule coroutines with `asyncio.run_coroutine_threadsafe()`
4. Close gracefully when worker shuts down (`worker_process_shutdown` signal)

This pattern ensures httpx connections can properly clean up between tasks because the loop stays alive.

**Impact:** Without this, job matching would fail intermittently with "Event loop is closed" errors.

---

### Lesson 2: Schema Master Principle

> **One tool owns DDL. Period.**

SQLAlchemy + Alembic own the database schema. Prisma only introspects. Running `prisma migrate` in production would have dropped tables.

**Prevention:**
- `job_agent_ui` user has no DDL privileges
- Documentation warnings everywhere
- CI could block `prisma migrate` commands (future)

---

### Lesson 3: SSE Connection Lifecycle

> **Long-lived connections need explicit keep-alive and proxy configuration.**

SSE connections for real-time status were being dropped silently. The fix required:
1. 15-second heartbeat comments (`: keep-alive\n\n`)
2. Caddy `read_timeout 600s`
3. Frontend EventSource cleanup on unmount

**Impact:** Without this, the Progress Stepper would freeze mid-workflow.

---

### Lesson 4: Multi-Stage Docker Builds and Stale Caches

> **Always verify critical packages at build time and force fresh builds for first-time setup.**

Multi-stage Docker builds copy packages from builder to runtime stage. If the image is cached from before a dependency was added, `docker compose run` silently reuses the stale image, causing `ModuleNotFoundError` at runtime.

**Problem scenario:**
1. VPS has cached Docker image from before `alembic` was added to `pyproject.toml`
2. `docker compose run --rm api python -m src.database.run_migrations` reuses cached image
3. Runtime fails with `ModuleNotFoundError: No module named 'alembic.config'`
4. Locally it works because the dev image was recently rebuilt

**Solution:**
1. **Add verification in Dockerfile** (builder stage):
   ```dockerfile
   RUN python -c "from alembic.config import Config; print('alembic OK')" && \
       python -c "import celery; print('celery OK')" && \
       python -c "import fastapi; print('fastapi OK')"
   ```
   This makes the build fail immediately if packages are missing.

2. **Force `--no-cache` in first-time setup**:
   ```bash
   $COMPOSE_BASE build --no-cache api
   ```
   This ensures no stale layers are reused.

**Key insight:** The failure mode is silent — `docker compose run` doesn't rebuild if an image exists. You only discover the problem at runtime. Build-time verification catches it early.

**Files affected:**
- `Dockerfile` (verification step)
- `setup.sh` (--no-cache build before migrations)

**Impact:** Without this, production deployments would fail mysteriously after adding new dependencies.

---

### Lesson 5: psql Variable Interpolation in PL/pgSQL Blocks

> **psql cannot interpolate `:variable` syntax inside dollar-quoted blocks.**

When writing SQL scripts that use psql variables (`:variable`) inside `DO $$ ... $$ BEGIN ... END;` blocks, the variables won't be interpolated — they're treated as literal text.

**Broken pattern:**
```sql
\set admin_pass 'mypassword'
DO $$
BEGIN
  EXECUTE format('CREATE USER job_agent_admin WITH PASSWORD %L', :'admin_pass');
END $$;
-- ERROR: syntax error at or near ":"
```

**Working pattern:** Use session config as an intermediary:
```sql
\set admin_pass 'mypassword'
SELECT set_config('var.admin_pass', :'admin_pass', false);  -- false = session-level

DO $$
DECLARE
  v_admin_pass text := current_setting('var.admin_pass');
BEGIN
  EXECUTE format('CREATE USER job_agent_admin WITH PASSWORD %L', v_admin_pass);
END $$;
```

**Key details:**
- `set_config(name, value, is_local)` — Use `false` for session-level persistence (survives the SELECT statement)
- `current_setting('var.name')` — Reads the value inside PL/pgSQL
- Prefix with `var.` to avoid conflicts with real PostgreSQL settings

**Files affected:** `scripts/grant-two-users-existing-db.sql`

**Impact:** Database user creation scripts would fail with cryptic syntax errors.

---

### Lesson 6: Bootstrap Ordering (Chicken-and-Egg Problem)

> **First-time setup must use always-available credentials, not application users.**

When scripting first-time database setup, don't assume application users exist. The postgres Docker image always creates a superuser (default: `postgres`), but application users must be explicitly created.

**Broken ordering:**
```bash
# Step 3: Drop schema (connects as job_agent_admin)
docker compose exec api python -m src.database.reset_db  # FAILS - user doesn't exist

# Step 4: Create users
psql -f create-users.sql  # Creates job_agent_admin
```

**Working ordering:**
```bash
# Step 3: Drop schema (as postgres superuser - always exists)
docker compose exec postgres psql -U postgres -d job_agent -c "
  DROP SCHEMA IF EXISTS public CASCADE;
  CREATE SCHEMA public;
  GRANT ALL ON SCHEMA public TO public;
"

# Step 4: Create application users
psql -f create-users.sql
```

**Key insight:** The `postgres` superuser is created automatically by the postgres Docker image. By using `psql` directly in the postgres container instead of going through the API container, you avoid the dependency on application users.

**Scenario matrix:**
| Scenario | Old Behavior | New Behavior |
|----------|--------------|--------------|
| Fresh DB, no volume | Fails (no job_agent_admin) | Works (postgres superuser) |
| Dirty DB from failed attempt | Fails (user may not exist) | Works (resets as superuser) |
| Existing DB with correct users | Works | Works |

**Files affected:** `setup.sh` (`action_first_time()` function)

**Impact:** Without this, first-time setup would fail on fresh VPS or after Docker volume cleanup.

---

### Lesson 7: NEXT_PUBLIC_* Variables Must Be Build-Time Arguments

> **Next.js `NEXT_PUBLIC_*` environment variables are inlined into JavaScript at BUILD TIME, not read at runtime.**

In Docker deployments, setting `NEXT_PUBLIC_*` as runtime environment variables in `docker-compose.yml` does NOT work. These variables must be available when `npm run build` runs.

**Broken pattern (runtime env):**
```yaml
# docker-compose.prod.yml
frontend:
  environment:
    NEXT_PUBLIC_API_URL: https://api.example.com  # ❌ Too late - build already happened
```

**Working pattern (build args):**
```dockerfile
# Dockerfile.frontend
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
# ... later ...
RUN npm run build  # Variables are now baked into JS bundle
```

```yaml
# docker-compose.prod.yml
frontend:
  build:
    args:
      NEXT_PUBLIC_API_URL: https://api.example.com  # ✅ Available at build time
```

**How Next.js handles environment variables:**
| Variable Type | When Available | How It Works |
|---------------|----------------|--------------|
| `NEXT_PUBLIC_*` | Build time | Text-replaced into JS bundle during `npm run build` |
| Server-only env | Runtime | Read via `process.env` in server components/API routes |

**Verification:**
```bash
# Check if localhost is baked into the JS bundle (bad)
docker compose exec frontend sh -c "grep -r 'localhost:3000' .next/static/ || echo 'Clean (good)'"
```

**Files affected:**
- `Dockerfile.frontend` (ARG/ENV declarations)
- `docker-compose.prod.yml` (build args instead of environment)
- `setup.sh` (`--no-cache` rebuild for frontend)

**Impact:** Without this, auth and API calls would go to `localhost:3000` instead of production URLs, causing CORS errors and authentication failures.

---

## Appendix: Quick Reference Commands

```bash
# Database migrations
docker compose exec api alembic upgrade head

# Prisma sync (frontend only)
cd frontend && npx prisma db pull && npx prisma generate

# View container logs
docker compose logs -f api celery-worker

# Generate Better Auth secret
openssl rand -base64 32

# Generate Flower Basic Auth hash
caddy hash-password

# SSH tunnel for database access
ssh -L 5433:127.0.0.1:5433 user@your-vps-ip

# Run backend tests
uv run pytest test/ -v
```

---

*Last updated: 2026-02-06 (Added Lessons 5-7 from production deployment)*
*Maintained by: Development Team*
