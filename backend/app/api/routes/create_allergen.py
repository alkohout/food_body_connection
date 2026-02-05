from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.table_class import Allergen
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/allergens", tags=["allergens"])

class AllergenCreate(BaseModel):
    allergen_name: str

@router.post("")
def create_allergen(
    payload: AllergenCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    name = payload.allergen_name.strip()

    # Check if exists
    existing = (
        db.query(Allergen)
        .filter(Allergen.user_id == current_user.user_id)
        .filter(Allergen.allergen_name.ilike(name))
        .first()
    )

    if existing:
        raise HTTPException(400, "Allergen already exists for this user")

    new_allergen = Allergen(
        user_id=current_user.user_id,
        allergen_name=name
    )

    db.add(new_allergen)
    db.commit()
    db.refresh(new_allergen)

    return {
        "message": "Allergen created",
        "allergen_id": new_allergen.allergen_id,
        "allergen_name": new_allergen.allergen_name
    }