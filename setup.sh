#!/usr/bin/env bash
# First-time setup: create database tables (run once after clone and .env copy).
# Usage: ./setup.sh [--dev|--prod]   (default: --dev)
# Note: Start the stack first (./start.sh) so postgres is up.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
  echo "Error: .env not found. Copy .env.example to .env and fill in values."
  exit 1
fi

MODE="dev"
for arg in "$@"; do
  case "$arg" in
    --prod) MODE="prod"; break ;;
    --dev)  MODE="dev";  break ;;
  esac
done

if [ "$MODE" = "prod" ]; then
  echo "Running table creation (production compose)..."
  docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api python -m src.database.create_tables
else
  echo "Running table creation (development compose)..."
  docker compose run --rm api python -m src.database.create_tables
fi

echo "Done. Tables created (idempotent; safe to run again)."
