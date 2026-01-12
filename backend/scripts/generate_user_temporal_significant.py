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

def generate_significant_allergen_data(
    user_email="significant_stat@example.com",
    days=90,
    entries_per_day=3,
    significant_allergens=["Dairy", "Peanuts", "Shellfish"],
    symptom_intensity_range=(1, 3)
):
    """
    Generate synthetic data for a new user, with specified allergens having a statistically
    significant increase in symptoms after exposure.
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

        # Separate significant and neutral allergens
        significant_allergen_objs = [a for a in all_allergens if a.allergen_name in significant_allergens]
        neutral_allergens = [a for a in all_allergens if a.allergen_name not in significant_allergens]

        # Common symptoms (can be used for all significant allergens)
        common_symptoms = [s for s in symptoms if s.symptom_name.lower() in [
            "abdominal pain", "bloating", "diarrhea", "nausea", "vomiting",
            "fatigue", "headache", "brain fog"
        ]]

        # Generate diary entries
        seed = 42
        random.seed(seed)
        np.random.seed(seed)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        for day_offset in range(days):
            
            date = start_date + timedelta(days=day_offset)
            n_entries = random.randint(max(1, entries_per_day - 1), entries_per_day + 1)

            for _ in range(n_entries):
                if day_offset % 3 == 0:  # every 3rd day
                    allergen = random.choice(neutral_allergens)
                elif random.random() < 0.6:  # ~60% chance of significant allergen
                    allergen = random.choice(significant_allergen_objs)
                    symptom_chance_before = 0.1  # Before exposure
                    symptom_chance_after = 0.7   # After exposure → significant increase
                else:
                    allergen = random.choice(neutral_allergens)
                    symptom_chance_before = 0.05
                    symptom_chance_after = 0.1

                unit = random.choice(units)
                quantity = random.randint(1, 5)

                # Log allergen consumption
                allergen_log = AllergenLog(
                    user_id=user.user_id,
                    date_time=date + timedelta(hours=random.randint(7, 21), minutes=random.randint(0, 59)),
                    allergen_id=allergen.allergen_id,
                    quantity=quantity,
                    unit_id=unit.unit_id
                )
                db.add(allergen_log)
                db.commit()
                db.refresh(allergen_log)

                # Symptoms BEFORE exposure (control window: -24 to 0h)
                if random.random() < symptom_chance_before:
                    symptom = random.choice(common_symptoms)
                    symptom_intensity = random.randint(*symptom_intensity_range)
                    symptom_log = SymptomLog(
                        user_id=user.user_id,
                        date_time=allergen_log.date_time - timedelta(minutes=random.randint(30, 180)),
                        symptom_id=symptom.symptom_id,
                        symptom_intensity=symptom_intensity
                    )
                    db.add(symptom_log)
                    db.commit()
                    db.refresh(symptom_log)

                # Symptoms AFTER exposure (causal window: 0 to +6h)
                if random.random() < symptom_chance_after:
                    symptom = random.choice(common_symptoms)
                    symptom_intensity = random.randint(*symptom_intensity_range)
                    symptom_log = SymptomLog(
                        user_id=user.user_id,
                        date_time=allergen_log.date_time + timedelta(minutes=random.randint(30, 180)),
                        symptom_id=symptom.symptom_id,
                        symptom_intensity=symptom_intensity
                    )
                    db.add(symptom_log)
                    db.commit()
                    db.refresh(symptom_log)

        print(f"Synthetic data generated for user {user_email} with significant allergens: {significant_allergens}")
    
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.generate_significant_allergen <days> <entries_per_day>")
        sys.exit(1)
    
    days = int(sys.argv[1])
    entries_per_day = int(sys.argv[2])
    
    generate_significant_allergen_data(days=days, entries_per_day=entries_per_day)
