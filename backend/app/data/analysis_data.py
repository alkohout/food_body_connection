# app/data/analysis_data.py
from sqlalchemy.orm import Session
from datetime import timedelta
from app.models.table_class import AllergenLog, SymptomLog, Allergen, Symptom, Unit
import pandas as pd

def get_allergen_events(db: Session, user_id: int, allergen_name: str, start_dt=None, end_dt=None):
    """
    Retrieve allergen log events for a specific user and allergen.

    Parameters
    ----------
    db : Session
        Database session.
    user_id : int
        ID of the user.
    allergen_name : str
        Name of the allergen to retrieve.
    start_dt : datetime, optional
        Filter events occurring on or after this datetime.
    end_dt : datetime, optional
        Filter events occurring on or before this datetime.

    Returns
    -------
    list[AllergenLog]
        List of matching allergen log ORM objects.
        Returns empty list if allergen does not exist.
    """

    # Fetch allergen object for user
    allergen = (
        db.query(Allergen)
        .filter(Allergen.user_id == user_id)
        .filter(Allergen.allergen_name == allergen_name)
        .first()
    )

    if not allergen:
        return []

    # Build allergen log query
    query = db.query(AllergenLog).filter(
        AllergenLog.user_id == user_id,
        AllergenLog.allergen_id == allergen.allergen_id
    )

    if start_dt:
        query = query.filter(AllergenLog.date_time >= start_dt)
    if end_dt:
        query = query.filter(AllergenLog.date_time <= end_dt)

    return query.all()

def get_allergen_events_df(
    db: Session,
    user_id: int,
    allergen_name: str,
    start_dt=None,
    end_dt=None,
):
    """
    Retrieve allergen log events as a pandas DataFrame,
    including calculated standardized volume.

    Parameters
    ----------
    db : Session
        Database session.
    user_id : int
        ID of the user.
    allergen_name : str
        Name of the allergen to retrieve.
    start_dt : datetime, optional
        Filter events occurring on or after this datetime.
    end_dt : datetime, optional
        Filter events occurring on or before this datetime.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing:
        - date_time
        - allergen_id
        - allergen_name
        - quantity
        - volume
    """

    # --------------------------------------------------
    # Retrieve raw allergen events from helper function
    # --------------------------------------------------
    events = get_allergen_events(
        db,
        user_id,
        allergen_name,
        start_dt,
        end_dt
    )

    # --------------------------------------------------
    # Build DataFrame rows with volume calculation
    # --------------------------------------------------
    rows = []

    for e in events:

        # Extract recorded quantity
        quantity = e.quantity

        # Retrieve unit conversion information
        unit_obj = get_unit(db, unit_id=e.unit_id)
        conversion = unit_obj.unit_conversion if unit_obj else None

        # Calculate standardized volume if both values exist
        volume = quantity * conversion if quantity and conversion else None

        # Append structured row
        rows.append({
            "date_time": e.date_time,
            "allergen_id": e.allergen_id,
            "allergen_name": allergen_name,
            "quantity": quantity,
            "volume": volume,
        })

    # --------------------------------------------------
    # Convert rows to pandas DataFrame and return
    # --------------------------------------------------
    return pd.DataFrame(rows)

