# Pre-Deployment Setup Guide

This guide prepares the **job-agent** application for deployment on **Hetzner Cloud** with **Caddy** for HTTPS and a domain from **GoDaddy**. Everything is ordered so you can follow it step-by-step.

**Core principle:** Whatever we can set up before uploading anything to the server, we do **locally first**. You get the full stack (API, Celery, Redis, PostgreSQL, Flower, Caddy) running on your machine with Docker Compose, then you commit to GitHub, SSH to the server, clone the repo, copy `.env` manually, run `./setup.sh --prod` once, then `./start.sh --prod`. We do **not** install Caddy (or app runtimes) directly on the VPS—Caddy and the app run in containers; the repo contains the **Caddyfile**, **start.sh**, **setup.sh**, and **stop.sh** so the server only needs Docker.

---

## Steps at a glance

| Step | What we'll do |
|------|----------------|
| **1** | Understand the app (API, Celery, Redis, Postgres, Flower) and what each part does. |
| **2** | Get a domain (GoDaddy) and point DNS to the server so Caddy can get HTTPS certs. |
| **3** | Create a Hetzner VPS, set firewall (22, 80, 443), and install **Docker only** (no Caddy install on the host). |
| **4** | Define all environment variables; keep `.env` out of git and **copy it to the server manually** (e.g. `nano`, `scp`, or paste in SSH). |
| **5** | **Caddy in the repo:** Use the **Caddyfile** in the repository and run **Caddy as a Docker Compose service**. Reverse proxy and HTTPS are configured in the Caddyfile; we do not install Caddy on the VPS. |
| **6** | **Self-hosted PostgreSQL** in Docker Compose; create tables once; optionally add a DB UI (e.g. pgAdmin or Supabase Studio in Docker) to access the database. |
| **7** | Run the full stack with Docker Compose (API, Celery worker, Flower, Caddy, Postgres, Redis). Port binding and routing are in the Caddyfile and compose; only ports 22, 80, 443 are opened on the host. |
| **8** | Use **Flower** (included in compose) to see task status and logs. |
| **9** | Pre-flight checklist: verify locally first, then on the server after clone and `.env` copy. |
| **10** | Quick reference (ports, URLs) and next steps after go-live. |

---

## 1. Application Overview

**In this step we:** See what components the app has and how they fit together.

| Component | Technology | Port (default) |
|-----------|------------|----------------|
| API | FastAPI (uvicorn) | 8000 |
| Worker | Celery | — |
| Broker / cache | Redis | 6379 |
| Database | PostgreSQL | 5432 |
| Monitoring | Flower | 5555 |
| Reverse proxy / HTTPS | Caddy | 80, 443 |

The app uses **Docker** (`Dockerfile`, `Dockerfile.dev`, `docker-compose.yml`). The API runs with uvicorn (port 8000). Celery tasks are triggered via the API and run in a separate worker container. **Caddy** runs as a container and proxies external traffic (80/443) to the API and optionally Flower; routing is configured in the **Caddyfile** in the repo, so we do not need to "allow" app ports on the host—only 22, 80, 443.

### 1.1 What is Flower and why use it?

**Flower** is a web UI for **Celery**. It shows workers, queued/active/completed/failed tasks, task args/results, and tracebacks on failure. Use it to see whether a workflow succeeded or failed and what error it raised, without reading raw container logs. It is **included in docker-compose** and is part of the "everything working locally" setup. How to expose it (e.g. via Caddy) is in **Section 8**.

---

## 2. Domain (GoDaddy)

**In this step we:** Get (or choose) a domain and set an A record so the domain points to your future VPS IP. This must be in place before Caddy can obtain HTTPS certificates.

### 2.1 Get the domain

Purchase or use an existing domain in GoDaddy (e.g. `yourapp.com` or `api.yourapp.com`).

### 2.2 DNS records

In GoDaddy DNS for the domain (or subdomain):

| Type | Name | Value | TTL |
|------|------|--------|-----|
| A | @ (or `api`) | `<HETZNER_SERVER_IP>` | 600 |

- **Root:** Name `@` → `yourapp.com` points to the server.
- **Subdomain (e.g. API):** Name `api` → `api.yourapp.com` points to the server.

After you create the VPS (Step 3), put its IPv4 in the A record. Wait for DNS to propagate (often minutes). Check:

```bash
dig yourapp.com +short
# or
dig api.yourapp.com +short
```

---

## 3. Hetzner Cloud VPS

