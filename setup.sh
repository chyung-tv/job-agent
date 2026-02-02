#!/usr/bin/env bash
# Single idempotent setup script: first-time deployment and schema updates.
# Usage: ./setup.sh [--dev|--prod] [--overwrite]
#   Default: runs alembic upgrade head (idempotent). First time = create tables; later = apply new migrations.
#   --overwrite  Drop public schema and re-run migrations (fresh start; destroys all data). Prompts for confirmation.
# Note: Start the stack first (./start.sh) so postgres is up.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
  echo "Error: .env not found. Copy .env.example to .env and fill in values."
  exit 1
fi

MODE="dev"
OVERWRITE=""
for arg in "$@"; do
  case "$arg" in
    --prod)     MODE="prod";     ;;
    --dev)      MODE="dev";      ;;
    --overwrite) OVERWRITE="1";  ;;
  esac
done

COMPOSE_CMD="docker compose run --rm api"
if [ "$MODE" = "prod" ]; then
  COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api"
fi

if [ -n "$OVERWRITE" ]; then
  echo ""
  echo "*** WARNING: --overwrite will DROP the public schema and DESTROY ALL DATA. ***"
  echo "    This cannot be undone."
  printf "    Type 'yes' to confirm: "
  read -r confirm
  if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
  fi
  echo "Overwrite: resetting database (drop public schema), then running migrations..."
  $COMPOSE_CMD python -m src.database.reset_db
fi

if [ "$MODE" = "prod" ]; then
  echo "Running migrations (production compose)..."
  $COMPOSE_CMD alembic upgrade head
else
  echo "Running migrations (development compose)..."
  $COMPOSE_CMD alembic upgrade head
fi

echo "Done. Database at alembic head (safe to run again)."
