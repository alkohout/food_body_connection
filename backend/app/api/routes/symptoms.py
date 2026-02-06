# backend/app/api/routes/symptoms.py

from fastapi import APIRouter, Depends, Query
from app.api.routes.auth import get_current_user
from app.models.table_class import User
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Symptom
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/symptoms", tags=["symptoms"], include_in_schema=True)

@router.get("")
def search_symptoms(
    q: Optional[str] = Query(None, min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    query = (
        db.query(Symptom)
        .filter(Symptom.user_id == current_user.user_id)
    )

    # Apply search filter if provided
    if q:
        query = query.filter(Symptom.symptom_name.ilike(f"%{q}%"))
        logger.info(f"With search filter: {query}")
        results = (
            query.order_by(Symptom.symptom_name)
                 .limit(10)
                 .all()
        )
    else:
        results = query.order_by(Symptom.symptom_name).all()
    
    logger.info(f"Raw SQL: {query.statement.compile(compile_kwargs={'literal_binds': True})}")
    logger.info(f"Results count: {len(results)}")
    logger.info(f"Results: {[(r.symptom_id, r.symptom_name) for r in results[:3]]}")

    return [
        {
            "allergen_id": a.allergen_id,
            "allergen_name": a.allergen_name
        }
        for a in results
    ]
