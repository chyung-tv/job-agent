# Phased Implementation Plan: Next.js Frontend

This document lays out a **step-by-step development plan** to implement the setup described in [next-js-setup.md](next-js-setup.md). Implementation is split into **two phases**: backend first (Alembic, model consolidation, Better Auth tables, two Postgres users), then frontend (Next.js, Better Auth, Prisma, Docker/Caddy).

**Principle:** Do not start the Next.js application until the data models are in place and the backend has been verified to work correctly.

The sections below incorporate **architect notes and industry best practices** so the VPS deployment is production-ready (e.g. Prisma connection handling, Better Auth routing, Caddy headers, optional RLS, PgBouncer, and checklist add-ons).

---

## Best Practices & Architect Notes

### 1. SQLAlchemy Master / Prisma DRL Pattern (Verified)

Using **SQLAlchemy for DDL** (migrations) and **Prisma for DRL** (reads/logic) is the pattern used by high-performance teams in multi-language monorepos.

- **Global Singleton for Prisma:** Next.js hot-reloading can create many DB connections in development and crash Postgres on a VPS with limited RAM. In `frontend/lib/prisma.ts`, use a **global singleton** so only one `PrismaClient` is reused:

```typescript
// frontend/lib/prisma.ts
import { PrismaClient } from "@prisma/client";

const prismaClientSingleton = () => {
  return new PrismaClient();
};

declare global {
  var prismaGlobal: undefined | ReturnType<typeof prismaClientSingleton>;
}

const prisma = globalThis.prismaGlobal ?? prismaClientSingleton();

export default prisma;

if (process.env.NODE_ENV !== "production") globalThis.prismaGlobal = prisma;
```

### 2. Better Auth: Key Architecture Differences

Better Auth does **not** use a `[...nextauth]` route. It uses its own **Internal API** and a single **`[...all]`** catch-all route.

- **Routing:** Better Auth typically uses **`/_auth/*`** as its base path. On a VPS with Caddy, ensure the **Caddyfile** routes the main app domain to the Next.js service so that **Next.js** (not the API) receives `/_auth/*` (sign-in, callbacks, etc.). The Next.js app must be the one handling these requests.

### 3. Data Flow: Server-to-Server Advantage

"No new read router" in FastAPI is a velocity win.

- **Next.js Server Components:** Use Prisma to query the DB directly (same Hetzner server → local network latency).
- **Next.js Server Actions:** Use Prisma for simple writes (e.g. `last_used_at`).
- **FastAPI:** Reserve for logic that **must** be in Python (AI agents, PDF processing, Celery task management).

### 4. Advanced Least Privilege: Row Level Security (Optional)

Beyond two Postgres users, **Row Level Security (RLS)** is the "Fortune 500" standard: even if the frontend user is compromised, `job_agent_ui` can only see rows where `user_id = current_user`.

- **Note:** RLS adds complexity. For a solo developer, the two-user plan is sufficient; consider RLS when scaling or when compliance requires it.

### 5. VPS Health & Performance (Hetzner)

On a typical Hetzner VPS (e.g. 4–8 GB RAM):

- **Connection pooling:** Prisma and SQLAlchemy both hold connections. If you see "Too many connections" errors, add **PgBouncer** between the apps and Postgres to manage the pool.
- **Restart policy:** In `docker-compose.yml`, use **`restart: always`** for all services so a frontend crash does not leave the API or workers down.

---

## Overview

| Phase | Focus | Gate before next phase |
|-------|--------|-------------------------|
| **Phase 1** | Backend: Alembic, model consolidation, Better Auth models, two Postgres users, workflow/code updates | Backend tests pass; workflows run; DB state matches new schema |
| **Phase 2** | Next.js: scaffold, Better Auth + Prisma (introspect only), Docker/Caddy, docs | N/A |

---

## Phase 1: Backend (Alembic + Model Consolidation + Better Auth Tables)

**Goal:** Replace `create_tables.py` with Alembic, consolidate models (remove WorkflowExecution; single `user` table with auth + profile), add Better Auth tables, introduce two Postgres users, and update all code so the backend continues to work. No frontend work in this phase.

**Reference:** [next-js-setup.md](next-js-setup.md) §§9–11, §10 (Alembic), §11 (model consolidation).

### 1.1 Alembic setup and replace create_tables

