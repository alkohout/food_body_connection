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
from app.analysis.time_series import time_series 
from datetime import timedelta, datetime
import traceback
from io import BytesIO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

logger = logging.getLogger("app/api/routes/plot_time_series.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/plot_time_series")
def plot_time_series(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        allergen_name: str = 'Dairy'
    ):
    """
    Generate a time series plot showing allergen exposure and
    symptom trends over time.

    The endpoint:
    1. Calls `time_series` to compute and generate the plot.
    2. Visualises exposure patterns across time.
    3. Returns the plot as a PNG streaming response.

    Parameters
    ----------
    db : Session
        Database session (FastAPI dependency).
    current_user : User
        Authenticated user (FastAPI dependency).
    allergen_name : str
        Name of allergen to analyse (default = 'Dairy').

    Returns
    -------
    StreamingResponse (image/png)
        PNG image containing the time series plot.
    """

    try: 

        # --------------------------------------------------
        # Generate time series plot buffer
        # --------------------------------------------------
        buf = time_series(
            db,
            current_user.user_id,
            allergen_name
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
