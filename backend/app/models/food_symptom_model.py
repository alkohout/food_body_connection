# backend/app/models/food_symptom_model.py

from app.database import SessionLocal
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

from sqlalchemy.orm import Session
from app.models.table_class import AllergenLog, Allergen, Unit
from app.models.table_class import SymptomLog, Symptom
import pandas as pd

db = SessionLocal()

# Query allergen log with related allergen name and unit conversion
query = (
    db.query(
        AllergenLog.date_time.label("allergen_date_time"),
        Allergen.allergen_name.label("allergen_name"),
        AllergenLog.quantity.label("quantity"),
        Unit.unit_conversion.label("unit_conversion")
    )
    .join(Allergen, AllergenLog.allergen_id == Allergen.allergen_id)
    .outerjoin(Unit, AllergenLog.unit_id == Unit.unit_id)
)

allergen_df = pd.read_sql(query.statement, db.bind)

# Query symptom log with symptom name and intensity
query = (
    db.query(
        SymptomLog.date_time.label("symptom_date_time"),
        Symptom.symptom_name.label("symptom_name"),
        Symptom.symptom_group.label("symptom_group"),
        SymptomLog.symptom_intensity.label("intensity")
    )
    .join(Symptom, SymptomLog.symptom_id == Symptom.symptom_id)
)

symptom_df = pd.read_sql(query.statement, db.bind)
db.close()


# 2. Prepare features
# ------------------------

# Convert datetime columns to datetime type
allergen_df["allergen_date_time"] = pd.to_datetime(allergen_df["allergen_date_time"], utc=True)
symptom_df["symptom_date_time"] = pd.to_datetime(symptom_df["symptom_date_time"], utc=True)

# Compute volume for each allergen exposure
allergen_df["volume"] = allergen_df["quantity"] * allergen_df["unit_conversion"].fillna(1)

# Merge allergen exposures with symptoms within 24 hours
merged = allergen_df.merge(
    symptom_df,
    how="left",
    left_on=[],  # empty = cross join
    right_on=[],
    suffixes=("_allergen", "_symptom")
)

# Keep only symptoms within 24 hours of exposure
merged["time_diff"] = merged["symptom_date_time"] - merged["allergen_date_time"]
merged_24h = merged[(merged["time_diff"].dt.total_seconds() >= 0) &
                    (merged["time_diff"].dt.total_seconds() <= 24*3600)]

# Aggregate features per allergen exposure
features = merged_24h.groupby(
    ["allergen_date_time", "allergen_name", "quantity", "unit_conversion", "volume"]
).agg(
    max_intensity=("intensity", "max"),
    num_symptoms=("symptom_name", "count")
).reset_index()

# Fill NaN for exposures with no symptoms
features["max_intensity"] = features["max_intensity"].fillna(0)
features["num_symptoms"] = features["num_symptoms"].fillna(0)

# Boolean target: any symptom within 24h
features["y"] = features["num_symptoms"] > 0

# X: include volume, max_intensity, num_symptoms, and allergen_name as one-hot
X = pd.get_dummies(features[["volume", "max_intensity", "num_symptoms", "allergen_name"]],
                   columns=["allergen_name"], drop_first=True)
y = features["y"]

print(X.head())
print(f"Features shape: {X.shape}, Target shape: {y.shape}")

# ------------------------
# 4. Prepare features
# ------------------------
X = allergen_df.drop(columns=["allergen_date_time", "symptom_date_time", "symptom_name", "symptom_group"])

y = allergen_df["symptom_occurred"]

print(X.head())
print(f"Features shape: {X.shape}, Target shape: {y.shape}")

# ------------------------
# 4. Train model
# ------------------------
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X, y)

print("Model training complete!")

# ------------------------
# 5. Save trained model
# ------------------------
MODEL_PATH = "app/models/food_symptom_model.pkl"
joblib.dump(model, MODEL_PATH)
print(f"Model saved to {MODEL_PATH}")

