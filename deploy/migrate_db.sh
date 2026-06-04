#!/bin/bash
# =============================================================
# migrate_db.sh — dump from old server, restore on new server
#
# Usage:
#   Step 1 — run on your OLD EC2 instance:
#     ./migrate_db.sh dump
#
#   Step 2 — copy the file to your local machine:
#     scp ubuntu@OLD_EC2_IP:~/fbc_backup.sql ./fbc_backup.sql
#
#   Step 3 — copy to Oracle Cloud instance:
#     scp ./fbc_backup.sql ubuntu@ORACLE_IP:~/fbc_backup.sql
#
#   Step 4 — run on the NEW Oracle Cloud instance:
#     ./migrate_db.sh restore
# =============================================================

set -e

DB_NAME="foodbodyconnection"
DB_USER="foodbody"
BACKUP_FILE="$HOME/fbc_backup.sql"

case "$1" in

  dump)
    echo "Dumping database '${DB_NAME}' to ${BACKUP_FILE} ..."
    pg_dump -h localhost -U "${DB_USER}" -d "${DB_NAME}" \
        --no-owner --no-acl \
        -f "${BACKUP_FILE}"
    echo "Done. File: ${BACKUP_FILE}"
    echo ""
    echo "Copy to your local machine:"
    echo "  scp ubuntu@\$(curl -s ifconfig.me):${BACKUP_FILE} ./fbc_backup.sql"
    ;;

  restore)
    if [ ! -f "${BACKUP_FILE}" ]; then
        echo "Error: ${BACKUP_FILE} not found."
        echo "Copy fbc_backup.sql here first: scp ./fbc_backup.sql ubuntu@ORACLE_IP:~/"
        exit 1
    fi
    echo "Restoring database '${DB_NAME}' from ${BACKUP_FILE} ..."
    psql -h localhost -U "${DB_USER}" -d "${DB_NAME}" -f "${BACKUP_FILE}"
    echo "Done."
    ;;

  *)
    echo "Usage: $0 [dump|restore]"
    exit 1
    ;;

esac