**In this step we:** Create the server, open only SSH/HTTP/HTTPS in the firewall, and install **Docker (and Docker Compose)**. We do **not** install Caddy or any app runtime on the host—they run inside Docker.

### 3.1 Create a server

- **Location:** e.g. Falkenstein, Nuremberg, Helsinki.
- **Image:** Ubuntu 24.04 LTS (or 22.04).
- **Type:** CX22 or CPX21 (2 vCPU, 4 GB RAM) minimum; CPX31+ for heavier Celery/LLM.
- **SSH key:** Add your public key for login.

Note the server **IPv4** and set the GoDaddy A record (Step 2) to this IP.

### 3.2 Firewall (recommended)

Allow only:

- **22** – SSH  
- **80** – HTTP (Caddy in Docker will bind this; redirect to HTTPS)  
- **443** – HTTPS (Caddy in Docker will bind this)

Do **not** expose 5432, 6379, 8000, or 5555 on the host. Caddy (running in Docker) will proxy to the API and Flower on the Docker network.

```bash
ufw allow 22
ufw allow 80
ufw allow 443
ufw enable
ufw status
```

### 3.3 Install Docker on the VPS (only)

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

## 4. Environment Variables and `.env` (Never in Git)

**In this step we:** List every env var the app needs so you can build a **production `.env`**. This file is **never committed to GitHub**. You will **copy it to the server manually** after cloning the repo (e.g. create the file with `nano .env` and paste, or use `scp` from your laptop).

### 4.1 Database (PostgreSQL)

| Variable | Description | Production note |
|----------|-------------|-----------------|
| `POSTGRES_HOST` | DB host | `postgres` (Docker service name when using compose) |
| `POSTGRES_PORT` | Port | `5432` |
| `POSTGRES_USER` | User | Strong user; avoid `postgres` in prod |
| `POSTGRES_PASSWORD` | Password | Strong, unique |
| `POSTGRES_DB` | Database name | e.g. `job_agent` |
| `DATABASE_URL` | Full URL | Optional if vars set; use `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE` |

### 4.2 Redis & Celery

| Variable | Description | Production note |
|----------|-------------|-----------------|
| `REDIS_PORT` | Redis port | `6379` (internal only) |
| `CELERY_BROKER_URL` | Broker URL | `redis://redis:6379/0` (Docker) |
| `CELERY_RESULT_BACKEND` | Result backend | Same as broker typically |

### 4.3 API & Ports

| Variable | Description | Production note |
|----------|-------------|-----------------|
| `API_PORT` | FastAPI port | `8000` (Caddy proxies 443 → api:8000) |
| `FLOWER_PORT` | Flower UI | `5555` (optional; Caddy can proxy to it) |
| `API_DOMAIN` | Domain for API (Caddy) | e.g. `api.yourapp.com` or `localhost` for local |
| `FLOWER_DOMAIN` | Domain for Flower (Caddy) | e.g. `flower.yourapp.com`; leave empty if not exposing Flower |

### 4.3a API key and Flower auth

| Variable | Description |
|----------|-------------|
| `API_KEY` | **Required.** Clients must send this in `X-API-Key` header or `Authorization: Bearer <key>`. Set for both dev and prod. Without it, protected endpoints return 401. |
| `FLOWER_BASIC_AUTH_USER` | Username for Flower Basic Auth (Caddy). Set if exposing Flower. |
| `FLOWER_BASIC_AUTH_HASH` | Bcrypt hash for Flower Basic Auth. Generate with `caddy hash-password` or `htpasswd -nbB user password`. |

### 4.4 External API keys (required for full functionality)

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini (workflow/LLM) |
| `SERPAPI_KEY` | SerpAPI (job discovery) |
| `EXA_API_KEY` | Exa (research) |
| `NYLAS_API_KEY` | Nylas (email delivery) |
| `NYLAS_API_URI` | e.g. `https://api.us.nylas.com` |
| `NYLAS_GRANT_ID` | Nylas grant |
| `PDFBOLTS_API_KEY` | PDF processing (CV) |

### 4.5 Observability (optional)

| Variable | Description |
|----------|-------------|
| `LANGFUSE_PUBLIC_KEY` | Langfuse |
| `LANGFUSE_SECRET_KEY` | Langfuse (no space around `=`) |
| `LANGFUSE_BASE_URL` | e.g. `https://us.cloud.langfuse.com` |
| `SENTRY_DSN` | Sentry (errors) |
| `ENVIRONMENT` | e.g. `production` |
| `RELEASE_VERSION` | e.g. `1.0.0` |

