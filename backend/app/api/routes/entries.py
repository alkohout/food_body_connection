# app/api/routes/entries.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.schemas.entry import AllergenEntryCreate
from app.models.table_class import AllergenLog

router = APIRouter(prefix="/entries", tags=["entries"])

@router.post("", response_model=EntryRead)
def allergen_entry_create(
    entry: AllergenEntryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    new_log = AllergenLog(
        user_id=current_user.user_id,
        date_time=entry.date_time,
        allergen_id=entry.allergen_id,
        quantity = entry.quantity,
        unit_id = entry.unit_id
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log