def get_symptom_events(
    db: Session,
    user_id: int,
    symptom_name: str,
    start_dt=None,
    end_dt=None
):
    """
    Retrieve symptom log events for a specific user and symptom.

    Parameters
    ----------
    db : Session
        Database session.
    user_id : int
        ID of the user.
    symptom_name : str
        Name of the symptom to retrieve.
    start_dt : datetime, optional
        Filter events occurring on or after this datetime.
    end_dt : datetime, optional
        Filter events occurring on or before this datetime.

    Returns
    -------
    list[SymptomLog]
        List of matching SymptomLog ORM objects.
        Returns empty list if the symptom does not exist.
    """

    # --------------------------------------------------
    # Fetch symptom object for this user
    # --------------------------------------------------
    symptom = (
        db.query(Symptom)
        .filter(Symptom.user_id == user_id)
        .filter(Symptom.symptom_name == symptom_name)
        .first()
    )

    # If symptom does not exist, return empty list
    if not symptom:
        return []

    # --------------------------------------------------
    # Build symptom log query
    # --------------------------------------------------
    query = db.query(SymptomLog).filter(
        SymptomLog.user_id == user_id,
        SymptomLog.symptom_id == symptom.symptom_id
    )

    # --------------------------------------------------
    # Apply optional datetime filters
    # --------------------------------------------------
    if start_dt:
        query = query.filter(SymptomLog.date_time >= start_dt)

    if end_dt:
        query = query.filter(SymptomLog.date_time <= end_dt)

    # --------------------------------------------------
    # Execute query and return results
    # --------------------------------------------------
    return query.all()

def get_all_symptom_events(
    db: Session,
    user_id: int,
    start_dt=None,
    end_dt=None
):
    """
    Retrieve all symptom log events for a user.

    Parameters
    ----------
    db : Session
        Database session.
    user_id : int
        ID of the user.
    start_dt : datetime, optional
        Filter events occurring on or after this datetime.
    end_dt : datetime, optional
        Filter events occurring on or before this datetime.
        Adds an additional 24 hours to include the full end day.

    Returns
    -------
    list[SymptomLog]
        List of SymptomLog ORM objects for the user.
    """

    # --------------------------------------------------
    # Build base query for user's symptom logs
    # --------------------------------------------------
    query = db.query(SymptomLog).filter(
        SymptomLog.user_id == user_id
    )

    # --------------------------------------------------
    # Apply optional datetime filters
    # --------------------------------------------------
    if start_dt:
        query = query.filter(SymptomLog.date_time >= start_dt)

    if end_dt:
        query = query.filter(
            SymptomLog.date_time <= end_dt + timedelta(hours=24)
        )

    # --------------------------------------------------
    # Execute query and return results
    # --------------------------------------------------
    return query.all()

def get_all_symptom_events_df(
    db: Session,
    user_id: int,
    symptom_name=None,
    symptom_group=None,
    start_dt=None,
    end_dt=None
):
    """
    Retrieve all symptom log events as a pandas DataFrame.

    Parameters
    ----------
    db : Session
        Database session.
    user_id : int
        ID of the user.
    symptom_name : str, optional
        Filter results by specific symptom name.
    symptom_group : str, optional
        Filter results by symptom group.
    start_dt : datetime, optional
        Filter events occurring on or after this datetime.
    end_dt : datetime, optional
        Filter events occurring on or before this datetime.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing:
        - date_time
        - symptom_id
        - symptom_name
        - symptom_group
        - symptom_intensity

        Returns empty DataFrame if no records found.
    """

    # --------------------------------------------------
    # Retrieve raw symptom events
    # --------------------------------------------------
    events = get_all_symptom_events(
        db,
        user_id,
        start_dt,
        end_dt
    )

    # --------------------------------------------------
    # Build DataFrame rows with symptom metadata
    # --------------------------------------------------
    rows = []

    for e in events:

        # Fetch symptom details
        symptom = (
            db.query(Symptom)
            .filter(Symptom.user_id == user_id)
            .filter(Symptom.symptom_id == e.symptom_id)
            .first()
        )

        rows.append({
            "date_time": e.date_time,
            "symptom_id": e.symptom_id,
            "symptom_name": symptom.symptom_name,
            "symptom_group": symptom.symptom_group,
            "symptom_intensity": e.symptom_intensity,
        })

    # --------------------------------------------------
    # Convert rows to DataFrame
    # --------------------------------------------------
    df = pd.DataFrame(rows)

    # Return early if empty
    if df.empty:
        return df

    # --------------------------------------------------
    # Ensure datetime column is timezone-aware
    # --------------------------------------------------
    df["date_time"] = pd.to_datetime(df["date_time"], utc=True)

    # --------------------------------------------------
    # Apply optional filters
    # --------------------------------------------------
    if symptom_name is not None:
        df = df[df["symptom_name"] == symptom_name]

    if symptom_group is not None:
        df = df[df["symptom_group"] == symptom_group]

    return df

