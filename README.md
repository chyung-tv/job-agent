# Job Agent

Automated job search and application workflow: build a profile from your CV, discover jobs, match them to your profile, research companies, generate tailored CVs and cover letters, and optionally deliver applications via email.

## Features

- **Profiling workflow** — Submit CV/PDF URLs; the system parses them, extracts skills and experience, and creates a structured user profile with suggested job titles.
- **Job search workflow** — Run a full pipeline: load profile → discover jobs (SerpAPI) → screen/match (AI) → research companies → fabricate CV and cover letter → deliver (e.g. Nylas email).
- **Run from profile** — Trigger multiple job searches in one request using a profile’s suggested job titles and location; each search runs as a separate Celery task.
- **Async execution** — Workflows run in Celery workers; the API returns `202 Accepted` with `run_id`, `execution_id`, `task_id`, and `status_url`.
- **Observability** — Optional Langfuse integration; Flower for Celery task monitoring.

## Tech Stack

| Layer        | Technology                          |
|-------------|-------------------------------------|
| **Frontend** | Next.js (App Router), TypeScript, Better Auth (Google OAuth), Prisma |
| **API**      | FastAPI, uvicorn                    |
| **Tasks**    | Celery, Redis (broker & result)     |
| **Database** | PostgreSQL (SQLAlchemy 2 + Alembic for migrations, Prisma for frontend reads) |
| **Job search** | SerpAPI, Gemini (matching/research), Exa (research) |
| **Delivery** | Nylas (email)                       |
| **CV parsing** | Docling, PyMuPDF, RapidOCR          |
| **Observability** | Langfuse, Flower, Sentry (optional) |
| **Runtime**  | Docker, Docker Compose, Caddy (HTTPS) |

## Architecture

- **Frontend** (`frontend/`) — Next.js application with Better Auth (Google OAuth) and Prisma for data access. Uses limited-privilege Postgres user for security.
- **API** (`src/api/api.py`) — REST endpoints for workflow triggers; all protected routes require `X-API-Key` or `Authorization: Bearer <key>`. No read endpoints; frontend uses Prisma directly.
- **Workflows** — Node-based pipelines in `src/workflow/`:
  - **Profiling**: UserInputNode → CVProcessingNode (parse PDFs, AI profile, save to DB).
  - **Job search**: ProfileRetrievalNode → DiscoveryNode → MatchingNode → ResearchNode → FabricationNode → CompletionNode → DeliveryNode.
- **Celery** — `execute_profiling_workflow` and `execute_job_search_workflow` run in worker containers; state is stored in PostgreSQL (`Run`, `user` table with auth + profile columns).
- **Database** — SQLAlchemy (backend) is the schema master; Alembic handles migrations. Prisma (frontend) introspects and generates a client; never runs migrations.

## Prerequisites

- Docker and Docker Compose
- Python 3.13+ (for backend; see `pyproject.toml`)
- Node.js 18+ (for frontend; see `frontend/package.json`)
- `.env` (copy from `.env.example` and set API keys, DB, Redis, etc.)
- `frontend/.env` (copy from `frontend/.env.example` and set `DATABASE_URL`, `BETTER_AUTH_*`, Google OAuth, etc.)

## Quick Start

1. **Clone and enter the repo**
   ```bash
   cd job-agent
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env: POSTGRES_*, REDIS, GEMINI_API_KEY, SERPAPI_KEY, API_KEY, etc.
   ```

3. **Run setup (menu or flags)**
   ```bash
   ./setup.sh                    # Interactive menu: first-time, overwrite, migrations, start/stop, etc.
   ./setup.sh --first-time       # First-time: start stack + run migrations (new DB)
   ./setup.sh --migrate           # Apply migrations only (alembic upgrade head)
   ./setup.sh --start             # Start stack (or use ./start.sh)
   ./setup.sh --stop              # Stop stack (or use ./stop.sh)
   ```
   Use `--dev` (default) or `--prod` with any flag. For a fresh DB with two Postgres users, run **First-time setup** from the menu or `./setup.sh --first-time`.

4. **Call the API** (e.g. health, then a workflow)
   ```bash
   curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/health
   ```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root (API name/version); requires API key |
| GET | `/health` | Health check (no auth) |
| POST | `/workflow/profiling` | Run profiling workflow (body: ProfilingWorkflow.Context); returns 202 |
| POST | `/workflow/job-search` | Run single job search (body: JobSearchWorkflow.Context); returns 202 |
| POST | `/workflow/job-search/from-profile` | Run job searches for all suggested job titles of a profile (body: `profile_id`, optional `num_results`, `max_screening`); returns 202 |

Responses for workflow endpoints include `run_id`, `execution_id`, `task_id`, `status`, `status_url`, and `estimated_completion_time`. Use Flower (e.g. port 5555) or your own status implementation to track runs.

## Authentication

Protected routes require either:

- Header: `X-API-Key: <your-api-key>`
- Or: `Authorization: Bearer <your-api-key>`

Set `API_KEY` in `.env` (and optionally override the default in `src/config.py` for development).

## Environment Variables

### Backend (`.env`)
See `.env.example` for the full list. Main groups:

