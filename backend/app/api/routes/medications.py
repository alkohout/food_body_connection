# app/api/routes/medications.py

from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.table_class import Medication, MedicationRegimen, User
from app.api.routes.auth import get_current_user
from app.schemas import (
    MedicationCreate, MedicationOut,
    MedicationRegimenCreate, MedicationRegimenUpdate, MedicationRegimenOut,
)

router = APIRouter(prefix="/medications", tags=["medications"])


# ── Medication names ──────────────────────────────────────────────────────────

@router.get("", response_model=list[MedicationOut])
def list_medications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Medication).filter(Medication.user_id == current_user.user_id).all()


@router.post("", response_model=MedicationOut, status_code=201)
def create_medication(
    payload: MedicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Python-level comparison (encrypted values can't be compared in SQL)
    all_meds = db.query(Medication).filter(Medication.user_id == current_user.user_id).all()
    existing = next((m for m in all_meds if m.medication_name == payload.medication_name), None)
    if existing:
        return existing

    med = Medication(user_id=current_user.user_id, medication_name=payload.medication_name)
    db.add(med)
    db.commit()
    db.refresh(med)
    return med


# ── Regimens ──────────────────────────────────────────────────────────────────

def _regimen_out(r: MedicationRegimen) -> dict:
    return {
        "regimen_id": r.regimen_id,
        "medication_id": r.medication_id,
        "medication_name": r.medication.medication_name,
        "dose": r.dose,
        "unit": r.unit,
        "note": r.note,
        "start_date": r.start_date,
        "end_date": r.end_date,
    }


@router.get("/regimens", response_model=list[MedicationRegimenOut])
def list_regimens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(MedicationRegimen)
        .filter(MedicationRegimen.user_id == current_user.user_id)
        .order_by(MedicationRegimen.start_date.desc())
        .all()
    )
    return [_regimen_out(r) for r in rows]


@router.get("/regimens/current", response_model=list[MedicationRegimenOut])
def current_regimens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(MedicationRegimen)
        .filter(
            MedicationRegimen.user_id == current_user.user_id,
            MedicationRegimen.end_date == None,  # noqa: E711
        )
        .order_by(MedicationRegimen.start_date)
        .all()
    )
    return [_regimen_out(r) for r in rows]


@router.post("/regimens", response_model=MedicationRegimenOut, status_code=201)
def create_regimen(
    payload: MedicationRegimenCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    med = (
        db.query(Medication)
        .filter(Medication.medication_id == payload.medication_id,
                Medication.user_id == current_user.user_id)
        .first()
    )
    if not med:
        raise HTTPException(400, "Invalid medication_id for this user")

    regimen = MedicationRegimen(
        user_id=current_user.user_id,
        medication_id=payload.medication_id,
        dose=payload.dose,
        unit=payload.unit,
        note=payload.note,
        start_date=payload.start_date,
        end_date=None,
    )
    db.add(regimen)
    db.commit()
    db.refresh(regimen)
    return _regimen_out(regimen)


@router.patch("/regimens/{regimen_id}", response_model=MedicationRegimenOut)
def update_regimen(
    regimen_id: int,
    payload: MedicationRegimenUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    regimen = (
        db.query(MedicationRegimen)
        .filter(MedicationRegimen.regimen_id == regimen_id,
                MedicationRegimen.user_id == current_user.user_id)
        .first()
    )
    if not regimen:
        raise HTTPException(404, "Regimen not found")

    if payload.dose is not None:
        regimen.dose = payload.dose
    if payload.unit is not None:
        regimen.unit = payload.unit
    if payload.note is not None:
        regimen.note = payload.note
    if payload.end_date is not None:
        regimen.end_date = payload.end_date

    db.commit()
    db.refresh(regimen)
    return _regimen_out(regimen)


@router.post("/regimens/{regimen_id}/change-dose", response_model=MedicationRegimenOut, status_code=201)
def change_dose(
    regimen_id: int,
    payload: MedicationRegimenCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Close an existing regimen and open a new one in a single call."""
    old = (
        db.query(MedicationRegimen)
        .filter(MedicationRegimen.regimen_id == regimen_id,
                MedicationRegimen.user_id == current_user.user_id)
        .first()
    )
    if not old:
        raise HTTPException(404, "Regimen not found")

    old.end_date = payload.start_date

    new_regimen = MedicationRegimen(
        user_id=current_user.user_id,
        medication_id=old.medication_id,
        dose=payload.dose,
        unit=payload.unit,
        note=payload.note if payload.note is not None else old.note,
        start_date=payload.start_date,
        end_date=None,
    )
    db.add(new_regimen)
    db.commit()
    db.refresh(new_regimen)
    return _regimen_out(new_regimen)
