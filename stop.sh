#!/usr/bin/env bash
# Stop the job-agent stack (dev or prod). Use same flag as start.sh.
# Usage: ./stop.sh [--dev|--prod]   (default: --dev)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODE="dev"
for arg in "$@"; do
  case "$arg" in
    --prod) MODE="prod"; break ;;
    --dev)  MODE="dev";  break ;;
  esac
done

if [ "$MODE" = "prod" ]; then
  echo "Stopping stack (production)..."
  docker compose -f docker-compose.yml -f docker-compose.prod.yml down
else
  echo "Stopping stack (development)..."
  docker compose down
fi

echo "Done."
