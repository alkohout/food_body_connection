#!/usr/bin/env bash
# Copy the server's backups onto this machine.
#
# The point of the exercise: a copy that is not in Neon's account and not in
# Oracle's either. Run it when you think of it — the server keeps thirty days,
# so a gap of a fortnight loses nothing.
#
# The dumps are useless without FERNET_KEY from the server's .env. Keep a copy
# of that key somewhere safe and somewhere else — not in this folder.
set -euo pipefail
HOST="${1:-ubuntu@159.13.61.101}"
DEST="${2:-$HOME/fbc-backups}"
mkdir -p "$DEST"
echo "==> pulling from $HOST"
sudo_rsync() { ssh "$HOST" "sudo tar -C /var/backups -cf - fbc" | tar -C "$DEST/.." -xf - ; }
ssh "$HOST" 'sudo ls -la /var/backups/fbc | tail -5'
sudo_rsync
echo "==> now in $DEST:"
ls -la "$DEST" | tail -5