def get_all_allergen_events(
    db: Session,
    user_id: int,
    start_dt=None,
    end_dt=None
):
    """
    Retrieve all allergen log events for a user.

    Parameters
    ----------
    db : Session
        Database session.
    user_id : int
        ID of the user.
    start_dt : datetime, optional
        Filter events occurring on or after this datetime.
    end_dt : datetime, optional
        Filter events occurring on or before this datetime.

    Returns
    -------
    list[AllergenLog]
        List of AllergenLog ORM objects matching the criteria.
    """

    # --------------------------------------------------
    # Build base query for user's allergen logs
    # --------------------------------------------------
    query = db.query(AllergenLog).filter(
        AllergenLog.user_id == user_id
    )

    # --------------------------------------------------
    # Apply optional datetime filters
    # --------------------------------------------------
    if start_dt:
        query = query.filter(AllergenLog.date_time >= start_dt)

    if end_dt:
        query = query.filter(AllergenLog.date_time <= end_dt)

    # --------------------------------------------------
    # Execute query and return results
    # --------------------------------------------------
    return query.all()

def get_all_allergen_events_df(
    db: Session,
    user_id: int,
    allergen_name=None,
    start_dt=None,
    end_dt=None
):
    """
    Retrieve all allergen log events as a pandas DataFrame.

    Parameters
    ----------
    db : Session
        Database session.
    user_id : int
        ID of the user.
    allergen_name : str, optional
        Filter results by allergen name.
    start_dt : datetime, optional
        Filter events occurring on or after this datetime.
    end_dt : datetime, optional
        Filter events occurring on or before this datetime.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing:
        - date_time
        - allergen_id
        - allergen_name
        - quantity
        - unit_id
        - volume

        Returns empty DataFrame if no records found.
    """

    # --------------------------------------------------
    # Retrieve raw allergen events
    # --------------------------------------------------
    events = get_all_allergen_events(
        db,
        user_id,
        start_dt,
        end_dt
    )

    # --------------------------------------------------
    # Build DataFrame rows with metadata and volume
    # --------------------------------------------------
    rows = []

    for e in events:

        # Fetch allergen metadata
        allergen = (
            db.query(Allergen)
            .filter(Allergen.user_id == user_id)
            .filter(Allergen.allergen_id == e.allergen_id)
            .first()
        )

        # Retrieve unit conversion
        unit_obj = get_unit(db, unit_id=e.unit_id)
        conversion = unit_obj.unit_conversion if unit_obj else None

        # Calculate standardized volume if possible
        volume = e.quantity * conversion if e.quantity and conversion else None

        rows.append({
            "date_time": e.date_time,
            "allergen_id": e.allergen_id,
            "allergen_name": allergen.allergen_name,
            "quantity": e.quantity,
            "unit_id": e.unit_id,
            "volume": volume,
        })

    # --------------------------------------------------
    # Convert rows to DataFrame
    # --------------------------------------------------
    df = pd.DataFrame(rows)

    # Return early if empty
    if df.empty:
        return df

    # --------------------------------------------------
    # Ensure datetime column is timezone-aware
    # --------------------------------------------------
    df["date_time"] = pd.to_datetime(df["date_time"], utc=True)

    # --------------------------------------------------
    # Apply optional allergen name filter
    # --------------------------------------------------
    if allergen_name is not None:
        df = df[df["allergen_name"] == allergen_name]

    return df

