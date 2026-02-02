#!/usr/bin/env bash
# Unified setup script: menu-driven or use flags for CI/automation.
# Usage:
#   ./setup.sh                    # Interactive menu
#   ./setup.sh --first-time       # First-time setup (start stack + migrations)
#   ./setup.sh --overwrite        # Reset DB and run migrations (destroys data)
#   ./setup.sh --migrate          # Run migrations only (alembic upgrade head)
#   ./setup.sh --two-users        # One-time: add job_agent_admin + job_agent_ui (existing DB)
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

# -----------------------------------------------------------------------------
# Actions
# -----------------------------------------------------------------------------
action_first_time() {
  check_env
  set_compose
  echo "First-time setup: starting stack, then running migrations..."
  $COMPOSE_BASE up -d
  echo "Waiting for Postgres to be ready..."
  sleep 5
  $COMPOSE_RUN_API alembic upgrade head
  echo "Done. Stack is up; database at alembic head."
}

action_overwrite() {
  check_env
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
  echo "Done. Database reset and at alembic head."
}

action_migrate() {
  check_env
  set_compose
  echo "Running migrations (alembic upgrade head)..."
  $COMPOSE_RUN_API alembic upgrade head
  echo "Done. Database at alembic head."
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

action_start() {
  check_env
  set_compose
  echo "Starting stack ($MODE)..."
  $COMPOSE_BASE up -d
  echo "Done. API: port 8000 (dev) or via Caddy 80/443 (prod)."
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
    echo "  3) Run migrations only - alembic upgrade head (apply new migrations)"
    echo "  4) Add two users        - One-time: create job_agent_admin + job_agent_ui (existing DB)"
    echo "  5) Start stack         - docker compose up -d"
    echo "  6) Stop stack          - docker compose down"
    echo "  7) Toggle dev/prod     - Current: $MODE"
    echo "  8) Quit"
    echo ""
    printf "Choice [1-8]: "
    read -r choice
    case "$choice" in
      1) action_first_time ;;
      2) action_overwrite ;;
      3) action_migrate ;;
      4) action_two_users ;;
      5) action_start ;;
      6) action_stop ;;
      7)
        if [ "$MODE" = "dev" ]; then MODE="prod"; else MODE="dev"; fi
        set_compose
        echo "Mode set to $MODE."
        ;;
      8) echo "Bye."; exit 0 ;;
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
    --first-time) set_compose; action_first_time; exit 0 ;;
    --overwrite)  set_compose; action_overwrite;  exit 0 ;;
    --migrate)    set_compose; action_migrate;   exit 0 ;;
    --two-users)  set_compose; action_two_users;  exit 0 ;;
    --start)      set_compose; action_start;     exit 0 ;;
    --stop)       set_compose; action_stop;      exit 0 ;;
  esac
done

run_menu
