from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.table_class import Symptom
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/symptoms", tags=["symptoms"])

class SymptomCreate(BaseModel):
    symptom_name: str
    symptom_group: str | None = None

@router.post("")
def create_symptom(
    payload: SymptomCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    name = payload.symptom_name.strip()

    # Check if exists
    existing = (
        db.query(Symptom)
        .filter(Symptom.user_id == current_user.user_id)
        .filter(Symptom.symptom_name.ilike(name))
        .first()
    )

    if existing:
        raise HTTPException(400, "Symptom already exists for this user")

    new_symptom = Symptom(
        user_id=current_user.user_id,
        symptom_name=name,
        symptom_group=payload.symptom_group
    )

    db.add(new_symptom)
    db.commit()
    db.refresh(new_symptom)

    return {
        "message": "Symptom created",
        "symptom_id": new_symptom.symptom_id,
        "symptom_name": new_symptom.symptom_name,
        "symptom_group": new_symptom.symptom_group
    }