- [ ] Add Alembic to the project (`alembic init`), configure `alembic.ini` and `alembic/env.py` to use the same DB URL as the app (e.g. from env).
- [ ] In **`alembic/env.py`:** hardcode the **search_path** or schema if you use a non-default Postgres schema so migrations run against the correct schema.
- [ ] Point Alembic at `src.database.models` (or `Base.metadata`) for autogenerate.
- [ ] Create the **initial revision**:
  - **Option A (fresh / new envs):** Run `create_tables` once to get current schema, then `alembic revision --autogenerate` to capture it.
  - **Option B (existing DB):** Autogenerate from current models against existing DB, then for existing DBs run `alembic stamp head` so no DDL is applied to current tables.
- [ ] Update **setup.sh**: replace `python -m src.database.create_tables` with `alembic upgrade head` (run in the same `api` container or a dedicated migration step).
- [ ] Document that `create_tables.py` is no longer used in the main setup path (optional: keep for local one-off use only).

**Acceptance:** New environment runs `./setup.sh` and ends with DB at `alembic upgrade head`; existing environment can be stamped and then uses Alembic for all future changes.

### 1.2 Two Postgres users

- [x] Create **backend user** (e.g. `job_agent_admin`): full privileges on the application schema; used by backend `.env` and Alembic.
- [x] Create **frontend user** (e.g. `job_agent_ui`): `SELECT`, `INSERT`, `UPDATE` only on the same schema; **no** `CREATE`, `ALTER`, or `DROP`.
- [x] Grant the limited user the required privileges on existing (and future) tables.
- [x] Ensure backend `.env` (and `alembic/env.py`) use the **admin** user; reserve the **UI** user for frontend `DATABASE_URL` in Phase 2.

**Acceptance:** Migrations run with admin user; limited user can read/write but cannot run migrations.

**Two-user setup (env and deployment):**

- **New deployment:** The Postgres container bootstraps as user `postgres` using `POSTGRES_INIT_PASSWORD`. An init script in `scripts/init-db-users.sh` (mounted at `/docker-entrypoint-initdb.d/`) runs only when the data volume is empty and creates `job_agent_admin` and `job_agent_ui` with passwords from `POSTGRES_PASSWORD` and `POSTGRES_UI_PASSWORD`, then grants schema and default privileges. Set `.env` with `POSTGRES_USER=job_agent_admin`, `POSTGRES_PASSWORD=<admin password>`, `POSTGRES_INIT_PASSWORD=<bootstrap password>`, `POSTGRES_UI_USER=job_agent_ui`, `POSTGRES_UI_PASSWORD=<ui password>`. Start the stack so Postgres runs the init script, then run `./setup.sh` so migrations run as `job_agent_admin`.
- **Existing deployment (volume already has data):** Init scripts do not run. Run the one-time SQL as `postgres` to create the two roles and grant on existing tables/sequences: `psql -v admin_pass='...' -v ui_pass='...' -d job_agent -f scripts/grant-two-users-existing-db.sql`. Then set `.env` to use `POSTGRES_USER=job_agent_admin` and `POSTGRES_PASSWORD=<admin password>`. No need to re-run migrations if the DB is already at head; optionally run `alembic stamp head` if you want Alembic to match current state.

### 1.3 Model consolidation (Run, WorkflowExecution, User, UserProfile)

Do this in the order below so that one Alembic revision can capture the full consolidated schema.

**1.3.1 Remove WorkflowExecution; add task_id to Run**

- [ ] In `src/database/models.py`: add **task_id** (String, nullable, Celery task id) to **Run**; keep **Run** as the single place for run-level status, error_message, counters, delivery_triggered.
- [ ] Remove the **WorkflowExecution** model and its table from the models (to be dropped in a migration).
- [ ] Update all code that creates or queries **WorkflowExecution** to use **Run** only:
  - [ ] `src/api/api.py`: stop creating WorkflowExecution; create Run with task_id when dispatching Celery task; pass run_id (and task_id if needed) to the task.
  - [ ] `src/workflow/base_workflow.py`: remove WorkflowExecution creation/usage; rely on Run and task context.
  - [ ] `src/tasks/utils.py`: remove `update_execution_status()` or replace with “update Run.status / Run.error_message by run_id”; ensure tasks receive run_id and optionally task_id.
  - [ ] `src/tasks/job_search_task.py`, `src/tasks/profiling_task.py`: set Run.task_id when starting; update Run.status (and error_message) on completion/failure.
- [ ] Create an Alembic revision: add `task_id` to `runs`; drop `workflow_executions` (or equivalent table name). Run `alembic upgrade head`.
- [ ] Update tests (e.g. `test/test_workflow.py`): remove WorkflowExecution assertions; assert on Run and task_id/status where appropriate.

**1.3.2 Single `user` table (auth + profile); drop user_profiles**

