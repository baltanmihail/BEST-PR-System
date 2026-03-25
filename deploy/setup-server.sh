#!/bin/bash
set -e

echo "=== BEST PR System — Server Setup ==="
echo "Ubuntu 22.04 / VPS"
echo ""

# 1. Home directory
if [ ! -d "$HOME" ] || [ "$HOME" = "/" ]; then
    echo "[1/6] Creating home directory..."
    sudo mkdir -p /home/$(whoami)
    sudo chown $(whoami):$(whoami) /home/$(whoami)
    export HOME=/home/$(whoami)
    echo "export HOME=/home/$(whoami)" >> /home/$(whoami)/.bashrc
else
    echo "[1/6] Home directory OK: $HOME"
fi

# 2. System packages
echo "[2/6] Installing base packages..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

# 3. Docker
if ! command -v docker &> /dev/null; then
    echo "[3/6] Installing Docker..."
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker $(whoami)
    echo "    Docker installed. You may need to re-login for group changes."
else
    echo "[3/6] Docker already installed: $(docker --version)"
fi

# 4. nginx
if ! command -v nginx &> /dev/null; then
    echo "[4/6] Installing nginx..."
    sudo apt-get install -y nginx
    sudo systemctl enable nginx
    sudo systemctl start nginx
else
    echo "[4/6] nginx already installed: $(nginx -v 2>&1)"
fi

# 5. Certbot (Let's Encrypt SSL)
if ! command -v certbot &> /dev/null; then
    echo "[5/6] Installing certbot..."
    sudo apt-get install -y certbot python3-certbot-nginx
else
    echo "[5/6] certbot already installed: $(certbot --version 2>&1)"
fi

# 6. Firewall
echo "[6/6] Configuring firewall (ufw)..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo ufw status

echo ""
echo "=== Setup complete! ==="
echo "Next steps:"
echo "  1. Log out and back in (for docker group)"
echo "  2. Run: docker --version"
echo "  3. Clone the repo and run deploy.sh"
