#!/bin/bash
# =============================================================
# oracle_guide.sh — step-by-step Oracle Cloud setup
#
# Shape:    VM.Standard.E2.1.Micro (AMD x86, 1 OCPU, 1 GB RAM)
# Database: Neon (external — no local PostgreSQL)
#
# REFERENCE SCRIPT — read each section and run commands
# manually. Do not execute this file directly.
# =============================================================


# -----------------------------------------------------------
# STEP 1 — Create a compute instance (OCI console)
# -----------------------------------------------------------
# 1. Go to https://cloud.oracle.com → Compute → Instances → Create Instance
#
# 2. Name:  foodbodyconnection
#
# 3. Image: Click "Change image"
#    → Canonical Ubuntu → Ubuntu 22.04
#
# 4. Shape: Click "Change shape"
#    → Specialty and previous generation → VM.Standard.E2.1.Micro
#      (always-free, AMD x86, 1 OCPU / 1 GB RAM)
#
# 5. Networking: leave defaults (new VCN created automatically)
#
# 6. SSH keys: "Generate a key pair for me"
#    → Download both files → save private key to ~/.ssh/oracle_fbc.key
#    → Run:  chmod 400 ~/.ssh/oracle_fbc.key
#
# 7. Click "Create". Note the Public IP address once provisioned.


# -----------------------------------------------------------
# STEP 2 — Open ports 80 and 443 in the Security List
# -----------------------------------------------------------
# Oracle blocks all inbound traffic except SSH by default.
#
# Networking → Virtual Cloud Networks → your VCN
# → Security Lists → Default Security List → Add Ingress Rules:
#
#   Rule 1:  Source 0.0.0.0/0  |  TCP  |  Port 80
#   Rule 2:  Source 0.0.0.0/0  |  TCP  |  Port 443
#
# The VM's internal iptables rules are handled by setup.sh.


# -----------------------------------------------------------
# STEP 3 — SSH into the instance
# -----------------------------------------------------------
# ssh -i ~/.ssh/oracle_fbc.key ubuntu@YOUR_ORACLE_IP


# -----------------------------------------------------------
# STEP 4 — Clone repo and run setup.sh
# -----------------------------------------------------------
# git clone https://github.com/alkohout/food_body_connection.git /tmp/capstone
#
# chmod +x /tmp/capstone/deploy/setup.sh
# /tmp/capstone/deploy/setup.sh
#
# The script will prompt for:
#   - Neon connection string  (console.neon.tech → your project → Connection Details)
#   - Anthropic API key       (console.anthropic.com → API Keys)
#
# Neon connection string format:
#   postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require


# -----------------------------------------------------------
# STEP 5 — Deploy the app code
# -----------------------------------------------------------
# sudo rsync -a /tmp/capstone/backend/ /opt/foodbodyconnection/
# sudo chown -R foodbody:foodbody /opt/foodbodyconnection/
#
# sudo -u foodbody python3.11 -m venv /opt/foodbodyconnection/venv
# sudo -u foodbody /opt/foodbodyconnection/venv/bin/pip install --upgrade pip
# sudo -u foodbody /opt/foodbodyconnection/venv/bin/pip install -r /opt/foodbodyconnection/requirements.txt


# -----------------------------------------------------------
# STEP 6 — Configure nginx
# -----------------------------------------------------------
# Edit the config to add your real IP before copying:
# nano /tmp/capstone/deploy/nginx.conf
#   → replace YOUR_ORACLE_IP with your actual public IP
#
# sudo cp /tmp/capstone/deploy/nginx.conf /etc/nginx/sites-available/foodbodyconnection
# sudo ln -sf /etc/nginx/sites-available/foodbodyconnection /etc/nginx/sites-enabled/
# sudo rm -f /etc/nginx/sites-enabled/default
# sudo nginx -t && sudo systemctl restart nginx


# -----------------------------------------------------------
# STEP 7 — Start the app service
# -----------------------------------------------------------
# sudo cp /tmp/capstone/deploy/foodbodyconnection.service /etc/systemd/system/
# sudo systemctl daemon-reload
# sudo systemctl enable --now foodbodyconnection
#
# Check it started:
# sudo systemctl status foodbodyconnection
# sudo journalctl -u foodbodyconnection -f      ← live logs
#
# Quick API test:
# curl http://localhost:8000/
# → should return {"status": "ok"}


# -----------------------------------------------------------
# STEP 8 — SSL certificate (HTTPS)
# -----------------------------------------------------------
# nip.io gives you a free hostname from your IP — no DNS needed.
# Your URL:  https://foodbodyconnection.YOUR_IP.nip.io
# (replace the dots in your IP with dashes)
#
# Example — if IP is 1.2.3.4:
#   sudo certbot --nginx -d foodbodyconnection.1-2-3-4.nip.io
#
# Certbot rewrites nginx.conf and sets up auto-renewal.


# -----------------------------------------------------------
# STEP 9 — Point the frontend at the new backend
# -----------------------------------------------------------
# On your Mac, edit docs/js/api.js:
#   export const API_URL = "https://foodbodyconnection.YOUR_IP.nip.io";
#
# Also add the nip.io URL to the CORS origins in backend/app/main.py:
#   "https://foodbodyconnection.YOUR_IP.nip.io",
#
# Commit and push — GitHub Pages picks it up automatically.
# Then redeploy the backend to pick up the CORS change (see Step 10).


# -----------------------------------------------------------
# STEP 10 — Redeploy after any code change
# -----------------------------------------------------------
# cd /tmp/capstone && git pull
# sudo rsync -a /tmp/capstone/backend/ /opt/foodbodyconnection/
# sudo chown -R foodbody:foodbody /opt/foodbodyconnection/
# sudo -u foodbody /opt/foodbodyconnection/venv/bin/pip install -r /opt/foodbodyconnection/requirements.txt
# sudo systemctl restart foodbodyconnection


# -----------------------------------------------------------
# USEFUL day-to-day commands
# -----------------------------------------------------------
# sudo systemctl status foodbodyconnection     → is the app running?
# sudo journalctl -u foodbodyconnection -f     → live app logs
# sudo systemctl restart foodbodyconnection    → restart after changes
# free -h                                      → check RAM usage (tight on micro)
