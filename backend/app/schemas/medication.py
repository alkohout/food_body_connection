# app/schemas/medication.py

from pydantic import BaseModel
from datetime import date
from typing import Optional


class MedicationCreate(BaseModel):
    medication_name: str


class MedicationOut(BaseModel):
    medication_id: int
    medication_name: str

    model_config = {"from_attributes": True}


class MedicationRegimenCreate(BaseModel):
    medication_id: int
    dose: float
    unit: str = "mg"
    note: Optional[str] = None
    start_date: date


class MedicationRegimenUpdate(BaseModel):
    dose: Optional[float] = None
    unit: Optional[str] = None
    note: Optional[str] = None
    end_date: Optional[date] = None


class MedicationRegimenOut(BaseModel):
    regimen_id: int
    medication_id: int
    medication_name: str
    dose: float
    unit: str
    note: Optional[str]
    start_date: date
    end_date: Optional[date]

    model_config = {"from_attributes": True}
