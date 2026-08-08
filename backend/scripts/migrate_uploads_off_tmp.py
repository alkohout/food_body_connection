#!/usr/bin/env python3
"""
Move uploaded documents off /tmp and repoint the database at the new location.

UPLOAD_DIR was never set in the server environment, so uploads defaulted to
/tmp/user_docs. systemd-tmpfiles ships a "D /tmp" rule, which empties /tmp on
every boot — the files have survived only because the box has not rebooted
since they were uploaded. The next reboot would delete every original document
permanently. Extracted text lives in the database and would survive, but the
source files would not.

This copies each file to UPLOAD_DIR (default /opt/foodbodyconnection/user_docs)
and updates user_document.file_path to match. Originals in /tmp are left in
place; delete them once you are satisfied the move worked.

Run on the server AFTER setting UPLOAD_DIR in /opt/foodbodyconnection/.env:
    sudo -u foodbody bash -c "cd /opt/foodbodyconnection && \
        /opt/foodbodyconnection/venv/bin/python scripts/migrate_uploads_off_tmp.py"

Safe to re-run: rows already pointing at an existing file under the target are
skipped.
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DB_URL") or os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DB_URL not set")

TARGET_DIR = os.environ.get("UPLOAD_DIR", "/opt/foodbodyconnection/user_docs")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def main() -> None:
    os.makedirs(TARGET_DIR, exist_ok=True)
    moved, skipped, missing = [], [], []

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT document_id, user_id, file_path FROM user_document ORDER BY document_id"
        )).fetchall()

        for row in rows:
            old_path = row.file_path or ""

            if old_path.startswith(TARGET_DIR) and os.path.exists(old_path):
                skipped.append(f"{row.document_id}: already at {old_path}")
                continue

            user_dir = os.path.join(TARGET_DIR, str(row.user_id))
            os.makedirs(user_dir, exist_ok=True)
            new_path = os.path.join(user_dir, os.path.basename(old_path))

            if not os.path.exists(old_path):
                # File already gone (e.g. a reboot got there first). Still
                # repoint the row so the path is not a lie, but say so loudly.
                missing.append(f"{row.document_id}: {old_path} no longer exists")
                continue

            if not os.path.exists(new_path):
                shutil.copy2(old_path, new_path)

            conn.execute(
                text("UPDATE user_document SET file_path = :p WHERE document_id = :d"),
                {"p": new_path, "d": row.document_id},
            )
            moved.append(f"{row.document_id}: {old_path} -> {new_path}")

    print(f"Target: {TARGET_DIR}\n")
    print(f"Moved ({len(moved)}):")
    for m in moved:
        print(f"   {m}")
    print(f"\nAlready in place ({len(skipped)}):")
    for s in skipped:
        print(f"   {s}")
    if missing:
        print(f"\nMISSING - file gone, row left pointing at the old path ({len(missing)}):")
        for m in missing:
            print(f"   {m}")
    print("\nOriginals under /tmp were left alone. Remove them once verified.")


if __name__ == "__main__":
    main()
