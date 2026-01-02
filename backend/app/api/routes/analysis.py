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
from sqlalchemy import text, func, union_all, select, func
from typing import Optional
import logging
import traceback

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

    all_dates = union_all(
        select(func.date(AllergenLog.date_time).label("date"))
            .where(AllergenLog.user_id == current_user.user_id),
        select(func.date(SymptomLog.date_time).label("date"))
            .where(SymptomLog.user_id == current_user.user_id),
    ).subquery()

    total_days = (
        db.query(func.count(func.distinct(all_dates.c.date)))
        .scalar()
    )

    total_allergens = db.query(func.count(AllergenLog.allergen_log_id)) \
                         .filter(AllergenLog.user_id == current_user.user_id) \
                         .scalar()
    total_symptoms = db.query(func.count(SymptomLog.symptom_log_id)) \
                        .filter(SymptomLog.user_id == current_user.user_id) \
                        .scalar()

    return {
        "Total allergens logged": total_allergens,
        "Total symptoms logged": total_symptoms,
        "Total days tracked": total_days    
    }
@router.get('/intensity-volume')
def intensity_volume(
    symptom_name: str,
    allergen_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try: 
        
        # Query for the allergen ID
        allergen = db.query(Allergen).filter(Allergen.allergen_name == allergen_name).first()
        if allergen:
            allergen_id = allergen.allergen_id
            logger.info("Allergen ID for %s is %s", allergen_name, allergen_id)
        else:
            logger.warning("No allergen found with name %s", allergen_name)
        # Query for the symptom ID
        symptom = db.query(Symptom).filter(Symptom.symptom_name == symptom_name).first()
        if symptom:
            symptom_id = symptom.symptom_id
            logger.info("Symptom ID for %s is %s", symptom_name, symptom_id)
        else:
            logger.warning("No symptom found with name %s", symptom_name)

        # --- Determine overall min/max dates ---
        min_allergen = db.query(func.min(AllergenLog.date_time)).filter(AllergenLog.user_id == current_user.user_id).scalar()
        max_allergen = db.query(func.max(AllergenLog.date_time)).filter(AllergenLog.user_id == current_user.user_id).scalar()
        min_symptom = db.query(func.min(SymptomLog.date_time)).filter(SymptomLog.user_id == current_user.user_id).scalar()
        max_symptom = db.query(func.max(SymptomLog.date_time)).filter(SymptomLog.user_id == current_user.user_id).scalar()

        start_dt = min(d for d in [min_allergen, min_symptom] if d is not None)
        end_dt = max(d for d in [max_allergen, max_symptom] if d is not None)

        # --- Query allergen and symptom events within range ---
        allergen_events = db.query(AllergenLog).filter(
            AllergenLog.user_id == current_user.user_id,
            AllergenLog.allergen_id == allergen_id,
            AllergenLog.date_time >= start_dt,
            AllergenLog.date_time <= end_dt
        ).all()

        symptom_events = db.query(SymptomLog).filter(
            SymptomLog.user_id == current_user.user_id,
            SymptomLog.symptom_id == symptom_id,
            SymptomLog.date_time >= start_dt,
            SymptomLog.date_time <= end_dt
        ).all()

        logger.info("Generating EDA plot for user_id=%d", current_user.user_id)
        logger.info("Start date: %s, End date: %s", start_dt, end_dt)   
        logger.info("Allergen events: %d, Symptom events: %d", len(allergen_events), len(symptom_events))

        # --- Time series: count of symptom events within 24h of each allergen ---
        from collections import defaultdict
        import pandas as pd
        from datetime import timedelta
        import pandas as pd
        from datetime import timedelta

        # Example unit conversion dictionary to standard volume (mL or g)
        unit_conversion = {
            "ml": 1,         # already in mL
            "Liters": 1000,   # 1 L = 1000 mL
            "teaspoons": 5,        # 1 teaspoon = 5 mL
            "tablespoons": 15,      # 1 tablespoon = 15 mL
            "cups": 240,      # 1 cup = 240 mL
            "grams": 1,          # grams for solids
            # add more units as needed
        }

        rows = []

        for allergen in allergen_events:
            window_end = allergen.date_time + timedelta(hours=24)
            
            matching_symptoms = [s for s in symptom_events if allergen.date_time <= s.date_time <= window_end]
            
            for s in matching_symptoms:
                quantity = getattr(s, "quantity", None)
                unit = getattr(s, "unit", None)
                intensity = getattr(s, "intensity", None)
                
                # Convert to standard volume/weight
                if quantity is not None and unit in unit_conversion:
                    volume = quantity * unit_conversion[unit]
                else:
                    volume = None  # unknown unit or missing quantity
                
                rows.append({
                    "allergen_id": allergen.allergen_id,
                    "allergen_name": getattr(allergen, "allergen_name", None),
                    "symptom_id": s.symptom_id,
                    "symptom_name": getattr(s, "symptom_name", None),
                    "quantity": quantity,
                    "unit": unit,
                    "volume": volume,
                    "intensity": intensity,
                    "allergen_time": allergen.date_time,
                    "symptom_time": s.date_time,
                })

        df = pd.DataFrame(rows)

        print(df.head())


        logger.info( df.head()) 

        # --- Plotting ---
        sns.set(style="whitegrid")
        fig, axes = plt.subplots(1, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3]})

        # Sort by count descending and take top 10
        sns.scatter(df, x="volume", y="intensity", ax=axes)
        axes.set_title(f"Symptom Intensity vs Allergen Volume for {allergen_name} and {symptom_name}")
        axes.set_xlabel("Allergen Volume")
        axes.set_ylabel("Symptom Intensity")

        plt.tight_layout()

        # --- Save to PNG ---
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:

        logger.error("Error generating plot: %s", e)
        logger.error(traceback.format_exc())
        # Optionally return a 500 with a message
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to generate plot")