### 4.6 Database tables

| Variable | Description |
|----------|-------------|
| `OVERWRITE_TABLES` | Set to `false` in production. Only for one-off schema reset. |

**Workflow:** Use `.env.example` as a template. Create `.env` locally for development; create a production `.env` and **copy it to the server** after you clone the repo (e.g. `nano .env` on the server and paste, or `scp .env user@server:~/job-agent/.env`). Never commit `.env` to GitHub.

---

## 5. Caddy (Reverse Proxy & HTTPS) — In the Repo, Run via Docker Compose

**In this step we:** Use a **Caddyfile** in the repository and run **Caddy as a Docker Compose service**. We do **not** install Caddy on the VPS. Port binding and routing are configured in the Caddyfile and in docker-compose (Caddy binds 80/443 on the host and proxies to the API and optionally Flower).

### 5.1 Caddyfile in the repository

The repository includes a **Caddyfile** at the project root. Domains are set via **environment variables** (no editing the Caddyfile on the server): set `API_DOMAIN` and optionally `FLOWER_DOMAIN` in `.env`. The Caddyfile uses `{$API_DOMAIN}` and (if you expose Flower) `{$FLOWER_DOMAIN}`.

- **API:** Set `API_DOMAIN=api.yourapp.com` (or `localhost` for local). Caddy proxies that domain to `api:8000`.
- **Flower (optional):** The Caddyfile includes a commented-out Flower block. To expose Flower:
  1. Uncomment the Flower block in the Caddyfile (the block that uses `{$FLOWER_DOMAIN}` and `basicauth`).
  2. Set `FLOWER_DOMAIN=flower.yourapp.com` (or `flower.localhost` for local) and set `FLOWER_BASIC_AUTH_USER` and `FLOWER_BASIC_AUTH_HASH` in `.env`. Generate the hash with `caddy hash-password` or `htpasswd -nbB user password`.

Caddy will obtain and renew TLS automatically for real domains. Ensure DNS for the domain(s) points to the Hetzner IP before first run.

### 5.2 Caddy as a Docker Compose service

`docker-compose.yml` includes a **caddy** service that:

- Uses the official Caddy image (`caddy:2-alpine`).
- Mounts the **Caddyfile** from the repo (`./Caddyfile:/etc/caddy/Caddyfile`).
- Receives `API_DOMAIN`, `FLOWER_DOMAIN`, and Flower Basic Auth vars from `.env`.
- Binds ports **80** and **443** on the host.
- Runs on the same Docker network as `api` and `flower`, so it can reach `api:8000` and `flower:5555`.

You do **not** run `apt install caddy` or `systemctl start caddy` on the VPS. Everything is defined in the repo and started with `./start.sh --prod` (or `docker compose up -d`).

---

## 6. Database Setup (Self-Hosted PostgreSQL in Docker Compose)

**In this step we:** Run **PostgreSQL in Docker Compose** (self-hosted), create app tables once, and optionally add a way to **browse the database** (e.g. pgAdmin or Supabase Studio in Docker).

### 6.1 PostgreSQL in Docker Compose

The `docker-compose.yml` defines a **postgres** service. We **self-host** PostgreSQL; we do not rely on an external managed DB unless you choose to (e.g. Supabase Cloud). For this guide, the database is the **postgres** service in the same compose file.

- Use `POSTGRES_HOST=postgres` and the same `DATABASE_URL` pattern in `.env`.
- Use strong `POSTGRES_USER` / `POSTGRES_PASSWORD` in production.
- A volume (`postgres_data`) persists data.

### 6.2 Create tables

After the stack is running, run **first-time setup** once (no Python required on the host—runs inside the API container):

```bash
# From project root. Use same mode as start: --dev or --prod
./setup.sh --prod
# Or explicitly: docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api python -m src.database.create_tables
```

For development: `./setup.sh --dev`. The script is idempotent (safe to run again). Do **not** set `OVERWRITE_TABLES=true` in production unless you intend to drop and recreate tables.

### 6.3 Database visibility (optional): pgAdmin, Supabase Studio, or SSH tunnel

You may want a **UI to access the database** locally and/or on the server.

