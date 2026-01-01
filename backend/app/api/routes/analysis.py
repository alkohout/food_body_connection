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
from app.schemas import AnalysisSummaryOut, AnalysisScope
from io import BytesIO
from datetime import date, datetime, time, timezone, timedelta
from sqlalchemy import text
from typing import Optional

router = APIRouter(prefix="/analysis", tags=["analysis"])

DEFAULT_ALLERGEN = "Dairy"          # default allergen if none selected
DEFAULT_SYMPTOM = "Nausea"          # default symptom if none selected
DEFAULT_START_DATE = date(2025, 1, 1)  # earliest date
DEFAULT_END_DATE = date.today()        # today

@router.get("/plot")
def plot_analysis(
    allergen: str = "Dairy",
    symptom: str = "Nausea",
    start_date: str = "2025-01-01",
    end_date: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Convert dates
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()

    # Query allergen and symptom events
    allergen_times = [
        t for (t,) in db.query(AllergenLog.date_time)
                       .filter(AllergenLog.user_id == current_user.user_id)
                       .filter(AllergenLog.date_time >= start_dt)
                       .filter(AllergenLog.date_time <= end_dt)
                       .all()
    ]

    symptom_times = [
        t for (t,) in db.query(SymptomLog.date_time)
                       .filter(SymptomLog.user_id == current_user.user_id)
                       .filter(SymptomLog.date_time >= start_dt)
                       .filter(SymptomLog.date_time <= end_dt)
                       .all()
    ]

    # Aggregate symptoms within 24h of allergen
    counts = {}
    for a_time in allergen_times:
        window_end = a_time + timedelta(hours=24)
        daily_count = sum(1 for s_time in symptom_times if a_time <= s_time <= window_end)
        day = a_time.date()
        counts[day] = counts.get(day, 0) + daily_count

    if not counts:
        counts = {start_dt.date(): 0, end_dt.date(): 0}

    # --- Plot with seaborn / matplotlib ---
    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 5))

    dates = list(sorted(counts.keys()))
    values = [counts[d] for d in dates]

    sns.lineplot(x=dates, y=values, marker="o", ax=ax)
    ax.set_title(f"Symptoms within 24h of {allergen}")
    ax.set_xlabel("Date")
    ax.set_ylabel(f"Number of {symptom} events")
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save to BytesIO
    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")

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
        .filter(Allergen.allergen_name == allergen)
    )

    # --- Symptom events ---
    symptom_q = (
        db.query(SymptomLog.date_time)
        .join(Symptom)
        .filter(SymptomLog.user_id == current_user.user_id)
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

