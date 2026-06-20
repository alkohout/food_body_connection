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
import math

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
    try:
        logger.info("=== ENTERED /analysis/stats ===")

        user_id = current_user.user_id
        logger.info("user_id: %s", user_id)

        total_allergen_records = db.execute(text("""
            SELECT COUNT(*)
            FROM allergen_log
            WHERE user_id = :user_id
        """), {"user_id": user_id}).scalar() or 0

        total_symptom_records = db.execute(text("""
            SELECT COUNT(*)
            FROM symptom_log
            WHERE user_id = :user_id
        """), {"user_id": user_id}).scalar() or 0

        total_days = db.execute(text("""
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT DATE(date_time) AS d
                FROM allergen_log
                WHERE user_id = :user_id
                  AND date_time IS NOT NULL

                UNION

                SELECT DISTINCT DATE(date_time) AS d
                FROM symptom_log
                WHERE user_id = :user_id
                  AND date_time IS NOT NULL
            ) x
        """), {"user_id": user_id}).scalar() or 0

        avg_allergens_per_day = db.execute(text("""
            SELECT AVG(cnt)::float
            FROM (
                SELECT DATE(date_time) AS d, COUNT(*) AS cnt
                FROM allergen_log
                WHERE user_id = :user_id
                  AND date_time IS NOT NULL
                GROUP BY DATE(date_time)
            ) x
        """), {"user_id": user_id}).scalar()
        avg_allergens_per_day = round(float(avg_allergens_per_day or 0), 2)

        avg_symptoms_per_day = db.execute(text("""
            SELECT AVG(cnt)::float
            FROM (
                SELECT DATE(date_time) AS d, COUNT(*) AS cnt
                FROM symptom_log
                WHERE user_id = :user_id
                  AND date_time IS NOT NULL
                GROUP BY DATE(date_time)
            ) x
        """), {"user_id": user_id}).scalar()
        avg_symptoms_per_day = round(float(avg_symptoms_per_day or 0), 2)

        payload = {
            "Total allergens logged": int(total_allergen_records),
            "Total symptoms logged": int(total_symptom_records),
            "Total days tracked": int(total_days),
            "Average allergens logged per day": float(avg_allergens_per_day),
            "Average symptoms logged per day": float(avg_symptoms_per_day),
        }

        if user_id == 4:
            payload.update(get_special_user_stats(db, user_id))

        return payload

    except Exception as e:
        logger.exception("analysis_stats failed")
        return JSONResponse(
            status_code=500,
            content={"detail": f"analysis_stats failed: {str(e)}"}
        )

from datetime import timedelta, datetime

def get_special_user_stats(db: Session, user_id: int) -> dict:
    avg_length_historic = 31.0

    # Resolve allergen IDs in Python — names are encrypted, can't compare in SQL
    all_allergens = db.query(Allergen).filter(Allergen.user_id == user_id).all()
    triptan = next((a for a in all_allergens if a.allergen_name.lower() == "triptan"), None)
    period  = next((a for a in all_allergens if a.allergen_name.lower() == "period"),  None)

    # Triptan stats
    if triptan:
        count_last28 = db.execute(text("""
            SELECT COUNT(*) FROM allergen_log
            WHERE user_id = :uid AND allergen_id = :aid
              AND date_time IS NOT NULL
              AND date_time >= (NOW() AT TIME ZONE 'UTC') - INTERVAL '28 days'
        """), {"uid": user_id, "aid": triptan.allergen_id}).scalar() or 0

        monthly_rows = db.execute(text("""
            SELECT DATE_TRUNC('month', date_time) AS month_start,
                   COUNT(*) AS monthly_count
            FROM allergen_log
            WHERE user_id = :uid AND allergen_id = :aid
              AND date_time IS NOT NULL
              AND DATE_TRUNC('month', date_time) <> DATE_TRUNC('month', NOW() AT TIME ZONE 'UTC')
              AND DATE_TRUNC('month', date_time) <> DATE '2025-12-01'
            GROUP BY DATE_TRUNC('month', date_time)
            ORDER BY month_start
        """), {"uid": user_id, "aid": triptan.allergen_id}).fetchall()
    else:
        count_last28 = 0
        monthly_rows = []

    average_per_month = (
        sum(row.monthly_count for row in monthly_rows) / len(monthly_rows)
        if monthly_rows else 0.0
    )

    # Period/cycle stats
    if period:
        cycle_rows = db.execute(text("""
            SELECT DISTINCT DATE(date_time) AS cycle_day
            FROM allergen_log
            WHERE user_id = :uid AND allergen_id = :aid
              AND date_time IS NOT NULL
            ORDER BY cycle_day
        """), {"uid": user_id, "aid": period.allergen_id}).fetchall()
    else:
        cycle_rows = []

    cycle_dates = [row.cycle_day for row in cycle_rows if row.cycle_day is not None]

    average_cycle_length = avg_length_historic
    predicted_next_cycle_date = None

    if len(cycle_dates) >= 2:
        intervals = [
            (cycle_dates[i] - cycle_dates[i - 1]).days
            for i in range(1, len(cycle_dates))
        ]
        observed_avg = sum(intervals) / len(intervals)
        average_cycle_length = round((avg_length_historic + observed_avg) / 2, 1)

    if cycle_dates:
        last_cycle_start = cycle_dates[-1]
        predicted_next_cycle_date = last_cycle_start + timedelta(days=average_cycle_length)

    return {
        "Triptan usage in past month": int(count_last28),
        "Average Triptan usage per month": int(round(average_per_month)),
        "Average cycle length": float(average_cycle_length),
        "Predicted next cycle date": (
            predicted_next_cycle_date.strftime("%A, %d %B %Y")
            if predicted_next_cycle_date else None
        ),
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
    # Resolve IDs in Python — names are encrypted, can't compare in SQL
    allergen_obj = next(
        (a for a in db.query(Allergen).filter(Allergen.user_id == current_user.user_id).all()
         if a.allergen_name == allergen),
        None,
    )
    symptom_obj = next(
        (s for s in db.query(Symptom).filter(Symptom.user_id == current_user.user_id).all()
         if s.symptom_name == symptom),
        None,
    )

    allergen_q = (
        db.query(AllergenLog.date_time)
        .filter(AllergenLog.user_id == current_user.user_id)
        .filter(AllergenLog.allergen_id == (allergen_obj.allergen_id if allergen_obj else -1))
    )

    symptom_q = (
        db.query(SymptomLog.date_time)
        .filter(SymptomLog.user_id == current_user.user_id)
        .filter(SymptomLog.symptom_id == (symptom_obj.symptom_id if symptom_obj else -1))
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

@router.get("/stats-ping")
def stats_ping(current_user: User = Depends(get_current_user)):
    logger.info("stats-ping hit for user_id=%s", current_user.user_id)
    return {"ok": True, "user_id": int(current_user.user_id)}