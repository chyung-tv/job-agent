# Debug Log: Production Deployment Issues

**Created:** 2026-02-06
**Status:** RESOLVED (2026-02-06)

---

## Takeaways

| Issue | Root Cause | Fix | Lesson Learned |
|-------|------------|-----|----------------|
| **Issue 1-5: Alembic missing** | Stale cached Docker image on VPS from before alembic was added to dependencies | Force `--no-cache` build + add verification step in Dockerfile | Multi-stage Docker builds can silently fail if images are cached; always verify critical packages at build time |
| **Issue 2: Frontend build** | Missing `public/` directory in source | Add `frontend/public/.gitkeep` | Multi-stage COPY fails silently if source doesn't exist; ensure all expected directories exist |
| **Issue 3: psql vars** | psql cannot interpolate variables inside `DO $$ ... $$` blocks | Use `set_config()` / `current_setting()` pattern | Use session config for passing variables into PL/pgSQL blocks |
| **Issue 4: Chicken-and-egg** | Script tried to connect as application user before creating it | Use postgres superuser for schema reset, create users after | First-time setup must use always-available superuser for bootstrap |
| **Issue 6: NEXT_PUBLIC_* vars** | Runtime env vars don't work for Next.js client-side code; they're inlined at build time | Pass as Docker build args (ARG/ENV), not runtime environment | NEVER use runtime env for `NEXT_PUBLIC_*` in Docker; must be available at `npm run build` |

---

## Issue 1: Alembic Not Found in Production Container

### Symptom

When running `./setup.sh --migrate --prod`, the migration fails with various errors depending on the invocation method:

```
# Original error:
exec: "alembic": executable file not found in $PATH

# After attempting python -m alembic:
No module named alembic.__main__; 'alembic' is a package and cannot be directly executed

# After attempting python -c one-liner:
ModuleNotFoundError: No module named 'alembic.config'
```

The error occurs inside the production Docker container (`job-agent-api`) when `setup.sh` runs:
```bash
$COMPOSE_RUN_API python -c "import sys; from alembic.config import main; sys.argv = ['alembic', 'upgrade', 'head']; main()"
```

### Hypotheses Tested

1. **Alembic not installed in container** - **DISPROVEN**
   - Ran `docker run --rm job-agent-api pip list | grep alembic` locally → Shows `alembic 1.18.3`
   - Ran `docker run --rm job-agent-api python -c "import alembic.config; print('ok')"` → Works locally

2. **PATH issue with CLI script** - **PARTIALLY CONFIRMED**
   - The `alembic` CLI script is in `/usr/local/bin` which should be in PATH
   - But direct `alembic upgrade head` fails, suggesting the script isn't properly installed or linked

3. **Stale Docker image on VPS** - **LIKELY**
   - Local container works fine with `alembic.config` import
   - VPS container fails with `ModuleNotFoundError`
   - VPS may be running an older image built before alembic was properly installed

4. **Multi-stage Dockerfile copy issue** - **POSSIBLE**
   - `Dockerfile` copies `/usr/local/lib/python3.13/site-packages` and `/usr/local/bin`
   - But `uv pip install --system .` may install differently than expected

### Failed Attempts

| Attempt | Code | Result |
|---------|------|--------|
| 1. Direct CLI | `alembic upgrade head` | `executable file not found in $PATH` |
| 2. Module execution | `python -m alembic upgrade head` | `No module named alembic.__main__` |
| 3. Python one-liner (v1) | `python -c "import alembic.config; alembic.config.main(argv=['upgrade', 'head'])"` | `ModuleNotFoundError: No module named 'alembic.config'` |
| 4. Python one-liner (v2) | `python -c "from alembic.config import main; main(argv=['upgrade', 'head'])"` | Same error |
| 5. Python one-liner (v3) | `python -c "import sys; from alembic.config import main; sys.argv = ['alembic', 'upgrade', 'head']; main()"` | **Not yet tested on VPS** (frontend build failed first) |

### Current State

**File:** `setup.sh` (lines 120, 158, 178)
```bash
$COMPOSE_RUN_API python -c "import sys; from alembic.config import main; sys.argv = ['alembic', 'upgrade', 'head']; main()"
```

**Blocker:** Cannot test because frontend build fails first (see Issue 2).

### Next Logical Steps

