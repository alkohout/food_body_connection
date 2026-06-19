#!/bin/bash
# =============================================================
# setup.sh — Food Body Connection server bootstrap
# Target: Oracle Cloud Ubuntu 22.04 VM.Standard.E2.1.Micro (AMD)
#         Database: Neon (external PostgreSQL — no local DB)
#
# Run once as the default 'ubuntu' user:
#   chmod +x setup.sh && ./setup.sh
# =============================================================

set -e

APP_DIR="/opt/foodbodyconnection"
APP_USER="foodbody"

echo ""
echo "=== [1/7] System update ==="
sudo NEEDRESTART_MODE=a apt-get update && sudo NEEDRESTART_MODE=a apt-get upgrade -y

echo ""
echo "=== [2/7] Installing system packages ==="
sudo NEEDRESTART_MODE=a apt-get install -y \
    python3.11 python3.11-venv python3.11-dev \
    python3-pip \
    nginx \
    certbot python3-certbot-nginx \
    git \
    netfilter-persistent iptables-persistent

echo ""
echo "=== [3/7] Opening firewall ports (iptables) ==="
# Oracle Cloud blocks ports 80/443 in iptables by default.
# The VCN Security List also needs rules — see oracle_guide.sh Step 2.
sudo iptables  -I INPUT 6 -m state --state NEW -p tcp --dport 80  -j ACCEPT
sudo iptables  -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo ip6tables -I INPUT 6 -m state --state NEW -p tcp --dport 80  -j ACCEPT
sudo ip6tables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

echo ""
echo "=== [4/7] Creating app system user ==="
sudo useradd --system --shell /bin/bash --create-home ${APP_USER} 2>/dev/null || \
    echo "User '${APP_USER}' already exists — skipping."

echo ""
echo "=== [5/7] Setting up app directory ==="
sudo mkdir -p ${APP_DIR}
sudo chown ${APP_USER}:${APP_USER} ${APP_DIR}

echo ""
echo "=== [6/7] Collecting credentials ==="

echo ""
echo "Paste your Neon connection string."
echo "Find it at: console.neon.tech → your project → Connection Details"
echo "It looks like: postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require"
echo ""
read -rp "Neon DB_URL: " NEON_URL
echo ""

read -rsp "Enter your Anthropic API key (leave blank to add later): " ANTHROPIC_KEY
echo ""

# Generate a random JWT secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo ""
echo "=== [7/7] Writing .env file ==="
sudo tee ${APP_DIR}/.env > /dev/null <<ENV
DB_URL=${NEON_URL}
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
ENV

sudo chown ${APP_USER}:${APP_USER} ${APP_DIR}/.env
sudo chmod 600 ${APP_DIR}/.env

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps (see oracle_guide.sh for full detail):"
echo ""
echo "  1. Copy code:    sudo rsync -a /tmp/capstone/backend/ ${APP_DIR}/"
echo "                   sudo chown -R ${APP_USER}:${APP_USER} ${APP_DIR}"
echo ""
echo "  2. Create venv:  sudo -u ${APP_USER} python3.11 -m venv ${APP_DIR}/venv"
echo "  3. Install deps: sudo -u ${APP_USER} ${APP_DIR}/venv/bin/pip install -r ${APP_DIR}/requirements.txt"
echo ""
echo "  4. Configure nginx (replace YOUR_ORACLE_IP first):"
echo "     sudo cp /tmp/capstone/deploy/nginx.conf /etc/nginx/sites-available/foodbodyconnection"
echo "     sudo ln -sf /etc/nginx/sites-available/foodbodyconnection /etc/nginx/sites-enabled/"
echo "     sudo rm -f /etc/nginx/sites-enabled/default"
echo "     sudo nginx -t && sudo systemctl restart nginx"
echo ""
echo "  5. Start app:"
echo "     sudo cp /tmp/capstone/deploy/foodbodyconnection.service /etc/systemd/system/"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable --now foodbodyconnection"
echo ""
echo "  6. SSL:  sudo certbot --nginx -d foodbodyconnection.YOUR_IP.nip.io"
echo ""
echo "Credentials written to ${APP_DIR}/.env  (chmod 600)"
echo "JWT secret key auto-generated."
