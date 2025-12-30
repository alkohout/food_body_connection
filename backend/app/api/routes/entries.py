# app/api/routes/entries.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import AllergenLog, User
from app.api.routes.auth import get_current_user
from app.schemas import AllergenLogCreate

router = APIRouter(prefix="/entries", tags=["entries"])

@router.post("/entries/allergen")
def log_allergen(
    payload: AllergenLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
    return {"message": "Allergen logged", "allergen_log_id": new_entry.allergen_log_id}




