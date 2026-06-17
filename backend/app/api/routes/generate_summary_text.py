import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.table_class import User
from app.analysis.ai_summary import generate_ai_summary

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/generate_summary_text")
def generate_summary_text(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return generate_ai_summary(db, current_user.user_id)
    except Exception as e:
        logger.error("Error generating AI summary: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to generate summary")
