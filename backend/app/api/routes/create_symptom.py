from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.table_class import Symptom
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/symptoms", tags=["symptoms"])

class SymptomCreate(BaseModel):
    symptom_name: str
    symptom_group: Optional[str] = None

@router.post("")
def create_symptom(
    payload: SymptomCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Create a new symptom for the current user.

    The endpoint:
    1. Strips whitespace from the symptom name.
    2. Checks if a symptom with the same name already exists
       for the user (case-insensitive).
    3. Creates and saves the new symptom.
    4. Returns confirmation with symptom details.

    Parameters
    ----------
    payload : SymptomCreate
        Request body containing:
        - symptom_name : str
        - symptom_group : str
    db : Session
        Database session (FastAPI dependency).
    current_user : User
        Authenticated user (FastAPI dependency).

    Returns
    -------
    dict
        {
            "message": str,
            "symptom_id": int,
            "symptom_name": str,
            "symptom_group": str
        }
    """

    # --------------------------------------------------
    # Clean input (remove leading/trailing whitespace)
    # --------------------------------------------------
    name = payload.symptom_name.strip()

    # --------------------------------------------------
    # Check if symptom already exists for this user
    # Python-level comparison (encrypted values can't use SQL ilike)
    # --------------------------------------------------
    all_symptoms = db.query(Symptom).filter(Symptom.user_id == current_user.user_id).all()
    if any(s.symptom_name.lower() == name.lower() for s in all_symptoms):
        raise HTTPException(400, "Symptom already exists for this user")

    # --------------------------------------------------
    # Create new symptom record
    # --------------------------------------------------
    new_symptom = Symptom(
        user_id=current_user.user_id,
        symptom_name=name,
        symptom_group=payload.symptom_group
    )

    db.add(new_symptom)
    db.commit()
    db.refresh(new_symptom)

    # --------------------------------------------------
    # Return response
    # --------------------------------------------------
    return {
        "message": "Symptom created",
        "symptom_id": new_symptom.symptom_id,
        "symptom_name": new_symptom.symptom_name,
        "symptom_group": new_symptom.symptom_group
    }