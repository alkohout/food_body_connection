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
    allergen_df["allergen_date_time"] = pd.to_datetime(allergen_df["date_time"], utc=True)
    symptom_df["symptom_date_time"] = pd.to_datetime(symptom_df["date_time"], utc=True)


    prediction =  1
    probalitiy = .85


    #prediction = model.predict(X)[0]
    #probability = model.predict_proba(X)[0].tolist()
    return {"prediction": int(prediction), "probability": probability}