- **Database** — `POSTGRES_*`, `DATABASE_URL` (uses admin user for migrations)
- **Redis / Celery** — `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- **External APIs** — `GEMINI_API_KEY`, `SERPAPI_KEY`, `EXA_API_KEY`, `NYLAS_*`, `PDFBOLTS_API_KEY`
- **Observability** — `LANGFUSE_*`, `SENTRY_DSN`
- **API / Flower** — `API_KEY`, `API_PORT`, `FLOWER_PORT`, `FLOWER_BASIC_AUTH_*`
- **Deployment** — `API_DOMAIN`, `FLOWER_DOMAIN` (for Caddy)

### Frontend (`frontend/.env`)
See `frontend/.env.example`. Main variables:

- **Database** — `DATABASE_URL` (uses limited-privilege user: `job_agent_ui`)
- **Authentication** — `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, Google OAuth (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
- **API Integration** — `NEXT_PUBLIC_API_URL`, `API_KEY` (server-side only)

**Important:** Frontend uses a limited-privilege Postgres user (`job_agent_ui`) that can only `SELECT`, `INSERT`, `UPDATE`—never `CREATE`, `ALTER`, or `DROP`. This prevents accidental Prisma migrations from affecting production.

## Project Layout

```
job-agent/
  frontend/              # Next.js frontend application
    app/                 # App Router pages and routes
      api/auth/[...all]/ # Better Auth catch-all route
    lib/                 # Auth config, Prisma client, utilities
    prisma/              # Prisma schema (introspected only, never migrated)
    components/          # React components (UI)
  src/                   # Backend Python code
    api/                 # FastAPI app and routes
    celery_app.py        # Celery app and task registration
    config.py            # Constants and API key
    database/            # Models, session, repository, Alembic migrations
    delivery/            # Nylas email, templates
    discovery/           # SerpAPI job search
    fabrication/         # CV and cover letter generation
    matcher/             # Job screening (AI)
    profiling/           # PDF parsing, profile building
    research/            # Company research (AI, Exa)
    tasks/               # Celery tasks (profiling, job search)
    workflow/            # Base workflow + job_search & profiling workflows + nodes
  alembic/               # Database migrations (Alembic)
  docs/                  # Documentation (see Documentation section below)
  test/                  # Request and workflow tests
  docker-compose.yml     # Development Docker Compose config
  docker-compose.prod.yml # Production overrides
  Caddyfile              # Caddy reverse proxy config
  setup.sh               # Setup script (migrations, start/stop)
```

## Documentation

Comprehensive documentation is available in the [`docs/`](docs/) directory:

### Setup & Deployment
- **[Pre-deployment setup guide](docs/pre-deployment-setup-guide.md)** — Local setup, domain configuration, Hetzner VPS, Caddy, environment variables, database tables, Flower
- **[Deployment guide](docs/deployment.md)** — Production deployment walkthrough (Hetzner, DNS, Caddy, HTTPS)
- **[Continuous development](docs/continuous-development.md)** — Redeploy checklist and workflow

### Frontend & Integration
- **[Next.js setup plan](docs/next-js-setup.md)** — Architecture decisions, Better Auth, Prisma, SQLAlchemy as schema master
- **[Next.js implementation plan](docs/next-implementation.md)** — Phased implementation: backend (Alembic, model consolidation) then frontend (Next.js, Better Auth, Prisma)
- **[API calls guide](docs/api-calls-guide.md)** — How to call the FastAPI endpoints from command line or HTTP clients

### Backend & Infrastructure
- **[Celery documentation](docs/celery.md)** — Celery setup and configuration
- **[Celery implementation plan](docs/celery-implementation-plan.md)** — Implementation details for async task execution
- **[Langfuse documentation](docs/langfuse.md)** — Observability and LLM tracing
- **[Langfuse integration guide](docs/langfuse-integration-guide.md)** — How to integrate Langfuse for workflow observability

### Additional Resources
- **[Workflow logs](docs/finished/WORKFLOW_LOGS.md)** — Understanding workflow execution logs and common messages

**Note:** Some completed documentation is archived in [`docs/finished/`](docs/finished/).

## Development

### Backend
- **Run tests**: from project root, run your test runner against `test/` (e.g. `pytest test/` if configured).
- **Local stack**: `./start.sh` then `./setup.sh`; API on port 8000, Flower on 5555 (see `docker-compose.yml`).
- **Production-like**: `./start.sh --prod` and `./setup.sh --prod` (uses `docker-compose.prod.yml` and Caddy).

### Frontend
- **Local development**: `cd frontend && npm run dev` (runs on port 3000).
- **Prisma sync**: After backend schema changes, run `npx prisma db pull` then `npx prisma generate` in `frontend/`. **Never** run `prisma migrate` or `prisma db push`.
- **Docker**: Frontend runs in Docker Compose alongside backend services.

### Database Migrations
- **Backend**: All schema changes via Alembic (`alembic revision --autogenerate`, then `alembic upgrade head`).
- **Frontend**: Prisma only introspects (`prisma db pull`) and generates client (`prisma generate`). See [Next.js setup plan](docs/next-js-setup.md) for details.

## License

See repository for license information.
