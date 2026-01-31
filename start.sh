#!/usr/bin/env bash
# Start the job-agent stack (dev or prod).
# Usage: ./start.sh [--dev|--prod]   (default: --dev)

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
  echo "Starting stack (production)..."
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
else
  echo "Starting stack (development)..."
  docker compose up -d
fi

echo "Done. API: port 8000 (dev) or via Caddy 80/443 (prod)."
