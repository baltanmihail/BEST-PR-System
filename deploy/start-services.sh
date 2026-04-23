#!/bin/bash
set -e

PROJECT_DIR="$HOME/best-pr-system"
cd "$PROJECT_DIR"

echo "============================================="
echo "  Starting BEST PR System services"
echo "  $(date)"
echo "============================================="
echo ""

# Need to use sudo for docker if user wasn't re-logged after group add
DOCKER_CMD="docker"
if ! docker ps &> /dev/null 2>&1; then
    DOCKER_CMD="sudo docker"
    echo "Using sudo for docker (re-login to avoid this)"
fi

echo "[1/5] Building containers (this may take 5-10 min first time)..."
$DOCKER_CMD compose build --parallel

echo "[2/5] Starting services..."
$DOCKER_CMD compose up -d

echo "[3/5] Waiting for database to be healthy..."
sleep 15

echo "[4/5] Running database migrations..."
$DOCKER_CMD compose exec -T backend python -m alembic upgrade head

echo "[5/5] Setting up nginx reverse proxy..."
sudo cp deploy/nginx/best-pr.conf /etc/nginx/sites-available/best-pr
sudo ln -sf /etc/nginx/sites-available/best-pr /etc/nginx/sites-enabled/best-pr
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "============================================="
echo "  ALL SERVICES RUNNING!"
echo "============================================="
echo ""
$DOCKER_CMD compose ps
echo ""
echo "Test locally:  curl http://localhost:8080/health"
echo "Test from web: http://192.144.12.196"
