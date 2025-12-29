# app/api/routes/entries.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import AllergenLog
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/entries", tags=["entries"])

@router.post("/allergen")
def log_allergen(
    allergen_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    entry = AllergenLog(
        user_id=user.user_id,
        allergen_id=allergen_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {"status": "ok", "allergen_log_id": entry.allergen_log_id}


