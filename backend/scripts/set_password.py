#!/usr/bin/env python3
"""
Set a user's login password directly.

For when the password-reset email is unavailable or you would rather not wait
for it. Uses the application's own hash_password(), so the stored hash is
exactly what verify_password() expects — including its 72-byte bcrypt
truncation, which a hand-rolled bcrypt call would get wrong.

The password is typed at a prompt, never passed as an argument: a command-line
argument is visible in `ps` output and lands in your shell history.

Run locally (against the same Neon database production uses):
    cd backend && .venv/bin/python scripts/set_password.py you@example.com

or on the server:
    sudo -u foodbody bash -c "cd /opt/foodbodyconnection && \
        venv/bin/python scripts/set_password.py you@example.com"
"""

import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.security import hash_password, verify_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.table_class import User  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <email>")
    email = sys.argv[1].strip().lower()

    db = SessionLocal()
    try:
        # Email is stored in plaintext, but compare case-insensitively so a
        # capitalised address still finds the account.
        user = next(
            (u for u in db.query(User).all()
             if (u.email or "").strip().lower() == email),
            None,
        )
        if user is None:
            existing = sorted((u.email or "") for u in db.query(User).all())
            raise SystemExit(
                f"No account for {email!r}.\nKnown accounts: {', '.join(existing)}"
            )

        pw = getpass.getpass(f"New password for {user.email}: ")
        if len(pw) < 8:
            raise SystemExit("Too short — use at least 8 characters.")
        if pw != getpass.getpass("Confirm: "):
            raise SystemExit("Passwords did not match — nothing changed.")

        user.password_hash = hash_password(pw)
        db.commit()

        # Prove the new hash actually validates before reporting success, so a
        # silent incompatibility can't lock the account instead of fixing it.
        db.refresh(user)
        if not verify_password(pw, user.password_hash):
            raise SystemExit(
                "Password was written but does not verify — do NOT log out; "
                "investigate before relying on it."
            )
        print(f"Password updated and verified for {user.email}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
