# Deployment Memo: Full-Stack Deployment (Frontend + Backend)

This memo outlines everything needed to deploy the complete job-agent application (Next.js frontend + FastAPI backend) and documents items that were not yet addressed.

---

## Domain Strategy (Decided)

| Service | Domain | Example |
|---------|--------|---------|
| Frontend | `app.yourdomain.com` | `app.jobland.io` |
| API | `api.yourdomain.com` | `api.jobland.io` |
| Flower | `flower.yourdomain.com` (optional) | `flower.jobland.io` |

**Rationale**: Subdomain (`app.`) is preferred over apex domain for:
- Easier CDN/separate hosting migration later
- Clearer separation of concerns
- Simpler cookie/CORS configuration

---

## Current State Summary

| Component | Status |
|-----------|--------|
| Backend (FastAPI, Celery) | Dockerized, production-ready |
| Frontend (Next.js) | **NOT Dockerized** - runs locally only |
| Database (PostgreSQL) | Dockerized, two-user setup exists |
| Reverse Proxy (Caddy) | Routes API only, **no frontend routing** |
| setup.sh | Handles backend DB setup only |

---

## 1. Required Changes

### 1.1 Create `Dockerfile.frontend`

A new Dockerfile is needed for the Next.js frontend with Docker BuildKit caching:

```dockerfile
# syntax=docker/dockerfile:1

# Build stage
FROM node:22-alpine AS builder
WORKDIR /app

# Copy package files first for better layer caching
COPY frontend/package*.json ./

# Use BuildKit cache mount for npm
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Copy source and prisma schema
COPY frontend/ .

# Generate Prisma client
RUN npx prisma generate

# Build Next.js
RUN npm run build

# Runtime stage
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Copy built assets
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/node_modules/.prisma ./node_modules/.prisma

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/api/health || exit 1

EXPOSE 3000
CMD ["node", "server.js"]
```

**Notes**:
- Uses BuildKit cache mount for faster npm installs
- Includes health check for Docker orchestration
- Next.js requires `output: 'standalone'` in `next.config.ts`

### 1.2 Update `next.config.ts`

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

### 1.3 Create Frontend Health Endpoint

Create `frontend/app/api/health/route.ts`:

```typescript
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ status: "healthy" }, { status: 200 });
}
```

This endpoint is used by Docker healthcheck and can be used for load balancer health probes.

### 1.4 Update `docker-compose.yml`

Add frontend service:

```yaml
# Next.js Frontend
frontend:
  build:
    context: .
    dockerfile: Dockerfile.frontend
  container_name: job-agent-frontend
  restart: unless-stopped
  ports:
    - "${FRONTEND_PORT:-3000}:3000"
  healthcheck:
    test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3000/api/health"]
    interval: 30s
    timeout: 10s
    start_period: 10s
    retries: 3
  environment:
    NODE_ENV: production
    # Database (limited privilege user)
    DATABASE_URL: postgresql://job_agent_ui:${POSTGRES_UI_PASSWORD}@postgres:5432/${POSTGRES_DB:-job_agent}
    # Better Auth
    BETTER_AUTH_SECRET: ${BETTER_AUTH_SECRET}
    BETTER_AUTH_URL: ${BETTER_AUTH_URL:-http://localhost:3000}
    NEXT_PUBLIC_BETTER_AUTH_URL: ${NEXT_PUBLIC_BETTER_AUTH_URL:-http://localhost:3000}
    # Google OAuth
    BETTER_AUTH_GOOGLE_CLIENT_ID: ${BETTER_AUTH_GOOGLE_CLIENT_ID}
    BETTER_AUTH_GOOGLE_CLIENT_SECRET: ${BETTER_AUTH_GOOGLE_CLIENT_SECRET}
    # Backend API
    NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://api:8000}
    API_KEY: ${JOB_LAND_API_KEY}
    # UploadThing
    UPLOADTHING_TOKEN: ${UPLOADTHING_TOKEN}
    # Gemini (for AI chat in onboarding)
    GEMINI_API_KEY: ${GEMINI_API_KEY}
  depends_on:
    postgres:
      condition: service_healthy
    api:
      condition: service_started
  networks:
    - job-agent-network
```

