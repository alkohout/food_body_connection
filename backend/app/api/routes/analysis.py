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
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df, get_allergen_events_df
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
    """
    Return overall logging statistics for the current user.

    Metrics include:
    - Total allergens logged
    - Total symptoms logged
    - Total unique days tracked
    - Average allergens logged per day
    - Average symptoms logged per day

    Returns
    -------
    dict
        Summary statistics for the user's data.
    """

    # --------------------------------------------------
    # Load allergen and symptom event data
    # --------------------------------------------------
    allergen_df = get_all_allergen_events_df(db, current_user.user_id)
    symptom_df = get_all_symptom_events_df(db, current_user.user_id)

    # If absolutely no data exists
    if allergen_df.empty and symptom_df.empty:
        return {
            "Total allergens logged": 0,
            "Total symptoms logged": 0,
            "Total days tracked": 0,
            "Average allergens logged per day": 0.0,
            "Average symptoms logged per day": 0.0,
        }

    # --------------------------------------------------
    # Safe total record counts
    # --------------------------------------------------
    total_allergen_records = len(allergen_df) if not allergen_df.empty else 0
    total_symptom_records = len(symptom_df) if not symptom_df.empty else 0

    # --------------------------------------------------
    # Helper: compute safe daily average
    # --------------------------------------------------
    def safe_avg(df, column):
        if df.empty or column not in df.columns:
            return 0.0

        if "date_time" not in df.columns:
            return 0.0

        df = df.copy()
        df["date_time"] = pd.to_datetime(df["date_time"], errors="coerce")
        df = df.dropna(subset=["date_time"])

        if df.empty:
            return 0.0

        daily = df.groupby(df["date_time"].dt.date)[column].count()
        return float(round(daily.mean(), 2)) if not daily.empty else 0.0

    avg_allergens_per_day = safe_avg(allergen_df, "allergen_name")
    avg_symptoms_per_day = safe_avg(symptom_df, "symptom_name")

    # --------------------------------------------------
    # Compute total unique days tracked
    # --------------------------------------------------
    def get_days(df):
        if df.empty or "date_time" not in df.columns:
            return set()
        df = df.copy()
        df["date_time"] = pd.to_datetime(df["date_time"], errors="coerce")
        return set(df["date_time"].dropna().dt.date)

    total_days = len(get_days(allergen_df) | get_days(symptom_df))

    if (current_user.user_id == 4) : # Special case for myself to count triptan usage

        # Calculate cutoff date (28 days ago from today)
        cutoff_date = pd.Timestamp.utcnow() - pd.Timedelta(days=28)
        # Filter and count
        count_last28 = ((allergen_df['allergen_name'] == 'Triptan') & (allergen_df['date_time'] >= cutoff_date)).sum()

        # Filter to Triptan only
        triptan_df = allergen_df[allergen_df['allergen_name'] == 'Triptan']
        # Count per month
        monthly_counts = (
            triptan_df
            .set_index('date_time')
            .resample('M')
            .size()
        )
        # Remove current month
        current_month = pd.Timestamp.utcnow().to_period('M')
        monthly_counts = monthly_counts[
            monthly_counts.index.to_period('M') != current_month
        ]

        # Remove December 2025 - only half recorded and would skew average
        monthly_counts = monthly_counts[
            monthly_counts.index.to_period('M') != pd.Period('2025-12')
        ]
        # Average per month
        average_per_month = monthly_counts.mean()

        # --------------------------------------------------
        # Cycle tracking
        # --------------------------------------------------
        avg_length_historic = 31.0

        cycle_df = get_allergen_events_df(
            db=db,
            user_id=current_user.user_id,
            allergen_name="Period"
        )

        cycle_dates = []
        if not cycle_df.empty and "date_time" in cycle_df.columns:
            cycle_df = cycle_df.copy()
            cycle_df["date_time"] = pd.to_datetime(cycle_df["date_time"], errors="coerce")
            cycle_dates = sorted(cycle_df["date_time"].dropna().tolist())

        average_cycle_length = avg_length_historic
        predicted_next_cycle_date = None
        last_cycle_start = None

        if cycle_dates:
            last_cycle_start = cycle_dates[-1]

        if len(cycle_dates) >= 2:
            intervals = [
                (cycle_dates[i] - cycle_dates[i - 1]).days
                for i in range(1, len(cycle_dates))
            ]

            observed_avg = sum(intervals) / len(intervals)
            average_cycle_length = round((avg_length_historic + observed_avg) / 2, 1)

        if last_cycle_start is not None:
            predicted_next_cycle_date = last_cycle_start + timedelta(days=average_cycle_length)

        return {
            "Total allergens logged": int(total_allergen_records),
            "Total symptoms logged": int(total_symptom_records),
            "Total days tracked": int(total_days),
            "Average allergens logged per day": avg_allergens_per_day,
            "Average symptoms logged per day": avg_symptoms_per_day,
            "Triptan usage in past month": int(count_last28), 
            "Average Triptan usage per month": round(average_per_month),
            "Average cycle length": average_cycle_length,
            "Predicted next cycle date": predicted_next_cycle_date.isoformat() if predicted_next_cycle_date else None,
        }

    return {
        "Total allergens logged": int(total_allergen_records),
        "Total symptoms logged": int(total_symptom_records),
        "Total days tracked": int(total_days),
        "Average allergens logged per day": avg_allergens_per_day,
        "Average symptoms logged per day": avg_symptoms_per_day,
    }

