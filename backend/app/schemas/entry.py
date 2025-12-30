# app/schemas/entry.py

from pydantic import BaseModel, Field 
from datetime import date, datetime
from typing import Optional
from typing_extensions import Annotated

class AllergenLogCreate(BaseModel):
    allergen_id: int
    date_time: str  # or datetime
    quantity: Optional[float] = None
    unit_id: Optional[int] = None

Intensity = Annotated[int, Field(ge=0, le=3)]
class SymptomLogCreate(BaseModel):
    symptom_id: int
    date_time: str  # or datetime
    intensity: Intensity
class UnitOut(BaseModel):
    unit_id: int
    unit_name: str

    class Config:
        orm_mode = True