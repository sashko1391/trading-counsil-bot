#!/usr/bin/env bash
#
# Oil Trading Intelligence Bot — Server Setup Script
#
# Run on a fresh Hetzner CPX22 (Ubuntu 24.04):
#   curl -sSL https://raw.githubusercontent.com/YOUR_REPO/main/deploy/setup-server.sh | bash
#
# Or copy and run manually:
#   scp deploy/setup-server.sh root@YOUR_IP:/root/
#   ssh root@YOUR_IP bash /root/setup-server.sh
#
set -euo pipefail

echo "═══════════════════════════════════════════════"
echo "  Oil Trading Intelligence Bot — Server Setup"
echo "═══════════════════════════════════════════════"

# 1. System updates
echo "→ Updating system..."
apt-get update -qq && apt-get upgrade -y -qq

# 2. Install Docker
echo "→ Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
fi

# 3. Install Docker Compose plugin (if not bundled)
if ! docker compose version &>/dev/null; then
    apt-get install -y -qq docker-compose-plugin
fi

# 4. Create app user
echo "→ Creating app user..."
if ! id oilbot &>/dev/null; then
    useradd -m -s /bin/bash -G docker oilbot
fi

# 5. Create project directory
APP_DIR="/opt/oil-trading-bot"
echo "→ Setting up ${APP_DIR}..."
mkdir -p "${APP_DIR}"
chown oilbot:oilbot "${APP_DIR}"

# 6. Firewall (ufw)
echo "→ Configuring firewall..."
if command -v ufw &>/dev/null; then
    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw allow 443/tcp
    echo "y" | ufw enable || true
fi

# 7. Swap (useful for 4GB RAM during Docker builds)
echo "→ Configuring swap..."
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo "/swapfile swap swap defaults 0 0" >> /etc/fstab
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Clone the repo:"
echo "     su - oilbot"
echo "     cd /opt/oil-trading-bot"
echo "     git clone YOUR_REPO_URL ."
echo ""
echo "  2. Create .env from example:"
echo "     cp .env.example .env"
echo "     nano .env  # fill in API keys"
echo ""
echo "  3. Set your domain in Caddyfile:"
echo "     nano deploy/Caddyfile"
echo "     # Replace YOUR_DOMAIN with oil.yourdomain.com"
echo ""
echo "  4. Start everything:"
echo "     docker compose up -d --build"
echo ""
echo "  5. Check status:"
echo "     docker compose ps"
echo "     docker compose logs -f bot"
echo "═══════════════════════════════════════════════"
