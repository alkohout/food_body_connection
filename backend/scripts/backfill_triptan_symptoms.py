"""
Backfill: for every existing Triptan allergen log for user 4,
create implied symptom logs at the same timestamp if they don't exist.

  Headache         intensity=2  (Bad — triptan was needed)
  Visual disturbance intensity=1  (Mild — usually present)

Run from the backend/ directory:
  python scripts/backfill_triptan_symptoms.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.table_class import Allergen, AllergenLog, Symptom, SymptomLog

USER_ID = 4

IMPLIED = [
    ("Headache", 2),
    ("Visual disturbance", 1),
]


def main():
    db = SessionLocal()
    try:
        # Locate triptan allergen for user 4 (name is encrypted — filter in Python)
        allergens = db.query(Allergen).filter(Allergen.user_id == USER_ID).all()
        triptan = next((a for a in allergens if a.allergen_name.lower() == "triptan"), None)
        if not triptan:
            print("ERROR: No 'Triptan' allergen found for user 4.")
            return

        logs = (
            db.query(AllergenLog)
            .filter(AllergenLog.user_id == USER_ID,
                    AllergenLog.allergen_id == triptan.allergen_id)
            .order_by(AllergenLog.date_time)
            .all()
        )
        print(f"Found {len(logs)} triptan log(s) for user {USER_ID}.")

        all_symptoms = db.query(Symptom).filter(Symptom.user_id == USER_ID).all()
        symptom_map = {s.symptom_name.lower(): s for s in all_symptoms}
        print(f"Available symptoms: {[s.symptom_name for s in all_symptoms]}")

        created = 0
        skipped = 0

        for log in logs:
            for sym_name, intensity in IMPLIED:
                sym = symptom_map.get(sym_name.lower())
                if not sym:
                    print(f"  WARNING: symptom '{sym_name}' not found — skipping.")
                    continue
                exists = (
                    db.query(SymptomLog)
                    .filter(
                        SymptomLog.user_id == USER_ID,
                        SymptomLog.symptom_id == sym.symptom_id,
                        SymptomLog.date_time == log.date_time,
                    )
                    .first()
                )
                if exists:
                    skipped += 1
                else:
                    db.add(SymptomLog(
                        user_id=USER_ID,
                        symptom_id=sym.symptom_id,
                        date_time=log.date_time,
                        symptom_intensity=intensity,
                    ))
                    created += 1

        db.commit()
        print(f"Done. Created {created} symptom log(s), skipped {skipped} already existing.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
