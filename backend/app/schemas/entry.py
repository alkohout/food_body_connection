# app/schemas/entry.py

from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class AllergenEntryCreate(BaseModel):
    date_time: datetime
    allergen_id: int
    quantity: Optional[float] = None
    unit_id: Optional[int] = None
