# backend/app/api/routes/symptoms.py

from fastapi import APIRouter, Depends, Query
from app.api.routes.auth import get_current_user
from app.models.table_class import User
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Symptom, SymptomLog
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/symptoms", tags=["symptoms"], include_in_schema=True)

@router.get("")
def search_symptoms(
    q: Optional[str] = Query(None, min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search the current user's symptoms by name (optional query string).

    The endpoint:
    1. Builds a base query for symptoms belonging to the authenticated user.
    2. If `q` is provided, applies a case-insensitive partial match filter on `symptom_name`.
    3. Returns up to 10 matches when searching; otherwise returns all symptoms.
    4. Logs SQL and basic debug info.

    Parameters
    ----------
    q : str, optional
        Search term used to filter symptoms by name (case-insensitive, partial match).
        If omitted/None, no search filter is applied.
    db : Session
        Database session (FastAPI dependency).
    current_user : User
        Authenticated user (FastAPI dependency).

    Returns
    -------
    list[dict]
        A list of symptoms as JSON objects with:
        - symptom_id
        - symptom_name
    """

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
            "symptom_id": a.symptom_id,
            "symptom_name": a.symptom_name
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
        Return the most recent symptoms logged by the current user.

        The endpoint:
        1. Queries the most recent SymptomLog rows for the authenticated user (descending date_time).
        2. Joins Symptom to include symptom metadata (name/id).
        3. Deduplicates symptoms while preserving recency order.
        4. Returns up to `limit` unique symptoms.

        Parameters
        ----------
        limit : int
            Max number of recent (unique) symptoms to return.
            Constrained to 1..50 (default 5).
        db : Session
            Database session (FastAPI dependency).
        current_user : User
            Authenticated user (FastAPI dependency).

        Returns
        -------
        list[dict]
            A list of recent unique symptoms as JSON objects with:
            - symptom_id
            - symptom_name
        """

        logger.info("=== GET /logs/recent CALLED ===")
        logger.info(f"User: {current_user.user_id}, limit: {limit}")

        query = (
            db.query(SymptomLog, Symptom)
            .join(Symptom, Symptom.symptom_id == SymptomLog.symptom_id)
            .filter(SymptomLog.user_id == current_user.user_id)
            .order_by(SymptomLog.date_time.desc())
            .limit(limit)
        )

        logger.info(
            "Recent logs SQL: %s",
            query.statement.compile(compile_kwargs={"literal_binds": True})
        )

        logs = query.all()
        logger.info(f"Recent logs count: {len(logs)}")

        # Shape the response
        # Deduplicate symptoms while preserving order (important!)
        seen = set()
        recent_symptoms = []

        for log, symptom in logs:
            if symptom.symptom_id in seen:
                continue
            seen.add(symptom.symptom_id)
            recent_symptoms.append({
                "symptom_id": symptom.symptom_id,
                "symptom_name": symptom.symptom_name,
            })

            if len(recent_symptoms) >= limit:
                break

        return recent_symptoms
