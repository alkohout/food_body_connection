from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Allergen
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/allergens", tags=["allergens"], include_in_schema=True)

@router.get("")
def search_allergens(
    q: Optional[str] = Query(None, min_length=1),
    db: Session = Depends(get_db),
):
    # ADD DEBUG LOGGING
    logger.info(f"=== SEARCH ALLERGENS CALLED ===")
    logger.info(f"Query param 'q': {q}")

    # BUILD QUERY
    query = db.query(Allergen)
    logger.info(f"Base query: {query}")

    # Apply search filter if provided
    if q:
        query = query.filter(Allergen.allergen_name.ilike(f"%{q}%"))
        logger.info(f"With search filter: {query}")
    
    # Execute query
#    results = query.order_by(Allergen.allergen_name).limit(10).all()
    
    logger.info(f"Raw SQL: {query.statement.compile(compile_kwargs={'literal_binds': True})}")
    logger.info(f"Results count: {len(results)}")
    logger.info(f"Results: {[(r.allergen_id, r.allergen_name) for r in results[:3]]}")

    results = (
        db.query(Allergen)
        .filter(Allergen.allergen_name.ilike(f"%{q}%"))
        .order_by(Allergen.allergen_name)
        .limit(10)
        .all()
    )

    return [
        {
            "allergen_id": a.allergen_id,
            "allergen_name": a.allergen_name
        }
        for a in results
    ]