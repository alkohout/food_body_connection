# app/api/routes/entries.py

from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.plot_cache import invalidate_cache
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import AllergenLog, SymptomLog, User, Allergen, Symptom, Unit
from app.api.routes.auth import get_current_user
from app.schemas import AllergenLogCreate, SymptomLogCreate, AllergenLogUpdate, SymptomLogUpdate

router = APIRouter(prefix="/entries", tags=["entries"])

@router.post("/allergens")
def log_allergen(
    payload: AllergenLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log a new allergen exposure event for the current user.

    The endpoint:
    1. Validates that the allergen belongs to the authenticated user.
    2. Creates a new allergen log entry.
    3. Saves the record to the database.
    4. Returns confirmation with the new log ID.

    Parameters
    ----------
    payload : AllergenLogCreate
        Request body containing:
        - allergen_id : int
        - date_time : datetime
        - quantity : float
        - unit_id : int
    current_user : User
        Authenticated user (FastAPI dependency).
    db : Session
        Database session (FastAPI dependency).

    Returns
    -------
    dict
        {
            "message": str,
            "allergen_log_id": int
        }
    """

    # --------------------------------------------------
    # Validate allergen belongs to current user
    # --------------------------------------------------
    allergen = (
        db.query(Allergen)
        .filter(Allergen.allergen_id == payload.allergen_id)
        .filter(Allergen.user_id == current_user.user_id)
        .first()
    )

    if not allergen:
        raise HTTPException(
            status_code=400,
            detail="Invalid allergen_id: this allergen does not belong to the current user"
        )

    # --------------------------------------------------
    # Create new allergen log entry
    # --------------------------------------------------
    new_entry = AllergenLog(
        user_id=current_user.user_id,
        allergen_id=payload.allergen_id,
        date_time=payload.date_time,
        quantity=payload.quantity,
        unit_id=payload.unit_id
    )

    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    uid = current_user.user_id
    invalidate_cache(f"allergen_rank_{uid}")
    invalidate_cache(f"triptan_monthly_{uid}")

    _maybe_imply_triptan_symptoms(db, current_user.user_id, allergen, payload.date_time)

    return {
        "message": "Allergen logged",
        "allergen_log_id": new_entry.allergen_log_id
    }


# Allergen names are Fernet-encrypted with a random IV so SQL filtering won't
# match — load all and compare in Python instead.
_TRIPTAN_USER_ID = 4
_TRIPTAN_IMPLIED = [
    ("Headache", 2),            # 2 = Bad (triptan was required)
    ("Visual disturbance", 1),  # 1 = Mild (usually present)
]


def _maybe_imply_triptan_symptoms(db, user_id, allergen, date_time):
    if user_id != _TRIPTAN_USER_ID or allergen.allergen_name.lower() != "triptan":
        return

    all_symptoms = db.query(Symptom).filter(Symptom.user_id == user_id).all()
    symptom_map = {s.symptom_name.lower(): s for s in all_symptoms}

    added = False
    for sym_name, intensity in _TRIPTAN_IMPLIED:
        sym = symptom_map.get(sym_name.lower())
        if not sym:
            continue
        already_logged = (
            db.query(SymptomLog)
            .filter(
                SymptomLog.user_id == user_id,
                SymptomLog.symptom_id == sym.symptom_id,
                SymptomLog.date_time == date_time,
            )
            .first()
        )
        if not already_logged:
            db.add(SymptomLog(
                user_id=user_id,
                symptom_id=sym.symptom_id,
                date_time=date_time,
                symptom_intensity=intensity,
            ))
            added = True

    if added:
        db.commit()
        invalidate_cache(f"symptom_calendar_{user_id}")

@router.post("/symptoms")
def log_symptom(
    payload: SymptomLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log a new symptom event for the current user.

    The endpoint:
    1. Validates that the symptom belongs to the authenticated user.
    2. Creates a new symptom log entry.
    3. Saves the record to the database.
    4. Returns confirmation with the new log ID.

    Parameters
    ----------
    payload : SymptomLogCreate
        Request body containing:
        - symptom_id : int
        - date_time : datetime
        - intensity : int
    current_user : User
        Authenticated user (FastAPI dependency).
    db : Session
        Database session (FastAPI dependency).

    Returns
    -------
    dict
        {
            "message": str,
            "symptom_log_id": int
        }
    """

    # --------------------------------------------------
    # Validate symptom belongs to current user
    # --------------------------------------------------
    symptom = (
        db.query(Symptom)
        .filter(Symptom.symptom_id == payload.symptom_id)
        .filter(Symptom.user_id == current_user.user_id)
        .first()
    )

    if not symptom:
        raise HTTPException(400, "Invalid symptom ID for this user")

    # --------------------------------------------------
    # Create new symptom log entry
    # --------------------------------------------------
    new_entry = SymptomLog(
        user_id=current_user.user_id,
        symptom_id=payload.symptom_id,
        date_time=payload.date_time,
        symptom_intensity=payload.intensity,
    )

    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    invalidate_cache(f"symptom_calendar_{current_user.user_id}")

    return {
        "message": "Symptom logged",
        "symptom_log_id": new_entry.symptom_log_id
    }


@router.get("/allergens")
def get_allergen_logs(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(AllergenLog, Allergen, Unit)
        .join(Allergen, Allergen.allergen_id == AllergenLog.allergen_id)
        .outerjoin(Unit, Unit.unit_id == AllergenLog.unit_id)
        .filter(AllergenLog.user_id == current_user.user_id)
        .order_by(AllergenLog.date_time.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "allergen_log_id": log.allergen_log_id,
            "allergen_id": log.allergen_id,
            "allergen_name": allergen.allergen_name,
            "date_time": log.date_time.isoformat(),
            "quantity": log.quantity,
            "unit_id": log.unit_id,
            "unit_name": unit.unit_name if unit else None,
        }
        for log, allergen, unit in logs
    ]


@router.get("/symptoms")
def get_symptom_logs(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(SymptomLog, Symptom)
        .join(Symptom, Symptom.symptom_id == SymptomLog.symptom_id)
        .filter(SymptomLog.user_id == current_user.user_id)
        .order_by(SymptomLog.date_time.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "symptom_log_id": log.symptom_log_id,
            "symptom_id": log.symptom_id,
            "symptom_name": symptom.symptom_name,
            "date_time": log.date_time.isoformat(),
            "intensity": log.symptom_intensity,
        }
        for log, symptom in logs
    ]


@router.patch("/allergens/{allergen_log_id}")
def update_allergen_log(
    allergen_log_id: int,
    payload: AllergenLogUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = (
        db.query(AllergenLog)
        .filter(
            AllergenLog.allergen_log_id == allergen_log_id,
            AllergenLog.user_id == current_user.user_id,
        )
        .first()
    )
    if not log:
        raise HTTPException(404, "Allergen log not found")

    if payload.allergen_id is not None:
        log.allergen_id = payload.allergen_id
    if payload.date_time is not None:
        log.date_time = payload.date_time
    log.quantity = payload.quantity
    log.unit_id = payload.unit_id

    db.commit()
    db.refresh(log)
    return {"message": "Updated", "allergen_log_id": log.allergen_log_id}


@router.patch("/symptoms/{symptom_log_id}")
def update_symptom_log(
    symptom_log_id: int,
    payload: SymptomLogUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = (
        db.query(SymptomLog)
        .filter(
            SymptomLog.symptom_log_id == symptom_log_id,
            SymptomLog.user_id == current_user.user_id,
        )
        .first()
    )
    if not log:
        raise HTTPException(404, "Symptom log not found")

    if payload.symptom_id is not None:
        log.symptom_id = payload.symptom_id
    if payload.date_time is not None:
        log.date_time = payload.date_time
    if payload.intensity is not None:
        log.symptom_intensity = payload.intensity

    db.commit()
    db.refresh(log)
    return {"message": "Updated", "symptom_log_id": log.symptom_log_id}

