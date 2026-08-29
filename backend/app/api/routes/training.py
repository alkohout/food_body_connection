# app/api/routes/training.py
"""Training log: exercises, sessions, sets and the training profile.

Every lookup filters on the authenticated user, and a session or set reached by
id is re-checked against that user before it is touched — an id in a URL is not
proof of ownership.
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.analysis.training_program import (
    ALWAYS_AVAILABLE, available_equipment, build_session, program,
    user_focus, visible_programs,
)
from app.data.programs import DEFAULT_FOCUS, PROGRAMS
from app.data.exercise_library import LIBRARY
from app.database import get_db
from app.models.table_class import (
    Exercise, PracticeItem, SetLog, TrainingProfile, User, WorkoutSession,
)
from app.schemas import (
    ExerciseCreate, ExerciseOut,
    SetCreate, SetUpdate, SessionCreate, SessionUpdate, PracticeItemIn,
    TrainingProfileIn, TrainingProfileOut,
)

router = APIRouter(prefix="/training", tags=["training"])


# ── Exercises ────────────────────────────────────────────────────────────────

@router.get("/exercises", response_model=list[ExerciseOut])
def list_exercises(
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Exercise).filter(Exercise.user_id == current_user.user_id)
    if not include_archived:
        q = q.filter(Exercise.is_archived.is_(False))
    # Names are encrypted, so ordering has to happen after decryption.
    return sorted(q.all(), key=lambda e: (e.target or "", e.exercise_name.lower()))


@router.post("/exercises", response_model=ExerciseOut, status_code=201)
def create_exercise(
    payload: ExerciseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Encrypted values cannot be compared in SQL, so the duplicate check is a
    # Python scan, as it is for allergens and medications.
    existing = next(
        (e for e in db.query(Exercise).filter(Exercise.user_id == current_user.user_id).all()
         if e.exercise_name.strip().lower() == payload.exercise_name.strip().lower()),
        None,
    )
    if existing:
        return existing

    ex = Exercise(user_id=current_user.user_id, **payload.model_dump())
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex


@router.post("/exercises/seed")
def seed_exercises(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add any catalogue exercise the user does not already have.

    Idempotent: safe to call repeatedly, and it never overwrites an exercise
    the user has edited.
    """
    have = {
        e.exercise_name.strip().lower()
        for e in db.query(Exercise).filter(Exercise.user_id == current_user.user_id).all()
    }
    added = 0
    for name, category, target, equipment, uni, iso, cues, url in LIBRARY:
        if name.strip().lower() in have:
            continue
        db.add(Exercise(
            user_id=current_user.user_id, exercise_name=name, category=category,
            target=target, equipment=equipment, is_unilateral=uni,
            is_isometric=iso, form_cues=cues, video_url=url,
        ))
        added += 1
    db.commit()
    return {"added": added, "already_present": len(have), "catalogue": len(LIBRARY)}


# ── Sessions ─────────────────────────────────────────────────────────────────

def _session_out(s: WorkoutSession) -> dict:
    return {
        "session_id": s.session_id,
        "date_time": s.date_time,
        "session_type": s.session_type,
        "duration_min": s.duration_min,
        "overall_rpe": s.overall_rpe,
        "notes": s.notes,
        "next_day_knee": s.next_day_knee,
        "sets": [
            {
                "set_id": st.set_id,
                "session_id": st.session_id,
                "exercise_id": st.exercise_id,
                "exercise_name": st.exercise.exercise_name if st.exercise else None,
                "set_number": st.set_number,
                "reps": st.reps,
                "weight_kg": st.weight_kg,
                "band_kg": st.band_kg,
                "hold_seconds": st.hold_seconds,
                "side": st.side,
                "rpe": st.rpe,
                "pain": st.pain,
            }
            for st in sorted(s.sets, key=lambda x: (x.exercise_id, x.set_number, x.set_id))
        ],
    }


def _owned_session(db, user_id: int, session_id: int) -> WorkoutSession:
    s = db.query(WorkoutSession).filter(
        WorkoutSession.session_id == session_id,
        WorkoutSession.user_id == user_id,
    ).first()
    if s is None:
        # 404 rather than 403: whether someone else's session exists is not
        # this user's business.
        raise HTTPException(status_code=404, detail="Session not found.")
    return s


