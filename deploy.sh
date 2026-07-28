#!/usr/bin/env bash
# Deploy the backend to the Oracle box.
#
# Frontend (docs/) needs no deploy — GitHub Pages serves it straight from main,
# so `git push` is the whole story there.
#
# Usage:  ./deploy.sh            deploy whatever is on origin/main
#         ./deploy.sh --logs     deploy, then tail the service logs
set -euo pipefail

cd "$(dirname "$0")"

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Uncommitted changes in the working tree — commit and push first." >&2
    exit 1
fi

LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u} 2>/dev/null || echo "none")
if [ "$LOCAL" != "$REMOTE" ]; then
    echo "Local main is not pushed (local $LOCAL vs upstream $REMOTE). Run: git push" >&2
    exit 1
fi

echo "==> Deploying $LOCAL to 159.13.61.101"

./ssh.sh 'bash -s' <<'REMOTE_SCRIPT'
set -euo pipefail

CHECKOUT=/tmp/capstone
APP_DIR=/opt/foodbodyconnection

if [ ! -d "$CHECKOUT/.git" ]; then
    rm -rf "$CHECKOUT"
    git clone https://github.com/alkohout/food_body_connection.git "$CHECKOUT"
fi

echo "--- pulling ---"
git -C "$CHECKOUT" fetch --quiet origin
git -C "$CHECKOUT" reset --hard --quiet origin/main
git -C "$CHECKOUT" --no-pager log -1 --oneline

echo "--- syncing code (.env preserved) ---"
sudo rsync -a --exclude '.env' --exclude 'venv/' "$CHECKOUT/backend/" "$APP_DIR/"
sudo chown -R foodbody:foodbody "$APP_DIR"

echo "--- installing deps ---"
sudo -u foodbody "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "--- restarting ---"
sudo systemctl restart foodbodyconnection
sleep 3
sudo systemctl is-active foodbodyconnection
curl -fsS http://localhost:8000/ && echo
REMOTE_SCRIPT

echo "==> Done"

if [ "${1:-}" = "--logs" ]; then
    ./ssh.sh 'sudo journalctl -u foodbodyconnection -f'
fi
