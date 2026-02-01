# app/api/routes/plot_time_series.py
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from fastapi import HTTPException
from fastapi import Response
from app.models.table_class import User
from app.data.analysis_data import get_all_allergen_events_df, get_all_symptom_events_df
from app.analysis.model import model_classification 
from datetime import timedelta, datetime
import traceback
from io import BytesIO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

logger = logging.getLogger("app/api/routes/generate_summary_text.py")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/generate_summary_text")
def generate_summary_text(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ):

    try: 

        buf = model_classification(
            db,
            current_user.user_id,
            return_text="text"
        )

        return Response(content=buf, media_type="text/plain")

    except Exception as e:

        logger.error("Error generating summary: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to generate summary")