@router.get("/plot-data")
def plot_data(
    allergen: Optional[str] = None,
    symptom: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return correlated allergen–symptom time series data
    for plotting on the frontend.

    The endpoint:
    1. Filters allergen and symptom logs by date range.
    2. Counts symptoms occurring within 24h after allergen exposure.
    3. Aggregates counts per day.
    """

    # --------------------------------------------------
    # Apply defaults if not provided
    # --------------------------------------------------
    allergen = allergen or DEFAULT_ALLERGEN
    symptom = symptom or DEFAULT_SYMPTOM

    # Parse start_date safely
    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else date(2025, 1, 1)
    except ValueError:
        start_date = date(2025, 1, 1)

    # Parse end_date safely
    try:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today()
    except ValueError:
        end_date = date.today()

    start_date = start_date or DEFAULT_START_DATE
    end_date = end_date or DEFAULT_END_DATE

    # --------------------------------------------------
    # Query allergen events
    # --------------------------------------------------
    allergen_q = (
        db.query(AllergenLog.date_time)
        .join(Allergen)
        .filter(AllergenLog.user_id == current_user.user_id)
        .filter(Allergen.user_id == current_user.user_id)
        .filter(Allergen.allergen_name == allergen)
    )

    # --------------------------------------------------
    # Query symptom events
    # --------------------------------------------------
    symptom_q = (
        db.query(SymptomLog.date_time)
        .join(Symptom)
        .filter(SymptomLog.user_id == current_user.user_id)
        .filter(Symptom.user_id == current_user.user_id)
        .filter(Symptom.symptom_name == symptom)
    )

    # Apply date filters
    if start_date:
        allergen_q = allergen_q.filter(AllergenLog.date_time >= start_date)
        symptom_q = symptom_q.filter(SymptomLog.date_time >= start_date)

    if end_date:
        allergen_q = allergen_q.filter(AllergenLog.date_time <= end_date)
        symptom_q = symptom_q.filter(SymptomLog.date_time <= end_date)

    allergen_times = [t for (t,) in allergen_q.all()]
    symptom_times = [t for (t,) in symptom_q.all()]

    # --------------------------------------------------
    # Correlate: symptoms within 24h after exposure
    # --------------------------------------------------
    counts = {}

    for a_time in allergen_times:
        window_end = a_time + timedelta(hours=24)

        daily_count = sum(
            1 for s_time in symptom_times
            if a_time <= s_time <= window_end
        )

        day = a_time.date()
        counts[day] = counts.get(day, 0) + daily_count

    # Provide fallback if no data
    if not counts:
        counts = {start_date: 0, end_date: 0}

    dates = [d.isoformat() for d in sorted(counts.keys())]
    counts_list = [counts[d] for d in sorted(counts.keys())]

    return JSONResponse(
        content={
            "dates": dates,
            "symptoms": {symptom: counts_list},
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
    """
    Return summary statistics within a given date range.

    Metrics:
    - Total exposures
    - Total symptoms
    - Total distinct tracked days
    - Average symptoms per tracked day
    """

    # --------------------------------------------------
    # Default date range if none provided
    # --------------------------------------------------
    if not start_date:
        start_date = date(2000, 1, 1)
    if not end_date:
        end_date = date.today()

    start_utc = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_utc = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

    # --------------------------------------------------
    # Count total exposures
    # --------------------------------------------------
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

    # --------------------------------------------------
    # Count total symptoms
    # --------------------------------------------------
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

    # --------------------------------------------------
    # Count distinct tracked days (based on exposure logs)
    # --------------------------------------------------
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

    # Compute average symptoms per tracked day
    avg_symptoms_per_day = (
        total_symptoms / days_tracked if days_tracked else 0
    )

    return {
        "total_exposures": total_exposures,
        "total_symptoms": total_symptoms,
        "days_tracked": days_tracked,
        "avg_symptoms_per_day": round(avg_symptoms_per_day, 2)
    }