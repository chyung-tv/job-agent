# Pre-Deployment Setup Guide

This guide covers all local tasks required before deploying the job-agent application (Next.js frontend + FastAPI backend) to production.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Step-by-Step Local Setup](#2-step-by-step-local-setup)
3. [Configuration Files Checklist](#3-configuration-files-checklist)
4. [Preflight Checks](#4-preflight-checks)
5. [Quick Reference](#5-quick-reference)

---

## 1. Prerequisites

### Required Tools

| Tool | Version | Check Command |
|------|---------|---------------|
| Docker | 20.10+ | `docker --version` |
| Docker Compose | 2.0+ | `docker compose version` |
| Node.js | 22+ | `node --version` |
| Python | 3.11+ | `python --version` |
| Git | 2.0+ | `git --version` |

### Required Accounts & Credentials

- [ ] **Google Cloud Console** - OAuth credentials for authentication
- [ ] **UploadThing** - Token for file uploads
- [ ] **Gemini API** - API key for AI chat features
- [ ] **Domain registrar** - Access to configure DNS records

---

## 2. Step-by-Step Local Setup

### Step 1: Create Frontend Dockerfile

Create `Dockerfile.frontend` in the project root:

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

### Step 2: Update Next.js Configuration

Edit `frontend/next.config.ts`:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

### Step 3: Create Frontend Health Endpoint

Create `frontend/app/api/health/route.ts`:

```typescript
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ status: "healthy" }, { status: 200 });
}
```

### Step 4: Create Frontend Database Permissions Script

Create `scripts/grant-frontend-read-permissions.sql`:

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

### Step 5: Update Docker Compose Configuration

Add the frontend service to `docker-compose.yml`:

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
    DATABASE_URL: postgresql://job_agent_ui:${POSTGRES_UI_PASSWORD}@postgres:5432/${POSTGRES_DB:-job_agent}
    BETTER_AUTH_SECRET: ${BETTER_AUTH_SECRET}
    BETTER_AUTH_URL: ${BETTER_AUTH_URL:-http://localhost:3000}
    NEXT_PUBLIC_BETTER_AUTH_URL: ${NEXT_PUBLIC_BETTER_AUTH_URL:-http://localhost:3000}
    BETTER_AUTH_GOOGLE_CLIENT_ID: ${BETTER_AUTH_GOOGLE_CLIENT_ID}
    BETTER_AUTH_GOOGLE_CLIENT_SECRET: ${BETTER_AUTH_GOOGLE_CLIENT_SECRET}
    NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://api:8000}
    API_KEY: ${JOB_LAND_API_KEY}
    UPLOADTHING_TOKEN: ${UPLOADTHING_TOKEN}
    GEMINI_API_KEY: ${GEMINI_API_KEY}
  depends_on:
    postgres:
      condition: service_healthy
    api:
      condition: service_started
  networks:
    - job-agent-network
```

Add to `docker-compose.prod.yml`:

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

### Step 6: Update Caddyfile

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

### Step 7: Update Environment Variables

Add these to your root `.env.example`:

```env
#################################
# Frontend (Next.js)            #
#################################

# Frontend port (host side, dev only)
FRONTEND_PORT=3000

# Domain configuration (production only)
APEX_DOMAIN=                    # e.g., yourapp.com
FRONTEND_DOMAIN=                # e.g., app.yourapp.com
API_DOMAIN=                     # e.g., api.yourapp.com

# Better Auth Secret (generate with: openssl rand -base64 32)
BETTER_AUTH_SECRET=

# Better Auth URLs
# Local: http://localhost:3000
# Production: https://app.yourapp.com
BETTER_AUTH_URL=http://localhost:3000
NEXT_PUBLIC_BETTER_AUTH_URL=http://localhost:3000

# Google OAuth
BETTER_AUTH_GOOGLE_CLIENT_ID=
BETTER_AUTH_GOOGLE_CLIENT_SECRET=

# Backend API URL (how frontend reaches backend)
# Local: http://localhost:8000
# Docker internal: http://api:8000
# Production (from browser): https://api.yourapp.com
NEXT_PUBLIC_API_URL=http://localhost:8000

# UploadThing Token (for file uploads)
UPLOADTHING_TOKEN=
```

Update `CORS_ORIGINS` for production:

```env
# Add your production domains
CORS_ORIGINS=https://app.yourapp.com,https://api.yourapp.com
```

### Step 8: Configure Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** > **Credentials**
3. Create or edit OAuth 2.0 Client ID
4. Add authorized redirect URIs:
   - Development: `http://localhost:3000/api/auth/callback/google`
   - Production: `https://app.yourapp.com/api/auth/callback/google`

### Step 9: Test Local Docker Build

```bash
# Build and test frontend Docker image
docker build -f Dockerfile.frontend -t job-agent-frontend:test .

# Verify the build succeeded
docker images | grep job-agent-frontend

# Test the container starts (requires DB)
docker compose up -d postgres redis
docker compose up frontend
```

---

## 3. Configuration Files Checklist

### Files to Create

| File | Purpose |
|------|---------|
| `Dockerfile.frontend` | Docker image for Next.js frontend |
| `frontend/app/api/health/route.ts` | Health endpoint for Docker/load balancer |
| `scripts/grant-frontend-read-permissions.sql` | SELECT grants for dashboard tables |

### Files to Modify

| File | Changes |
|------|---------|
| `frontend/next.config.ts` | Add `output: 'standalone'` |
| `docker-compose.yml` | Add frontend service |
| `docker-compose.prod.yml` | Add frontend production overrides |
| `Caddyfile` | Add frontend routing + apex redirect |
| `.env.example` | Add frontend variables |
| `setup.sh` | Add Prisma sync, --no-cache restart |

---

## 4. Preflight Checks

Run these checks before deploying to ensure everything is properly configured.

### 4.1 File Existence Checks

```bash
# Run from project root
echo "=== File Existence Checks ==="

# Required files
FILES=(
  "Dockerfile.frontend"
  "frontend/app/api/health/route.ts"
  "scripts/grant-frontend-read-permissions.sql"
  "docker-compose.yml"
  "docker-compose.prod.yml"
  "Caddyfile"
  ".env"
)

for file in "${FILES[@]}"; do
  if [ -f "$file" ]; then
    echo "✓ $file exists"
  else
    echo "✗ $file MISSING"
  fi
done
```

### 4.2 Next.js Configuration Check

```bash
echo "=== Next.js Config Check ==="
if grep -q "output.*standalone" frontend/next.config.ts 2>/dev/null; then
  echo "✓ Standalone output configured"
else
  echo "✗ Missing 'output: standalone' in next.config.ts"
fi
```

### 4.3 Environment Variables Check

```bash
echo "=== Environment Variables Check ==="

# Required variables for production
REQUIRED_VARS=(
  "POSTGRES_PASSWORD"
  "POSTGRES_UI_PASSWORD"
  "BETTER_AUTH_SECRET"
  "BETTER_AUTH_GOOGLE_CLIENT_ID"
  "BETTER_AUTH_GOOGLE_CLIENT_SECRET"
  "FRONTEND_DOMAIN"
  "API_DOMAIN"
  "APEX_DOMAIN"
  "UPLOADTHING_TOKEN"
  "CORS_ORIGINS"
)

# Source .env file
if [ -f .env ]; then
  source .env
  for var in "${REQUIRED_VARS[@]}"; do
    if [ -n "${!var}" ]; then
      echo "✓ $var is set"
    else
      echo "✗ $var is NOT SET"
    fi
  done
else
  echo "✗ .env file not found"
fi
```

### 4.4 Docker Build Check

```bash
echo "=== Docker Build Check ==="

# Test frontend Dockerfile builds
echo "Building frontend image..."
if docker build -f Dockerfile.frontend -t job-agent-frontend:preflight . --quiet 2>/dev/null; then
  echo "✓ Frontend Docker build successful"
  docker rmi job-agent-frontend:preflight --force 2>/dev/null
else
  echo "✗ Frontend Docker build FAILED"
fi

# Test backend Dockerfile builds
echo "Building backend image..."
if docker build -f Dockerfile -t job-agent-backend:preflight . --quiet 2>/dev/null; then
  echo "✓ Backend Docker build successful"
  docker rmi job-agent-backend:preflight --force 2>/dev/null
else
  echo "✗ Backend Docker build FAILED"
fi
```

### 4.5 Docker Compose Validation

```bash
echo "=== Docker Compose Validation ==="

# Validate compose files
if docker compose -f docker-compose.yml config --quiet 2>/dev/null; then
  echo "✓ docker-compose.yml is valid"
else
  echo "✗ docker-compose.yml has errors"
fi

if docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet 2>/dev/null; then
  echo "✓ docker-compose.prod.yml is valid"
else
  echo "✗ docker-compose.prod.yml has errors"
fi
```

### 4.6 Frontend Dependencies Check

```bash
echo "=== Frontend Dependencies Check ==="
cd frontend

# Check package-lock.json exists
if [ -f "package-lock.json" ]; then
  echo "✓ package-lock.json exists"
else
  echo "✗ package-lock.json MISSING (run npm install)"
fi

# Check Prisma schema exists
if [ -f "prisma/schema.prisma" ]; then
  echo "✓ Prisma schema exists"
else
  echo "✗ Prisma schema MISSING"
fi

cd ..
```

### 4.7 Security Checks

```bash
echo "=== Security Checks ==="

# Check .env is gitignored
if grep -q "^\.env$" .gitignore 2>/dev/null; then
  echo "✓ .env is in .gitignore"
else
  echo "✗ .env might not be gitignored"
fi

# Check for secrets in git
if git log --all -p | grep -q "BETTER_AUTH_SECRET=" 2>/dev/null; then
  echo "✗ WARNING: Secrets may be in git history"
else
  echo "✓ No secrets found in recent git history"
fi

# Check BETTER_AUTH_SECRET length
if [ -f .env ]; then
  source .env
  if [ ${#BETTER_AUTH_SECRET} -ge 32 ]; then
    echo "✓ BETTER_AUTH_SECRET is sufficiently long"
  else
    echo "✗ BETTER_AUTH_SECRET should be at least 32 characters"
  fi
fi
```

### 4.8 Full Preflight Script

Save this as `scripts/preflight-check.sh`:

```bash
#!/bin/bash
# Pre-deployment preflight checks

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

pass() {
  echo -e "${GREEN}✓${NC} $1"
  ((PASS++))
}

fail() {
  echo -e "${RED}✗${NC} $1"
  ((FAIL++))
}

warn() {
  echo -e "${YELLOW}!${NC} $1"
  ((WARN++))
}

echo "========================================"
echo "     Pre-Deployment Preflight Check    "
echo "========================================"
echo ""

# 1. Required Files
echo "--- Required Files ---"
FILES=(
  "Dockerfile.frontend"
  "frontend/app/api/health/route.ts"
  "scripts/grant-frontend-read-permissions.sql"
  "docker-compose.yml"
  "docker-compose.prod.yml"
  "Caddyfile"
)

for file in "${FILES[@]}"; do
  [ -f "$file" ] && pass "$file" || fail "$file MISSING"
done

# 2. Next.js Config
echo ""
echo "--- Next.js Configuration ---"
grep -q "output.*standalone" frontend/next.config.ts 2>/dev/null && \
  pass "Standalone output configured" || \
  fail "Missing 'output: standalone' in next.config.ts"

# 3. Environment Variables
echo ""
echo "--- Environment Variables ---"
if [ -f .env ]; then
  source .env
  REQUIRED_VARS=(
    "POSTGRES_PASSWORD"
    "POSTGRES_UI_PASSWORD"
    "BETTER_AUTH_SECRET"
    "BETTER_AUTH_GOOGLE_CLIENT_ID"
    "BETTER_AUTH_GOOGLE_CLIENT_SECRET"
    "FRONTEND_DOMAIN"
    "API_DOMAIN"
    "UPLOADTHING_TOKEN"
  )
  
  for var in "${REQUIRED_VARS[@]}"; do
    [ -n "${!var}" ] && pass "$var is set" || fail "$var is NOT SET"
  done
else
  fail ".env file not found"
fi

# 4. Docker Compose Validation
echo ""
echo "--- Docker Compose ---"
docker compose -f docker-compose.yml config --quiet 2>/dev/null && \
  pass "docker-compose.yml valid" || \
  fail "docker-compose.yml invalid"

docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet 2>/dev/null && \
  pass "docker-compose.prod.yml valid" || \
  fail "docker-compose.prod.yml invalid"

# 5. Security Checks
echo ""
echo "--- Security ---"
grep -q "^\.env$" .gitignore 2>/dev/null && \
  pass ".env is gitignored" || \
  warn ".env might not be gitignored"

if [ -n "$BETTER_AUTH_SECRET" ] && [ ${#BETTER_AUTH_SECRET} -ge 32 ]; then
  pass "BETTER_AUTH_SECRET length OK"
else
  fail "BETTER_AUTH_SECRET should be ≥32 chars"
fi

# Summary
echo ""
echo "========================================"
echo "             SUMMARY                    "
echo "========================================"
echo -e "${GREEN}Passed:${NC}  $PASS"
echo -e "${RED}Failed:${NC}  $FAIL"
echo -e "${YELLOW}Warnings:${NC} $WARN"
echo ""

if [ $FAIL -gt 0 ]; then
  echo -e "${RED}PREFLIGHT FAILED - Fix issues before deploying${NC}"
  exit 1
else
  echo -e "${GREEN}PREFLIGHT PASSED - Ready to deploy${NC}"
  exit 0
fi
```

Make it executable:

```bash
chmod +x scripts/preflight-check.sh
```

---

## 5. Quick Reference

### Commands Summary

| Task | Command |
|------|---------|
| Run preflight checks | `./scripts/preflight-check.sh` |
| Generate auth secret | `openssl rand -base64 32` |
| Test frontend build | `docker build -f Dockerfile.frontend -t test .` |
| Validate compose | `docker compose config --quiet` |
| Local dev with Docker | `docker compose up -d` |

### Domain Configuration

| Service | Domain Pattern | Example |
|---------|----------------|---------|
| Frontend | `app.{domain}` | `app.jobland.io` |
| API | `api.{domain}` | `api.jobland.io` |
| Apex redirect | `{domain}` → `app.{domain}` | `jobland.io` → `app.jobland.io` |

### DNS Records Needed

| Type | Name | Value |
|------|------|-------|
| A | @ | `<SERVER_IP>` |
| A | app | `<SERVER_IP>` |
| A | api | `<SERVER_IP>` |
| A | flower | `<SERVER_IP>` (optional) |

### Security Checklist

- [ ] `BETTER_AUTH_SECRET` is 32+ character random string
- [ ] `POSTGRES_PASSWORD` and `POSTGRES_UI_PASSWORD` are strong and different
- [ ] `.env` is in `.gitignore` and never committed
- [ ] Google OAuth redirect URIs configured for production domain
- [ ] `CORS_ORIGINS` includes only your domains
- [ ] Flower is behind Basic Auth or not exposed publicly
- [ ] UFW firewall allows only ports 22, 80, 443

---

## Next Steps After Preflight

Once all checks pass:

1. Commit all changes to git
2. Push to remote repository
3. On the server: `git clone` or `git pull`
4. Run `./setup.sh --first-time --prod` for first deployment
5. Verify health endpoints:
   - `curl https://api.yourapp.com/health`
   - `curl https://app.yourapp.com/api/health`
