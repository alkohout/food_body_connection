# app/schemas/entry.py

from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


class AllergenLogCreate(BaseModel):
    allergen_id: int
    date_time: str  # or datetime

