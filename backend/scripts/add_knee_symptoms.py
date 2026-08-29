"""Add a family of knee symptoms, named by side and location.

Knee pain is worth telling apart. Medial, lateral, anterior and posterior pain
have different likely causes and different implications for loading, and
"Knee pain" alone cannot distinguish a kneecap problem from a ligament one.
Swelling, stiffness and giving way are different kinds of problem again, not
degrees of pain.

Every name contains "knee", which is what the training back-off matches on, so
any of these logged at moderate or worse will ease that day's leg work.

Idempotent: existing names are left exactly as they are.

    ./venv/bin/python scripts/add_knee_symptoms.py <user_id>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.database import SessionLocal              # noqa: E402
from app.models.table_class import Symptom         # noqa: E402

GROUP = "Musculoskeletal"

# Anatomical terms with the plain-English sense in the name, so the list is
# usable without looking anything up.
LOCATIONS = [
    ("medial", "inner side"),
    ("lateral", "outer side"),
    ("anterior", "front, around the kneecap"),
    ("posterior", "back of the knee"),
]
OTHER = ["swelling", "stiffness", "giving way"]
SIDES = ["right", "left"]

# The original entry predates the convention and describes the medial pain.
RENAME = {"knee pain - right": "Knee pain - right medial"}


def main(user_id: int) -> int:
    db = SessionLocal()
    try:
        existing = {
            (s.symptom_name or "").strip().lower(): s
            for s in db.query(Symptom).filter(Symptom.user_id == user_id).all()
        }

        for old, new in RENAME.items():
            s = existing.get(old)
            if s and new.strip().lower() not in existing:
                s.symptom_name = new
                s.symptom_group = s.symptom_group or GROUP
                existing[new.strip().lower()] = s
                del existing[old]
                print(f"renamed  {old} -> {new}")

        wanted = [f"Knee pain - {side} {loc}" for side in SIDES for loc, _ in LOCATIONS]
        wanted += [f"Knee {what} - {side}" for side in SIDES for what in OTHER]

        added = 0
        for name in wanted:
            if name.strip().lower() in existing:
                continue
            db.add(Symptom(user_id=user_id, symptom_name=name, symptom_group=GROUP))
            existing[name.strip().lower()] = True
            added += 1
            print(f"added    {name}")
        db.commit()

        total = db.query(Symptom).filter(Symptom.user_id == user_id).count()
        print(f"\nAdded {added}. User {user_id} now tracks {total} symptoms.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: add_knee_symptoms.py <user_id>")
    raise SystemExit(main(int(sys.argv[1])))