def get_unit(
    db: Session,
    unit_id=None,
    unit_name=None
):
    """
    Retrieve a Unit by ID or name.

    Parameters
    ----------
    db : Session
        Database session.
    unit_id : int, optional
        ID of the unit to retrieve.
    unit_name : str, optional
        Name of the unit to retrieve.

    Returns
    -------
    Unit or None
        Matching Unit ORM object if found.
        Returns None if no match or no identifier provided.
    """

    # --------------------------------------------------
    # Retrieve unit by name (priority if provided)
    # --------------------------------------------------
    if unit_name:
        query = db.query(Unit).filter(
            Unit.unit_name == unit_name
        )
        return query.first()

    # --------------------------------------------------
    # Retrieve unit by ID
    # --------------------------------------------------
    elif unit_id:
        query = db.query(Unit).filter(
            Unit.unit_id == unit_id
        )
        return query.first()

    # --------------------------------------------------
    # No identifier provided
    # --------------------------------------------------
    else:
        return None

def get_allergen(
    db: Session,
    user_id: int,
    allergen_id=None,
    allergen_name=None
):
    """
    Retrieve an Allergen for a specific user by ID or name.

    Parameters
    ----------
    db : Session
        Database session.
    user_id : int
        ID of the user who owns the allergen.
    allergen_id : int, optional
        ID of the allergen to retrieve.
    allergen_name : str, optional
        Name of the allergen to retrieve.

    Returns
    -------
    Allergen or None
        Matching Allergen ORM object if found.
        Returns None if no match or no identifier provided.
    """

    # --------------------------------------------------
    # Retrieve allergen by name (priority if provided)
    # --------------------------------------------------
    if allergen_name:
        query = (
            db.query(Allergen)
            .filter(Allergen.user_id == user_id)
            .filter(Allergen.allergen_name == allergen_name)
        )
        return query.first()

    # --------------------------------------------------
    # Retrieve allergen by ID
    # --------------------------------------------------
    elif allergen_id:
        query = (
            db.query(Allergen)
            .filter(Allergen.user_id == user_id)
            .filter(Allergen.allergen_id == allergen_id)
        )
        return query.first()

    # --------------------------------------------------
    # No identifier provided
    # --------------------------------------------------
    else:
        return None

def get_symptom(
    db: Session,
    user_id: int,
    symptom_id=None,
    symptom_name=None
):
    """
    Retrieve a Symptom for a specific user by ID or name.

    Parameters
    ----------
    db : Session
        Database session.
    user_id : int
        ID of the user who owns the symptom.
    symptom_id : int, optional
        ID of the symptom to retrieve.
    symptom_name : str, optional
        Name of the symptom to retrieve.

    Returns
    -------
    Symptom or None
        Matching Symptom ORM object if found.
        Returns None if no match or no identifier provided.
    """

    # --------------------------------------------------
    # Retrieve symptom by name (priority if provided)
    # --------------------------------------------------
    if symptom_name:
        query = (
            db.query(Symptom)
            .filter(Symptom.user_id == user_id)
            .filter(Symptom.symptom_name == symptom_name)
        )
        return query.first()

    # --------------------------------------------------
    # Retrieve symptom by ID
    # --------------------------------------------------
    elif symptom_id:
        query = (
            db.query(Symptom)
            .filter(Symptom.user_id == user_id)
            .filter(Symptom.symptom_id == symptom_id)
        )
        return query.first()

    # --------------------------------------------------
    # No identifier provided
    # --------------------------------------------------
    else:
        return None

def get_allergen_name_str(
    db: Session,
    user_id: int,
    allergen_id=None
):
    """
    Retrieve the allergen name as a string for a given allergen ID.

    Parameters
    ----------
    db : Session
        Database session.
    user_id : int
        ID of the user who owns the allergen.
    allergen_id : int, optional
        ID of the allergen.

    Returns
    -------
    str or None
        Allergen name if found.
        Returns None if allergen_id is not provided
        or no matching allergen exists.
    """

    # --------------------------------------------------
    # Retrieve allergen by ID
    # --------------------------------------------------
    if allergen_id:
        obj = (
            db.query(Allergen)
            .filter(Allergen.user_id == user_id)
            .filter(Allergen.allergen_id == allergen_id)
            .first()
        )
    else:
        return None

    # --------------------------------------------------
    # Return allergen name if object exists
    # --------------------------------------------------
    return obj.allergen_name if obj else None

