# app/schemas/training.py

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Side = Literal["left", "right"]


# ── Exercises ────────────────────────────────────────────────────────────────

class ExerciseCreate(BaseModel):
    exercise_name: str
    category: str = "strength"
    target: Optional[str] = None
    equipment: str = "bodyweight"
    is_unilateral: bool = False
    is_isometric: bool = False
    form_cues: Optional[str] = None
    video_url: Optional[str] = None


class ExerciseOut(BaseModel):
    exercise_id: int
    exercise_name: str
    category: str
    target: Optional[str]
    equipment: str
    is_unilateral: bool
    is_isometric: bool
    form_cues: Optional[str]
    video_url: Optional[str]
    is_archived: bool

    model_config = {"from_attributes": True}


# ── Sets ─────────────────────────────────────────────────────────────────────

class SetCreate(BaseModel):
    exercise_id: int
    set_number: int = 1
    reps: Optional[int] = Field(default=None, ge=0)
    weight_kg: Optional[float] = Field(default=None, ge=0)
    band_kg: Optional[float] = Field(default=None, ge=0)
    hold_seconds: Optional[int] = Field(default=None, ge=0)
    side: Optional[Side] = None
    rpe: Optional[int] = Field(default=None, ge=1, le=10)
    # Bounds are enforced here as well as by the database check constraint, so
    # a bad value is a 422 naming the field rather than a 500 from psycopg2.
    pain: Optional[int] = Field(default=None, ge=0, le=10)


class SetOut(BaseModel):
    set_id: int
    session_id: int
    exercise_id: int
    exercise_name: str
    set_number: int
    reps: Optional[int]
    weight_kg: Optional[float]
    band_kg: Optional[float]
    hold_seconds: Optional[int]
    side: Optional[str]
    rpe: Optional[int]
    pain: Optional[int]


# ── Sessions ─────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    date_time: Optional[datetime] = None
    session_type: str = "strength"
    duration_min: Optional[int] = Field(default=None, ge=0)
    overall_rpe: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None


class SessionUpdate(BaseModel):
    session_type: Optional[str] = None
    duration_min: Optional[int] = Field(default=None, ge=0)
    overall_rpe: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None
    # Recorded the day after, which is the point of it.
    next_day_knee: Optional[int] = Field(default=None, ge=0, le=10)


class SessionOut(BaseModel):
    session_id: int
    date_time: datetime
    session_type: str
    duration_min: Optional[int]
    overall_rpe: Optional[int]
    notes: Optional[str]
    next_day_knee: Optional[int]
    sets: list[SetOut] = []


# ── Profile ──────────────────────────────────────────────────────────────────

class TrainingProfileIn(BaseModel):
    goals: Optional[str] = None
    constraints: Optional[str] = None
    dumbbell_bar_kg: Optional[float] = Field(default=None, ge=0)
    barbell_bar_kg: Optional[float] = Field(default=None, ge=0)
    equipment_json: Optional[str] = None


class TrainingProfileOut(BaseModel):
    goals: Optional[str]
    constraints: Optional[str]
    dumbbell_bar_kg: Optional[float]
    barbell_bar_kg: Optional[float]
    equipment_json: Optional[str]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}
