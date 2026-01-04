# backend/app/api/routes/predict.py

from fastapi import APIRouter
from pydantic import BaseModel
import joblib
import pandas as pd
from app.database import SessionLocal
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib
from fastapi import Depends
from app.database import get_db
from sqlalchemy.orm import Session
from app.models.table_class import Unit
from app.api.routes.auth import get_current_user
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from datetime import timedelta, datetime
import pandas as pd
import numpy as np
import logging


logger = logging.getLogger("app/api/routes/stats_report.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

# Load the model once when the app starts
MODEL_PATH = "app/models/food_symptom_model.pkl"
model = joblib.load(MODEL_PATH)

# Keep a list of feature columns used in training
FEATURE_COLUMNS = model.feature_names_in_  # this keeps all columns including one-hot

# ------------------------
# Prediction endpoint
# ------------------------
@router.post("/predict")
def predict(
    db: Session = Depends(get_db),   
    current_user = Depends(get_current_user)    
):

    allergen_df = get_all_allergen_events_df(db, current_user.user_id)
    symptom_df = get_all_symptom_events_df(db, current_user.user_id)

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

    prediction = model.predict(X)[0]
    probability = model.predict_proba(X)[0].tolist()
    return {"prediction": int(prediction), "probability": probability}
