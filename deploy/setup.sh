#!/bin/bash
# =============================================================
# setup.sh — Food Body Connection server bootstrap
# Target: Oracle Cloud Ubuntu 22.04 (ARM Ampere A1 or AMD)
#
# Run once as the default 'ubuntu' user:
#   chmod +x setup.sh && ./setup.sh
# =============================================================

set -e

APP_DIR="/opt/foodbodyconnection"
APP_USER="foodbody"
DB_NAME="foodbodyconnection"
DB_USER="foodbody"

echo ""
echo "=== [1/8] System update ==="
sudo apt-get update && sudo apt-get upgrade -y

echo ""
echo "=== [2/8] Installing system packages ==="
sudo apt-get install -y \
    python3.11 python3.11-venv python3.11-dev \
    python3-pip \
    postgresql postgresql-contrib \
    nginx \
    certbot python3-certbot-nginx \
    git \
    netfilter-persistent iptables-persistent

echo ""
echo "=== [3/8] Opening firewall ports (iptables) ==="
# Oracle Cloud Ubuntu VMs block ports 80/443 in iptables by default.
# The Security List in the OCI console also needs rules — see README.
sudo iptables  -I INPUT 6 -m state --state NEW -p tcp --dport 80  -j ACCEPT
sudo iptables  -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo ip6tables -I INPUT 6 -m state --state NEW -p tcp --dport 80  -j ACCEPT
sudo ip6tables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

echo ""
echo "=== [4/8] Setting up PostgreSQL ==="
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Prompt for DB password
read -rsp "Enter a password for the PostgreSQL app user '${DB_USER}': " DB_PASS
echo ""

sudo -u postgres psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
  END IF;
END
\$\$;
SQL

sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" 2>/dev/null || \
    echo "Database '${DB_NAME}' already exists — skipping."

echo ""
echo "=== [5/8] Creating app system user ==="
sudo useradd --system --shell /bin/bash --create-home ${APP_USER} 2>/dev/null || \
    echo "User '${APP_USER}' already exists — skipping."

echo ""
echo "=== [6/8] Setting up app directory ==="
sudo mkdir -p ${APP_DIR}
sudo chown ${APP_USER}:${APP_USER} ${APP_DIR}

echo ""
echo "=== [7/8] Writing .env file ==="
# Generate a random secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

sudo tee ${APP_DIR}/.env > /dev/null <<ENV
DB_URL=postgresql://${DB_USER}:${DB_PASS}@localhost/${DB_NAME}
DB_MAINT_URL=postgresql://postgres:POSTGRES_SUPERUSER_PASSWORD@localhost/postgres
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ENV

sudo chown ${APP_USER}:${APP_USER} ${APP_DIR}/.env
sudo chmod 600 ${APP_DIR}/.env

echo ""
echo "=== [8/8] Base setup complete ==="
echo ""
echo "Next steps (run after copying your code to ${APP_DIR}):"
echo ""
echo "  1. Copy repo:    sudo rsync -a /tmp/capstone/backend/ ${APP_DIR}/"
echo "                   sudo chown -R ${APP_USER}:${APP_USER} ${APP_DIR}"
echo ""
echo "  2. Create venv:  sudo -u ${APP_USER} python3.11 -m venv ${APP_DIR}/venv"
echo "  3. Install deps: sudo -u ${APP_USER} ${APP_DIR}/venv/bin/pip install -r ${APP_DIR}/requirements.txt"
echo ""
echo "  4. Copy and enable service + nginx configs:"
echo "     sudo cp /tmp/capstone/deploy/foodbodyconnection.service /etc/systemd/system/"
echo "     sudo cp /tmp/capstone/deploy/nginx.conf /etc/nginx/sites-available/foodbodyconnection"
echo "     sudo ln -sf /etc/nginx/sites-available/foodbodyconnection /etc/nginx/sites-enabled/"
echo "     sudo rm -f /etc/nginx/sites-enabled/default"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable --now foodbodyconnection"
echo "     sudo nginx -t && sudo systemctl restart nginx"
echo ""
echo "  5. SSL:  sudo certbot --nginx -d foodbodyconnection.YOUR_IP.nip.io"
echo ""
echo "  6. Import database:"
echo "     psql -h localhost -U ${DB_USER} -d ${DB_NAME} < backup.sql"
echo ""
echo "DB credentials written to ${APP_DIR}/.env"
echo "Secret key auto-generated."
