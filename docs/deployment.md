# Deployment Guide

This guide walks you through deploying **job-agent** to a server (e.g. Hetzner Cloud) with **Flower exposed on the internet** (HTTPS + Basic Auth). For background and env var reference, see [pre-deployment-setup-guide.md](pre-deployment-setup-guide.md).

**Assumptions:** You have already run the stack locally (`./setup.sh --dev`, `./start.sh --dev`), tested the API with the API key, and confirmed Flower works at `http://localhost:5555`.

---

## Steps at a glance

| Step | What you do |
|------|--------------|
| 1 | Get a domain (e.g. GoDaddy) and plan subdomains: `api.yourapp.com`, `flower.yourapp.com`. |
| 2 | Create a Hetzner VPS, note the IPv4, set firewall (22, 80, 443), install Docker only. |
| 3 | Point DNS A records for `api` and `flower` to the server IP; wait for propagation. |
| 4 | Build production `.env` from `.env.example` (set API_DOMAIN, FLOWER_DOMAIN, Flower Basic Auth, API key, DB, etc.). |
| 5 | Enable Flower in the Caddyfile (uncomment the Flower block). |
| 6 | On the server: clone repo, copy `.env`, run `./setup.sh --prod` once, then `./start.sh --prod`. |
| 7 | Verify: HTTPS for API and Flower, health endpoint, API key 401, Flower Basic Auth. |
| 8 | (Optional) View DB in production: SSH tunnel + DBeaver/pgAdmin, or add pgAdmin in Docker. |

---

## 1. Domain (e.g. GoDaddy)

- Use an existing domain or buy one (e.g. `yourapp.com`).
- You will create two subdomains:
  - **API:** `api.yourapp.com` → later point A record to your server IP.
  - **Flower:** `flower.yourapp.com` → same A record (same server).

No DNS changes yet; do them after you have the server IP (Step 3).

---

## 2. Hetzner VPS

