#!/usr/bin/env bash
# Unified setup script: menu-driven or use flags for CI/automation.
# Usage:
#   ./setup.sh                    # Interactive menu
#   ./setup.sh --first-time       # First-time setup (start stack + migrations)
#   ./setup.sh --overwrite        # Reset DB and run migrations (destroys data)
#   ./setup.sh --migrate          # Run migrations only (alembic upgrade head)
#   ./setup.sh --two-users        # One-time: add job_agent_admin + job_agent_ui (existing DB)
#   ./setup.sh --restart          # Stop, rebuild with --no-cache, start fresh
#   ./setup.sh --rebuild-frontend # Rebuild and restart frontend container only
#   ./setup.sh --start            # Start stack (docker compose up -d)
#   ./setup.sh --stop             # Stop stack (docker compose down)
# Use --dev (default) or --prod with any flag or from menu.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# -----------------------------------------------------------------------------
# Config: load .env and compose command
# -----------------------------------------------------------------------------
check_env() {
  if [ ! -f .env ]; then
    echo "Error: .env not found. Copy .env.example to .env and fill in values."
    exit 1
  fi
}

load_env() {
  set -a
  # shellcheck source=/dev/null
  [ -f .env ] && . .env
  set +a
}

MODE="dev"
COMPOSE_BASE="docker compose"
COMPOSE_RUN_API="docker compose run --rm api"

set_compose() {
  if [ "$MODE" = "prod" ]; then
    COMPOSE_BASE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
    COMPOSE_RUN_API="$COMPOSE_BASE run --rm api"
  else
    COMPOSE_BASE="docker compose"
    COMPOSE_RUN_API="$COMPOSE_BASE run --rm api"
  fi
}

# Grant frontend read permissions on backend tables
grant_frontend_permissions() {
  echo "Granting frontend read permissions on backend tables..."
  if ! cat scripts/grant-frontend-read-permissions.sql | $COMPOSE_BASE exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U postgres -d "${POSTGRES_DB:-job_agent}" -f -; then
    echo "Warning: Failed to grant frontend read permissions."
  fi
}

# Sync Prisma schema with database (for local development)
sync_prisma() {
  if [ -d "frontend" ] && [ -f "frontend/prisma/schema.prisma" ]; then
    echo "Syncing Prisma schema with database..."
    if command -v npm &> /dev/null; then
      (cd frontend && npx prisma db pull && npx prisma generate)
      echo "Prisma schema synced."
    else
      echo "Note: npm not found. Run 'npx prisma db pull && npx prisma generate' in frontend/ manually."
    fi
  fi
}

# -----------------------------------------------------------------------------
# Actions
# -----------------------------------------------------------------------------
action_first_time() {
  check_env
  load_env
  set_compose
  
  # Validate required env vars
  if [ -z "${POSTGRES_PASSWORD:-}" ] || [ -z "${POSTGRES_UI_PASSWORD:-}" ]; then
    echo "Error: POSTGRES_PASSWORD and POSTGRES_UI_PASSWORD must be set in .env"
    exit 1
  fi
  
  echo "=== First-time setup: Complete database initialization ==="
  
  echo "1. Starting database services (postgres, redis)..."
  $COMPOSE_BASE up -d postgres redis
  
  echo "2. Waiting for Postgres to be healthy..."
  # Wait for postgres health check to pass (up to 60 seconds)
  for i in {1..12}; do
    if $COMPOSE_BASE exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
      echo "   Postgres is ready."
      break
    fi
    if [ $i -eq 12 ]; then
      echo "Error: Postgres did not become ready in time."
      exit 1
    fi
    echo "   Waiting for Postgres... ($i/12)"
    sleep 5
  done
  
  echo "3. Dropping existing schema (if any)..."
  $COMPOSE_RUN_API python -m src.database.reset_db
  
  echo "4. Creating users (job_agent_admin, job_agent_ui)..."
  ADMIN_ESC="${POSTGRES_PASSWORD//\'/\'\'}"
  UI_ESC="${POSTGRES_UI_PASSWORD//\'/\'\'}"
  if ! cat scripts/grant-two-users-existing-db.sql | $COMPOSE_BASE exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U postgres -d "${POSTGRES_DB:-job_agent}" \
    -v admin_pass="${ADMIN_ESC}" -v ui_pass="${UI_ESC}" -f -; then
    echo "Error: Failed to create users. Check logs."
    exit 1
  fi
  
  echo "5. Running migrations (creating tables)..."
  $COMPOSE_RUN_API alembic upgrade head
  
  echo "6. Granting Better Auth permissions to UI account..."
  if ! cat scripts/grant-better-auth-permissions.sql | $COMPOSE_BASE exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U postgres -d "${POSTGRES_DB:-job_agent}" -f -; then
    echo "Warning: Failed to grant Better Auth permissions. You may need to run this manually."
  fi
  
  echo "7. Granting frontend read permissions on backend tables..."
  grant_frontend_permissions
  
  echo "8. Syncing Prisma schema..."
  sync_prisma
  
  echo "9. Starting all services..."
  $COMPOSE_BASE up -d --build
  
  echo "=== Setup complete! ==="
  echo "Stack is up; database initialized with users and permissions."
  echo "Frontend: http://localhost:3000"
  echo "Backend:  http://localhost:8000"
}

