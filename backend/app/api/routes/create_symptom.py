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

class SymptomUpdate(BaseModel):
    symptom_name: Optional[str] = None
    symptom_group: Optional[str] = None


@router.patch("/{symptom_id}")
def update_symptom(
    symptom_id: int,
    payload: SymptomUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Rename a symptom or set its group.

    Neither could be changed once created, so a symptom named in a hurry — or
    created without a group, which quietly excludes it from the grouped
    analysis — was stuck that way. Renaming keeps every existing log attached,
    since logs reference the id rather than the text.
    """
    symptom = db.query(Symptom).filter(
        Symptom.symptom_id == symptom_id,
        Symptom.user_id == current_user.user_id,
    ).first()
    if symptom is None:
        raise HTTPException(404, "Symptom not found")

    if payload.symptom_name is not None:
        name = payload.symptom_name.strip()
        if not name:
            raise HTTPException(400, "Symptom name cannot be empty")
        # Encrypted values cannot be compared in SQL, so the clash check is a
        # Python scan, as it is everywhere else in this app.
        clash = next(
            (s for s in db.query(Symptom).filter(
                Symptom.user_id == current_user.user_id).all()
             if s.symptom_id != symptom_id
             and (s.symptom_name or "").strip().lower() == name.lower()),
            None,
        )
        if clash:
            raise HTTPException(400, f"You already track a symptom called '{name}'")
        symptom.symptom_name = name

    if payload.symptom_group is not None:
        symptom.symptom_group = payload.symptom_group.strip() or None

    db.commit()
    db.refresh(symptom)
    return {
        "symptom_id": symptom.symptom_id,
        "symptom_name": symptom.symptom_name,
        "symptom_group": symptom.symptom_group,
    }
