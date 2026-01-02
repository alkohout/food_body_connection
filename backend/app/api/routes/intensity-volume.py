from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.database import get_db
from app.models.table_class import User
from app.data.analysis_data import get_all_symptom_events, get_allergen_events, get_unit
from datetime import datetime, timedelta
import pandas as pd
import seaborn as sns
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from starlette.responses import StreamingResponse
import logging
import traceback
from fastapi import HTTPException
from io import BytesIO

logger = logging.getLogger("plot_eda")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get('/intensity-volume')
def intensity_volume(
    allergen_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try: 
        
        # --- Determine overall min/max dates ---
        allergen_events = get_allergen_events(db, current_user.user_id)
        symptom_events = get_all_symptom_events(db, current_user.user_id)
        start_dt = min(allergen_events.date_time)
        end_dt = max(allergen_events.date_time)

        logger.info("Generating EDA plot for user_id=%d", current_user.user_id)
        logger.info("Start date: %s, End date: %s", start_dt, end_dt)   
        logger.info("Allergen events: %d, Symptom events: %d", len(allergen_events), len(symptom_events))

        # --- Time series: count of symptom events within 24h of each allergen ---
        rows = []
        for allergen in allergen_events:

            window_end = allergen.date_time + timedelta(hours=24)
            
            matching_symptoms = [s for s in symptom_events if allergen.date_time <= s.date_time <= window_end]
            
            # Lookup the unit conversion from the database
            quantity = allergen.quantity
            unit_id = allergen.unit_id
            unit_obj = get_unit(db, unit_id=unit_id)
            conversion = unit_obj.unit_conversion if unit_obj else None
            volume = quantity * conversion if quantity and conversion else None

            # Sum intensity and square it
            total_intensity = sum(s.symptom_intensity or 0 for s in matching_symptoms)
            burden_score = total_intensity ** 2  # emphasize larger clusters

            rows.append({
                "volume": volume,
                "burden_score": burden_score,
            })

        df = pd.DataFrame(rows)
        logger.info("Valid rows for plot: %d", len(df))
        logger.info(df.head(74))

        # --- Plotting ---
        sns.set(style="whitegrid")
        fig, axes = plt.subplots(1, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3]})

        # Sort by count descending and take top 10
        sns.scatterplot(data=df, x="volume", y="burden_score", ax=axes)
        axes.set_title(f"Total symptom Burden Score vs Allergen Volume for {allergen_name}")
        axes.set_xlabel("Allergen Volume")
        axes.set_ylabel("Symptom Burden Score")

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
        raise HTTPException(status_code=500, detail="Failed to generate plot")