### 1.5 Update `docker-compose.prod.yml`

Add frontend production overrides:

```yaml
frontend:
  build:
    context: .
    dockerfile: Dockerfile.frontend
  ports: []  # Caddy handles routing
  environment:
    NEXT_PUBLIC_API_URL: https://${API_DOMAIN}
    BETTER_AUTH_URL: https://${FRONTEND_DOMAIN}
    NEXT_PUBLIC_BETTER_AUTH_URL: https://${FRONTEND_DOMAIN}
```

### 1.6 Update `Caddyfile`

Add frontend routing and apex domain redirect:

```caddy
# Apex domain redirect: yourapp.com -> app.yourapp.com
{$APEX_DOMAIN} {
	redir https://{$FRONTEND_DOMAIN}{uri} permanent
}

# Frontend: app subdomain (e.g. app.yourapp.com)
{$FRONTEND_DOMAIN} {
	reverse_proxy frontend:3000
}

# API: api subdomain (e.g. api.yourapp.com)
{$API_DOMAIN} {
	reverse_proxy api:8000 {
		transport http {
			read_timeout 600s
		}
	}
}
```

**Note**: The apex redirect ensures users visiting `yourapp.com` are redirected to `app.yourapp.com`. Requires `APEX_DOMAIN` env var (e.g., `yourapp.com`).

---

## 2. Database Permissions (Overlooked!)

### Current Grants for `job_agent_ui`
- SELECT, INSERT, UPDATE, DELETE on: `user`, `session`, `account`, `verification` (Better Auth tables)
- USAGE on schema `public`
- DEFAULT PRIVILEGES for future tables created by `job_agent_admin`

### Missing Grants (Frontend Dashboard Needs)
The frontend dashboard reads data from backend tables. The `job_agent_ui` user needs **SELECT-only** access to:

| Table | Access Needed | Purpose |
|-------|---------------|---------|
| `job_searches` | SELECT | Dashboard overview, search history |
| `runs` | SELECT | Run status, history |
| `matched_jobs` | SELECT | Match list, detail view |
| `job_postings` | SELECT | Job details within matches |
| `artifacts` | SELECT | View cover letters, CVs |
| `company_research` | SELECT | View research in match detail |

### New SQL Script: `grant-frontend-read-permissions.sql`

```sql
-- Grant SELECT on backend tables to job_agent_ui (frontend)
-- Run after migrations create these tables

DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'job_searches') THEN
    GRANT SELECT ON TABLE public.job_searches TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'runs') THEN
    GRANT SELECT ON TABLE public.runs TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'matched_jobs') THEN
    GRANT SELECT ON TABLE public.matched_jobs TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'job_postings') THEN
    GRANT SELECT ON TABLE public.job_postings TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'artifacts') THEN
    GRANT SELECT ON TABLE public.artifacts TO job_agent_ui;
  END IF;
  IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'company_research') THEN
    GRANT SELECT ON TABLE public.company_research TO job_agent_ui;
  END IF;
END $$;
```

### Update `grant-better-auth-permissions.sql`
Rename to `grant-frontend-permissions.sql` and merge with above grants.

---

## 3. Environment Variables (Overlooked!)

### New Variables for Root `.env.example`

