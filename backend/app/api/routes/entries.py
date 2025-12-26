# app/api/routes/entries.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Entry
from app.api.routes.auth import get_current_user
from app.schemas.entry import EntryCreate

router = APIRouter(prefix="/entries", tags=["entries"])

@router.post("", response_model=EntryCreate)
def create_entry(entry: EntryCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    new_entry = Entry(
        user_id=current_user.user_id,
        food=entry.food,
        symptom=entry.symptom,
        date=entry.date
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry

