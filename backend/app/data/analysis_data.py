# app/data/analysis_data.py
from sqlalchemy.orm import Session
from datetime import timedelta
from app.models.table_class import AllergenLog, SymptomLog, Allergen, Symptom, Unit
import pandas as pd

def get_allergen_events(db: Session, user_id: int, allergen_name: str, start_dt=None, end_dt=None):
    allergen = db.query(Allergen).filter(Allergen.allergen_name == allergen_name).first()
    if not allergen:
        return [] 

    query = db.query(AllergenLog).filter(
        AllergenLog.user_id == user_id,
        AllergenLog.allergen_id == allergen.allergen_id
    )
    if start_dt:
        query = query.filter(AllergenLog.date_time >= start_dt)
    if end_dt:
        query = query.filter(AllergenLog.date_time <= end_dt)

    events = query.all()
    return events

def get_allergen_events_df(
    db: Session,
    user_id: int,
    allergen_name: str,
    start_dt=None,
    end_dt=None,
):
    events = get_allergen_events(db, user_id, allergen_name, start_dt, end_dt)

    # --- Build DataFrame with volume calculation ---
    rows = []
    for e in events:
        quantity = e.quantity
        unit_id = e.unit_id 
        unit_obj = get_unit(db, unit_id=unit_id)
        conversion = unit_obj.unit_conversion if unit_obj else None
        volume = quantity * conversion if quantity and conversion else None

        rows.append({
            "date_time": e.date_time,
            "allergen_id": e.allergen_id,
            "allergen_name": allergen_name,
            "quantity": quantity,
            "volume": volume,
        })

    df = pd.DataFrame(rows)

    return df

def get_symptom_events(db: Session, user_id: int, symptom_name: str, start_dt=None, end_dt=None):
    symptom = db.query(Symptom).filter(Symptom.symptom_name == symptom_name).first()
    if not symptom:
        return []

    query = db.query(SymptomLog).filter(
        SymptomLog.user_id == user_id,
        SymptomLog.symptom_id == symptom.symptom_id
    )
    if start_dt:
        query = query.filter(SymptomLog.date_time >= start_dt)
    if end_dt:
        query = query.filter(SymptomLog.date_time <= end_dt)

    events = query.all()
    return events

def get_all_symptom_events(db: Session, user_id: int, start_dt=None, end_dt=None):
    query = db.query(SymptomLog).filter(SymptomLog.user_id == user_id)
    if start_dt:
        query = query.filter(SymptomLog.date_time >= start_dt)
    if end_dt:
        query = query.filter(SymptomLog.date_time <= end_dt + timedelta(hours=24))
    return query.all()

def get_all_symptom_events_df(db: Session, user_id: int, symptom_name=None, symptom_group=None, start_dt=None, end_dt=None):

    events = get_all_symptom_events(db, user_id, start_dt, end_dt)

    rows = []
    for e in events:
        symptom = db.query(Symptom).filter(Symptom.symptom_id == e.symptom_id).first()
        rows.append({
            "date_time": e.date_time,
            "symptom_id": e.symptom_id,
            "symptom_name": symptom.symptom_name,
            "symptom_group": symptom.symptom_group,
            "symptom_intensity": e.symptom_intensity,
        })        

    df = pd.DataFrame(rows)
    df["date_time"] = pd.to_datetime(df["date_time"], utc=True)

    if symptom_name is not None:
        df = df[df['symptom_name'] == symptom_name]

    if symptom_group is not None:
        df = df[df['symptom_group'] == symptom_group]

    return df

def get_all_allergen_events(db: Session, user_id: int, start_dt=None, end_dt=None):
    query = db.query(AllergenLog).filter(AllergenLog.user_id == user_id)
    if start_dt:
        query = query.filter(AllergenLog.date_time >= start_dt)
    if end_dt:
        query = query.filter(AllergenLog.date_time <= end_dt)
    return query.all()

def get_all_allergen_events_df(db: Session, user_id: int, allergen_name=None,start_dt=None, end_dt=None):

    events = get_all_allergen_events(db, user_id, start_dt, end_dt)

    rows = []
    for e in events:
        allergen = db.query(Allergen).filter(Allergen.allergen_id == e.allergen_id).first()
        unit_obj = get_unit(db, unit_id=e.unit_id)
        conversion = unit_obj.unit_conversion if unit_obj else None
        volume = e.quantity * conversion if e.quantity and conversion else None
        rows.append({
            "date_time": e.date_time,
            "allergen_id": e.allergen_id,
            "allergen_name": allergen.allergen_name,
            "quantity": e.quantity,
            "unit_id": e.unit_id,
            "volume": volume,
        })        

    df = pd.DataFrame(rows)
    df["date_time"] = pd.to_datetime(df["date_time"], utc=True)

    if allergen_name is not None:
        df = df[df['allergen_name'] == allergen_name]

    return df

def get_unit(db: Session, unit_id=None, unit_name=None):
    if unit_name:
        query = db.query(Unit).filter(Unit.unit_name == unit_name)
        return query.first()
    elif unit_id:
        query = db.query(Unit).filter(Unit.unit_id == unit_id)
        return query.first()
    else:
        return None

def get_allergen(db: Session, allergen_id=None, allergen_name=None):
    if allergen_name:
        query = db.query(Allergen).filter(Allergen.allergen_name == allergen_name)
        return query.first()
    elif allergen_id:
        query = db.query(Allergen).filter(Allergen.allergen_id == allergen_id)
        return query.first()
    else:
        return None

def get_allergen_df(db: Session, user_id: int):

    events = get_allergen(db, user_id)

    rows = []
    for e in events:
        rows.append({
            "allergen_id": e.allergen_id,
            "allergen_name": e.allergen_name,
        })        

    df = pd.DataFrame(rows)

    return df

def get_symptom(db: Session, symptom_id=None, symptom_name=None):
    if symptom_name:
        query = db.query(Symptom).filter(Symptom.symptom_name == symptom_name)
        return query.first()
    elif symptom_id:
        query = db.query(Symptom).filter(Symptom.symptom_id == symptom_id)
        return query.first()
    else:
        return None