```env
#################################
# Frontend (Next.js)            #
#################################

# Frontend port (host side, dev only)
FRONTEND_PORT=3000

# Apex domain (production only, e.g. yourapp.com)
# Redirects to FRONTEND_DOMAIN (app.yourapp.com)
APEX_DOMAIN=

# Frontend domain (production only, e.g. app.yourapp.com)
# Using subdomain (app.) is recommended over apex domain
FRONTEND_DOMAIN=

# Better Auth Secret (generate with: openssl rand -base64 32)
BETTER_AUTH_SECRET=

# Better Auth URLs
# Local: http://localhost:3000
# Production: https://app.yourapp.com (your FRONTEND_DOMAIN)
BETTER_AUTH_URL=http://localhost:3000
NEXT_PUBLIC_BETTER_AUTH_URL=http://localhost:3000

# Google OAuth (create credentials in Google Cloud Console)
# IMPORTANT: Add redirect URIs in Google Cloud:
#   - http://localhost:3000/api/auth/callback/google (dev)
#   - https://app.yourapp.com/api/auth/callback/google (prod)
BETTER_AUTH_GOOGLE_CLIENT_ID=
BETTER_AUTH_GOOGLE_CLIENT_SECRET=

# Backend API URL (how frontend reaches backend)
# Local: http://localhost:8000
# Docker internal: http://api:8000
# Production (from browser): https://api.yourapp.com
NEXT_PUBLIC_API_URL=http://localhost:8000

# UploadThing Token (for file uploads)
# No domain allowlisting required - token provides authentication
UPLOADTHING_TOKEN=
```

### UploadThing Configuration

**Does UploadThing require domain allowlisting?** No.

UploadThing uses token-based authentication (`UPLOADTHING_TOKEN`). Security is handled via:
- The token authenticates your app with UploadThing's servers
- Middleware-based auth in your file routes (verify user session before allowing uploads)
- Webhook callbacks are signed with HMAC SHA256 (auto-verified since SDK v6.7)

**Optional dashboard settings** (at uploadthing.com/dashboard):
- **Region**: Select where files are stored (default: US West - Seattle)
- **ACL**: Choose `public-read` or `private` (private requires signed URLs)

No domain/origin allowlisting is needed - just set `UPLOADTHING_TOKEN` in your environment.

### CORS Configuration (Overlooked!)

The backend needs to accept requests from the frontend domain. Current `.env.example` has:

```env
CORS_ORIGINS=http://localhost:3000
```

For production, this needs:
```env
CORS_ORIGINS=https://app.yourapp.com,https://api.yourapp.com
```

**TODO**: Update `src/config.py` and `src/api/api.py` to read CORS_ORIGINS and apply to FastAPI CORS middleware.

---

## 4. Revised `setup.sh` Functions

### Menu Options

| # | Option | Description |
|---|--------|-------------|
| 1 | First-time setup | Factory reset: wipe DB, create users, run migrations, grant permissions, sync Prisma. **Warning displayed.** |
| 2 | DB migration - hard | Drop schema, re-run migrations, sync Prisma. **Destroys all data. Warning displayed.** |
| 3 | DB migration - soft | Alembic upgrade head + re-grant permissions + sync Prisma. Non-destructive. |
| 4 | Restart containers | Stop, rebuild with `--no-cache`, start fresh. For deploying code changes. |
| 5 | Start applications | `docker compose up -d` (uses cached images) |
| 6 | Stop applications | `docker compose down` |
| 7 | Toggle dev/prod | Switch between dev and prod compose files |
| 8 | Quit | Exit menu |

### Implementation Notes

#### Option 1: First-time Setup
```bash
# Steps:
1. Display WARNING: "This will DESTROY all data and factory reset the application."
2. Require user to type 'yes' to confirm
3. Stop all containers (if running)
4. Remove postgres volume (docker volume rm job-agent_postgres_data)
5. Start postgres and redis only
6. Wait for postgres healthy
7. Run grant-two-users-existing-db.sql (creates job_agent_admin, job_agent_ui)
8. Run alembic upgrade head (creates all tables)
9. Run grant-frontend-permissions.sql (grants SELECT on backend tables to UI user)
10. Run grant-better-auth-permissions.sql (grants CRUD on auth tables to UI user)
11. Sync Prisma schema with database:
    - Run: npx prisma db pull (in frontend directory)
    - Run: npx prisma generate
12. Start all containers
13. Display success message
```