1. **Fix Issue 2 first** (frontend build) so `--restart` can complete
2. **Force rebuild on VPS** with `docker compose build --no-cache api`
3. **Debug inside running container on VPS:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api sh
   # Inside container:
   pip list | grep alembic
   python -c "import alembic; print(alembic.__file__)"
   python -c "from alembic.config import main; print('ok')"
   ```
4. If alembic is missing, check if `pyproject.toml` changes were pushed to VPS
5. If alembic is present but import fails, check `sys.path` vs package location

---

## Issue 2: Frontend Docker Build Failure

### Symptom

```
ERROR [frontend runner 3/6] COPY --from=builder /app/public ./public
failed to calculate checksum of ref...: "/app/public": not found
```

### Cause

The `frontend/` directory does not contain a `public/` folder. `Dockerfile.frontend` line 32 tries to copy it:
```dockerfile
COPY --from=builder /app/public ./public
```

Since `COPY frontend/ .` in the builder stage doesn't create empty directories, and there's no `public/` folder in the source, the copy fails.

### Fix Applied

**File:** `Dockerfile.frontend` (line 31-32)
```dockerfile
# Copy built assets
RUN mkdir -p ./public
COPY --from=builder /app/public ./public
```

**Status:** RESOLVED - Verified on VPS 2026-02-06.

---

## Issue 3: Database Users Creation Script Failed

### Symptom

```
psql syntax error at or near ":"
```

### Cause

`scripts/grant-two-users-existing-db.sql` uses psql variables (`:'admin_pass'`) inside a `DO $$ ... $$ BEGIN ... END $$;` block. Psql cannot interpolate variables inside dollar-quoted strings.

### Fix Applied

**File:** `scripts/grant-two-users-existing-db.sql`
```sql
-- Pass variables via session config
SELECT set_config('var.admin_pass', :'admin_pass', true);
SELECT set_config('var.ui_pass', :'ui_pass', true);

DO $$
DECLARE
  v_admin_pass text := current_setting('var.admin_pass');
  v_ui_pass text := current_setting('var.ui_pass');
BEGIN
  -- use v_admin_pass and v_ui_pass instead of :'admin_pass'
END $$;
```

**Status:** RESOLVED - Verified on VPS 2026-02-06.

---

## Issue 4: First-Time Setup Chicken-and-Egg Problem

### Symptom

```
psycopg.OperationalError: connection failed: FATAL: password authentication failed for user "job_agent_admin"
```

This error occurs at step 3 "Dropping existing schema (if any)" when running `./setup.sh --first-time --prod`.

### Cause

The `action_first_time()` function had a chicken-and-egg ordering problem:

1. **Step 3**: Runs `reset_db.py` which connects as `job_agent_admin`
2. **Step 4**: Creates users `job_agent_admin` and `job_agent_ui`

The script tried to connect as `job_agent_admin` before that user existed. This fails on:
- **Fresh databases**: The user doesn't exist yet
- **Dirty volumes from failed attempts**: The user may not exist or may have wrong password

### Root Cause Analysis

`reset_db.py` runs inside the API container and uses `DATABASE_URL` from environment, which specifies `job_agent_admin` as the connection user. The postgres superuser (`postgres`) always exists, but the application users don't until step 4 creates them.

### Fix Applied

**File:** `setup.sh` - `action_first_time()` function

**Before (broken):**
```bash
echo "3. Dropping existing schema (if any)..."
$COMPOSE_RUN_API python -m src.database.reset_db  # Connects as job_agent_admin - FAILS
```

**After (works):**
```bash
echo "3. Resetting schema (as postgres superuser)..."
$COMPOSE_BASE exec -T postgres psql -U postgres -d "${POSTGRES_DB:-job_agent}" -c "
  DROP SCHEMA IF EXISTS public CASCADE;
  CREATE SCHEMA public;
  GRANT ALL ON SCHEMA public TO public;
