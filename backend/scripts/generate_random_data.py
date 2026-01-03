import os
import sys
import random
from datetime import datetime, timedelta, timezone

# Ensure project root is in sys.path so 'app' can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, project_root)

from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Unit, Symptom
from app.database import SessionLocal

def generate_random_allergen_data(
    user_email="random_user@example.com",
    days=90,
    entries_per_day=3,
    symptom_intensity_range=(0, 3)
):
    """
    Generate synthetic allergen/symptom data for a new user with no correlation
    between allergen consumption and symptom occurrence.
    """
    db = SessionLocal()
    try:
        # Create or get user
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            user = User(email=user_email)
            db.add(user)
            db.commit()
            db.refresh(user)

        # Get allergens, units, and symptoms
        all_allergens = db.query(Allergen).all()
        units = db.query(Unit).all()
        symptoms = db.query(Symptom).all()

        # Common symptoms
        common_symptoms = [s for s in symptoms if s.symptom_name.lower() in [
            "abdominal pain", "bloating", "diarrhea", "nausea", "vomiting",
            "fatigue", "headache", "brain fog"
        ]]

        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        for day_offset in range(days):
            date = start_date + timedelta(days=day_offset)
            n_entries = random.randint(max(1, entries_per_day - 1), entries_per_day + 1)

            for _ in range(n_entries):
                # Randomly pick an allergen and unit
                allergen = random.choice(all_allergens)
                unit = random.choice(units)
                quantity = random.randint(1, 5)

                # Log allergen consumption
                allergen_log = AllergenLog(
                    user_id=user.user_id,
                    date_time=date + timedelta(hours=random.randint(7, 21),
                                               minutes=random.randint(0, 59)),
                    allergen_id=allergen.allergen_id,
                    quantity=quantity,
                    unit_id=unit.unit_id
                )
                db.add(allergen_log)
                db.commit()
                db.refresh(allergen_log)

                # Random symptom BEFORE exposure (control window)
                if random.random() < 0.1:  # ~10% chance
                    symptom = random.choice(common_symptoms)
                    symptom_intensity = random.randint(*symptom_intensity_range)
                    symptom_log = SymptomLog(
                        user_id=user.user_id,
                        date_time=allergen_log.date_time - timedelta(
                            minutes=random.randint(30, 180)),
                        symptom_id=symptom.symptom_id,
                        symptom_intensity=symptom_intensity
                    )
                    db.add(symptom_log)
                    db.commit()
                    db.refresh(symptom_log)

                # Random symptom AFTER exposure (causal window)
                if random.random() < 0.1:  # ~10% chance, independent
                    symptom = random.choice(common_symptoms)
                    symptom_intensity = random.randint(*symptom_intensity_range)
                    symptom_log = SymptomLog(
                        user_id=user.user_id,
                        date_time=allergen_log.date_time + timedelta(
                            minutes=random.randint(30, 180)),
                        symptom_id=symptom.symptom_id,
                        symptom_intensity=symptom_intensity
                    )
                    db.add(symptom_log)
                    db.commit()
                    db.refresh(symptom_log)

        print(f"Random uncorrelated data generated for user {user_email}")

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.generate_random_allergen <days> <entries_per_day>")
        sys.exit(1)

    days = int(sys.argv[1])
    entries_per_day = int(sys.argv[2])

    generate_random_allergen_data(days=days, entries_per_day=entries_per_day)

