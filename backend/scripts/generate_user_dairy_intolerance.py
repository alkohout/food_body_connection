import os
import sys
import random
from datetime import datetime, timedelta, timezone

# Ensure project root is in sys.path so 'app' can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, project_root)

from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Unit, Symptom
from app.database import SessionLocal

def generate_dairy_intolerance_data(user_email="test@example.com", days=90, entries_per_day=3):
    db = SessionLocal()
    
    try:
        # Get user
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise ValueError(f"No user found with email {user_email}")

        # Get allergens and units
        dairy_allergens = db.query(Allergen).filter(Allergen.allergen_name.in_(["Milk", "Lactose", "Casein", "Whey"])).all()
        other_allergens = db.query(Allergen).filter(~Allergen.allergen_name.in_([a.allergen_name for a in dairy_allergens])).all()
        units = db.query(Unit).all()
        symptoms = db.query(Symptom).all()

        # Common symptoms triggered by dairy
        dairy_symptoms = [s for s in symptoms if s.symptom_name.lower() in [
            "abdominal pain", "bloating", "diarrhea", "nausea", "vomiting", 
            "fatigue", "headache", "brain fog"
        ]]

        # Generate diary entries
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        for day_offset in range(days):
            date = start_date + timedelta(days=day_offset)
            n_entries = random.randint(max(1, entries_per_day - 1), entries_per_day + 1)
            for _ in range(n_entries):
                if random.random() < 0.8:  
                    allergen = random.choice(dairy_allergens)
                    symptom_chance = 0.7
                else:
                    allergen = random.choice(other_allergens)
                    symptom_chance = 0.1

                unit = random.choice(units)
                quantity = random.randint(1, 5)
                
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

                if random.random() < symptom_chance:
                    symptom = random.choice(dairy_symptoms)
                    symptom_intensity = random.randint(0, 3) 
                    symptom_log = SymptomLog(
                        user_id=user.user_id,
                        date_time=allergen_log.date_time + timedelta(minutes=random.randint(30, 180)),
                        symptom_id=symptom.symptom_id,
                        symptom_intensity=symptom_intensity
                    )
                    db.add(symptom_log)
                    db.commit()
                    db.refresh(symptom_log)

        print(f"Synthetic dairy intolerance data generated for {days} days, {entries_per_day} entries per day.")
    
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.generate_user_dairy_intolerance <days> <entries_per_day>")
        sys.exit(1)
    
    days = int(sys.argv[1])
    entries_per_day = int(sys.argv[2])
    
    generate_dairy_intolerance_data(days=days, entries_per_day=entries_per_day)