"
```

### Why This is Bulletproof

| Scenario | Old Behavior | New Behavior |
|----------|--------------|--------------|
| Fresh DB, no volume | Fails (no job_agent_admin) | Works (postgres superuser exists) |
| Dirty DB from failed attempt | Fails (job_agent_admin may not exist) | Works (resets as superuser first) |
| Existing DB with correct users | Works | Works (reset then recreate) |

### Key Insight

The `postgres` superuser is created automatically by the postgres Docker image and always exists. By using `psql` directly in the postgres container instead of going through the API container, we avoid the dependency on application users.

**Status:** RESOLVED - Verified on VPS 2026-02-06.

---

## Summary of Modified Files

| File | Change | Status |
|------|--------|--------|
| `scripts/grant-two-users-existing-db.sql` | Use `set_config`/`current_setting` for psql vars; fixed `set_config(..., false)` for session-level persistence | Tested |
| `setup.sh` | Replaced `reset_db.py` with direct psql as postgres superuser; fixed step ordering; added `--no-cache` API build before migrations (Issue 5) | Tested |
| `src/database/run_migrations.py` | NEW: Robust Alembic migration runner using programmatic API | Tested |
| `frontend/public/.gitkeep` | NEW: Ensures public directory exists for Docker build | Tested |
| `Dockerfile` | Added verification step after `uv pip install` to fail fast if alembic/celery/fastapi missing (Issue 5) | Tested |

## Deployment Sequence

Once all fixes are committed and pushed to VPS:

```bash
# For fresh setup (or to reset everything):
./setup.sh --first-time --prod

# OR for existing DB that just needs code updates:
./setup.sh --restart --prod
```

The `--first-time` flag now handles all scenarios (fresh DB, dirty volume, existing users) by using postgres superuser for schema reset before creating application users.

---

## Issue 5: Alembic Missing in Production Multi-Stage Docker Build

### Symptom

```
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/app/src/database/run_migrations.py", line 20, in <module>
    from alembic.config import Config
ModuleNotFoundError: No module named 'alembic.config'
```

This error occurs during step 5 of first-time setup when running migrations in production mode:
```bash
$COMPOSE_RUN_API python -m src.database.run_migrations
```

### Root Cause Analysis

**Why it works locally (dev mode) but fails on server (prod mode):**

| Aspect | Local (dev mode) | Server (prod mode) |
|--------|------------------|---------------------|
| Compose files | `docker-compose.yml` only | `docker-compose.yml` + `docker-compose.prod.yml` |
| Dockerfile | `Dockerfile.dev` (single-stage) | `Dockerfile` (multi-stage) |
| Build process | Direct install in runtime image | Install in builder, COPY to runtime |
| Source volumes | Mounts `./src`, `./alembic`, etc. | `volumes: []` (no mounts) |

The production `Dockerfile` uses a multi-stage build:

```dockerfile
# Stage 1: Builder
FROM python:3.13-slim as builder
COPY pyproject.toml uv.lock* ./
RUN pip install uv && uv pip install --system .

# Stage 2: Runtime
FROM python:3.13-slim
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
```

**Three possible causes:**

1. **Stale cached image on VPS** - The VPS has a cached Docker image from before `alembic>=1.14.0` was added to `pyproject.toml`. The `docker compose run --rm api` command reuses the cached image instead of rebuilding.

2. **uv installs to unexpected location** - `uv pip install --system .` may install packages to a different path than `/usr/local/lib/python3.13/site-packages` in some environments (e.g., different Python minor version, different base image).

3. **Missing `uv.lock` on VPS** - The `COPY pyproject.toml uv.lock* ./` uses a wildcard; if `uv.lock` is missing on VPS, `uv pip install` behavior may differ from local.

### Why Local Dev Works

In development mode, `docker-compose.yml` uses `Dockerfile.dev` which is a **single-stage build**:
- Packages are installed directly into the runtime image (no COPY between stages)
- No risk of path mismatches or missing files
- Image is frequently rebuilt locally during development

### Fix Applied

**File:** `Dockerfile` - Added verification step after `uv pip install`:

```dockerfile
# Verify critical packages are installed (fail fast if missing)
RUN python -c "from alembic.config import Config; print('alembic OK')"
```

This ensures the Docker build fails immediately if alembic isn't properly installed, rather than failing later at runtime during migrations.

**File:** `setup.sh` - Added `--no-cache` build before migrations in `action_first_time()`:

```bash
echo "5. Building API image (--no-cache to ensure fresh dependencies)..."
$COMPOSE_BASE build --no-cache api

echo "6. Running migrations (creating tables)..."
$COMPOSE_RUN_API python -m src.database.run_migrations
```

This forces a fresh build of the API image before running migrations, ensuring no stale cached layers are used.

### Verification

After applying fixes, verify on server:

```bash
# 1. Force rebuild to verify Dockerfile fix
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache api