action_overwrite() {
  check_env
  load_env
  set_compose
  echo ""
  echo "*** WARNING: This will DROP the public schema and DESTROY ALL DATA. ***"
  echo "    This cannot be undone."
  printf "    Type 'yes' to confirm: "
  read -r confirm
  if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
  fi
  echo "Resetting database (drop public schema), then running migrations..."
  $COMPOSE_RUN_API python -m src.database.reset_db
  $COMPOSE_RUN_API alembic upgrade head
  
  echo "Re-granting permissions..."
  if ! cat scripts/grant-better-auth-permissions.sql | $COMPOSE_BASE exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U postgres -d "${POSTGRES_DB:-job_agent}" -f -; then
    echo "Warning: Failed to grant Better Auth permissions."
  fi
  grant_frontend_permissions
  
  echo "Syncing Prisma schema..."
  sync_prisma
  
  echo "Done. Database reset and at alembic head with permissions granted."
}

action_migrate() {
  check_env
  load_env
  set_compose
  echo "Running migrations (alembic upgrade head)..."
  $COMPOSE_RUN_API alembic upgrade head
  
  echo "Granting Better Auth permissions to UI account..."
  if ! cat scripts/grant-better-auth-permissions.sql | $COMPOSE_BASE exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U postgres -d "${POSTGRES_DB:-job_agent}" -f -; then
    echo "Warning: Failed to grant Better Auth permissions."
  fi
  
  echo "Granting frontend read permissions..."
  grant_frontend_permissions
  
  echo "Syncing Prisma schema..."
  sync_prisma
  
  echo "Done. Database at alembic head with permissions granted."
}

action_two_users() {
  check_env
  load_env
  set_compose
  if [ -z "${POSTGRES_PASSWORD:-}" ] || [ -z "${POSTGRES_UI_PASSWORD:-}" ]; then
    echo "Error: POSTGRES_PASSWORD and POSTGRES_UI_PASSWORD must be set in .env for this action."
    exit 1
  fi
  echo "Adding two Postgres users (job_agent_admin, job_agent_ui) for existing DB..."
  ADMIN_ESC="${POSTGRES_PASSWORD//\'/\'\'}"
  UI_ESC="${POSTGRES_UI_PASSWORD//\'/\'\'}"
  if ! cat scripts/grant-two-users-existing-db.sql | $COMPOSE_BASE exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U postgres -d "${POSTGRES_DB:-job_agent}" \
    -v admin_pass="${ADMIN_ESC}" -v ui_pass="${UI_ESC}" -f -; then
    echo "Hint: ensure the stack is running (./setup.sh --start) and Postgres is up."
    exit 1
  fi
  echo "Done. Two users created and granted. Set POSTGRES_USER=job_agent_admin in .env and use for backend."
}

