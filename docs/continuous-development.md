# Continuous Development – Redeploy Checklist

Short refresher for redeploying after you change the codebase. Follow these steps whenever you want the server to run your latest code (and optionally updated env).

---

## Before you start

- **Code:** Commit and push your changes to GitHub (e.g. `main`).
- **Env (optional):** If you changed `.env` (API keys, Flower auth, domains, etc.), you will copy the updated `.env` to the server in Step 2.

**Placeholders used below:** Replace `SERVER_IP` with your server’s IP (e.g. `46.62.135.5`), `PROJECT_PATH` with your app path on the server (e.g. `/opt/job-agent`), and `BRANCH` with your branch (e.g. `main`).

---

## Step 1: SSH into the server

From your **laptop** terminal:

```bash
ssh root@SERVER_IP
```

(Use your actual user if not `root`, e.g. `ubuntu@SERVER_IP`.)

---

## Step 2: (Optional) Copy updated `.env` from laptop to server

If you changed `.env` locally, copy it to the server **before** restarting the stack. Do this from **another terminal on your laptop** (keep the SSH session from Step 1 open).

**On your laptop** (second terminal), from the project root:

```bash
cd "/path/to/your/job-agent"   # your local repo
scp .env root@SERVER_IP:PROJECT_PATH/.env
```

Example:

```bash
cd "/Users/chyung0104/Documents/學習/Full-Stack Developer/experiments/job-agent"
scp .env root@46.62.135.5:/opt/job-agent/.env
```

Then switch back to the **SSH terminal** (Step 1) for the next steps.

---

## Step 3: Go to project and pull latest code

In the **SSH terminal** (on the server):

```bash
cd PROJECT_PATH
git pull origin BRANCH
```

Example:

```bash
cd /opt/job-agent
git pull origin main
```

---

## Step 4: Restart Docker services

Still on the server, in the same project directory:

```bash
./stop.sh --prod
./start.sh --prod
```

This stops the stack and starts it again so it uses the new code (and the new `.env` if you copied it in Step 2).

---

## Step 5 (optional): Force recreate containers

If you updated `.env` but Caddy or other services still use old values, force a full recreate:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate
```

---

## Quick command list (copy-paste)

**Terminal 1 – Laptop (only if you need to copy .env):**

```bash
cd "/path/to/your/job-agent"
scp .env root@SERVER_IP:/opt/job-agent/.env
```

**Terminal 2 – SSH on server:**

```bash
ssh root@SERVER_IP
cd /opt/job-agent
git pull origin main
./stop.sh --prod
./start.sh --prod
```

**Optional – Server (if env still not applied):**

```bash
cd /opt/job-agent
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate
```

---

## Verify

- **API:** `curl https://api.profilescreens.com/health` → `{"status":"healthy"}`
- **Flower:** Open `https://flower.profilescreens.com` and log in with Basic Auth.

For more detail (first-time deploy, DNS, firewall, TablePlus), see [deployment.md](deployment.md).
