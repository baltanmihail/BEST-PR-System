#!/bin/bash
set -e

REPO_URL="https://github.com/baltanmihail/BEST-PR-System.git"
PROJECT_DIR="$HOME/best-pr-system"
DOMAIN="pr.bmstu-best.ru"
SERVER_IP="192.144.12.196"

echo "============================================="
echo "  BEST PR System — Full Server Setup"
echo "  $(date)"
echo "============================================="
echo ""

# ---- STEP 1: Home directory ----
if [ ! -d "$HOME" ] || [ "$HOME" = "/" ]; then
    echo "[1/8] Creating home directory..."
    sudo mkdir -p /home/$(whoami)
    sudo chown $(whoami):$(whoami) /home/$(whoami)
    export HOME=/home/$(whoami)
    echo "export HOME=/home/$(whoami)" >> /home/$(whoami)/.bashrc
else
    echo "[1/8] Home directory OK: $HOME"
fi

# ---- STEP 2: System packages ----
echo "[2/8] Installing system packages..."
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release git ufw

# ---- STEP 3: Docker ----
if ! command -v docker &> /dev/null; then
    echo "[3/8] Installing Docker..."
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker $(whoami)
    echo "    Docker installed: $(docker --version)"
else
    echo "[3/8] Docker OK: $(docker --version)"
fi

# ---- STEP 4: nginx ----
if ! command -v nginx &> /dev/null; then
    echo "[4/8] Installing nginx..."
    sudo apt-get install -y nginx
    sudo systemctl enable nginx
else
    echo "[4/8] nginx OK"
fi

# ---- STEP 5: Certbot ----
if ! command -v certbot &> /dev/null; then
    echo "[5/8] Installing certbot..."
    sudo apt-get install -y certbot python3-certbot-nginx
else
    echo "[5/8] certbot OK"
fi

# ---- STEP 6: Firewall ----
echo "[6/8] Configuring firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
echo "    Firewall status:"
sudo ufw status numbered

# ---- STEP 7: Clone repo ----
if [ ! -d "$PROJECT_DIR" ]; then
    echo "[7/8] Cloning repository..."
    git clone "$REPO_URL" "$PROJECT_DIR"
else
    echo "[7/8] Repository exists, pulling latest..."
    cd "$PROJECT_DIR"
    git pull origin main
fi

cd "$PROJECT_DIR"

# ---- STEP 8: Create .env ----
if [ ! -f .env ]; then
    echo "[8/8] Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "============================================="
    echo "  SETUP COMPLETE!"
    echo "============================================="
    echo ""
    echo "NEXT: Edit .env with real values:"
    echo "  nano $PROJECT_DIR/.env"
    echo ""
    echo "Then run:"
    echo "  cd $PROJECT_DIR && bash deploy/start-services.sh"
else
    echo "[8/8] .env already exists"
    echo ""
    echo "============================================="
    echo "  SETUP COMPLETE!"
    echo "============================================="
    echo ""
    echo "Run to start services:"
    echo "  cd $PROJECT_DIR && bash deploy/start-services.sh"
fi