action_restart() {
  check_env
  set_compose
  echo "Restarting stack with fresh rebuild (--no-cache)..."
  $COMPOSE_BASE down
  $COMPOSE_BASE build --no-cache
  $COMPOSE_BASE up -d
  echo "Done. Containers rebuilt without cache and restarted."
}

action_rebuild_frontend() {
  check_env
  set_compose
  echo "Rebuilding and restarting frontend container..."
  $COMPOSE_BASE build frontend
  $COMPOSE_BASE up -d --force-recreate frontend
  echo "Waiting for frontend health check..."
  sleep 5
  # Check health status
  for i in {1..6}; do
    STATUS=$($COMPOSE_BASE ps frontend --format '{{.Health}}' 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "healthy" ]; then
      echo "Frontend is healthy!"
      break
    fi
    if [ $i -eq 6 ]; then
      echo "Warning: Frontend health check not yet healthy. Check logs with: docker compose logs frontend"
    else
      echo "  Waiting for frontend to be healthy... ($i/6)"
      sleep 5
    fi
  done
  echo "Done. Frontend rebuilt and restarted."
  echo "Access at: http://localhost:3000"
}

action_start() {
  check_env
  set_compose
  echo "Starting stack ($MODE)..."
  $COMPOSE_BASE up -d --build
  echo "Done. API: port 8000 (dev) or via Caddy 80/443 (prod). Frontend: port 3000."
}

action_stop() {
  set_compose
  echo "Stopping stack ($MODE)..."
  $COMPOSE_BASE down
  echo "Done."
}

# -----------------------------------------------------------------------------
# Menu
# -----------------------------------------------------------------------------
run_menu() {
  check_env
  load_env
  while true; do
    echo ""
    echo "--- job-agent setup ---"
    echo "  1) First-time setup     - Start Postgres/Redis + run migrations (new DB)"
    echo "  2) Overwrite DB         - Drop public schema, re-run migrations (DESTROYS DATA)"
    echo "  3) Run migrations only  - alembic upgrade head (apply new migrations)"
    echo "  4) Add two users        - One-time: create job_agent_admin + job_agent_ui (existing DB)"
    echo "  5) Restart (no-cache)   - Stop, rebuild --no-cache, start (deploy code changes)"
    echo "  6) Rebuild frontend     - Rebuild and restart frontend container only"
    echo "  7) Start stack          - docker compose up -d --build"
    echo "  8) Stop stack           - docker compose down"
    echo "  9) Toggle dev/prod      - Current: $MODE"
    echo "  0) Quit"
    echo ""
    printf "Choice [0-9]: "
    read -r choice
    case "$choice" in
      1) action_first_time ;;
      2) action_overwrite ;;
      3) action_migrate ;;
      4) action_two_users ;;
      5) action_restart ;;
      6) action_rebuild_frontend ;;
      7) action_start ;;
      8) action_stop ;;
      9)
        if [ "$MODE" = "dev" ]; then MODE="prod"; else MODE="dev"; fi
        set_compose
        echo "Mode set to $MODE."
        ;;
      0) echo "Bye."; exit 0 ;;
      *) echo "Invalid choice." ;;
    esac
  done
}

# -----------------------------------------------------------------------------
# Parse args: optional --dev/--prod plus one action flag (e.g. ./setup.sh --migrate --prod)
# -----------------------------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    --prod) MODE="prod" ;;
    --dev)  MODE="dev" ;;
  esac
done
for arg in "$@"; do
  case "$arg" in
    --first-time)       set_compose; action_first_time;       exit 0 ;;
    --overwrite)        set_compose; action_overwrite;        exit 0 ;;
    --migrate)          set_compose; action_migrate;          exit 0 ;;
    --two-users)        set_compose; action_two_users;        exit 0 ;;
    --restart)          set_compose; action_restart;          exit 0 ;;
    --rebuild-frontend) set_compose; action_rebuild_frontend; exit 0 ;;
    --start)            set_compose; action_start;            exit 0 ;;
    --stop)             set_compose; action_stop;             exit 0 ;;
  esac
done

run_menu
