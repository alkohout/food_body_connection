# app/api/routes/entries.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import AllergenLog, SymptomLog, User, Allergen, Symptom
from app.api.routes.auth import get_current_user
from app.schemas import AllergenLogCreate, SymptomLogCreate

router = APIRouter(prefix="/entries", tags=["entries"])

@router.post("/allergens")
def log_allergen(
    payload: AllergenLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log a new allergen exposure event for the current user.

    The endpoint:
    1. Validates that the allergen belongs to the authenticated user.
    2. Creates a new allergen log entry.
    3. Saves the record to the database.
    4. Returns confirmation with the new log ID.

    Parameters
    ----------
    payload : AllergenLogCreate
        Request body containing:
        - allergen_id : int
        - date_time : datetime
        - quantity : float
        - unit_id : int
    current_user : User
        Authenticated user (FastAPI dependency).
    db : Session
        Database session (FastAPI dependency).

    Returns
    -------
    dict
        {
            "message": str,
            "allergen_log_id": int
        }
    """

    # --------------------------------------------------
    # Validate allergen belongs to current user
    # --------------------------------------------------
    allergen = (
        db.query(Allergen)
        .filter(Allergen.allergen_id == payload.allergen_id)
        .filter(Allergen.user_id == current_user.user_id)
        .first()
    )

    if not allergen:
        raise HTTPException(
            status_code=400,
            detail="Invalid allergen_id: this allergen does not belong to the current user"
        )

    # --------------------------------------------------
    # Create new allergen log entry
    # --------------------------------------------------
    new_entry = AllergenLog(
        user_id=current_user.user_id,
        allergen_id=payload.allergen_id,
        date_time=payload.date_time,
        quantity=payload.quantity,
        unit_id=payload.unit_id
    )

    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    return {
        "message": "Allergen logged",
        "allergen_log_id": new_entry.allergen_log_id
    }

@router.post("/symptoms")
def log_symptom(
    payload: SymptomLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log a new symptom event for the current user.

    The endpoint:
    1. Validates that the symptom belongs to the authenticated user.
    2. Creates a new symptom log entry.
    3. Saves the record to the database.
    4. Returns confirmation with the new log ID.

    Parameters
    ----------
    payload : SymptomLogCreate
        Request body containing:
        - symptom_id : int
        - date_time : datetime
        - intensity : int
    current_user : User
        Authenticated user (FastAPI dependency).
    db : Session
        Database session (FastAPI dependency).

    Returns
    -------
    dict
        {
            "message": str,
            "symptom_log_id": int
        }
    """

    # --------------------------------------------------
    # Validate symptom belongs to current user
    # --------------------------------------------------
    symptom = (
        db.query(Symptom)
        .filter(Symptom.symptom_id == payload.symptom_id)
        .filter(Symptom.user_id == current_user.user_id)
        .first()
    )

    if not symptom:
        raise HTTPException(400, "Invalid symptom ID for this user")

    # --------------------------------------------------
    # Create new symptom log entry
    # --------------------------------------------------
    new_entry = SymptomLog(
        user_id=current_user.user_id,
        symptom_id=payload.symptom_id,
        date_time=payload.date_time,
        symptom_intensity=payload.intensity,
    )

    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    return {
        "message": "Symptom logged",
        "symptom_log_id": new_entry.symptom_log_id
    }


