#!/bin/bash
# =============================================================
# fly_guide.sh — step-by-step Fly.io migration
#
# This is a REFERENCE script — read each section and run the
# commands manually rather than executing this file directly.
# =============================================================


# -----------------------------------------------------------
# STEP 1 — Install flyctl (run on your Mac)
# -----------------------------------------------------------
# curl -L https://fly.io/install.sh | sh
# Then add to PATH if prompted, or open a new terminal.


# -----------------------------------------------------------
# STEP 2 — Sign up and log in
# -----------------------------------------------------------
# fly auth signup      # opens browser — needs a credit card (won't be charged on free tier)
# fly auth login       # if you already have an account


# -----------------------------------------------------------
# STEP 3 — Dump your database from the OLD EC2 server
# -----------------------------------------------------------
# Run these on your EC2 instance (or wherever postgres is running):
#
#   pg_dump -h localhost -U foodbody -d foodbodyconnection \
#       --no-owner --no-acl -f ~/fbc_backup.sql
#
# Copy to your local machine:
#   scp ubuntu@YOUR_EC2_IP:~/fbc_backup.sql ./fbc_backup.sql
#
# Keep this file — you'll need it in Step 7.


# -----------------------------------------------------------
# STEP 4 — Create the Fly app (run from backend/ directory)
# -----------------------------------------------------------
# cd /path/to/capstone/backend
#
# fly launch --no-deploy
#   - When prompted for app name: choose something unique, e.g. "fbc-alison"
#     (if "foodbodyconnection" is taken, pick another name)
#   - Region: syd
#   - Say NO to creating a Postgres database now (we do it separately)
#   - Say NO to deploying now
#
# This updates the app name in fly.toml if you chose a different name.
# The app URL will be: https://<your-app-name>.fly.dev


# -----------------------------------------------------------
# STEP 5 — Create the Fly Postgres database
# -----------------------------------------------------------
# fly postgres create --name fbc-db --region syd --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 3
#
# This creates a free Postgres instance.
# NOTE the password shown — you won't see it again (but can reset it).
#
# Attach it to your app (this sets DATABASE_URL secret automatically):
# fly postgres attach fbc-db --app <your-app-name>


# -----------------------------------------------------------
# STEP 6 — Set the remaining secrets
# -----------------------------------------------------------
# fly secrets set \
#   SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
#   --app <your-app-name>
#
# DB_URL is handled automatically by the DATABASE_URL secret that
# fly postgres attach set — our app reads either DB_URL or DATABASE_URL.


# -----------------------------------------------------------
# STEP 7 — Deploy the app (first deploy creates the tables)
# -----------------------------------------------------------
# cd /path/to/capstone/backend
# fly deploy --app <your-app-name>
#
# Watch the logs to confirm it starts:
# fly logs --app <your-app-name>
#
# Check the health endpoint:
# curl https://<your-app-name>.fly.dev/
# → should return {"status": "ok"}


# -----------------------------------------------------------
# STEP 8 — Import your database backup
# -----------------------------------------------------------
# Fly Postgres runs as its own Fly app. Connect via proxy:
#
# In terminal 1 — open a tunnel to Fly Postgres on local port 5433:
#   fly proxy 5433:5432 -a fbc-db
#
# In terminal 2 — restore the dump:
#   psql "postgresql://postgres:<POSTGRES_PASSWORD>@localhost:5433/foodbodyconnection" \
#       < ./fbc_backup.sql
#
# Get the postgres password:
#   fly secrets list -a fbc-db   # shows secret names
#   fly postgres connect -a fbc-db  # opens psql directly if you just want to poke around


# -----------------------------------------------------------
# STEP 9 — Update the frontend API URL
# -----------------------------------------------------------
# Edit docs/js/api.js:
#   export const API_URL = "https://<your-app-name>.fly.dev";
#
# Commit and push — GitHub Pages picks it up automatically.


# -----------------------------------------------------------
# STEP 10 — Test, then terminate your EC2 instance
# -----------------------------------------------------------
# Open the dashboard, log in, check all tabs work.
# Once confirmed, stop/terminate the EC2 instance in the AWS console.


# -----------------------------------------------------------
# USEFUL fly commands for day-to-day management
# -----------------------------------------------------------
# fly logs -a <app>               → live log stream
# fly status -a <app>             → machine health
# fly deploy -a <app>             → redeploy after code changes
# fly ssh console -a <app>        → shell inside the running container
# fly secrets set KEY=val         → update an env var
# fly postgres connect -a fbc-db  → psql into the database