#### Option 2: DB Migration - Hard
```bash
# Steps:
1. Display WARNING: "This will DROP the public schema and DESTROY ALL DATA."
2. Require user to type 'yes' to confirm
3. Run reset_db.py (DROP SCHEMA public CASCADE; CREATE SCHEMA public)
4. Run alembic upgrade head
5. Re-run all permission grants
6. Sync Prisma schema:
    - Run: npx prisma db pull (in frontend directory)
    - Run: npx prisma generate
7. Display success message
```

#### Option 3: DB Migration - Soft
```bash
# Steps:
1. Run alembic upgrade head
2. Re-run all permission grants (idempotent)
3. Sync Prisma schema:
    - Run: npx prisma db pull (in frontend directory)
    - Run: npx prisma generate
4. Display success message with "No data was lost."
```

#### Option 4: Restart Containers (Fresh Rebuild)
```bash
# Steps:
1. docker compose down
2. docker compose build --no-cache   # Force fresh build, no layer cache
3. docker compose up -d
4. Display: "Containers rebuilt without cache and restarted."
```

**Why `--no-cache`?** Ensures code changes are picked up. Cached layers may contain stale code. Use this after `git pull` to deploy updates.

#### Option 5: Start Applications (Use Cache)
```bash
# Steps:
1. docker compose up -d --build    # Uses cached layers for speed
2. Display: "Containers started (using cached images where available)."
```

### Command-Line Flags

```bash
./setup.sh --first-time [--dev|--prod]   # First-time setup
./setup.sh --hard-reset [--dev|--prod]   # DB migration - hard
./setup.sh --migrate [--dev|--prod]      # DB migration - soft
./setup.sh --restart [--dev|--prod]      # Restart with --no-cache rebuild
./setup.sh --start [--dev|--prod]        # Start applications (cached)
./setup.sh --stop [--dev|--prod]         # Stop applications
```

### Prisma Sync Details

After any migration, the frontend's Prisma schema must be synced with the database:

```bash
# Run inside the frontend directory (or via docker exec)
cd frontend
npx prisma db pull      # Introspect DB and update schema.prisma
npx prisma generate     # Regenerate Prisma Client with new schema
```

For Docker builds, this happens automatically in `Dockerfile.frontend` during build. The sync step in setup.sh ensures local development and the checked-in `schema.prisma` stay in sync.

---

## 5. Deployment Workflow

### First Deployment (Server)

```bash
# 1. Clone repo
git clone git@github.com:your-org/job-agent.git
cd job-agent

# 2. Create .env from .env.example, fill in all values
#    - Set APEX_DOMAIN=yourapp.com
#    - Set FRONTEND_DOMAIN=app.yourapp.com
#    - Set API_DOMAIN=api.yourapp.com
#    - Generate BETTER_AUTH_SECRET with: openssl rand -base64 32

# 3. Run first-time setup (includes Prisma sync)
./setup.sh --first-time --prod

# 4. Verify
curl https://api.yourapp.com/health        # Backend health
curl https://app.yourapp.com/api/health    # Frontend health
# Open https://app.yourapp.com in browser
```

### Subsequent Deployments

```bash
cd job-agent
git pull origin main

# If schema changed (backend Alembic migration):
./setup.sh --migrate --prod    # Includes prisma db pull + generate

# Restart to pick up code changes (rebuilds with --no-cache):
./setup.sh --restart --prod
```

### Quick Reference

| Scenario | Command |
|----------|---------|
| First time on new server | `./setup.sh --first-time --prod` |
| Deploy code changes | `git pull && ./setup.sh --restart --prod` |
| Deploy with DB migration | `git pull && ./setup.sh --migrate --prod && ./setup.sh --restart --prod` |
| Factory reset (wipe all) | `./setup.sh --first-time --prod` |
| Just stop | `./setup.sh --stop --prod` |
| Just start (no rebuild) | `./setup.sh --start --prod` |

---

## 6. Overlooked Items Summary

