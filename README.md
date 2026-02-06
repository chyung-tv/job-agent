# Job Agent

An AI-powered job search automation platform that transforms your CV into a structured profile, discovers relevant job postings, intelligently screens matches against your experience, researches target companies, and generates tailored application materials — all orchestrated through an async workflow engine.

**Status:** Production-ready and deployed. The platform uses a modern full-stack architecture with Next.js frontend, FastAPI backend, Celery task queue, and PostgreSQL database.

## Features

### Core Workflows

- **Profile Building** — Upload CV/PDF URLs; the system parses documents (via Docling, PyMuPDF, RapidOCR), extracts skills and experience using AI, and creates a structured profile with suggested job titles.

- **Intelligent Job Search** — Execute a full automation pipeline:
  1. **Discovery** — Find relevant jobs via SerpAPI Google Jobs
  2. **Screening** — AI-powered matching against your profile (Gemini)
  3. **Research** — Gather company intelligence (Exa, web search)
  4. **Fabrication** — Generate tailored CV and cover letter
  5. **Delivery** — Send applications via email (Nylas)

- **Batch Search** — Trigger searches for all your suggested job titles in one request; each runs as a separate async task.

### Platform Features

- **Real-time Progress** — Server-Sent Events (SSE) stream workflow status to the frontend
- **Async Execution** — Celery workers handle long-running AI tasks; API returns `202 Accepted` with tracking IDs
- **User Authentication** — Better Auth with Google OAuth integration
- **Observability** — Optional Langfuse for LLM tracing; Flower for task monitoring; Sentry for error tracking

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

```
┌─────────────────────────────────────────────────────────────────┐
│                        Caddy (HTTPS)                            │
│         TLS termination, domain-based routing                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│   │  Frontend   │    │    API      │    │   Celery    │        │
│   │  Next.js    │───▶│  FastAPI    │───▶│   Worker    │        │
│   │   :3000     │    │   :8000     │    │             │        │
│   └─────────────┘    └─────────────┘    └─────────────┘        │
│          │                  │                  │                │
│          ▼                  ▼                  ▼                │
│   ┌─────────────────────────────────────────────────┐          │
│   │              PostgreSQL :5432                   │          │
│   │   job_agent_ui (frontend) │ job_agent_admin (api)│         │
│   └─────────────────────────────────────────────────┘          │
│                             │                                   │
│                    ┌────────┴────────┐                         │
│                    │  Redis :6379    │                         │
│                    │  (task broker)  │                         │
│                    └─────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

- **Frontend** (`frontend/`) — Next.js application with Better Auth (Google OAuth) and Prisma for data access. Uses limited-privilege Postgres user for security.
- **API** (`src/api/api.py`) — REST endpoints for workflow triggers; all protected routes require `X-API-Key`. No read endpoints; frontend uses Prisma directly.
- **Workflows** — Node-based pipelines in `src/workflow/`:
  - **Profiling**: UserInputNode → CVProcessingNode (parse PDFs, AI profile, save to DB)
  - **Job Search**: ProfileRetrievalNode → DiscoveryNode → MatchingNode → ResearchNode → FabricationNode → CompletionNode → DeliveryNode
- **Celery** — Workers execute workflows asynchronously; state stored in PostgreSQL
- **Database** — SQLAlchemy (backend) is the schema master; Alembic handles migrations. Prisma (frontend) introspects only; never runs migrations.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.13+ (for local backend development)
- Node.js 18+ (for local frontend development)

### 1. Configure Environment

```bash
# Copy and edit backend environment
cp .env.example .env
# Set: POSTGRES_*, GEMINI_API_KEY, SERPAPI_KEY, JOB_LAND_API_KEY, etc.

# Copy and edit frontend environment
cp frontend/.env.example frontend/.env
# Set: DATABASE_URL, BETTER_AUTH_SECRET, GOOGLE_CLIENT_ID, etc.
```

### 2. Run Setup

```bash
# Interactive menu
./setup.sh

