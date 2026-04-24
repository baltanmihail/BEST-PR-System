#!/bin/bash
set -e

DOMAIN="best-pr-system.ru"
PROJECT_DIR="/home/misha_b/best-pr-system"
REPO_URL="https://github.com/baltanmihail/BEST-PR-System.git"

echo "=== BEST PR System — First Deploy ==="
echo ""

# 1. Clone repo
if [ ! -d "$PROJECT_DIR" ]; then
    echo "[1/6] Cloning repository..."
    git clone "$REPO_URL" "$PROJECT_DIR"
else
    echo "[1/6] Repository exists, pulling latest..."
    cd "$PROJECT_DIR"
    git pull origin main
fi

cd "$PROJECT_DIR"

# 2. Create .env from example if not exists
if [ ! -f .env ]; then
    echo "[2/6] Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "!!! IMPORTANT: Edit .env with your real values !!!"
    echo "    nano $PROJECT_DIR/.env"
    echo ""
    echo "At minimum set:"
    echo "  - POSTGRES_PASSWORD (strong random password)"
    echo "  - SECRET_KEY (run: openssl rand -hex 32)"
    echo "  - TELEGRAM_BOT_TOKEN"
    echo "  - TELEGRAM_GENERAL_CHAT_ID"
    echo "  - GOOGLE_CREDENTIALS_1_JSON"
    echo ""
    read -p "Press Enter after editing .env to continue..."
else
    echo "[2/6] .env already exists"
fi

# 3. Build and start containers
echo "[3/6] Building and starting Docker containers..."
docker compose up -d --build

echo "[4/6] Waiting for database to be healthy..."
sleep 10

# 4. Run migrations
echo "[5/6] Running database migrations..."
docker compose exec -T backend python -m alembic upgrade head

# 5. Setup nginx
echo "[6/6] Setting up nginx..."
sudo cp deploy/nginx/best-pr.conf /etc/nginx/sites-available/best-pr
sudo ln -sf /etc/nginx/sites-available/best-pr /etc/nginx/sites-enabled/best-pr
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo ""
echo "=== First deploy complete! ==="
echo ""
echo "Services:"
docker compose ps
echo ""
echo "Next steps:"
echo "  1. Make sure DNS A-record points $DOMAIN -> $(curl -s ifconfig.me 2>/dev/null || echo '192.144.12.196')"
echo "  2. Get SSL certificate:"
echo "     sudo certbot --nginx -d $DOMAIN"
echo "  3. Test: curl http://$DOMAIN/health"
