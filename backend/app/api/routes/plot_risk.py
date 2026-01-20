# app/api/routes/plot_time_series.py
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.models.table_class import User
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.analysis.temporal_stats import plot_stats 
from datetime import timedelta, datetime
import traceback
from io import BytesIO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

logger = logging.getLogger("app/api/routes/plot_risk.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/plot_risk")
def plot_risk(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        allergen_name: str = 'Dairy',
        lag_start: int = 0,
        lag_end: int = 6,
        symptom_group: str = 'Gastrointestinal',
    ):

    try: 

        buf = plot_stats(
            db,
            current_user.user_id,
            allergen_name,
            lag_start,
            lag_end,
            symptom_group
        )

        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:

        logger.error("Error generating plot: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to generate plot")
