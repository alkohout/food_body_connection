# app/schemas/analysis.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class AnalysisScope(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class X(BaseModel):
    allergen_id: int
    allergen_name: str
    exposure_volume: float
    hours_since_exposure: float

class y(BaseModel):
    symptom_occurred: int
    symptom_max_intensity: Optional[int] = None
class AnalysisSummaryOut(BaseModel):
    total_exposures: int
    total_symptoms: int
    days_tracked: int
    avg_symptoms_per_day: float

class SymptomCount(BaseModel):
    symptom_id: int
    count: int
    avg_intensity: Optional[float] = None

class SymptomDistributionOut(BaseModel):
    total_symptoms: int
    distribution: List[SymptomCount]

class LagPoint(BaseModel):
    exposure_time: datetime
    symptom_time: datetime
    lag_hours: float
    intensity: int

class LagAnalysisOut(BaseModel):
    max_lag_hours: int
    lags: List[LagPoint]

class DoseResponsePoint(BaseModel):
    quantity: float
    unit_id: int
    symptom_count: int
    avg_intensity: Optional[float]

class DoseResponseOut(BaseModel):
    unit_id: int
    points: List[DoseResponsePoint]

