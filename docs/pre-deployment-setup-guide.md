# Pre-Deployment Setup Guide

This guide prepares the **job-agent** application for deployment on **Hetzner Cloud** with **Caddy** for domain routing and a domain from **GoDaddy**. Follow these steps before going live.

---

## 1. Application Overview

| Component | Technology | Port (default) |
|-----------|------------|----------------|
| API | FastAPI (uvicorn) | 8000 |
| Worker | Celery | — |
| Broker / cache | Redis | 6379 |
| Database | PostgreSQL | 5432 |
| Monitoring (optional) | Flower | 5555 |

The app uses **Docker** (see repo `Dockerfile`, `docker-compose.yml`). The API runs with `uvicorn` (host `0.0.0.0`, port 8000). Celery tasks are triggered via the API and run in a separate worker process/container.

---

## 2. Hetzner Cloud VPS

### 2.1 Create a server

- **Location:** Choose a region (e.g. Falkenstein, Nuremberg, Helsinki).
- **Image:** Ubuntu 24.04 LTS (or 22.04).
- **Type:** CX22 or CPX21 (2 vCPU, 4 GB RAM) minimum; use CPX31+ if you expect heavier Celery/LLM usage.
- **SSH key:** Add your public key for root/login access.

Note the server **IPv4**; you will point your domain to it.

### 2.2 Firewall (optional but recommended)

Allow only what you need:

- **22** – SSH
- **80** – HTTP (for Caddy / redirect to HTTPS)
- **443** – HTTPS (Caddy)

Do **not** expose 5432, 6379, 8000, or 5555 to the internet unless you have a specific reason (e.g. managed DB elsewhere). Caddy will proxy to the API on localhost.

Example (UFW on the VPS):

```bash
ufw allow 22
ufw allow 80
ufw allow 443
ufw enable
ufw status
```

### 2.3 Install Docker on the VPS

On the Hetzner server:

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
# Log out and back in (or new SSH session) for group to apply
```

Confirm:

```bash
docker --version
docker compose version
```

---

## 3. Domain (GoDaddy)

### 3.1 Get the domain

Purchase or use an existing domain in GoDaddy (e.g. `yourapp.com` or `api.yourapp.com`).

### 3.2 DNS records

In GoDaddy DNS management for the domain (or subdomain):

| Type | Name | Value | TTL |
|------|------|--------|-----|
| A | @ (or `api`) | `<HETZNER_SERVER_IP>` | 600 |

- **Root domain:** Use name `@` so `yourapp.com` → your server.
- **Subdomain (e.g. API):** Use name `api` so `api.yourapp.com` → your server.

Wait for DNS to propagate (up to 48 hours, often minutes). Check with:

```bash
dig yourapp.com +short
# or
dig api.yourapp.com +short
```

---

## 4. Caddy (Reverse Proxy & HTTPS)

Caddy will terminate HTTPS and route traffic to your FastAPI app (and optionally Flower).

### 4.1 Install Caddy on the VPS

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
sudo systemctl enable caddy
sudo systemctl start caddy
```

### 4.2 Caddyfile for your domain

Replace `api.yourapp.com` and `yourapp.com` with your real domain.

**Option A – API only (e.g. `api.yourapp.com`)**

```bash
sudo nano /etc/caddy/Caddyfile
```

```caddy
api.yourapp.com {
    reverse_proxy localhost:8000
}
```

**Option B – API + Flower on subdomains**

```caddy
api.yourapp.com {
    reverse_proxy localhost:8000
}

flower.yourapp.com {
    reverse_proxy localhost:5555
}
```

**Option C – Root domain to API**

```caddy
yourapp.com {
    reverse_proxy localhost:8000
}
```

Reload Caddy:

```bash
sudo systemctl reload caddy
```

Caddy will obtain and renew TLS certificates automatically. Ensure DNS for the domain(s) points to your Hetzner IP before reloading.

---

## 5. Environment Variables Checklist

The app is configured via environment variables. Use a production `.env` on the server (or your orchestration’s secret store) and **never** commit it.

### 5.1 Database (PostgreSQL)

| Variable | Description | Production note |
|----------|-------------|-----------------|
| `POSTGRES_HOST` | DB host | `postgres` if using Docker Compose service name; or your managed DB host |
| `POSTGRES_PORT` | Port | `5432` |
| `POSTGRES_USER` | User | Strong user, not `postgres` in prod |
| `POSTGRES_PASSWORD` | Password | Strong, unique password |
| `POSTGRES_DB` | Database name | e.g. `job_agent` |
| `DATABASE_URL` | Full URL | Optional if individual vars are set; use `postgresql+psycopg://...` (psycopg3) |

Connection string format: `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE`

### 5.2 Redis & Celery

| Variable | Description | Production note |
|----------|-------------|-----------------|
| `REDIS_PORT` | Redis port | `6379` (internal only) |
| `CELERY_BROKER_URL` | Broker URL | `redis://redis:6379/0` (Docker) or `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Result backend | Same as broker in typical setup |

### 5.3 API & Ports

| Variable | Description | Production note |
|----------|-------------|-----------------|
| `API_PORT` | FastAPI port | `8000` (used internally; Caddy proxies 443 → 8000) |
| `FLOWER_PORT` | Flower UI | `5555` (optional) |

### 5.4 External API keys (required for full functionality)

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini (workflow/LLM) |
| `SERPAPI_KEY` | SerpAPI (job discovery) |
| `EXA_API_KEY` | Exa (research) |
| `NYLAS_API_KEY` | Nylas (email delivery) |
| `NYLAS_API_URI` | e.g. `https://api.us.nylas.com` |
| `NYLAS_GRANT_ID` | Nylas grant |
| `PDFBOLTS_API_KEY` | PDF processing (CV) |

