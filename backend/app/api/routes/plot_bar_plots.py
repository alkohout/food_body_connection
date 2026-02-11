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

logger = logging.getLogger("app/api/routes/plot_bar_plots.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

def plot_bar_plots(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        allergen_name: str = 'Dairy',
        lag_start: int = 0,
        lag_end: int = 6,
        symptom_group: str = 'Gastrointestinal',
    ):
    """
    Generate and return a bar plot summarising the relationship
    between allergen exposure and symptoms within a specified lag window.

    The function:
    1. Calls `plot_stats` to compute exposure–symptom statistics.
    2. Generates a bar chart showing:
        - % exposure-days followed by symptoms
        - % symptom-days preceded by exposure
    3. Returns the plot as a PNG streaming response.
    4. Logs and handles errors gracefully.

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
        PNG image containing the generated bar plot.
    """

    try: 

        # --------------------------------------------------
        # Generate plot buffer using statistical helper
        # --------------------------------------------------
        buf = plot_stats(
            db,
            current_user.user_id,
            allergen_name,
            lag_start,
            lag_end,
            symptom_group
        )

        # Return PNG image as streaming response
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:

        # --------------------------------------------------
        # Log full error details for debugging
        # --------------------------------------------------
        logger.error("Error generating plot: %s", e)
        logger.error(traceback.format_exc())

        # Return generic server error to client
        raise HTTPException(
            status_code=500,
            detail="Failed to generate plot"
        )