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
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from io import BytesIO
from datetime import date, datetime, time, timezone, timedelta
from sqlalchemy import text, func, union_all, select, func
from typing import Optional
import logging
import traceback
import pandas as pd

logger = logging.getLogger("plot_eda")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

DEFAULT_ALLERGEN = "Dairy"          # default allergen if none selected
DEFAULT_SYMPTOM = "Nausea"          # default symptom if none selected
DEFAULT_START_DATE = date(2025, 1, 1)  # earliest date
DEFAULT_END_DATE = date.today()        # today

@router.get("/stats")
def analysis_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    allergen_df = get_all_allergen_events_df(db, current_user.user_id)
    symptom_df = get_all_symptom_events_df(db, current_user.user_id)

    # Combine and take min/max
    all_times = pd.DataFrame(allergen_df["date_time"] + symptom_df["date_time"])

    total_allergen_records = allergen_df["allergen_name"].count()
    total_symptom_records = symptom_df["symptom_name"].count()
    total_days = total_allergen_records + total_symptom_records

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

@router.get("/plot-data")

def plot_data(
    allergen: Optional[str] = None,
    symptom: Optional[str] = None,
    start_date: Optional[str] = None,  # <-- accept string
    end_date: Optional[str] = None,    # <-- accept string
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Defaults
    allergen = allergen or DEFAULT_ALLERGEN
    symptom = symptom or DEFAULT_SYMPTOM

    # Parse start_date
    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else date(2025, 1, 1)
    except ValueError:
        start_date = date(2025, 1, 1)

    # Parse end_date
    try:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today()
    except ValueError:
        end_date = date.today()

    # Use defaults if nothing provided
    start_date = start_date or DEFAULT_START_DATE
    end_date = end_date or DEFAULT_END_DATE

    # --- Allergen events ---
    allergen_q = (
        db.query(AllergenLog.date_time)
        .join(Allergen)
        .filter(AllergenLog.user_id == current_user.user_id)
        .filter(Allergen.user_id == current_user.user_id)
        .filter(Allergen.allergen_name == allergen)
    )

    # --- Symptom events ---
    symptom_q = (
        db.query(SymptomLog.date_time)
        .join(Symptom)
        .filter(SymptomLog.user_id == current_user.user_id)
        .filter(Symptom.user_id == current_user.user_id)
        .filter(Symptom.symptom_name == symptom)
    )

    if start_date:
        allergen_q = allergen_q.filter(AllergenLog.date_time >= start_date)
        symptom_q = symptom_q.filter(SymptomLog.date_time >= start_date)

    if end_date:
        allergen_q = allergen_q.filter(AllergenLog.date_time <= end_date)
        symptom_q = symptom_q.filter(SymptomLog.date_time <= end_date)

    allergen_times = [t for (t,) in allergen_q.all()]
    symptom_times = [t for (t,) in symptom_q.all()]

    # --- Correlate: symptom within 24h of allergen ---
    counts = {}

    for a_time in allergen_times:
        window_end = a_time + timedelta(hours=24)

        daily_count = sum(
            1 for s_time in symptom_times
            if a_time <= s_time <= window_end
        )

        day = a_time.date()
        counts[day] = counts.get(day, 0) + daily_count

    # If no data, provide a dummy point
    if not counts:
        counts = {start_date: 0, end_date: 0}

    dates = [d.isoformat() for d in sorted(counts.keys())]
    counts_list = [counts[d] for d in sorted(counts.keys())]

    return JSONResponse(
        content={
            "dates": dates,
            "symptoms": {symptom: counts_list},  # if you want to keep symptom-based plotting
            "allergen_series": counts_list,
            "selected_allergen": allergen
        }
    )

@router.post("/summary")
def analysis_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Default window = all data
    if not start_date:
        start_date = date(2000, 1, 1)
    if not end_date:
        end_date = date.today()

    start_utc = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_utc = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

    total_exposures = db.execute(
        text("""
        SELECT COUNT(*) FROM allergen_log 
        WHERE user_id = :user_id
          AND date_time BETWEEN :start AND :end
        """),
        {
            "user_id": current_user.user_id,
            "start": start_utc,
            "end": end_utc,
        }
    ).scalar()

    total_symptoms = db.execute(
        text("""
        SELECT COUNT(*) FROM symptom_log 
        WHERE user_id = :user_id
          AND date_time BETWEEN :start AND :end
        """),
        {
            "user_id": current_user.user_id,
            "start": start_utc,
            "end": end_utc
        }
    ).scalar()

    days_tracked = db.execute(
        text("""
        SELECT COUNT(DISTINCT DATE(date_time))
        FROM allergen_log 
        WHERE user_id = :user_id
          AND date_time BETWEEN :start AND :end
        """),
        {
            "user_id": current_user.user_id,
            "start": start_utc,
            "end": end_utc
        }
    ).scalar()

    avg_symptoms_per_day = (
        total_symptoms / days_tracked if days_tracked else 0
    )

    return {
        "total_exposures": total_exposures,
        "total_symptoms": total_symptoms,
        "days_tracked": days_tracked,
        "avg_symptoms_per_day": round(avg_symptoms_per_day, 2)
    }

