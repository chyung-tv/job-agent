# Next.js Frontend Setup Plan

This document summarizes the decisions and plan for adding a Next.js frontend to the job-agent monorepo. It is intended as the single reference for how we spin up and integrate the Next.js application.

---

## 1. Summary of Decisions

| Topic | Decision |
|-------|----------|
| **Repository structure** | Monorepo. Add a `frontend/` folder at repo root. No separate repo and no need to move backend into a `backend/` folder. |
| **Authentication** | **Better Auth** with **Google** OAuth (sign up / log in). Use the **session** plugin for database-backed sessions. [Better Auth](https://www.better-auth.com/). |
| **Schema master** | **SQLAlchemy (backend) is the single source of truth** for the database. All tables—including Better Auth tables (`user`, `session`, `account`, `verification`)—are **defined in SQLAlchemy** and **created/altered only via backend migrations**. This avoids "two chefs in one kitchen" and prevents Prisma from ever dropping or altering production tables. |
| **Migrations** | Use **Alembic** for versioned database migrations. Replace **create_tables.py** with Alembic: all DDL goes through Alembic; `setup.sh` runs `alembic upgrade head` instead of `create_tables`. See §10 for options and transition steps. |
| **Auth tables** | Better Auth expects **user**, **session**, **account**, **verification** (singular table names). These are **SQLAlchemy models in the backend**, migrated with Alembic—**not** created by Prisma. Field names must match Better Auth defaults (e.g. `emailVerified`, `expiresAt`, `createdAt`) for seamless introspection. Better Auth (via **prismaAdapter**) then reads/writes them at runtime. |
| **Data access** | **Prisma for all frontend data access.** Next.js uses the Prisma **client** with Better Auth's **prismaAdapter** for auth, and for domain data (user, runs, etc.) reads and optional simple writes. Prisma **never** changes schema: only **introspect** (`prisma db pull`) and **generate** (`prisma generate`). **Never** run `prisma migrate` or `prisma db push`. Frontend `DATABASE_URL` must use the limited-privilege Postgres user. |
| **User identity vs profile** | **Single `user` table** (Better Auth default name) integrating auth and job-agent profile: auth columns (id, name, email, emailVerified, image, etc.) + profile columns (location, profile_text, suggested_job_titles, source_pdfs, references, last_used_at). No separate **user_profiles** table. See §11 (model consolidation). |
| **Backend (API)** | No new read router. FastAPI keeps only workflow endpoints. All domain reads (and optional light writes) from the frontend go through Prisma. Workflow-trigger writes go through the API (Celery). |
| **Celery** | Unchanged. Celery remains for async workflow tasks only. |
| **Postgres users** | **Two users (required).** Backend user (e.g. `job_agent_admin`): full privileges for migrations. Frontend user (e.g. `job_agent_ui`): `SELECT`, `INSERT`, `UPDATE` only—**no** `CREATE`, `ALTER`, or `DROP`. Frontend `DATABASE_URL` uses the limited user so Postgres blocks any accidental migration. |
| **Deployment** | Same VPS, same Docker Compose. Frontend uses limited DB user; backend uses admin user. |

---

## 2. Repository Layout (After Setup)

```
job-agent/
  frontend/              # Next.js app (new)
    app/
      # Better Auth mounts at /_auth/ by default; ensure Caddy routes main domain → frontend
    lib/
      auth.ts            # Better Auth config (prismaAdapter, Google OAuth, session plugin)
      prisma.ts          # Prisma client (auth + domain reads)
    prisma/
      schema.prisma      # Introspected only (from `prisma db pull`). Never migrate or db push.
    public/
    package.json
    next.config.js
    ...
  src/                   # Backend (unchanged; no reads router)
    api/
      api.py             # App entry, workflow endpoints only
    database/
      models.py          # All models: Better Auth (user, session, account, verification) + domain (user with profile cols, runs + task_id, job_searches, etc.); no WorkflowExecution, no user_profiles
    workflow/
  alembic/               # Backend migrations (Alembic); single source of DDL
    ...
  docs/
  docker-compose.yml     # Add frontend service; frontend needs DATABASE_URL
  docker-compose.prod.yml
  Caddyfile              # Add block for main app domain
  Dockerfile
  ...
```

Backend stays at repo root; no migration of existing code into a `backend/` folder.

---

## 3. Authentication (Better Auth + Google + Database Session)

- **Library:** [Better Auth](https://www.better-auth.com/). **Provider:** Google OAuth (primary social provider). **Session:** Database-backed via the **session** plugin.
- **Where auth tables come from:** The backend defines **user**, **session**, **account**, **verification** (singular table names per Better Auth defaults) as **SQLAlchemy models** in `src/database/models.py`, matching Better Auth's core schema. Field names must align with Better Auth expectations (e.g. `emailVerified`, `expiresAt`, `createdAt`) so that introspection and the adapter work without mapping. An **Alembic migration** creates these tables. The frontend **never** creates or alters them via Prisma.
- **Frontend config:** In `frontend/lib/auth.ts`, configure Better Auth with the **prismaAdapter**, Google OAuth, and the **session** plugin. At runtime, Better Auth uses the Prisma **client** to read/write the same tables SQLAlchemy created. After any backend schema change: run `npx prisma db pull` then `npx prisma generate` in the frontend; **never** run `prisma migrate` or `prisma db push`.

---

## 4. User Identity and Profile (Single `user` Table)

- **Current state:** `UserProfile` (backend) holds name, email, location, profile_text, suggested_job_titles, source_pdfs, etc. There is no logged-in user concept yet.
- **Target state:** A single **`user`** table (Better Auth default name) with **auth columns** (id, name, email, emailVerified, image, etc. per Better Auth) and **profile columns** (location, profile_text, suggested_job_titles, source_pdfs, references, last_used_at; nullable until profiling). No separate `user_profiles` table. Domain tables (e.g. runs) reference `user_id` (FK to `user.id`). See §11 (model consolidation) for migration from existing `user_profiles`.

---

## 5. SQLAlchemy as Schema Master; Prisma in Its Lane

**Principle:** One chef in the kitchen. SQLAlchemy (backend) is the **single source of truth** for the database. Prisma **never** runs CREATE, ALTER, or DROP. It only **introspects** the DB and **generates** a type-safe client.

| Data | Who defines schema | Who runs DDL | Who reads/writes at runtime |
|------|---------------------|--------------|-----------------------------|
| **user, session, account, verification** (auth + profile on user) | SQLAlchemy (backend) | Alembic (backend) | Better Auth (prismaAdapter) + Prisma client (frontend) |
| **runs, job_searches, matched_jobs, etc.** (domain) | SQLAlchemy (backend) | Alembic (backend) | Backend (workflows) + Prisma client (frontend reads / optional light writes) |

### 5.1 What Prisma Can Do

- **Introspect:** `npx prisma db pull` — connects to Postgres, reads existing tables (created by SQLAlchemy/Alembic), and **writes** `schema.prisma`. It does **not** change the database.
- **Generate client:** `npx prisma generate` — produces the TypeScript Prisma client from `schema.prisma`. Used at runtime for SELECT, INSERT, UPDATE (e.g. Better Auth prismaAdapter, domain reads).
- **Runtime access:** The frontend uses the Prisma client to read/write auth and domain tables (subject to Postgres permissions). No API read endpoints needed.

### 5.2 What Prisma Must Not Do

- **Never run `npx prisma migrate dev`**, **`prisma migrate deploy`**, or **`prisma db push`**. Prisma would compare its schema to the DB, see tables it doesn’t “own,” and can try to drop or alter them—**risk of dropping production tables**. All schema changes are done in the backend (SQLAlchemy + Alembic). Frontend `DATABASE_URL` must use the limited-privilege Postgres user so that even an accidental migrate would be rejected by Postgres.

### 5.3 Sync Workflow (After Any Backend Schema Change)

1. **Backend:** Add or change models in `src/database/models.py`. Create an Alembic revision and run `alembic upgrade head`. Tables are now updated in Postgres.
2. **Frontend:** In `frontend/`, run `npx prisma db pull` so Prisma updates `schema.prisma` from the DB. Then run `npx prisma generate` so the TypeScript client is in sync.

### 5.4 Security (Required): Two Postgres Users

We use **two Postgres users** so the frontend can never run DDL, even by mistake:

- **Backend user** (e.g. `job_agent_admin`): `ALL PRIVILEGES` on the application schema. Used by SQLAlchemy and Alembic for migrations and by the API/Celery at runtime.
- **Frontend user** (e.g. `job_agent_ui`): `SELECT`, `INSERT`, `UPDATE` on the same tables; **no** `CREATE`, `ALTER`, or `DROP`. Use this user in `frontend/.env` as `DATABASE_URL`. If someone runs `prisma migrate`, Postgres will return “Permission denied.”

**Setup:** Create both users and grant the limited user only the required privileges on existing/future tables. Backend `.env` uses the admin user; frontend `.env` uses the UI user.

### 5.5 Writes

- **Workflow-driven writes** (create/update users profile fields, Run, etc.) go through the API (POST) and Celery; backend (SQLAlchemy) writes to the DB.
- **Optional:** Frontend can use the Prisma client for simple updates (e.g. `last_used_at` on users) if desired; keep business logic in the backend.

---

## 6. Backend: No New Read Endpoints

- **Leave the API alone.** Do not add a reads router or CRUD endpoints. The existing `api.py` stays as-is: workflow endpoints only (POST `/workflow/profiling`, POST `/workflow/job-search`, POST `/workflow/job-search/from-profile`), plus health and root. All domain reads (and optional light writes) from the frontend go through Prisma against the same Postgres.
- **CORS:** Configure FastAPI `CORSMiddleware` only for the workflow POSTs that the frontend may call from the browser (e.g. when triggering a workflow from the UI). Fewer endpoints to think about.

---

## 7. Frontend: How It Gets Data

- **Auth:** Better Auth + Prisma (user, session, account, verification). Session plugin provides the current user; use session for "my" data filtering.
- **Domain reads:** Prisma. In Server Components, Server Actions, or API routes, use the Prisma client to read user (with profile columns), runs, job_searches, matched_jobs, etc. Filter by `user_id` from the Better Auth session when showing "my" data.
- **Workflow triggers (writes):** Next.js calls existing FastAPI endpoints (e.g. `POST /workflow/profiling`, `POST /workflow/job-search/from-profile`) with the API key. See [api-calls-guide.md](api-calls-guide.md). These trigger Celery; the backend (SQLAlchemy) writes to the DB. The frontend then reads the result via Prisma (e.g. poll or refetch).
- **Base URL and API key:** Store `NEXT_PUBLIC_API_URL` and server-side `API_KEY` for workflow POSTs only. Use only in server-side code; send `X-API-Key` or `Authorization: Bearer` in requests to FastAPI.

---

## 8. Docker and Caddy

- **Compose:** Add a `frontend` service in `docker-compose.yml` (and prod override if needed):
  - Build context: `./frontend`, Dockerfile in `frontend/`.
  - Environment: `NEXT_PUBLIC_API_URL`, `DATABASE_URL` (same Postgres, **limited-privilege user** for frontend), `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, and Google OAuth client id/secret.
  - Expose port 3000 (dev) or no host port in prod (traffic via Caddy).
  - Same network as API and postgres so Next.js can call `http://api:8000` and connect to `postgres:5432` for Better Auth and Prisma domain reads.
- **Caddy:** Add a block for the main app domain (e.g. `profilescreens.com`) → `reverse_proxy frontend:3000`. Better Auth uses the default path `/_auth/`; ensure the main domain is routed to the frontend so `https://yourdomain.com/_auth/*` is served by the Next.js app. Keep existing `API_DOMAIN` and `FLOWER_DOMAIN` blocks unchanged.
- **Deploy flow:** Unchanged: SSH → `git pull` → `./stop.sh --prod` → `./start.sh --prod`. See [continuous-development.md](continuous-development.md).

---

## 9. Implementation Checklist

Use this as a high-level order of work when implementing.

1. **Backend: Model consolidation and Alembic (do before frontend)**
   - [ ] **Consolidate models** (see §11): Remove **WorkflowExecution**; add **task_id** to **Run**; integrate **User** and **UserProfile** into a single **user** table (Better Auth default name; auth + profile columns); drop **user_profiles**. Update all code that references WorkflowExecution or UserProfile.
   - [ ] Add Alembic and transition from `create_tables.py` to versioned migrations (see §10). Update `setup.sh` to run `alembic upgrade head` instead of `create_tables`.
   - [ ] Add SQLAlchemy models for **Better Auth** in `src/database/models.py`: **user**, **session**, **account**, **verification** (singular table names). Match [Better Auth](https://www.better-auth.com/) core schema; use field names like `emailVerified`, `expiresAt`, `createdAt` for seamless introspection. Merge auth + profile into single **user** table: auth defaults + profile columns (location, profile_text, suggested_job_titles, source_pdfs, references, last_used_at).
   - [ ] Create **two Postgres users** (admin + limited); grant limited user SELECT, INSERT, UPDATE only. Use admin for backend `.env` and migrations; use limited for frontend `DATABASE_URL`.
   - [ ] Run Alembic: `alembic revision --autogenerate`, then `alembic upgrade head`. Result: tables `user` (auth + profile), `session`, `account`, `verification`, `runs` (with task_id, user_id), job_searches, etc.; no workflow_executions, no user_profiles.
   - [ ] Update backend workflow logic to set Run.task_id and Run.status from the Celery task; use users (profile columns) instead of UserProfile.

2. **Frontend: scaffold + Better Auth + Prisma (introspect only; no Prisma migrate/db push)**
   - [ ] Create `frontend/` at repo root (e.g. `npx create-next-app@latest frontend` with TypeScript, App Router).
   - [ ] Install **Better Auth** and Prisma. Configure Better Auth in `frontend/lib/auth.ts`: **prismaAdapter**, **Google OAuth** (primary social provider), **session** plugin for database-backed sessions.
   - [ ] **Do not** hand-write or run Prisma migrations or `prisma db push`. In `frontend/`, run `npx prisma db pull` so Prisma introspects the DB (populates `schema.prisma` with all tables SQLAlchemy created). Then run `npx prisma generate`. Frontend `DATABASE_URL` must use the limited-privilege Postgres user.
   - [ ] Set env: `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `DATABASE_URL`, Google OAuth client id/secret.
   - [ ] Use Prisma in Server Components / Server Actions to read user (with profile columns), runs, job_searches, matched_jobs, etc. Filter by Better Auth session `user_id` where appropriate.
   - [ ] Configure `NEXT_PUBLIC_API_URL` and server-side `API_KEY` for workflow POSTs only. Implement a small server-side helper that calls FastAPI (e.g. POST profiling, POST job-search/from-profile) with the API key.

3. **Docker and Caddy**
   - [ ] Add `frontend` service to `docker-compose.yml` (build `./frontend`, env: `DATABASE_URL`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, Google OAuth, `NEXT_PUBLIC_API_URL`, `API_KEY`).
   - [ ] Add production overrides in `docker-compose.prod.yml` if needed (e.g. no host port, production build).
   - [ ] Update Caddyfile: main app domain → `reverse_proxy frontend:3000` so `/_auth/` (Better Auth default path) is served by the frontend. Keep existing `API_DOMAIN` and `FLOWER_DOMAIN` blocks unchanged.
   - [ ] Update deploy docs (e.g. [continuous-development.md](continuous-development.md), [deployment.md](deployment.md)) to mention frontend, new domain, and Better Auth/Google env vars.

4. **Docs and env**
   - [ ] Add `frontend/.env.example` with `DATABASE_URL`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, Google OAuth vars, `NEXT_PUBLIC_API_URL`, `API_KEY`.
   - [ ] Document the sync workflow: after any backend schema change, run `alembic upgrade head` (backend), then in frontend `npx prisma db pull` and `npx prisma generate`. **Never** run `prisma migrate` or `prisma db push` in the frontend.

---

## 10. Alembic: Replacing create_tables.py

The project currently uses **create_tables.py** (run via `setup.sh`: `docker compose run --rm api python -m src.database.create_tables`). It is idempotent but not versioned: there is no history of schema changes and no safe rollback.

**Options when moving to Alembic:**

1. **Full replacement (recommended)**  
   - Add Alembic (`alembic init`), point it at your DB and `src.database.models` (or a single `Base.metadata`).  
   - Create an **initial revision** that defines all current tables (either autogenerate from existing models or from a fresh DB created by `create_tables` once).  
   - **Change setup.sh:** instead of `python -m src.database.create_tables`, run `alembic upgrade head` (inside the same `api` container or a dedicated migration step).  
   - From then on: all schema changes = new Alembic revision + `alembic upgrade head`. Do **not** run `create_tables.py` in production.

2. **One-time migration from an existing DB**  
   - If the DB already has tables (e.g. from `create_tables.py`), add Alembic and create an initial revision that matches the current state (autogenerate or hand-written).  
   - Run `alembic stamp head` to mark the DB as “at head” without applying changes.  
   - Future changes: new revisions + `alembic upgrade head`.  
   - **Change setup.sh:** for **new** environments, run `alembic upgrade head`; for existing ones, either keep running `create_tables` once for legacy or run `alembic stamp head` then `alembic upgrade head`.

3. **What changes in setup.sh**  
   - **Before:** `docker compose run --rm api python -m src.database.create_tables`  
   - **After:** `docker compose run --rm api alembic upgrade head` (ensure `alembic.ini` and `alembic/env.py` use the same DB URL as the app, e.g. from env).  
   - Optional: keep `create_tables.py` for local/dev one-off use only; do **not** use it in production or in the main setup path once Alembic is in place.

**Summary:** Use Alembic as the single path for DDL. Replace the `create_tables` step in `setup.sh` with `alembic upgrade head`. Create two Postgres users (admin + limited) and use the admin user for running migrations.

---

## 11. Database Model Consolidation (Before Frontend Development)

Before adding the frontend and Better Auth, we consolidate and simplify the current models so the schema is easier to reason about and does not overlap with Celery/Flower.

### 11.1 Run vs WorkflowExecution vs Flower

- **Run** (current): Tracks a job-search “run”: status, error_message, completion counters (research_completed_count, fabrication_completed_count, etc.), delivery_triggered, job_search_id, user_profile_id. Used to group matched jobs, decide when the run is “complete,” and trigger delivery. **We keep Run** for this business meaning.
- **WorkflowExecution** (current): Stores run_id, workflow_type, status, current_node, context_snapshot, error_message, started_at, completed_at. Updated by tasks via `update_execution_status()`. It overlaps with what **Celery/Flower** already provide: task state (pending, started, success, failure). The “current node” is also in the in-memory task context. So WorkflowExecution duplicates task-level status and node progress.
- **Recommendation:** **Remove the WorkflowExecution table.** Use **Run** for business state (counters, delivery_triggered, status, error_message). Add **task_id** (Celery task id, string) to **Run** so the frontend can link to Flower for live task status and logs. Update Run.status from the task when it completes or fails. Node-level progress stays in task context and/or Flower; we do not persist it in the DB unless we later add a minimal “current_node” or “last_node” on Run for UI display.

### 11.2 User and UserProfile Integration

- **Current:** Separate **UserProfile** (name, email, location, profile_text, suggested_job_titles, source_pdfs, etc.) and (planned) auth **User** (id, name, email, image). Two concepts for “person.”
- **Recommendation:** **Single `user` table** (Better Auth default name) that includes both auth columns (id, name, email, emailVerified, image, etc. per Better Auth) and job-agent profile columns (location, profile_text, suggested_job_titles, source_pdfs, references, last_used_at). Auth columns are required for sign-in; profile columns are nullable until the user runs the profiling workflow. **Drop the `user_profiles` table.** All references to user_profiles (e.g. runs.user_profile_id) become user_id (FK to user.id). Migration path: add user table with auth + profile columns; migrate existing user_profiles data into user where possible (e.g. by email); repoint runs and any other FKs to user_id; drop user_profiles.

### 11.3 Resulting Table Set (After Consolidation)

- **Auth (Better Auth, singular names):** user (with profile columns), session, account, verification.  
- **Domain:** runs (with task_id, user_id), job_searches, job_postings, matched_jobs, company_research, cover_letters, artifacts.  
- **Removed:** workflow_executions, user_profiles.

Code that currently creates or queries WorkflowExecution (e.g. api.py, base_workflow.py, tasks/utils.py, tasks/job_search_task.py, tasks/profiling_task.py) must be updated to use Run only (and set task_id on Run; update Run.status from the task). Code that uses UserProfile must be updated to use the users table (profile columns).

---

## 12. References

- **API usage and auth:** [api-calls-guide.md](api-calls-guide.md)
- **Redeploy flow:** [continuous-development.md](continuous-development.md)
- **First-time deployment (VPS, DNS, Caddy):** [deployment.md](deployment.md)
- **Backend DB models:** `src/database/models.py`
- **Better Auth (schema & config):** [Better Auth](https://www.better-auth.com/)

---

*This plan reflects: **SQLAlchemy as schema master** (all tables defined in backend; Alembic for migrations; replace create_tables.py—see §10); **Prisma in read-only lane** (introspect + generate only; never prisma migrate or db push; frontend DATABASE_URL = limited user); **two Postgres users required** (admin + limited); **model consolidation** (remove WorkflowExecution, integrate User+UserProfile into single user table—see §11); **Better Auth** (Google OAuth, session plugin, prismaAdapter); API unchanged (workflow endpoints only).*
