#!/bin/bash
set -e

PROJECT_DIR="/home/misha_b/best-pr-system"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

echo "=== BEST PR System — Deploy ==="
echo "$(date)"

cd "$PROJECT_DIR"

echo "[1/4] Pulling latest code..."
git pull origin main

echo "[2/4] Building containers..."
docker compose build --parallel

echo "[3/4] Restarting services..."
docker compose up -d

echo "[4/4] Running migrations..."
docker compose exec -T backend python -m alembic upgrade head

echo ""
echo "=== Deploy complete! ==="
docker compose ps
