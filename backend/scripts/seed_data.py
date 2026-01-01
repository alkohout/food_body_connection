import os
import sys

# Ensure project root is in sys.path so 'app' can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, project_root)

from datetime import datetime, timezone
from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Unit, Symptom
from app.core.security import hash_password
from app.database import Base, SessionLocal

def main():

    # Create a session
    db = SessionLocal()

    try:
        existing_user = db.query(User).filter(User.email == "test@example.com").first()
        if not existing_user:
            test_user = User(
                email="test@example.com",
                password_hash=hash_password("password123")
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
        else:
            test_user = existing_user

        # Create symptoms
        symptoms = [
            # Gastrointestinal
            "Abdominal Pain",
            "Bloating",
            "Constipation",
            "Diarrhea",
            "Gas",
            "Heartburn",
            "Indigestion",
            "Nausea",
            "Vomiting",
            "Loss of Appetite",
            "Increased Appetite",

            # Neurological
            "Headache",
            "Migraine",
            "Dizziness",
            "Vertigo",
            "Brain Fog",
            "Light Sensitivity",
            "Sound Sensitivity",
            "Visual Disturbances",
            "Tingling",
            "Numbness",

            # Skin
            "Rash",
            "Hives",
            "Itching",
            "Eczema",
            "Acne",
            "Flushing",
            "Swelling",
            "Dry Skin",

            # Respiratory
            "Cough",
            "Sneezing",
            "Runny Nose",
            "Nasal Congestion",
            "Shortness of Breath",
            "Chest Tightness",
            "Wheezing",

            # Cardiovascular / Autonomic
            "Palpitations",
            "Rapid Heart Rate",
            "Low Blood Pressure",
            "High Blood Pressure",
            "Cold Hands or Feet",

            # Systemic / Inflammatory
            "Fatigue",
            "Fever",
            "Chills",
            "Body Aches",
            "Joint Pain",
            "Muscle Pain",
            "Weakness",

            # Sleep
            "Difficulty Falling Asleep",
            "Difficulty Staying Asleep",
            "Unrefreshing Sleep",
            "Night Sweats",

            # Mood / Cognitive
            "Anxiety",
            "Depression",
            "Irritability",
            "Low Mood",
            "Poor Concentration",

            # Mentstrual
            "Cramps",
            "Cycle" ,
        ]

        symptom_objects = [Symptom(symptom_name=s) for s in symptoms]
        db.add_all(symptom_objects)
        db.commit()
        for s in symptom_objects:
            db.refresh(s)

        # Create allergens
        allergens = [

            # Major food allergens (global)
            "Dairy",
            "Eggs",
            "Peanuts",
            "Tree Nuts",
            "Soy",
            "Gluten",
            "Fish",
            "Shellfish",
            "Sesame",
            "Mustard",
            "Celery",
            "Lupin",
            "Sulphites",

            # Vegetables / legumes
            "Tomatoes",
            "Potatoes",
            "Nightshades",
            "Legumes",
            "Chickpeas",
            "Lentils",

            # Additives
            "MSG",
            "Artificial Sweeteners",
            "Aspartame",
            "Food Colorings",
            "Preservatives",

            # Beverages & stimulants
            "Caffeine",
            "Alcohol",
            "Red Wine",
            "Beer",

            # Non-food triggers (very useful for migraine/allergy overlap)
            "Pollen",
            "Dust Mites",
            "Mold",
            "Pet Dander",
            "Fragrances",
            "Cleaning Products",
            "Smoke",
            "Perfume"
        ]

        allergen_objects = [Allergen(allergen_name=a) for a in allergens]
        db.add_all(allergen_objects)
        db.commit()
        for a in allergen_objects:
            db.refresh(a)


        # Create base units
        units = ["grams", 
                 "ml", 
                 "Liters", 
                 "tablespoons", 
                 "teaspoons", 
                 "cups"
        ]
        unit_objects = [Unit(unit_name=u) for u in units]
        db.add_all(unit_objects)
        db.commit()
        for u in unit_objects:
            db.refresh(u)

        # Create some allergen diary entries
        entry = AllergenLog(
            user_id = test_user.user_id,
            date_time = datetime.now(timezone.utc),
            allergen_id = 1,
            quantity = 2,
            unit_id = 1
        )
        db.add(entry)

        # Create some symptom diary entries
        entry = SymptomLog(
            user_id = test_user.user_id,
            date_time = datetime.now(timezone.utc),
            symptom_id = 1, 
            symptom_intensity = 3
        )
        db.add(entry)

        # Commit all diary entries
        db.commit()

        print("Seed data created successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    main()

