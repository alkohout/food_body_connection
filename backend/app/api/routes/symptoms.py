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

def get_recent_logs(
        limit: int = Query(5, ge=1, le=50, description="Max number of recent logs to return"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        """
        Return the most recent unique symptoms logged by the current user.

        The endpoint:
        1. Retrieves symptom logs joined with symptom metadata.
        2. Orders results by most recent `date_time` (descending).
        3. Limits the raw query to the requested number.
        4. Deduplicates symptoms while preserving order.
        5. Returns up to `limit` unique recent symptoms.

        Parameters
        ----------
        limit : int
            Maximum number of recent logs to return (default = 5, max = 50).
        db : Session
            Database session (FastAPI dependency).
        current_user : User
            Authenticated user (FastAPI dependency).

        Returns
        -------
        list[dict]
            A list of recent unique symptoms:
            [
                {
                    "symptom_id": int,
                    "symptom_name": str
                }
            ]
        """

        # --------------------------------------------------
        # Log endpoint call and input parameters
        # --------------------------------------------------
        logger.info("=== GET /logs/recent CALLED ===")
        logger.info(f"User: {current_user.user_id}, limit: {limit}")

        # --------------------------------------------------
        # Build query for recent symptom logs
        # --------------------------------------------------
        query = (
            db.query(SymptomLog, Symptom)
            .join(Symptom, Symptom.symptom_id == SymptomLog.symptom_id)
            .filter(SymptomLog.user_id == current_user.user_id)
            .order_by(SymptomLog.date_time.desc())
            .limit(limit)
        )

        # Log generated SQL for debugging
        logger.info(
            "Recent logs SQL: %s",
            query.statement.compile(compile_kwargs={"literal_binds": True})
        )

        # Execute query
        logs = query.all()
        logger.info(f"Recent logs count: {len(logs)}")

        # --------------------------------------------------
        # Deduplicate symptoms while preserving order
        # --------------------------------------------------
        seen = set()
        recent_symptoms = []

        for log, symptom in logs:
            # Skip if symptom already included
            if symptom.symptom_id in seen:
                continue

            seen.add(symptom.symptom_id)

            # Append formatted symptom data
            recent_symptoms.append({
                "symptom_id": symptom.symptom_id,
                "symptom_name": symptom.symptom_name,
            })

            # Stop once desired limit of unique symptoms is reached
            if len(recent_symptoms) >= limit:
                break

        # Return formatted response
        return recent_symptoms