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

# The unit file is version-controlled but used to be applied by hand, so the
# repo copy could silently drift from what was actually running. Install it when
# it differs; systemd needs the reload before the restart below picks it up.
UNIT_SRC="$CHECKOUT/deploy/foodbodyconnection.service"
UNIT_DST=/etc/systemd/system/foodbodyconnection.service
if [ -f "$UNIT_SRC" ] && ! sudo cmp -s "$UNIT_SRC" "$UNIT_DST"; then
    echo "--- updating systemd unit ---"
    sudo cp "$UNIT_SRC" "$UNIT_DST"
    sudo systemctl daemon-reload
fi

echo "--- restarting ---"
sudo systemctl restart foodbodyconnection
sudo systemctl is-active foodbodyconnection

# Workers take ~30s to come up: uvicorn forks them, then each imports pandas,
# sklearn and matplotlib before it will accept a connection. A fixed short sleep
# reported "Connection refused" on a deploy that had in fact succeeded, so poll
# instead and only fail once it is genuinely not coming back.
for i in $(seq 1 24); do
    # -s without -S: a refused connection is the expected state while the
    # workers boot, not something to print eight times before succeeding.
    if curl -fs -o /dev/null http://localhost:8000/; then
        echo "healthy after $((i * 5))s"
        break
    fi
    if [ "$i" -eq 24 ]; then
        echo "STILL DOWN after 120s — check: journalctl -u foodbodyconnection -n 50"
        exit 1
    fi
    sleep 5
done
REMOTE_SCRIPT

echo "==> Done"

if [ "${1:-}" = "--logs" ]; then
    ./ssh.sh 'sudo journalctl -u foodbodyconnection -f'
fi
