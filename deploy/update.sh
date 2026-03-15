#!/usr/bin/env bash
#
# Quick update: pull latest code and redeploy
# Run from project root: bash deploy/update.sh
#
set -euo pipefail

echo "→ Pulling latest code..."
git pull --ff-only

echo "→ Rebuilding and restarting containers..."
docker compose up -d --build

echo "→ Cleaning up old images..."
docker image prune -f

echo "→ Status:"
docker compose ps

echo ""
echo "→ Logs (Ctrl+C to exit):"
docker compose logs -f --tail=50 bot