### 5.5 Observability (optional)

| Variable | Description |
|----------|-------------|
| `LANGFUSE_PUBLIC_KEY` | Langfuse |
| `LANGFUSE_SECRET_KEY` | Langfuse (no space around `=`) |
| `LANGFUSE_BASE_URL` | e.g. `https://us.cloud.langfuse.com` |
| `SENTRY_DSN` | Sentry (errors) |
| `ENVIRONMENT` | e.g. `production` |
| `RELEASE_VERSION` | e.g. `1.0.0` |

### 5.6 Database tables

| Variable | Description |
|----------|-------------|
| `OVERWRITE_TABLES` | Set to `false` in production. Use only for one-off schema reset. |

Use a dedicated production `.env` on the server; ensure the same vars are passed to the **api** and **celery-worker** containers (see your `docker-compose` or deployment config).

---

## 6. Database Setup (PostgreSQL)

### 6.1 Postgres on the same VPS (Docker)

Your `docker-compose.yml` already defines a `postgres` service. In production you can use a compose override or a production compose file that:

- Keeps `POSTGRES_HOST=postgres` and the same `DATABASE_URL` pattern.
- Uses strong `POSTGRES_USER` / `POSTGRES_PASSWORD` from `.env`.
- Keeps a volume for `postgres_data` so data persists.

### 6.2 Create tables

After the app/DB is running, run the table-creation script once (from the host or a one-off container):

```bash
# From project root on the server, with .env loaded and POSTGRES_HOST=postgres
python -m src.database.create_tables
```

Do **not** set `OVERWRITE_TABLES=true` in production unless you intend to drop and recreate tables.

---

## 7. Docker Compose for Production

Your repo has:

- `Dockerfile` – multi-stage build, runs `uvicorn` with 2 workers on port 8000.
- `docker-compose.yml` – dev-oriented (hot reload, Flower, etc.).

For production on the VPS:

1. **Option A – Use existing compose:**  
   Set `ENVIRONMENT=production` and ensure the api service uses the production Dockerfile (no `--reload`). You can override the api command to match the Dockerfile CMD (uvicorn with workers, no reload).

2. **Option B – Production override:**  
   Create `docker-compose.prod.yml` that:
   - Builds from `Dockerfile` (not `Dockerfile.dev`).
   - Runs api with: `uvicorn src.api.api:app --host 0.0.0.0 --port 8000 --workers 2`.
   - Keeps postgres, redis, api, celery-worker; Flower is optional.
   - Binds only `localhost` for api/flower if Caddy is on the same host (e.g. `ports: ["127.0.0.1:8000:8000"]`).

Example production run:

```bash
# Copy project (including .env) to server, then:
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
# Or a single prod compose file
docker compose -f docker-compose.prod.yml up -d
```

Ensure `.env` is present on the server and not committed.

---

## 8. Pre-Flight Checklist

Before considering the deployment “ready”:

- [ ] **Hetzner:** Server created, SSH key added, firewall (22, 80, 443) configured.
- [ ] **Docker:** Docker and Docker Compose installed and working.
- [ ] **GoDaddy:** Domain DNS A record points to Hetzner IP; propagation checked.
- [ ] **Caddy:** Installed; Caddyfile configured for your domain(s); `systemctl reload caddy`; HTTPS works.
- [ ] **Environment:** Production `.env` on server with all required vars (DB, Redis, Celery, API keys); no secrets in repo.
- [ ] **Database:** Postgres running; `create_tables` run once; `OVERWRITE_TABLES=false`.
- [ ] **Containers:** API and Celery worker start successfully; logs show no DB/Redis connection errors.
- [ ] **Health:** `curl https://api.yourapp.com/health` returns `{"status":"healthy"}` (or your chosen URL).
- [ ] **Workflow:** Trigger a profiling or job-search workflow and confirm a Celery task runs (check worker logs / Flower if enabled).

---

## 9. Quick Reference – Ports and URLs

| Service | Internal port | Exposed / Caddy |
|---------|----------------|------------------|
| FastAPI | 8000 | Proxied via Caddy (e.g. `https://api.yourapp.com`) |
| Flower | 5555 | Optional; proxied via Caddy if you add a server block |
| PostgreSQL | 5432 | Local / Docker only |
| Redis | 6379 | Local / Docker only |

---

## 10. Next Steps After Pre-Deployment

- Set up **backups** for PostgreSQL (e.g. cron + `pg_dump` or Hetzner snapshots).
- Consider **log aggregation** (e.g. Sentry, or shipping logs to a service).
- Harden **SSH** (disable password auth, use key-only).
- Optionally add **rate limiting** or **auth** in front of the API (Caddy middleware or app-level).

Once the checklist in section 8 is complete, you’re ready to deploy and point your clients at `https://your-domain`.
