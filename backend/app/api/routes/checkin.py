import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.database import get_db
from app.models.table_class import DailyCheckin, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/checkin", tags=["checkin"])

_ALL_VARS = ("mood", "sleep", "fatigue", "gut", "stress",
             "headache", "headache_overnight", "brain_fog", "tinnitus", "visual_disturbance",
             "training", "virus")


class CheckinPayload(BaseModel):
    checkin_date:     str
    period:           str
    checkin_datetime: Optional[str] = None   # ISO string from frontend local time
    mood:               Optional[int] = None
    sleep:              Optional[int] = None
    fatigue:            Optional[int] = None
    gut:                Optional[int] = None
    stress:             Optional[int] = None
    headache:             Optional[int] = None
    headache_overnight:   Optional[int] = None
    brain_fog:            Optional[int] = None
    tinnitus:           Optional[int] = None
    visual_disturbance: Optional[int] = None
    training:           Optional[int] = None
    virus:              Optional[int] = None


def _checkin_dict(c: DailyCheckin) -> dict:
    return {
        "exists": True,
        "period": c.period,
        **{v: getattr(c, v) for v in _ALL_VARS},
    }


@router.get("")
def get_checkin(
    date_str: str = Query(..., alias="date"),
    period: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(400, "Invalid date format — use YYYY-MM-DD")

    if period not in ("morning", "evening"):
        raise HTTPException(400, "period must be 'morning' or 'evening'")

    row = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == current_user.user_id,
        DailyCheckin.checkin_date == d,
        DailyCheckin.period == period,
    ).first()

    return _checkin_dict(row) if row else {"exists": False}


@router.post("")
def submit_checkin(
    body: CheckinPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.period not in ("morning", "evening"):
        raise HTTPException(400, "period must be 'morning' or 'evening'")

    try:
        checkin_date = date.fromisoformat(body.checkin_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format — use YYYY-MM-DD")

    existing = db.query(DailyCheckin).filter(
        DailyCheckin.user_id == current_user.user_id,
        DailyCheckin.checkin_date == checkin_date,
        DailyCheckin.period == body.period,
    ).first()

    parsed_dt = None
    if body.checkin_datetime:
        try:
            parsed_dt = datetime.fromisoformat(body.checkin_datetime.replace("Z", "+00:00"))
        except ValueError:
            pass

    if existing:
        for v in _ALL_VARS:
            val = getattr(body, v)
            if val is not None:
                setattr(existing, v, val)
        if parsed_dt:
            existing.checkin_datetime = parsed_dt
        existing.recorded_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "updated", "checkin_id": existing.checkin_id}

    row = DailyCheckin(
        user_id=current_user.user_id,
        checkin_date=checkin_date,
        period=body.period,
        checkin_datetime=parsed_dt,
        **{v: getattr(body, v) for v in _ALL_VARS},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"status": "created", "checkin_id": row.checkin_id}
