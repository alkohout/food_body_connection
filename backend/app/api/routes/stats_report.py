# app/api/routes/stats_report.py

from io import BytesIO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from fastapi.responses import StreamingResponse,JSONResponse
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Symptom
from io import BytesIO
from datetime import date, datetime, time, timezone, timedelta
from sqlalchemy import text, func, union_all, select, func
from typing import Optional
import logging
import traceback
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
import pandas as pd

logger = logging.getLogger("app/api/routes/stats_report.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/stats")
def analysis_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    allergen_df = get_all_allergen_events_df(db, current_user.user_id)
    symptom_df = get_all_symptom_events_df(db, current_user.user_id)

    # Combine and take min/max
    all_times = pd.DataFrame(allergen_df["date_time"] + symptom_df["date_time"])
    total_days = all_times["date_time"].dt.date.nunique()

    total_allergen_records = allergen_df["allergen_name"].count()
    total_symptom_records = symptom_df["symptom_name"].count()

    avg_allergens_per_day = allergen_df.groupby(allergen_df["date_time"].dt.date)["allergen_name"].count().mean()
    avg_symptoms_per_day = symptom_df.groupby(symptom_df["date_time"].dt.date)["symptom_name"].count().mean()

    logger.info(f" Averge allergens per day: {avg_allergens_per_day}, Average symptoms per day: {avg_symptoms_per_day}")

    return {
        "Total allergens logged": total_allergen_records,
        "Total symptoms logged": total_symptom_records,
        "Total days tracked": total_days,
        "Average allergens logged per day": round(avg_allergens_per_day, 2),
        "Average symptoms logged per day": round(avg_symptoms_per_day, 2),
    }

