# app/schemas/entry.py

from typing_extensions import Annotated
from pydantic import BaseModel, Field 
from datetime import date, datetime
from typing import Optional

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
class AllergenLogUpdate(BaseModel):
    allergen_id: Optional[int] = None
    date_time: Optional[str] = None
    quantity: Optional[float] = None
    unit_id: Optional[int] = None

class SymptomLogUpdate(BaseModel):
    symptom_id: Optional[int] = None
    date_time: Optional[str] = None
    intensity: Optional[int] = None

class UnitOut(BaseModel):
    unit_id: int
    unit_name: str

    model_config = {
        "from_attributes": True
    }
