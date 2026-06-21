#!/usr/bin/env python3
"""
Encrypt existing plaintext data in the database.

Run once on the server after deploying the encryption changes:
    sudo -u foodbody bash -c "cd /opt/foodbodyconnection && /opt/foodbodyconnection/venv/bin/python /opt/foodbodyconnection/scripts/migrate_encrypt.py"

Safe to re-run: already-encrypted rows are detected and skipped.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DB_URL") or os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def get_fernet() -> Fernet:
    key = os.environ.get("FIELD_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("FIELD_ENCRYPTION_KEY not set in environment")
    return Fernet(key.encode())


def is_encrypted(fernet: Fernet, value: str) -> bool:
    try:
        fernet.decrypt(value.encode())
        return True
    except (InvalidToken, Exception):
        return False


def encrypt_column(fernet: Fernet, table: str, id_col: str, col: str) -> int:
    # Fetch all rows with a fresh connection
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT {id_col}, {col} FROM {table}")).fetchall()

    count = 0
    for row_id, value in rows:
        if value is None or is_encrypted(fernet, value):
            continue

        encrypted = fernet.encrypt(value.encode()).decode()

        # Each UPDATE gets its own connection — a dropped SSL connection
        # won't roll back previously committed rows
        for attempt in range(3):
            try:
                with engine.connect() as conn:
                    conn.execute(
                        text(f"UPDATE {table} SET {col} = :enc WHERE {id_col} = :id"),
                        {"enc": encrypted, "id": row_id},
                    )
                    conn.commit()
                count += 1
                break
            except Exception as exc:
                if attempt == 2:
                    raise
                print(f"    retrying {table}.{col} id={row_id} ({exc})")
                time.sleep(2)

    return count


def main():
    fernet = get_fernet()

    jobs = [
        ("allergen",           "allergen_id",   "allergen_name"),
        ("symptom",            "symptom_id",    "symptom_name"),
        ("symptom",            "symptom_id",    "symptom_group"),
        ("medication",         "medication_id", "medication_name"),
        ("medication_regimen", "regimen_id",    "note"),
        ("user_document",      "document_id",   "filename"),
        ("user_document",      "document_id",   "description"),
        ("user_document",      "document_id",   "extracted_text"),
        ("daily_checkin",      "checkin_id",    "mood"),
        ("daily_checkin",      "checkin_id",    "sleep"),
        ("daily_checkin",      "checkin_id",    "fatigue"),
        ("daily_checkin",      "checkin_id",    "gut"),
        ("daily_checkin",      "checkin_id",    "stress"),
        ("daily_checkin",      "checkin_id",    "headache"),
        ("daily_checkin",      "checkin_id",    "headache_overnight"),
        ("daily_checkin",      "checkin_id",    "brain_fog"),
        ("daily_checkin",      "checkin_id",    "tinnitus"),
        ("daily_checkin",      "checkin_id",    "visual_disturbance"),
        ("daily_checkin",      "checkin_id",    "training"),
        ("daily_checkin",      "checkin_id",    "virus"),
    ]

    for table, id_col, col in jobs:
        print(f"  {table}.{col}...", end=" ", flush=True)
        n = encrypt_column(fernet, table, id_col, col)
        print(f"{n} rows encrypted")

    print("\nMigration complete.")


if __name__ == "__main__":
    main()
