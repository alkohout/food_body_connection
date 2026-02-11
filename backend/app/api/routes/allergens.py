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
    """
    Search allergens belonging to the current user.

    If a query string `q` is provided:
        - Performs case-insensitive partial match (ILIKE).
        - Returns up to 10 results ordered alphabetically.

    If no query is provided:
        - Returns all allergens for the user ordered alphabetically.

    Parameters
    ----------
    q : Optional[str]
        Search string for allergen name (minimum length 1).
    db : Session
        Database session (FastAPI dependency).
    current_user : User
        Authenticated user (FastAPI dependency).

    Returns
    -------
    list[dict]
        List of allergens:
        [
            {
                "allergen_id": int,
                "allergen_name": str
            }
        ]
    """

    # --------------------------------------------------
    # Debug logging
    # --------------------------------------------------
    logger.info(f"=== SEARCH ALLERGENS CALLED ===")
    logger.info(f"Query param 'q': {q}")
    logger.info(f"Current user: {current_user}")

    # --------------------------------------------------
    # Base query: allergens belonging to current user
    # --------------------------------------------------
    query = (
        db.query(Allergen)
        .filter(Allergen.user_id == current_user.user_id)
    )

    logger.info(f"Base query: {query}")

    # --------------------------------------------------
    # Apply search filter if query string provided
    # --------------------------------------------------
    if q:
        query = query.filter(Allergen.allergen_name.ilike(f"%{q}%"))
        logger.info(f"With search filter: {query}")

        # Limit results for autocomplete-style behaviour
        results = (
            query.order_by(Allergen.allergen_name)
                 .limit(10)
                 .all()
        )
    else:
        # Return all allergens if no search term
        results = query.order_by(Allergen.allergen_name).all()
    
    # Log raw SQL and result preview for debugging
    logger.info(
        f"Raw SQL: {query.statement.compile(compile_kwargs={'literal_binds': True})}"
    )
    logger.info(f"Results count: {len(results)}")
    logger.info(
        f"Results: {[(r.allergen_id, r.allergen_name) for r in results[:3]]}"
    )

    # --------------------------------------------------
    # Shape response
    # --------------------------------------------------
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
    Return the most recent allergen logs for the current user.

    The endpoint:
    1. Retrieves recent allergen log entries ordered by most recent first.
    2. Joins allergen metadata.
    3. Deduplicates allergens while preserving order.
    4. Returns up to `limit` unique allergens.

    Parameters
    ----------
    limit : int
        Maximum number of recent allergens to return (1–50).
        Default = 5.
    db : Session
        Database session (FastAPI dependency).
    current_user : User
        Authenticated user (FastAPI dependency).

    Returns
    -------
    list[dict]
        List of unique recent allergens:
        [
            {
                "allergen_id": int,
                "allergen_name": str
            }
        ]
    """

    logger.info("=== GET /logs/recent CALLED ===")
    logger.info(f"User: {current_user.user_id}, limit: {limit}")

    # --------------------------------------------------
    # Build query for recent allergen logs
    # --------------------------------------------------
    query = (
        db.query(AllergenLog, Allergen)
        .join(Allergen, Allergen.allergen_id == AllergenLog.allergen_id)
        .filter(AllergenLog.user_id == current_user.user_id)
        .order_by(AllergenLog.date_time.desc())
        .limit(limit)
    )

    # Log raw SQL for debugging
    logger.info(
        "Recent logs SQL: %s",
        query.statement.compile(compile_kwargs={"literal_binds": True})
    )

    logs = query.all()
    logger.info(f"Recent logs count: {len(logs)}")

    # --------------------------------------------------
    # Deduplicate allergens while preserving order
    # --------------------------------------------------
    seen = set()
    recent_allergens = []

    for log, allergen in logs:

        # Skip if allergen already included
        if allergen.allergen_id in seen:
            continue

        seen.add(allergen.allergen_id)

        recent_allergens.append({
            "allergen_id": allergen.allergen_id,
            "allergen_name": allergen.allergen_name,
        })

        # Stop once we reach desired limit
        if len(recent_allergens) >= limit:
            break

    return recent_allergens