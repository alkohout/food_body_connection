# app/api/routes/plot_eda.py
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.models.table_class import User
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from datetime import timedelta, datetime
import traceback
from app.analysis.model import model_classification 
from io import BytesIO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

logger = logging.getLogger("app/api/routes/plot_allergen_rank.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/plot_allergen_rank")
def plot_allergen_rank(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):
    """
    Generate an allergen ranking plot (PNG) based on the user's classification model results.

    The endpoint:
    1. Runs the classification analysis via `model_classification`.
    2. Requests the result in image format (default behavior of `model_classification`).
    3. Returns the generated plot as a streamed PNG image response.
    4. Handles and logs errors gracefully.

    Parameters
    ----------
    db : Session
        Database session (FastAPI dependency).
    current_user : User
        Authenticated user (FastAPI dependency).

    Returns
    -------
    StreamingResponse (image/png)
        Generated allergen ranking plot streamed as PNG.
    """

    try: 

        # --------------------------------------------------
        # Run classification model and generate plot output
        # --------------------------------------------------
        buf = model_classification(
            db,
            current_user.user_id
        )

        # Return as streamed PNG image response
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:

        # --------------------------------------------------
        # Log full error details for debugging
        # --------------------------------------------------
        logger.error("Error generating plot: %s", e)
        logger.error(traceback.format_exc())

        # Return generic error to client
        raise HTTPException(status_code=500, detail="Failed to generate plot")