# 2. Verify alembic is accessible
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api \
  python -c "from alembic.config import Config; print('alembic OK')"

# 3. Run first-time setup
./setup.sh --first-time --prod
```

**Status:** RESOLVED - Verified on VPS 2026-02-06. First-time setup completed successfully with all migrations applied.

---

## Issue 6: NEXT_PUBLIC_* Variables Not Available in Production Frontend

### Symptom

Browser console on `https://app.profilescreens.com` shows CORS errors:

```
Access to fetch at 'http://localhost:3000/api/auth/get-session' from origin 'https://app.profilescreens.com' 
has been blocked by CORS policy: Permission was denied for this request to access the `loopback` address space.

Failed to check session on signup page: TypeError: Failed to fetch

Access to fetch at 'http://localhost:3000/api/auth/sign-in/social' from origin 'https://app.profilescreens.com' 
has been blocked by CORS policy: Response to preflight request doesn't pass access control check
```

The frontend is calling `http://localhost:3000` instead of `https://app.profilescreens.com` for auth endpoints.

### Root Cause

**Next.js `NEXT_PUBLIC_*` environment variables are inlined into the JavaScript bundle at BUILD TIME, not read at runtime.**

The `docker-compose.prod.yml` was setting these variables as runtime environment variables:

```yaml
frontend:
  environment:
    NEXT_PUBLIC_BETTER_AUTH_URL: https://${FRONTEND_DOMAIN}
    NEXT_PUBLIC_API_URL: https://${API_DOMAIN}
```

But the `Dockerfile.frontend` built the image without these variables, so the default fallback values (`http://localhost:3000`) were baked into the JavaScript bundle.

**How Next.js handles NEXT_PUBLIC_* variables:**

| Variable Type | Available When | How It Works |
|---------------|----------------|--------------|
| `NEXT_PUBLIC_*` | Build time | Text-replaced into JS bundle during `npm run build` |
| Server-only env | Runtime | Read via `process.env` in server components/API routes |

### Fix Applied

**File:** `Dockerfile.frontend` - Added ARG/ENV declarations for build-time variables:

```dockerfile
# Build stage
FROM node:22-alpine AS builder
WORKDIR /app

# Build arguments for NEXT_PUBLIC_* vars (must be available at build time)
ARG NEXT_PUBLIC_BETTER_AUTH_URL=http://localhost:3000
ARG NEXT_PUBLIC_API_URL=http://localhost:8000

# Set as environment variables for the build
ENV NEXT_PUBLIC_BETTER_AUTH_URL=$NEXT_PUBLIC_BETTER_AUTH_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
```

**File:** `docker-compose.prod.yml` - Changed from runtime env to build args:

```yaml
frontend:
  build:
    context: .
    dockerfile: Dockerfile.frontend
    args:
      NEXT_PUBLIC_BETTER_AUTH_URL: https://${FRONTEND_DOMAIN}
      NEXT_PUBLIC_API_URL: https://${API_DOMAIN}
  environment:
    # Only server-side env vars here (work at runtime)
    BETTER_AUTH_URL: https://${FRONTEND_DOMAIN}
```

**File:** `setup.sh` - Added `--no-cache` to `action_rebuild_frontend()`:

```bash
# Before:
$COMPOSE_BASE build frontend

# After:
$COMPOSE_BASE build --no-cache frontend
```

This ensures the "rebuild" action actually rebuilds from scratch, picking up Dockerfile changes.

### Verification

After rebuilding, verify the embedded URLs:

```bash
# Rebuild frontend with new build args
./setup.sh --rebuild-frontend --prod

# Verify no localhost references in built JS (inside container)
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec frontend \
  sh -c "grep -r 'localhost:3000' .next/static/ || echo 'No localhost references found (good)'"
```

Then check browser console on `https://app.profilescreens.com` - auth requests should go to `https://app.profilescreens.com/api/auth/...` instead of localhost.

### Key Insight

**NEVER rely on runtime environment variables for `NEXT_PUBLIC_*` in Docker builds.** These must be passed as build arguments (ARG) and set as ENV before `npm run build`.

**Status:** RESOLVED - 2026-02-06
