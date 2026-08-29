"""Add training_profile.focus to an existing database.

SQLAlchemy's create_all builds missing tables but never alters existing ones,
so a column added to the model after the table exists has to be applied by
hand. Safe to run repeatedly: it checks first and does nothing if the column
is already there.

    cd /opt/foodbodyconnection && ./venv/bin/python scripts/add_training_focus.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from sqlalchemy import inspect, text          # noqa: E402
from app.database import engine               # noqa: E402


def main() -> int:
    insp = inspect(engine)
    if "training_profile" not in insp.get_table_names():
        print("training_profile does not exist yet; create_all will build it "
              "with the column already present. Nothing to do.")
        return 0

    columns = {c["name"] for c in insp.get_columns("training_profile")}
    if "focus" in columns:
        print("focus column already present. Nothing to do.")
        return 0

    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE training_profile "
            "ADD COLUMN focus VARCHAR(30) NOT NULL DEFAULT 'general'"
        ))
    print("Added training_profile.focus, defaulting existing rows to 'general'.")

    after = {c["name"] for c in inspect(engine).get_columns("training_profile")}
    if "focus" not in after:
        print("VERIFY FAILED: the column is still not there.")
        return 1
    print("Verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
