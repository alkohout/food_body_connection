# backend/app/api/routes/symptom_groups.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Symptom

router = APIRouter(prefix="/symptom_groups", tags=["symptom_groups"], include_in_schema=True)


@router.get("")
def search_symptom_groups(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    """
    Search for unique symptom group names matching a query string.

    The endpoint:
    1. Performs a case-insensitive partial match on `symptom_group`.
    2. Returns distinct symptom group names only.
    3. Orders results alphabetically.
    4. Limits results to a maximum of 10 matches.

    Parameters
    ----------
    q : str
        Search query string (minimum length = 1).
    db : Session
        Database session (FastAPI dependency).

    Returns
    -------
    list[dict]
        A list of dictionaries containing matching symptom group names.
        Example:
            [
                {"symptom_group": "Gastrointestinal"},
                {"symptom_group": "Neurological"}
            ]
    """

    # --------------------------------------------------
    # Query distinct symptom groups matching search term
    # --------------------------------------------------
    results = (
        db.query(Symptom.symptom_group)
        .filter(Symptom.symptom_group.ilike(f"%{q}%"))  # Case-insensitive partial match
        .distinct()  # Only unique values
        .order_by(Symptom.symptom_group)  # Alphabetical order
        .limit(10)  # Limit to 10 results
        .all()
    )

    # --------------------------------------------------
    # Format results as list of dictionaries
    # --------------------------------------------------
    return [{"symptom_group": sg[0]} for sg in results]



