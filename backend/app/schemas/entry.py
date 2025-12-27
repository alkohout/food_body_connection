# app/schemas/entry.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AllergenEntryCreate(BaseModel):
    date_time: datetime
    allergen_id: int
    quantity: Optional[float] = None
    unit_id: Optional[int] = None

class EntryRead(BaseModel):
    id: int
    allergen: str
    symptom: Optional[str]
    date: date

    class Config:
        orm_mode = True