1. Create a server in [Hetzner Cloud](https://www.hetzner.com/cloud).
   - **Image:** Ubuntu 24.04 LTS (or 22.04).
   - **Type:** CX22 or CPX21 (2 vCPU, 4 GB RAM) minimum; CPX31+ for heavier Celery/LLM.
   - **Location:** e.g. Falkenstein, Nuremberg, Helsinki.
   - **SSH key:** Add your public key.
2. Note the server **IPv4** (e.g. `95.217.x.x`).

### Firewall (on the server)

Allow only SSH, HTTP, and HTTPS:

```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
sudo ufw status
```

### Install Docker (and Compose) only

No Caddy or app runtimes on the host—everything runs in containers.

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
```

Log out and back in (or open a new SSH session), then confirm:

```bash
docker --version
docker compose version
```

---

## 3. DNS (GoDaddy or your provider)

In your domain’s DNS settings, add A records so both the API and Flower subdomains point to the **same** server IP:

| Type | Name   | Value           | TTL |
|------|--------|-----------------|-----|
| A    | api    | `<SERVER_IPv4>` | 600 |
| A    | flower | `<SERVER_IPv4>` | 600 |

Example: if your server IP is `95.217.1.2`, then `api.yourapp.com` and `flower.yourapp.com` both resolve to `95.217.1.2`.

Wait a few minutes for DNS to propagate, then check:

```bash
dig api.yourapp.com +short
dig flower.yourapp.com +short
```

Both should return your server IP.

---

## 4. Production `.env`

Build a production `.env` from **`.env.example`**. You will **copy this file to the server manually** (never commit it). The example file already includes `API_DOMAIN` and `FLOWER_DOMAIN` (empty); in production you **must** set them to your real domain (e.g. from GoDaddy).

### Required for API and Caddy

- **POSTGRES_HOST=postgres** (Docker service name)
- **POSTGRES_USER**, **POSTGRES_PASSWORD**, **POSTGRES_DB** – use strong values in production.
- **API_DOMAIN** – your real API domain (e.g. `api.yourapp.com` from GoDaddy). Set this in production; leave empty or `localhost` only for local dev.
- **API_KEY** – use the static key from `src/config.py` (`JOB_LAND_API_KEY`) or your own secret; clients must send it in `X-API-Key` or `Authorization: Bearer`.
- **CELERY_BROKER_URL=redis://redis:6379/0**, **CELERY_RESULT_BACKEND=redis://redis:6379/0**.
- External API keys (GEMINI_API_KEY, SERPAPI_KEY, EXA_API_KEY, NYLAS_*, PDFBOLTS_API_KEY, etc.) as needed.
- **OVERWRITE_TABLES=false** in production.

### Required for Flower on the internet

- **FLOWER_DOMAIN** – your real Flower subdomain (e.g. `flower.yourapp.com` from GoDaddy). Must match the DNS A record you add for Flower.
- **FLOWER_BASIC_AUTH_USER** – username for Flower (e.g. `admin`).
- **FLOWER_BASIC_AUTH_HASH** – bcrypt hash of the password.

Generate the hash (run on your laptop or any machine with Caddy/OpenSSL):

```bash
# Option A: Caddy (if you have it)
caddy hash-password

# Option B: htpasswd (Apache utils)
htpasswd -nbB username yourpassword
# Use the part after the second colon (the hash only) as FLOWER_BASIC_AUTH_HASH
```

Put the **hash only** (no username) in `FLOWER_BASIC_AUTH_HASH` in `.env`.

Example `.env` snippet for Flower:

```env
FLOWER_DOMAIN=flower.yourapp.com
FLOWER_BASIC_AUTH_USER=admin
FLOWER_BASIC_AUTH_HASH=$2a$14$...your_bcrypt_hash...
```

---

## 5. Enable Flower in the Caddyfile

To expose Flower on the internet, the Caddyfile must include the Flower server block. In the repo it is **commented out** by default.

1. Open **`Caddyfile`** at the project root.
2. **Uncomment** the Flower block so it looks like this:

```caddy
# API: set API_DOMAIN in .env (e.g. api.yourapp.com or localhost for local)
{$API_DOMAIN} {
	reverse_proxy api:8000
}

# Flower: set FLOWER_DOMAIN and Basic Auth vars in .env
{$FLOWER_DOMAIN} {
	basicauth * {$FLOWER_BASIC_AUTH_USER} {$FLOWER_BASIC_AUTH_HASH}
	reverse_proxy flower:5555
}
```

3. Commit and push the change (so the server gets this Caddyfile when you clone).

If you do **not** want Flower on the internet, skip this step and leave the block commented; do not set `FLOWER_DOMAIN` in production `.env`.

---

## 6. Deploy on the server

### 6.1 On your laptop: push to GitHub

Before the server can clone your code, commit and push from your **local machine** (ensure `.env` is in `.gitignore` and never committed):

```bash
cd /path/to/job-agent

# Ensure .env is not staged (it must be in .gitignore)
git status

# Stage changes (Caddyfile, docker-compose, scripts, etc.). Do NOT add .env
git add .
git status   # double-check .env is not listed

# Commit and push (replace main with your branch name if different)
git commit -m "Deploy: Caddyfile with Flower, docker-compose, scripts"
git push origin main
```

If you use SSH for GitHub:

```bash
git remote -v   # should show git@github.com:your-org/job-agent.git
git push origin main
```

If you use HTTPS and GitHub asks for credentials, use a personal access token (PAT) instead of your password, or set up SSH keys and switch the remote to `git@github.com:your-org/job-agent.git`.

### 6.2 On the server: clone and run

1. **SSH** to the Hetzner server (replace `user` with `root`, `ubuntu`, or your image’s user):
   ```bash
   ssh user@<SERVER_IPv4>
   ```

2. **Clone** the repo. Use **HTTPS** or **SSH** (if the server has your GitHub deploy key):

   **HTTPS:**
   ```bash
   git clone https://github.com/your-org/job-agent.git
   cd job-agent
   ```

   **SSH (recommended for servers):**
   ```bash
   git clone git@github.com:your-org/job-agent.git
   cd job-agent
   ```

   Replace `your-org/job-agent` with your actual GitHub org/repo (e.g. `myusername/job-agent`).

3. **Copy `.env` to the server** (from your laptop, in a new terminal):
   ```bash
   scp .env user@<SERVER_IPv4>:~/job-agent/.env
   ```
   Or on the server, create `.env` and paste the contents (e.g. `nano .env`).

4. **First-time setup** (create DB tables):
   ```bash
   ./setup.sh --prod
   ```

5. **Start the stack**:
   ```bash
   ./start.sh --prod
   ```

6. **Stop the stack** (when needed):
   ```bash
   ./stop.sh --prod
   ```

**Later: pull updates and restart**

After you change code and push to GitHub, on the server run:

```bash
cd ~/job-agent
git pull origin main
./stop.sh --prod
./start.sh --prod
```

Caddy will bind 80/443 and obtain TLS for `api.yourapp.com` and `flower.yourapp.com` automatically (DNS must already point to this server).

---

## 7. Verify

- **API health (no API key):**
  ```bash
  curl https://api.yourapp.com/health
  ```
  Expected: `{"status":"healthy"}`.

- **API protected (no key → 401):**
  ```bash
  curl -i https://api.yourapp.com/
  ```
  Expected: 401.

- **API with key:**
  ```bash
  curl -H "X-API-Key: YOUR_API_KEY" https://api.yourapp.com/
  ```
  Expected: 200 and JSON.

- **Flower:** Open `https://flower.yourapp.com` in a browser. You should be prompted for the Basic Auth username and password (the ones you set in `FLOWER_BASIC_AUTH_USER` and the password you hashed for `FLOWER_BASIC_AUTH_HASH`). After login, you should see workers and tasks.

- **Workflow:** Trigger a workflow via the API (with the API key); confirm the task appears in Flower and completes.

---

## 8. Viewing the database in production

We do **not** use Supabase Studio. To look at the PostgreSQL database once in production you have two options.

### Option A: SSH tunnel + local client (recommended)

No extra services. From your **laptop**, open an SSH tunnel so that a local port forwards to Postgres on the server:

1. **Postgres on server localhost:** In production, `docker-compose.prod.yml` already binds Postgres to `127.0.0.1:5432` on the server (not exposed to the internet). No change needed; just run `./start.sh --prod` as in the deploy steps.

2. **From your laptop**, run (replace `user` and `<SERVER_IPv4>`):

   ```bash
   ssh -L 5433:127.0.0.1:5432 user@<SERVER_IPv4>
   ```

   Keep this SSH session open.

3. **Connect your DB client** (DBeaver, pgAdmin, TablePlus, etc.) to:
   - Host: `localhost`
   - Port: `5433`
   - User / password / database: use the same values as in your production `.env` (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`).

You can now browse and query the job-agent tables. When you close the SSH session, the tunnel stops.

### Option B: pgAdmin in Docker (optional)

If you prefer a web UI on the server, you can add a **pgAdmin** service to `docker-compose.yml` (and optionally expose it via Caddy with Basic Auth at e.g. `db.yourapp.com`). See [pre-deployment-setup-guide.md](pre-deployment-setup-guide.md) Section 6.3 for a short note. This requires adding the service and securing it (Basic Auth, IP allowlist, or VPN).

---

## 9. Checklist

- [ ] Domain has A records for `api` and `flower` to the server IP.
- [ ] Server has firewall 22, 80, 443; Docker (and Compose) installed.
- [ ] Production `.env` on server with API_DOMAIN, FLOWER_DOMAIN, Flower Basic Auth, API_KEY, DB credentials, external API keys.
- [ ] Caddyfile Flower block uncommented and committed.
- [ ] Repo cloned on server; `.env` in place (not in git).
- [ ] `./setup.sh --prod` run once; `./start.sh --prod` started the stack.
- [ ] `https://api.yourapp.com/health` returns healthy.
- [ ] `https://api.yourapp.com/` returns 401 without key, 200 with X-API-Key.
- [ ] `https://flower.yourapp.com` asks for Basic Auth and shows Flower UI after login.

---

## 10. Next steps after go-live

- **Backups:** Schedule PostgreSQL backups (e.g. cron + `pg_dump` or Hetzner volume snapshots).
- **SSH:** Harden SSH (disable password auth, use key-only).
- **Monitoring:** Optional Sentry or log aggregation.
- **Rate limiting:** Optional Caddy or app-level rate limiting for the API.

For more detail on env vars, Caddy, and Flower, see [pre-deployment-setup-guide.md](pre-deployment-setup-guide.md).
