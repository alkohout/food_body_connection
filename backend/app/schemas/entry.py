# app/schemas/entry.py

from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class AllergenLogCreate(BaseModel):
    allergen_id: int
    date_time: str  # or datetime
    quantity: Optional[float] = None
    unit_id: Optional[int] = None

class UnitOut(BaseModel):
    unit_id: int
    unit_name: str

    class Config:
        orm_mode = True