# Or use flags directly
./setup.sh --first-time       # Fresh database: create users, run migrations
./setup.sh --migrate          # Apply pending migrations only
./setup.sh --start            # Start all services
./setup.sh --stop             # Stop all services
```

Add `--prod` for production mode (uses `docker-compose.prod.yml` and Caddy).

### 3. Verify

```bash
# Health check (no auth required)
curl http://localhost:8000/health

# Protected endpoint (requires API key)
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (no auth) |
| POST | `/workflow/profiling` | Parse CVs and build user profile |
| POST | `/workflow/job-search` | Run full job search pipeline |
| POST | `/workflow/job-search/from-profile` | Batch search using profile's suggested titles |
| GET | `/workflow/status/{run_id}` | Poll workflow status |
| GET | `/workflow/status/{run_id}/stream` | SSE stream for real-time progress |

All workflow endpoints return `202 Accepted` with `run_id`, `task_id`, and `status_url` for tracking.

## Environment Variables

### Backend (`.env`)

| Variable | Description |
|----------|-------------|
| `POSTGRES_*` | Database connection (host, port, db, user, password) |
| `DATABASE_URL` | SQLAlchemy connection string (uses admin user) |
| `CELERY_BROKER_URL` | Redis URL for task queue |
| `GEMINI_API_KEY` | Google AI for matching/research |
| `SERPAPI_KEY` | Job search API |
| `JOB_LAND_API_KEY` | Internal API authentication |
| `NYLAS_*` | Email delivery credentials |

### Frontend (`frontend/.env`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Prisma connection (uses limited `job_agent_ui` user) |
| `BETTER_AUTH_SECRET` | Session encryption key |
| `BETTER_AUTH_URL` | Auth callback URL |
| `GOOGLE_CLIENT_ID/SECRET` | OAuth credentials |
| `NEXT_PUBLIC_API_URL` | Backend URL (build-time) |

**Security Note:** Frontend uses `job_agent_ui` which can only SELECT/INSERT/UPDATE — no DDL privileges. This prevents Prisma from accidentally modifying schema.

## Development

### Backend

```bash
# Run tests
uv run pytest test/ -v

# Start development stack
./start.sh

# View logs
docker compose logs -f api celery-worker
```

### Frontend

```bash
cd frontend

# Local development
npm run dev

# After backend schema changes
npx prisma db pull && npx prisma generate
```

### Database Migrations

```bash
# Create migration
docker compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec api alembic upgrade head
```

## Documentation

Comprehensive guides in [`docs/`](docs/):

- **[Pre-deployment Setup](docs/pre-deployment-setup-guide.md)** — Local setup, VPS configuration
- **[Deployment Guide](docs/deployment.md)** — Production deployment walkthrough
- **[Continuous Development](docs/continuous-development.md)** — Redeploy workflow
- **[API Calls Guide](docs/api-calls-guide.md)** — Endpoint usage examples
- **[Celery Documentation](docs/celery.md)** — Task queue configuration

## Project Layout

```
job-agent/
├── frontend/                 # Next.js application
│   ├── app/                  # App Router pages
│   ├── components/           # React components
│   ├── lib/                  # Auth, Prisma, utilities
│   └── prisma/               # Schema (introspect only)
├── src/                      # Python backend
│   ├── api/                  # FastAPI endpoints
│   ├── workflow/             # Node-based pipelines
│   ├── database/             # SQLAlchemy models
│   ├── tasks/                # Celery tasks
│   ├── profiling/            # CV parsing
│   ├── discovery/            # Job search (SerpAPI)
│   ├── matcher/              # AI screening
│   ├── research/             # Company research
│   ├── fabrication/          # CV/cover letter generation
│   └── delivery/             # Email delivery
├── alembic/                  # Database migrations
├── test/                     # Test suite
├── docker-compose.yml        # Development config
├── docker-compose.prod.yml   # Production overrides
├── Caddyfile                 # Reverse proxy config
└── setup.sh                  # Deployment automation
```

## License

See repository for license information.
