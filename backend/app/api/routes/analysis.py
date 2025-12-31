from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.table_class import User, AllergenLog, SymptomLog
from app.schemas import AnalysisSummaryOut, AnalysisScope
from datetime import date, datetime, time, timezone
from sqlalchemy import text
from typing import Optional

from fastapi.responses import JSONResponse

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/plot-data")
def plot_data(
    allergen: Optional[str] = None,
    symptom: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(AnalysisScope.start_date, AnalysisScope.end_date, SymptomLog.date_time, SymptomLog.symptom_id)

    if allergen:
        query = query.filter(AllergenLog.allergen_id == allergen)
    if symptom:
        query = query.filter(SymptomLog.symptom_id == symptom)
    if start_date:
        query = query.filter(AnalysisScope.start_date >= start_date)
    if end_date:
        query = query.filter(AnalysisScope.end_date <= end_date)

    results = query.all()

    # Count occurrences per date
    counts = {}
    for row in results:
        counts[row.date] = counts.get(row.date, 0) + 1

    # Convert to sorted list
    data = [{"date": d.isoformat(), "count": c} for d, c in sorted(counts.items())]

    return JSONResponse(content=data)

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