@router.get("/plot-eda")
def plot_eda(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):

    try: 
        
        # --- Determine overall min/max dates ---
        min_allergen = db.query(func.min(AllergenLog.date_time)).filter(AllergenLog.user_id == current_user.user_id).scalar()
        max_allergen = db.query(func.max(AllergenLog.date_time)).filter(AllergenLog.user_id == current_user.user_id).scalar()
        min_symptom = db.query(func.min(SymptomLog.date_time)).filter(SymptomLog.user_id == current_user.user_id).scalar()
        max_symptom = db.query(func.max(SymptomLog.date_time)).filter(SymptomLog.user_id == current_user.user_id).scalar()

        start_dt = min(d for d in [min_allergen, min_symptom] if d is not None)
        end_dt = max(d for d in [max_allergen, max_symptom] if d is not None)

        # --- Query allergen and symptom events within range ---
        allergen_events = db.query(AllergenLog).filter(
            AllergenLog.user_id == current_user.user_id,
            AllergenLog.date_time >= start_dt,
            AllergenLog.date_time <= end_dt
        ).all()

        symptom_events = db.query(SymptomLog).filter(
            SymptomLog.user_id == current_user.user_id,
            SymptomLog.date_time >= start_dt,
            SymptomLog.date_time <= end_dt
        ).all()

        logger.info("Generating EDA plot for user_id=%d", current_user.user_id)
        logger.info("Start date: %s, End date: %s", start_dt, end_dt)   
        logger.info("Allergen events: %d, Symptom events: %d", len(allergen_events), len(symptom_events))

        # --- Time series: count of symptom events within 24h of each allergen ---
        from datetime import timedelta
        from collections import defaultdict

        # --- Count symptom events within 24h of each allergen ---
        counts_by_allergen = defaultdict(int)
        # Ensure we only count allergens that actually exist
        for a in allergen_events:
            window_end = a.date_time + timedelta(hours=24)
            
            # Count number of symptoms within 24h of this allergen event
            count = sum(1 for s in symptom_events if a.date_time <= s.date_time <= window_end)
            
            # Accumulate count per allergen_id
            counts_by_allergen[a.allergen_id] += count


        # Map allergen IDs to names for plotting
        allergen_ids = list(counts_by_allergen.keys())
        allergens = db.query(Allergen).filter(Allergen.allergen_id.in_(allergen_ids)).all()
        allergen_names = {a.allergen_id: a.allergen_name for a in allergens}
        logger.info("Allergen names mapping: %s", allergen_names)

        # Map symptom IDs to names for heatmap
        symptom_ids = list({s.symptom_id for s in symptom_events})
        symptoms = db.query(Symptom).filter(Symptom.symptom_id.in_(symptom_ids)).all()
        symptom_names = {s.symptom_id: s.symptom_name for s in symptoms}
        logger.info("Symptom names mapping: %s", symptom_names)

        # Convert freq_table to a DataFrame for seaborn
        import pandas as pd

        # --- Plotting ---
        sns.set(style="whitegrid")
        fig, axes = plt.subplots(1, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3]})

        # Convert counts to DataFrame for barplot
        bar_data = pd.DataFrame({
            "Allergen": [allergen_names[a_id] for a_id in counts_by_allergen.keys()],
            "Count": [counts_by_allergen[a_id] for a_id in counts_by_allergen.keys()]
        })

        # Optional: remove allergens with 0 count if you want
        bar_data = bar_data[bar_data["Count"] > 0]

        # Sort by count descending and take top 10
        bar_data_top10 = bar_data.sort_values("Count", ascending=False).head(10)
        sns.barplot(data=bar_data_top10, x="Allergen", y="Count", ax=axes)
        axes.set_title(f"Number of symptoms within 24h of allergen exposures (top 10 allergens)")
        axes.set_xlabel("Allergen")
        axes.set_ylabel("Symptom Count")

        plt.tight_layout()

        # --- Save to PNG ---
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        # logging for debugging
        logger.info("Number of allergen events: %d", len(allergen_events))
        logger.info("Number of symptom events: %d", len(symptom_events))
        logger.info("Counts by allergen: %s", counts_by_allergen)

        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:

        logger.error("Error generating plot: %s", e)
        logger.error(traceback.format_exc())
        # Optionally return a 500 with a message
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to generate plot")

@router.get("/plot")
def plot_analysis(
    allergen: str = "Dairy",
    symptom: str = "Nausea",
    start_date: str = "2025-01-01",
    end_date: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    min_allergen = db.query(func.min(AllergenLog.date_time)) \
                     .filter(AllergenLog.user_id == current_user.user_id) \
                     .scalar()
    max_allergen = db.query(func.max(AllergenLog.date_time)) \
                     .filter(AllergenLog.user_id == current_user.user_id) \
                     .scalar()
    
    min_symptom = db.query(func.min(SymptomLog.date_time)) \
                    .filter(SymptomLog.user_id == current_user.user_id) \
                    .scalar()
    max_symptom = db.query(func.max(SymptomLog.date_time)) \
                    .filter(SymptomLog.user_id == current_user.user_id) \
                    .scalar()
    # Start = earliest of allergen/symptom logs
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else min(
        d for d in [min_allergen, min_symptom] if d is not None
    )

    # End = latest of allergen/symptom logs
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else max(
        d for d in [max_allergen, max_symptom] if d is not None
    )
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
    plt.savefig(buf, format="png", bbox_inches="tight")
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