@router.get("/sessions")
def list_sessions(
    limit: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == current_user.user_id)
        .order_by(WorkoutSession.date_time.desc())
        .limit(limit)
        .all()
    )
    return [_session_out(s) for s in rows]


@router.post("/sessions", status_code=201)
def create_session(
    payload: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = WorkoutSession(
        user_id=current_user.user_id,
        date_time=payload.date_time or datetime.now(timezone.utc),
        session_type=payload.session_type,
        duration_min=payload.duration_min,
        overall_rpe=payload.overall_rpe,
        notes=payload.notes,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _session_out(s)


@router.patch("/sessions/{session_id}")
def update_session(
    session_id: int,
    payload: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = _owned_session(db, current_user.user_id, session_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return _session_out(s)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.delete(_owned_session(db, current_user.user_id, session_id))
    db.commit()


# ── Sets ─────────────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/sets", status_code=201)
def add_set(
    session_id: int,
    payload: SetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned_session(db, current_user.user_id, session_id)

    ex = db.query(Exercise).filter(
        Exercise.exercise_id == payload.exercise_id,
        Exercise.user_id == current_user.user_id,
    ).first()
    if ex is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")

    st = SetLog(
        user_id=current_user.user_id,
        session_id=session_id,
        **payload.model_dump(),
    )
    db.add(st)
    db.commit()
    db.refresh(st)
    return _session_out(_owned_session(db, current_user.user_id, session_id))


@router.patch("/sets/{set_id}")
def update_set(
    set_id: int,
    payload: SetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Correct a logged set. Mistyped a weight, logged the wrong side, and so on."""
    st = db.query(SetLog).filter(
        SetLog.set_id == set_id, SetLog.user_id == current_user.user_id
    ).first()
    if st is None:
        raise HTTPException(status_code=404, detail="Set not found.")

    # exclude_unset, not exclude_none: sending an explicit null clears a value,
    # while leaving the field out leaves it alone.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(st, field, value)
    db.commit()
    return _session_out(_owned_session(db, current_user.user_id, st.session_id))


@router.delete("/sets/{set_id}", status_code=204)
def delete_set(
    set_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    st = db.query(SetLog).filter(
        SetLog.set_id == set_id, SetLog.user_id == current_user.user_id
    ).first()
    if st is None:
        raise HTTPException(status_code=404, detail="Set not found.")
    db.delete(st)
    db.commit()


@router.get("/focus")
def list_focus(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The programmes on offer, and which one is selected."""
    current = user_focus(db, current_user.user_id)
    profile = db.query(TrainingProfile).filter(
        TrainingProfile.user_id == current_user.user_id).first()
    return {
        "current": current,
        "options": [
            {"key": key, "label": spec["label"], "blurb": spec["blurb"],
             "selected": key == current}
            for key, spec in visible_programs(profile).items()
        ],
    }


@router.put("/focus")
def set_focus(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Switch programme. Logged history is kept: it is the same exercises and
    the same progression rules, only a different selection of them."""
    focus = str(payload.get("focus") or "")
    p = db.query(TrainingProfile).filter(
        TrainingProfile.user_id == current_user.user_id).first()
    allowed = visible_programs(p)
    if focus not in allowed:
        # A private programme reads as unknown rather than forbidden: there is
        # no reason to tell one account what another one is using.
        raise HTTPException(
            status_code=400,
            detail=f"Unknown programme. Choose one of: {', '.join(allowed)}.",
        )
    if p is None:
        p = TrainingProfile(user_id=current_user.user_id)
        db.add(p)
    p.focus = focus
    db.commit()
    return {"focus": focus, "label": PROGRAMS[focus]["label"]}


@router.get("/equipment")
def equipment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """What kit the plan can draw on, and what each piece unlocks.

    Built from the catalogue rather than hard-coded, so a kind of equipment
    that no exercise uses is never offered — a checkbox that unlocks nothing
    is just a question the user cannot answer usefully.
    """
    counts = {}
    for _, _, _, equip, *_ in LIBRARY:
        if equip in ALWAYS_AVAILABLE:
            continue
        counts[equip] = counts.get(equip, 0) + 1

    profile = db.query(TrainingProfile).filter(
        TrainingProfile.user_id == current_user.user_id).first()
    owned = available_equipment(profile)

    labels = {"dumbbell": "Dumbbells", "band": "Resistance bands",
              "barbell": "Barbell", "tube": "Tube / pedal puller"}
    return {
        # Unset means everything, which is the right default before anyone has
        # said otherwise.
        "unset": owned is None,
        "items": [
            {
                "key": key,
                "label": labels.get(key, key.title()),
                "unlocks": n,
                "available": True if owned is None else key in owned,
            }
            for key, n in sorted(counts.items(), key=lambda kv: -kv[1])
        ],
    }


# ── Profile ──────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=TrainingProfileOut)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.query(TrainingProfile).filter(
        TrainingProfile.user_id == current_user.user_id
    ).first()
    if p is None:
        # An empty profile rather than a 404: the client always has something
        # to render, and the first save creates the row.
        return TrainingProfileOut(
            goals=None, constraints=None, dumbbell_bar_kg=None,
            barbell_bar_kg=None, equipment_json=None, updated_at=None,
        )
    return p


@router.put("/equipment")
def save_equipment(
    payload: list[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record which kit is to hand. Merged into the profile, not overwriting it."""
    valid = {equip for _, _, _, equip, *_ in LIBRARY} - ALWAYS_AVAILABLE
    unknown = [k for k in payload if k not in valid]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Not equipment this app knows about: {', '.join(unknown)}.",
        )

    p = db.query(TrainingProfile).filter(
        TrainingProfile.user_id == current_user.user_id).first()
    if p is None:
        p = TrainingProfile(user_id=current_user.user_id)
        db.add(p)

    try:
        data = json.loads(p.equipment_json) if p.equipment_json else {}
        if not isinstance(data, dict):
            data = {}
    except (ValueError, TypeError):
        data = {}          # unreadable: rebuild rather than lose the setting
    # Plate inventory lives in the same blob and must survive this write.
    data["available"] = sorted(set(payload))
    p.equipment_json = json.dumps(data)
    db.commit()
    return {"available": data["available"]}


@router.put("/profile", response_model=TrainingProfileOut)
def save_profile(
    payload: TrainingProfileIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.query(TrainingProfile).filter(
        TrainingProfile.user_id == current_user.user_id
    ).first()
    if p is None:
        p = TrainingProfile(user_id=current_user.user_id)
        db.add(p)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p


# ── Programme ────────────────────────────────────────────────────────────────

@router.get("/today")
def todays_session(
    day: Optional[str] = Query(None, pattern="^[ABC]$"),
    tz_offset: int = Query(0),
    kind: Optional[str] = Query(None, pattern="^(strength|practice)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """What to do next, and why.

    Loads come from logged history through fixed rules rather than from a
    model, so the knee back-off is a guarantee rather than a suggestion.
    """
    return build_session(db, current_user.user_id, day=day,
                         tz_offset=tz_offset, kind=kind)


@router.get("/assessment")
def assessment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The baseline tests, matched to the user's own exercise ids.

    Submaximal throughout: a true 1RM is both the highest-risk thing here and
    the exact stimulus that provokes this knee, and a rep test gives the same
    programming information without it.
    """
    focus = user_focus(db, current_user.user_id)
    by_name = {
        e.exercise_name.strip().lower(): e
        for e in db.query(Exercise).filter(Exercise.user_id == current_user.user_id).all()
    }
    items, missing = [], []
    for name, how, why in program(focus)["assessment"]:
        ex = by_name.get(name.strip().lower())
        if ex is None:
            missing.append(name)
            continue
        # Shaped like a plan block so the session runner can drive it: one
        # set, and no target, because the point is to find out what the
        # numbers are rather than to hit one. A hold with no target counts up.
        scheme = ("iso" if ex.is_isometric
                  else "load" if ex.equipment in ("dumbbell", "barbell")
                  else "reps")
        items.append({
            "exercise_id": ex.exercise_id,
            "exercise": ex.exercise_name,
            "how": how,
            "why": why,
            "form_cues": ex.form_cues,
            "video_url": ex.video_url,
            "scheme": scheme,
            "group": "assessment",
            "prescription": how,
            "sets": 1,
            "target_reps": None,
            "target_seconds": None,
            "target_weight": None,
            "per_side": bool(ex.is_unilateral),
        })

    already = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == current_user.user_id,
                WorkoutSession.session_type == "assessment")
        .count()
    )
    return {
        "items": items,
        "missing": missing,
        "focus": focus,
        "focus_label": program(focus)["label"],
        "completed_before": already,
        "guidance": (
            "Stop every set two reps short of failure, and stop any set where "
            "pain goes above 3/10. Log it as a session of type 'assessment'."
        ),
    }


# ── Practice ─────────────────────────────────────────────────────────────────

def _practice_out(item: PracticeItem) -> dict:
    return {
        "practice_item_id": item.practice_item_id,
        "exercise_id": item.exercise_id,
        "exercise": item.exercise.exercise_name if item.exercise else None,
        "slot": item.slot,
        "position": item.position,
        "scheme": item.scheme,
        "sets": item.sets,
        "low": item.low,
        "high": item.high,
        "alternates_with_id": item.alternates_with_id,
        "alternates_with": item.alternate.exercise_name if item.alternate else None,
    }


def _user_practice(db, user_id):
    return sorted(
        db.query(PracticeItem).filter(PracticeItem.user_id == user_id).all(),
        key=lambda i: (i.slot != "before", i.position, i.practice_item_id),
    )


@router.get("/practice")
def list_practice(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The user's own routine. Empty means the programme's default is used."""
    items = _user_practice(db, current_user.user_id)
    return {
        "items": [_practice_out(i) for i in items],
        "using_default": not items,
    }


def _own_exercise(db, user_id, exercise_id):
    ex = db.query(Exercise).filter(
        Exercise.exercise_id == exercise_id, Exercise.user_id == user_id
    ).first()
    if ex is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")
    return ex


@router.post("/practice", status_code=201)
def add_practice(
    payload: PracticeItemIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _own_exercise(db, current_user.user_id, payload.exercise_id)
    if payload.alternates_with_id is not None:
        _own_exercise(db, current_user.user_id, payload.alternates_with_id)
        if payload.alternates_with_id == payload.exercise_id:
            raise HTTPException(
                status_code=400,
                detail="An exercise cannot alternate with itself.",
            )

    # Append to the end of its slot.
    tail = [i for i in _user_practice(db, current_user.user_id) if i.slot == payload.slot]
    item = PracticeItem(
        user_id=current_user.user_id,
        position=(tail[-1].position + 1) if tail else 0,
        **payload.model_dump(),
    )
    db.add(item)
    db.commit()
    return {"items": [_practice_out(i) for i in _user_practice(db, current_user.user_id)]}


@router.patch("/practice/{item_id}")
def move_practice(
    item_id: int,
    direction: str = Query(..., pattern="^(up|down)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reorder within a slot. Order matters: a warm-up before, a wind-down after."""
    items = _user_practice(db, current_user.user_id)
    item = next((i for i in items if i.practice_item_id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Practice item not found.")

    same = [i for i in items if i.slot == item.slot]
    idx = same.index(item)
    swap = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap < len(same):
        # Renumber the whole slot rather than swapping two values, so positions
        # stay contiguous however the rows were created.
        same[idx], same[swap] = same[swap], same[idx]
        for n, i in enumerate(same):
            i.position = n
        db.commit()
    return {"items": [_practice_out(i) for i in _user_practice(db, current_user.user_id)]}


@router.delete("/practice/{item_id}", status_code=204)
def remove_practice(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(PracticeItem).filter(
        PracticeItem.practice_item_id == item_id,
        PracticeItem.user_id == current_user.user_id,
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Practice item not found.")
    db.delete(item)
    db.commit()
