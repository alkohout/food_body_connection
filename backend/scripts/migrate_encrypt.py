#!/usr/bin/env python3
"""
Encrypt existing plaintext data in the database.

Run once on the server after deploying the encryption changes:
    cd /opt/foodbodyconnection
    source .env  # or however you load env vars
    venv/bin/python scripts/migrate_encrypt.py

Safe to re-run: already-encrypted rows are detected and skipped.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from app.database import SessionLocal


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


def encrypt_column(db, fernet: Fernet, table: str, id_col: str, col: str) -> int:
    rows = db.execute(text(f"SELECT {id_col}, {col} FROM {table}")).fetchall()
    count = 0
    for row_id, value in rows:
        if value is None or is_encrypted(fernet, value):
            continue
        encrypted = fernet.encrypt(value.encode()).decode()
        db.execute(
            text(f"UPDATE {table} SET {col} = :enc WHERE {id_col} = :id"),
            {"enc": encrypted, "id": row_id},
        )
        count += 1
    db.commit()
    return count


def main():
    fernet = get_fernet()
    db = SessionLocal()

    try:
        jobs = [
            ("allergen",           "allergen_id",  "allergen_name"),
            ("symptom",            "symptom_id",   "symptom_name"),
            ("symptom",            "symptom_id",   "symptom_group"),
            ("medication",         "medication_id", "medication_name"),
            ("medication_regimen", "regimen_id",   "note"),
            ("user_document",      "document_id",  "filename"),
            ("user_document",      "document_id",  "description"),
            ("user_document",      "document_id",  "extracted_text"),
        ]

        for table, id_col, col in jobs:
            n = encrypt_column(db, fernet, table, id_col, col)
            print(f"  {table}.{col}: {n} rows encrypted")

        print("\nMigration complete.")

    except Exception as exc:
        db.rollback()
        print(f"\nError — rolled back: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
