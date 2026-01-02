# app/data/analysis_data.py
from sqlalchemy.orm import Session
from datetime import timedelta
from app.models.table_class import AllergenLog, SymptomLog, Allergen, Symptom, Unit

def get_allergen_events(db: Session, user_id: int, allergen_name: str, start_dt=None, end_dt=None):
    allergen = db.query(Allergen).filter(Allergen.allergen_name == allergen_name).first()
    if not allergen:
        return [], None

    query = db.query(AllergenLog).filter(
        AllergenLog.user_id == user_id,
        AllergenLog.allergen_id == allergen.allergen_id
    )
    if start_dt:
        query = query.filter(AllergenLog.date_time >= start_dt)
    if end_dt:
        query = query.filter(AllergenLog.date_time <= end_dt)

    events = query.all()
    return events, allergen

def get_symptom_events(db: Session, user_id: int, symptom_name: str, start_dt=None, end_dt=None):
    symptom = db.query(Symptom).filter(Symptom.symptom_name == symptom_name).first()
    if not symptom:
        return [], None

    query = db.query(SymptomLog).filter(
        SymptomLog.user_id == user_id,
        SymptomLog.symptom_id == symptom.symptom_id
    )
    if start_dt:
        query = query.filter(SymptomLog.date_time >= start_dt)
    if end_dt:
        query = query.filter(SymptomLog.date_time <= end_dt)

    events = query.all()
    return events, symptom

def get_all_symptom_events(db: Session, user_id: int, start_dt=None, end_dt=None):
    query = db.query(SymptomLog).filter(SymptomLog.user_id == user_id)
    if start_dt:
        query = query.filter(SymptomLog.date_time >= start_dt)
    if end_dt:
        query = query.filter(SymptomLog.date_time <= end_dt + timedelta(hours=24))
    return query.all()

def get_all_allergen_events(db: Session, user_id: int, start_dt=None, end_dt=None):
    query = db.query(AllergenLog).filter(AllergenLog.user_id == user_id)
    if start_dt:
        query = query.filter(AllergenLog.date_time >= start_dt)
    if end_dt:
        query = query.filter(AllergenLog.date_time <= end_dt)
    return query.all()

def get_unit(db: Session, unit_id=None, unit_name=None):
    if unit_name:
        query = db.query(Unit).filter(Unit.unit_name == unit_name)
        return query.first()
    elif unit_id:
        query = db.query(Unit).filter(Unit.unit_id == unit_id)
        return query.first()
    else:
        return None
