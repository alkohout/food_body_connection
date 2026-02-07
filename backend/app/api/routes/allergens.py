from fastapi import APIRouter, Depends, Query
from app.api.routes.auth import get_current_user
from app.models.table_class import User
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Allergen, AllergenLog
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/allergens", tags=["allergens"], include_in_schema=True)

@router.get("")
def search_allergens(
    q: Optional[str] = Query(None, min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ADD DEBUG LOGGING
    logger.info(f"=== SEARCH ALLERGENS CALLED ===")
    logger.info(f"Query param 'q': {q}")
    logger.info(f"Current user: {current_user}")

    # BUILD QUERY
    query = (
        db.query(Allergen)
        .filter(Allergen.user_id == current_user.user_id)
    )
    logger.info(f"Base query: {query}")

    # Apply search filter if provided
    if q:
        query = query.filter(Allergen.allergen_name.ilike(f"%{q}%"))
        logger.info(f"With search filter: {query}")
        results = (
            query.order_by(Allergen.allergen_name)
                 .limit(10)
                 .all()
        )
    else:
        results = query.order_by(Allergen.allergen_name).all()
    
    logger.info(f"Raw SQL: {query.statement.compile(compile_kwargs={'literal_binds': True})}")
    logger.info(f"Results count: {len(results)}")
    logger.info(f"Results: {[(r.allergen_id, r.allergen_name) for r in results[:3]]}")

    return [
        {
            "allergen_id": a.allergen_id,
            "allergen_name": a.allergen_name
        }
        for a in results
    ]

@router.get("/recent")
def get_recent_logs(
    limit: int = Query(5, ge=1, le=50, description="Max number of recent logs to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the most recent logs for the current user, ordered by created_at DESC.
    Default limit: 5 (up to max 50).
    """

    logger.info("=== GET /logs/recent CALLED ===")
    logger.info(f"User: {current_user.user_id}, limit: {limit}")

    query = (
        db.query(AllergenLog)
        .filter(AllergenLog.user_id == current_user.user_id)
        .order_by(AllergenLog.created_at.desc())
        .limit(limit)
    )

    logger.info(
        "Recent logs SQL: %s",
        query.statement.compile(compile_kwargs={"literal_binds": True})
    )

    logs = query.all()
    logger.info(f"Recent logs count: {len(logs)}")

    # Shape the response
    return [
        {
            "log_id": l.log_id,
            "created_at": l.created_at.isoformat() if getattr(l, "created_at", None) else None,
            # Add any fields you want to expose:
            # "message": l.message,
            # "level": l.level,
            # "metadata": l.metadata,
        }
        for l in logs
    ]