| Item | Status | Action Required |
|------|--------|-----------------|
| **Dockerfile.frontend** | Missing | Create new file (with BuildKit cache + healthcheck) |
| **next.config.ts standalone** | Missing | Add `output: 'standalone'` |
| **Frontend health endpoint** | Missing | Create `app/api/health/route.ts` |
| **docker-compose.yml frontend** | Missing | Add frontend service |
| **docker-compose.prod.yml frontend** | Missing | Add frontend overrides |
| **Caddyfile frontend routing** | Missing | Add frontend domain block |
| **Frontend DB permissions** | Incomplete | Add SELECT grants for dashboard tables |
| **Root .env.example** | Incomplete | Add frontend env vars |
| **CORS for production** | Not configured | Update CORS_ORIGINS for `app.yourapp.com` |
| **Google OAuth redirect URIs** | Docs only | User must configure in Google Cloud Console |
| **UploadThing production** | Documented | No domain allowlisting needed (token-based auth) |
| **Prisma schema sync** | Automated | `prisma db pull && generate` runs in setup.sh after migrations |
| **Frontend .env vs Root .env** | Separate files | Consolidate into single root .env |

---

## 7. DNS Records Needed

| Type | Name | Value | Purpose |
|------|------|-------|---------|
| A | @ | `<SERVER_IP>` | Apex domain (`yourapp.com`) - redirects to app |
| A | app | `<SERVER_IP>` | Frontend (`app.yourapp.com`) |
| A | api | `<SERVER_IP>` | Backend API (`api.yourapp.com`) |
| A | flower | `<SERVER_IP>` | Flower monitoring (optional) |

All records point to the same server IP. Caddy routes based on hostname and handles the apex→app redirect.

---

## 8. Security Checklist

- [ ] `BETTER_AUTH_SECRET` is a strong random string (32+ bytes)
- [ ] `POSTGRES_PASSWORD` and `POSTGRES_UI_PASSWORD` are strong and different
- [ ] `.env` is in `.gitignore` and never committed
- [ ] Google OAuth redirect URIs are set for production domain
- [ ] CORS_ORIGINS includes only your domains
- [ ] Flower is behind Basic Auth (or not exposed)
- [ ] UFW firewall allows only 22, 80, 443

---

## 9. Files to Create/Modify

### Create
- `Dockerfile.frontend` - with BuildKit cache mounts and healthcheck
- `frontend/app/api/health/route.ts` - health endpoint for Docker/load balancer
- `scripts/grant-frontend-permissions.sql` (or merge into existing)

### Modify
- `frontend/next.config.ts` - add `output: 'standalone'`
- `docker-compose.yml` - add frontend service
- `docker-compose.prod.yml` - add frontend overrides
- `Caddyfile` - add frontend routing + apex redirect (`yourapp.com` → `app.yourapp.com`)
- `.env.example` - add frontend variables (APEX_DOMAIN, FRONTEND_DOMAIN, BETTER_AUTH_*, etc.)
- `setup.sh` - rewrite with new functions (prisma sync, --no-cache restart)
- `scripts/grant-better-auth-permissions.sql` - add backend table SELECT grants

### Consider Merging
- `frontend/.env.example` → root `.env.example` (avoid managing two env files)

---

## 10. Decisions Made

| Question | Decision |
|----------|----------|
| Frontend domain strategy | Use `app.yourapp.com` (subdomain) - easier for future CDN/separate hosting |
| Apex domain redirect | Yes - `yourapp.com` redirects to `app.yourapp.com` via Caddy |
| UploadThing domain allowlisting | Not needed - uses token-based auth |
| Prisma schema sync | Automated via `prisma db pull && generate` in setup.sh after migrations |
| Docker build caching | Use BuildKit cache mounts; `--no-cache` for restart option |
| Frontend health checks | Add `/api/health` endpoint for Docker healthcheck |
| CI/CD | Not needed - manual deployment via `git pull && setup.sh` |

---

## Next Steps

1. Implement all changes listed in Section 9
2. Test full-stack deployment locally with `--dev`
3. Test on staging server with `--prod`
4. Update `docs/deployment.md` with frontend-specific instructions
5. Remove `start.sh` and `stop.sh` (functionality moved to `setup.sh`)

