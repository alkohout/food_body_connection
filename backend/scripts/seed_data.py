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
        existing_user = db.query(User).filter(User.email == "random_user@example.com").first()
        if not existing_user:
            test_user = User(
                email="random_user@example.com",
                password_hash=hash_password("password123")
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
        else:
            test_user = existing_user
    finally:
        db.close()

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.email == "significant_stat@example.com").first()
        if not existing_user:
            test_user = User(
                email="significant_stat@example.com",
                password_hash=hash_password("password123")
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
        else:
            test_user = existing_user
    finally:
        db.close()

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
        # Symptom groups mapping
        SYMPTOM_GROUPS = {
            "Gastrointestinal": [
                "Abdominal Pain","Bloating","Constipation","Diarrhea","Gas","Heartburn",
                "Indigestion","Nausea","Vomiting","Loss of Appetite","Increased Appetite"
            ],
            "Neurological": [
                "Headache","Migraine","Dizziness","Vertigo","Brain Fog","Light Sensitivity",
                "Sound Sensitivity","Visual Disturbances","Tingling","Numbness"
            ],
            "Skin": ["Rash","Hives","Itching","Eczema","Acne","Flushing","Swelling","Dry Skin"],
            "Respiratory": ["Cough","Sneezing","Runny Nose","Nasal Congestion","Shortness of Breath","Chest Tightness","Wheezing"],
            "Cardiovascular": ["Palpitations","Rapid Heart Rate","Low Blood Pressure","High Blood Pressure","Cold Hands or Feet"],
            "Systemic": ["Fatigue","Fever","Chills","Body Aches","Joint Pain","Muscle Pain","Weakness"],
            "Sleep": ["Difficulty Falling Asleep","Difficulty Staying Asleep","Unrefreshing Sleep","Night Sweats"],
            "Mood/Cognitive": ["Anxiety","Depression","Irritability","Low Mood","Poor Concentration"],
            "Menstrual": ["Cramps","Cycle"]
        }

        # Create symptom objects with groups
        symptom_objects = []
        for group_name, symptoms in SYMPTOM_GROUPS.items():
            for s in symptoms:
                symptom_objects.append(Symptom(symptom_name=s, symptom_group=group_name))

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

        # Define your units and conversions
        units = ["grams", "ml", "liters", "tablespoons", "teaspoons", "cups"]
        conversions = [1, 1, 1000, 15, 5, 240]  # convert to base unit (grams or ml)

        # Create Unit objects with both name and conversion
        unit_objects = [Unit(unit_name=u, unit_conversion=c) for u, c in zip(units, conversions)]

        db.add_all(unit_objects)
        db.commit()
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