- **pgAdmin in Docker:** Add a `pgadmin` service to `docker-compose.yml`, connect it to `postgres:5432` with your credentials. Access at `http://localhost:5050` locally, or expose via Caddy on the server (e.g. `db.yourapp.com` → pgAdmin) with Basic Auth or IP restrict.
- **Supabase:**  
  - **Supabase Cloud:** Use Supabase’s managed Postgres and Studio in the browser; set `DATABASE_URL` to their connection string.  
  - **Supabase self-hosted (Docker):** Supabase provides a Docker-based stack (Postgres + Studio, etc.). You can run that stack if you want Supabase Studio; the job-agent app would point to that Postgres. Alternatively, keep our **postgres** service and add only a UI (e.g. pgAdmin) instead of the full Supabase stack.
- **SSH tunnel + local client:** From your laptop: `ssh -L 5433:127.0.0.1:5433 user@your-vps-ip` (production binds Postgres to host port 5433). Connect DBeaver/pgAdmin/TablePlus to `localhost:5433` with your `POSTGRES_*` credentials. No extra services needed.

**Summary:** We self-host PostgreSQL in Docker Compose. For a UI, use pgAdmin in Docker, Supabase (Cloud or self-hosted Docker), or SSH tunnel + local GUI.

---

## 7. Run Everything Locally First, Then on the Server

**In this step we:** Get the full stack running **locally** with Docker Compose (API, Celery worker, Flower, Caddy, Postgres, Redis), then repeat the same flow on the server after cloning and copying `.env`.

### 7.1 Local development (before any server work)

1. Clone the repo (or you are already in it).
2. Copy `.env.example` to `.env` and fill in values. Use `POSTGRES_HOST=postgres` when using Docker Compose. Set `API_DOMAIN=localhost` and **`API_KEY`** (required; clients send it in `X-API-Key` or `Authorization: Bearer`).
3. Run first-time setup once, then start the stack:

   ```bash
   ./setup.sh --dev
   ./start.sh --dev
   ```

4. Open `http://localhost:8000` for the API; `http://localhost:5555` for Flower. Confirm the API health endpoint (`GET /health` is public) and that Celery tasks appear in Flower.
5. **Local test:** Run `python test/test_request.py`. The test script reads `API_KEY` from `.env` and sends it on protected requests. Without `API_KEY` in `.env`, protected endpoints return 401 (so you can verify protection).

### 7.2 Deploying to the server

1. **Commit and push** your changes (including Caddyfile, docker-compose, start.sh, setup.sh, stop.sh) to GitHub. Ensure **`.env` is in `.gitignore`** and never committed.
2. **SSH** to the Hetzner VPS.
3. **Clone** the repo: `git clone <your-repo-url>` (using SSH key if required).
4. **Copy `.env` to the server:** Create `.env` on the server (e.g. `nano .env` and paste, or `scp .env user@server:~/job-agent/.env`). Include `API_DOMAIN`, `API_KEY`, and optionally `FLOWER_DOMAIN` and Flower Basic Auth vars.
5. **Run first-time setup once, then start the stack:**

   ```bash
   cd job-agent
   ./setup.sh --prod
   ./start.sh --prod
   ```

6. Caddy (in Docker) will bind 80/443 and proxy to the API (and optionally Flower). Only Docker is installed on the VPS; no separate Caddy install. To stop: `./stop.sh --prod`.

---

## 8. Flower: Task Monitoring and Logs

**In this step we:** Use **Flower** (already in docker-compose) to see task status, success/failure, and tracebacks.

### 8.1 What Flower shows

- **Workers** – Connected workers and resource usage.
- **Tasks** – Queued, active, completed, failed (e.g. `profiling_workflow`, `job_search_workflow`).
- **Task details** – Args, result, runtime, **traceback on failure**.
- **Broker** – Redis queue status.

Use it to answer “what is my application doing?” and “why did this workflow fail?” at the **task** level.

### 8.2 Enabling and exposing Flower

- **Docker Compose:** The repo defines a **flower** service. Start it with the rest of the stack (`./start.sh --dev` or `./start.sh --prod`). Flower listens on port **5555** inside the network. In development, port 5555 is published so you can open `http://localhost:5555` directly.

- **Exposing via Caddy (production):** The **Caddyfile** at the project root includes a **commented-out** Flower block. To expose Flower:
  1. Uncomment the Flower block in the Caddyfile (the block that uses `{$FLOWER_DOMAIN}` and `basicauth`).
  2. Set in `.env`: `FLOWER_DOMAIN=flower.yourapp.com`, `FLOWER_BASIC_AUTH_USER`, and `FLOWER_BASIC_AUTH_HASH`. Generate the hash with `caddy hash-password` or `htpasswd -nbB user password`.
  3. Restart Caddy (e.g. `./stop.sh --prod` then `./start.sh --prod`).

  Open `https://flower.yourapp.com`. **Important:** Flower has no built-in auth; the Caddy block uses Basic Auth so only users with the configured credentials can access it.