- [ ] In `src/database/models.py`:
  - Add **user** table (Better Auth default name) with:
    - **Auth columns** (match Better Auth): id, name, email, emailVerified, image, createdAt, updatedAt, etc.
    - **Profile columns** (nullable): location, profile_text, suggested_job_titles, source_pdfs, references, last_used_at.
  - Remove **UserProfile** model (and plan to drop `user_profiles` in migration).
  - Update **Run**: rename `user_profile_id` → **user_id**, FK to `user.id`.
- [ ] Create a **data migration** (or combined schema + data): create `user` table; migrate existing `user_profiles` data into `user` where possible (e.g. by email or a chosen mapping); repoint `runs.user_profile_id` → `runs.user_id`; drop `user_profiles`.
- [ ] Update all code that references **UserProfile** or `user_profile_id` to use **user** and profile columns on **user**:
  - [ ] `src/api/api.py`: e.g. resolve profile by user_id; use User (profile columns) instead of UserProfile.
  - [ ] `src/workflow/nodes/profile_retrieval_node.py`, `cv_processing_node.py`, `delivery_node.py`: use User and profile columns.
  - [ ] `src/profiling/profile.py`: use User (profile columns).
  - [ ] `src/fabrication/fab_cover_letter.py`: replace get_user_profile_for_run / get_latest_user_profile with User-based equivalents.
  - [ ] `src/delivery/nylas_service.py`: query User instead of UserProfile.
  - [ ] `src/database/repository.py`: remove UserProfile-specific helpers or reimplement against User.
- [ ] Update `src/database/__init__.py`: export User; remove UserProfile and WorkflowExecution.
- [ ] Run Alembic revision(s) and `alembic upgrade head`; fix any remaining references in tests/docs.

**Acceptance:** No WorkflowExecution or UserProfile in code or DB. Run has task_id and user_id; user table has auth + profile columns. All workflows and tests that depend on profile/run still pass.

### 1.4 Better Auth tables (SQLAlchemy)

- [ ] In `src/database/models.py`, add SQLAlchemy models for Better Auth (singular table names):
  - **session**
  - **account**
  - **verification**
- [ ] Ensure the **user** table (from 1.3.2) matches Better Auth expectations (e.g. emailVerified, expiresAt, createdAt where applicable). Adjust column names if needed for Better Auth’s prismaAdapter.
- [ ] Create an Alembic revision that creates **session**, **account**, **verification** (and any missing columns on **user**). Run `alembic upgrade head`.

**Acceptance:** Tables `user`, `session`, `account`, `verification` exist and match Better Auth schema; backend and Alembic use admin user only.

### 1.5 Backend verification (gate for Phase 2)

- [ ] Run full backend test suite (e.g. workflow tests, API tests).
- [ ] Manually verify: run setup on a clean DB with `alembic upgrade head`; trigger at least one profiling and one job-search workflow; confirm Run and User (profile) are updated correctly and no references to WorkflowExecution or UserProfile remain.
- [ ] Optionally run lint/type checks on changed files.

**Gate:** Phase 2 must not start until Phase 1 is complete and the backend is confirmed working with the new schema and two Postgres users.

---

## Phase 2: Next.js Application (After Backend Is Stable)

**Goal:** Add the Next.js frontend in `frontend/`, with Better Auth (Google OAuth, session plugin), Prisma (introspect + generate only), and Docker/Caddy. No Prisma migrations or db push.

**Reference:** [next-js-setup.md](next-js-setup.md) §§2–8, §9 (checklist items 2–4).

### 2.1 Next.js scaffold and Prisma (introspect only)

- [ ] Create `frontend/` at repo root (e.g. `npx create-next-app@latest frontend` with TypeScript, App Router).
- [ ] Install Prisma and Better Auth in `frontend/`.
- [ ] Implement **`frontend/lib/prisma.ts`** with the **Global Singleton Pattern** (see Best Practices §1) to avoid excess DB connections in development.
- [ ] Configure `frontend/.env`: set `DATABASE_URL` to the **limited-privilege** Postgres user (e.g. `job_agent_ui`).
- [ ] Run **`npx prisma db pull`** in `frontend/` so `schema.prisma` is generated from the existing DB (all tables created by Alembic). Then run **`npx prisma generate`**. **Reminder:** run `prisma db pull` (and then `prisma generate`) every time you add or change a column in the backend.
- [ ] Add `frontend/.env.example` with: `DATABASE_URL`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, Google OAuth vars, `NEXT_PUBLIC_API_URL`, `API_KEY`. Document that **never** run `prisma migrate` or `prisma db push`.
- [ ] Generate **`BETTER_AUTH_SECRET`** with high entropy (e.g. `openssl rand -base64 32`); do not use a weak or default value.

