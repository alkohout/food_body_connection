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
from app.analysis.temporal_stats import plot_stats_risk 
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
    """
    Generate a risk comparison plot showing the probability of symptoms
    on exposed vs unexposed days for a specific allergen.

    The endpoint:
    1. Calls `plot_stats_risk` to compute risk statistics.
    2. Compares:
        - Baseline symptom probability (no exposure)
        - Symptom probability after exposure
    3. Displays absolute risk difference and p-value.
    4. Returns the plot as a PNG streaming response.

    Parameters
    ----------
    db : Session
        Database session (FastAPI dependency).
    current_user : User
        Authenticated user (FastAPI dependency).
    allergen_name : str
        Name of allergen to analyse (default = 'Dairy').
    lag_start : int
        Start of lag window in hours (default = 0).
    lag_end : int
        End of lag window in hours (default = 6).
    symptom_group : str
        Symptom category to analyse (default = 'Gastrointestinal').

    Returns
    -------
    StreamingResponse (image/png)
        PNG image containing the risk comparison plot.
    """

    try: 

        # --------------------------------------------------
        # Generate risk plot buffer
        # --------------------------------------------------
        buf = plot_stats_risk(
            db,
            current_user.user_id,
            allergen_name,
            lag_start,
            lag_end,
            symptom_group
        )

        # --------------------------------------------------
        # Return PNG image as streaming response
        # --------------------------------------------------
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:

        # --------------------------------------------------
        # Log full error details for debugging
        # --------------------------------------------------
        logger.error("Error generating plot: %s", e)
        logger.error(traceback.format_exc())

        # --------------------------------------------------
        # Return generic server error to client
        # --------------------------------------------------
        raise HTTPException(
            status_code=500,
            detail="Failed to generate plot"
        )