### 8.3 Flower vs. application logs

- **Flower** – Task status and task-level tracebacks.
- **Container logs** – Full output: `docker compose logs -f celery-worker` (and `api`) for line-by-line debugging.
- **Sentry / Langfuse** – Production error tracking and traces.

Use **Flower** for task status and task errors; use **worker logs** for the full log stream.

---

## 9. Pre-Flight Checklist

**In this step we:** Verify everything **locally first**, then on the server after clone and `.env` copy.

**Local (before server):**

- [ ] Repo has `Dockerfile`, `Dockerfile.dev`, `docker-compose.yml`, **docker-compose.prod.yml**, **Caddyfile**, **start.sh**, **setup.sh**, **stop.sh**.
- [ ] `.env` exists locally (from `.env.example`); `POSTGRES_HOST=postgres` for Docker; `API_DOMAIN`, **`API_KEY`** set.
- [ ] `./setup.sh --dev` run once; `./start.sh --dev` starts postgres, redis, api, celery-worker, flower, caddy.
- [ ] API health: `curl http://localhost:8000/health` returns healthy (no API key required).
- [ ] Flower: `http://localhost:5555` shows workers and tasks.
- [ ] `python test/test_request.py` runs (with `API_KEY` in `.env`); without `API_KEY`, protected requests get 401.
- [ ] Trigger a workflow; see task in Flower and worker logs.

**Server (after clone and .env copy):**

- [ ] **Hetzner:** Server created, SSH key added, firewall (22, 80, 443) configured.
- [ ] **Docker:** Only Docker (and Docker Compose) installed; no Caddy installed on host.
- [ ] **GoDaddy:** Domain DNS A record points to Hetzner IP; propagation checked.
- [ ] **Repo:** Cloned via SSH/git; **Caddyfile**, **docker-compose**, **start.sh**, **setup.sh**, **stop.sh** in repo.
- [ ] **Environment:** Production `.env` on server (copied manually); includes `API_DOMAIN`, **`API_KEY`**; not in git.
- [ ] **Setup and start:** `./setup.sh --prod` run once; `./start.sh --prod` started the stack.
- [ ] **Caddy:** Runs as a container; Caddyfile from repo; HTTPS works for your domain(s).
- [ ] **Database:** Postgres container running; tables created via setup.sh; `OVERWRITE_TABLES=false`.
- [ ] **Containers:** API, Celery worker, Flower, Caddy start successfully; no DB/Redis errors in logs.
- [ ] **Health:** `curl https://api.yourapp.com/health` returns `{"status":"healthy"}` (no API key required).
- [ ] **API key:** Requests without `X-API-Key` or `Authorization: Bearer` get 401 on protected endpoints.
- [ ] **Workflow:** Trigger a workflow (with API key); confirm task in Flower and worker logs.
- [ ] **Flower (optional):** If you uncommented the Flower block and set `FLOWER_DOMAIN`, open `https://flower.yourapp.com` and confirm Basic Auth and task history.
- [ ] **Database visibility (optional):** If using pgAdmin/Supabase/SSH tunnel, confirm you can open the DB UI and see job-agent tables.

---

## 10. Quick Reference – Ports and URLs

| Service | Internal port | Host / exposure |
|---------|----------------|------------------|
| FastAPI | 8000 | Proxied via Caddy (e.g. `https://api.yourapp.com`) |
| Flower | 5555 | Optional; proxied via Caddy if configured in Caddyfile |
| Caddy | 80, 443 | Bound on host (docker-compose ports) |
| PostgreSQL | 5432 | Docker network only (or localhost if you expose for DB UI) |
| Redis | 6379 | Docker network only |

Port binding and routing are configured in the **Caddyfile** and **docker-compose**; you do not need to "allow" 8000 or 5555 on the host firewall—only 22, 80, 443.

---

## 11. Next Steps After Pre-Deployment

- Set up **backups** for PostgreSQL (e.g. cron + `pg_dump` or Hetzner snapshots).
- Consider **log aggregation** (e.g. Sentry or shipping logs to a service).
- Harden **SSH** (disable password auth, key-only).
- Optionally add **rate limiting** or **auth** in front of the API (Caddy or app-level).

Once the checklist in **Section 9** is complete (locally and on the server), you are ready to go live and point clients at `https://your-domain`.