**Acceptance:** Frontend has a Prisma client that reflects current DB; DATABASE_URL uses limited user; schema.prisma is introspected only.

### 2.2 Better Auth configuration

- [ ] Implement `frontend/lib/auth.ts`: configure Better Auth with **prismaAdapter**, **Google OAuth**, and **session** plugin (database-backed sessions).
- [ ] Use Better Auth’s **`[...all]`** catch-all route (not `[...nextauth]`); mount at default **`/_auth/`** or document the path.
- [ ] Set env: `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, Google OAuth client id/secret.
- [ ] Use Prisma in auth flow only as needed (Better Auth uses the same tables created by backend).

**Acceptance:** Sign-in with Google works; session stored in DB; frontend can read current user from session.

### 2.3 Data access and workflow triggers

- [ ] Use Prisma in Server Components / Server Actions to read **user** (with profile columns), **runs**, **job_searches**, **matched_jobs**, etc.; filter by session `user_id` where appropriate.
- [ ] Configure `NEXT_PUBLIC_API_URL` and server-side `API_KEY` for workflow POSTs. Implement a server-side helper that calls FastAPI (e.g. POST `/workflow/profiling`, POST `/workflow/job-search/from-profile`) with the API key (see [api-calls-guide.md](api-calls-guide.md)).

**Acceptance:** Frontend can show “my” data via Prisma and trigger workflows via the existing API.

### 2.4 Docker and Caddy

- [ ] Add **frontend** service to `docker-compose.yml`: build `./frontend`, env for `DATABASE_URL` (limited user), `BETTER_AUTH_*`, Google OAuth, `NEXT_PUBLIC_API_URL`, `API_KEY`; expose port 3000 for dev.
- [ ] Set **`restart: always`** for all services (api, workers, frontend, postgres, etc.) so a frontend or API crash does not leave the stack down.
- [ ] Add production overrides in `docker-compose.prod.yml` if needed (e.g. no host port, production build).
- [ ] Update **Caddyfile**: main app domain → `reverse_proxy frontend:3000` so **`/_auth/*`** (Better Auth) is served by the frontend; leave existing API and Flower blocks unchanged.
- [ ] Ensure Caddy passes **`X-Forwarded-For`** and **`X-Forwarded-Proto`** to the frontend so Better Auth can verify requests are coming via HTTPS (required for auth callbacks).
- [ ] Update [continuous-development.md](continuous-development.md) (and [deployment.md](deployment.md) if present) to mention frontend, new domain, and env vars.

**Acceptance:** `docker compose up` brings up API, workers, Postgres, and frontend; Caddy routes main domain to frontend.

### 2.5 Docs and sync workflow

- [ ] Document the **sync workflow** after any backend schema change: run `alembic upgrade head` (backend); then in `frontend/` run `npx prisma db pull` and `npx prisma generate`. Emphasize: **never** run `prisma migrate` or `prisma db push` in the frontend.

**Acceptance:** New contributors can follow docs to add a backend column and refresh the frontend Prisma client without touching Prisma migrations.

---

## Final Implementation Checklist Add-on

Cross-cutting items that apply across phases:

- [ ] **Alembic `env.py`:** Hardcode the search path or schema if you use one (see §1.1).
- [ ] **Prisma `db pull`:** Run `npx prisma db pull` (then `npx prisma generate`) in `frontend/` every time you add or change a column in the backend.
- [ ] **Better Auth secret:** Generate `BETTER_AUTH_SECRET` with high entropy (e.g. `openssl rand -base64 32`).
- [ ] **Caddy headers:** Ensure Caddy passes `X-Forwarded-For` and `X-Forwarded-Proto` to the frontend so Better Auth can verify HTTPS.
- [ ] **Optional – RLS:** If scaling or compliance requires it, consider Row Level Security for the limited Postgres user (see Best Practices §4).
- [ ] **Optional – PgBouncer:** If the VPS shows "Too many connections," add PgBouncer between apps and Postgres (see Best Practices §5).

---

## Summary

| Phase | Key deliverables |
|-------|-------------------|
| **Phase 1** | Alembic in place; create_tables removed from setup; WorkflowExecution removed, Run has task_id; single user table (auth + profile), user_profiles dropped; Better Auth tables (session, account, verification); two Postgres users; all backend code and tests updated and passing. |
| **Phase 2** | Next.js app in `frontend/`; Prisma introspect + generate only; Better Auth (Google, session); Docker + Caddy; docs and env examples. |

**Order of work:** Complete Phase 1 and verify the backend before starting Phase 2. This keeps schema and migration ownership in the backend and avoids frontend work depending on unstable schema.

For detailed decisions and table layouts, see [next-js-setup.md](next-js-setup.md).
