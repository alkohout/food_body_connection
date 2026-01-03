import os
import sys
import random
from datetime import datetime, timedelta, timezone
import numpy as np

# Ensure project root is in sys.path so 'app' can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, project_root)

from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Unit, Symptom
from app.database import SessionLocal

def generate_dairy_intolerance_data(user_email="test@example.com", days=90, entries_per_day=3):
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise ValueError(f"No user found with email {user_email}")

        dairy = db.query(Allergen).filter(Allergen.allergen_name == "Dairy").one()
        other_allergens = db.query(Allergen).filter(Allergen.allergen_name != "Dairy").all()
        units = db.query(Unit).all()
        symptoms = db.query(Symptom).all()

        dairy_symptoms = [
            s for s in symptoms
            if s.symptom_name.lower() in {
                "abdominal pain", "bloating", "diarrhea",
                "nausea", "fatigue", "headache", "brain fog"
            }
        ]

        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        # --- Habitual diet probabilities (heavy-tailed) ---
        base_diet = (
            [dairy] * 4 +
            random.sample(other_allergens, min(6, len(other_allergens)))
        )

        sensitivity = 0.0          # latent intolerance state
        decay = 0.85               # recovery per exposure
        dairy_boost = 1.2          # how much dairy raises sensitivity

        for day_offset in range(days):
            day = start_date + timedelta(days=day_offset)

            for _ in range(entries_per_day):
                exposure_time = day + timedelta(
                    hours=random.randint(7, 21),
                    minutes=random.randint(0, 59),
                )

                allergen = random.choice(base_diet)
                unit = random.choice(units)
                quantity = random.randint(1, 3)

                allergen_log = AllergenLog(
                    user_id=user.user_id,
                    date_time=exposure_time,
                    allergen_id=allergen.allergen_id,
                    quantity=quantity,
                    unit_id=unit.unit_id,
                )
                db.add(allergen_log)
                db.commit()
                db.refresh(allergen_log)

                # --- Update latent sensitivity ---
                if allergen.allergen_id == dairy.allergen_id:
                    sensitivity += dairy_boost * quantity
                else:
                    sensitivity *= decay

                # --- Symptom generation ---
                expected_symptoms = max(0, sensitivity - 1.0)

                n_symptoms = min(
                    random.poisson(lam=expected_symptoms)
                    if expected_symptoms > 0 else 0,
                    3
                )

                for _ in range(n_symptoms):
                    symptom = random.choice(dairy_symptoms)
                    symptom_log = SymptomLog(
                        user_id=user.user_id,
                        date_time=exposure_time + timedelta(
                            minutes=random.randint(30, 240)
                        ),
                        symptom_id=symptom.symptom_id,
                        symptom_intensity=random.randint(1, 3),
                    )
                    db.add(symptom_log)

                db.commit()

        print("Realistic dairy intolerance data generated.")

    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.generate_user_dairy_intolerance <days> <entries_per_day>")
        sys.exit(1)

    days = int(sys.argv[1])
    entries_per_day = int(sys.argv[2])

    generate_dairy_intolerance_data(days=days, entries_per_day=entries_per_day)