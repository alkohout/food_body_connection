"""Typed tools that let the AI read the user's logged data.

Why tools rather than generated SQL
-----------------------------------
The obvious design is text-to-SQL: let the model write a query and run it
read-only. That cannot work here. Names are encrypted at rest with a
non-deterministic cipher, so `WHERE allergen_name = 'Triptan'` never matches —
and it does not error either, it silently returns nothing. Of the 66 columns,
20 are opaque to SQL, including every name and label.

So the model picks from a small set of operations implemented here in Python,
where the ORM decrypts transparently. user_id is supplied by the route and is
never a model-supplied parameter, so a tool call cannot reach another user's
data. Row counts are capped and truncation is reported rather than hidden.
"""

import logging
from datetime import datetime, timedelta, timezone

from app.models.table_class import (
    Allergen,
    AllergenLog,
    DailyCheckin,
    Medication,
    MedicationRegimen,
    Symptom,
    SymptomLog,
    Unit,
)

logger = logging.getLogger(__name__)

MAX_ROWS = 400
_INTENSITY_LABELS = {0: "None", 1: "Mild", 2: "Moderate", 3: "Severe"}

_CHECKIN_FIELDS = [
    "sleep", "mood", "fatigue", "gut", "stress", "headache",
    "headache_overnight", "brain_fog", "tinnitus", "visual_disturbance",
    "training", "virus",
]


# ──────────────────────────────────────────────
# Tool schemas handed to the model
# ──────────────────────────────────────────────

TOOLS = [
    {
        "name": "list_tracked_items",
        "description": (
            "List the things this user actually logs — allergens/foods, symptoms, "
            "or medications — with how many entries each has and the date range "
            "covered. Call this FIRST when you are unsure of the exact name of "
            "something, because the other tools match on these names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["allergen", "symptom", "medication", "all"],
                    "description": "Which category to list. Use 'all' if unsure.",
                }
            },
            "required": ["kind"],
        },
    },
    {
        "name": "query_logs",
        "description": (
            "Return the individual logged entries — one row per event — for one or "
            "more allergens or symptoms, optionally filtered by date range and "
            "minimum symptom intensity. Use this when the user wants to SEE specific "
            "records ('show me every headache in March', 'what did I eat on 3 July')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["allergen", "symptom"]},
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Exact names as returned by list_tracked_items. "
                        "Omit or leave empty to include everything of this kind."
                    ),
                },
                "date_from": {"type": "string", "description": "YYYY-MM-DD, inclusive."},
                "date_to": {"type": "string", "description": "YYYY-MM-DD, inclusive."},
                "min_intensity": {
                    "type": "integer",
                    "description": "Symptoms only: minimum intensity 0-3.",
                },
                "limit": {
                    "type": "integer",
                    "description": f"Max rows to return (default 100, hard cap {MAX_ROWS}).",
                },
            },
            "required": ["kind"],
        },
    },
    {
        "name": "aggregate_logs",
        "description": (
            "Count or average logged entries, grouped by day, week, month, weekday, "
            "hour of day, or item name. Use this for 'how many', 'how often', "
            "'which is most common', or trend-over-time questions, rather than "
            "pulling every row and counting them yourself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["allergen", "symptom"]},
                "group_by": {
                    "type": "string",
                    "enum": ["day", "week", "month", "weekday", "hour", "item"],
                },
                "names": {"type": "array", "items": {"type": "string"}},
                "date_from": {"type": "string", "description": "YYYY-MM-DD, inclusive."},
                "date_to": {"type": "string", "description": "YYYY-MM-DD, inclusive."},
            },
            "required": ["kind", "group_by"],
        },
    },
    {
        "name": "get_checkins",
        "description": (
            "Return daily morning/evening wellbeing check-in scores (sleep, mood, "
            "fatigue, gut, stress, headache, brain fog, tinnitus, visual "
            "disturbance, training, virus). Scores are 0-2 where higher is more "
            "severe, except sleep and mood where higher is better."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "YYYY-MM-DD, inclusive."},
                "date_to": {"type": "string", "description": "YYYY-MM-DD, inclusive."},
                "fields": {
                    "type": "array",
                    "items": {"type": "string", "enum": _CHECKIN_FIELDS},
                    "description": "Which scores to return. Omit for all of them.",
                },
            },
        },
    },
]


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

class BadDate(ValueError):
    """A date the model supplied could not be parsed."""


def _parse_day(value, end_of_day=False):
    """Parse YYYY-MM-DD from the model into a local-day boundary.

    Raises rather than returning None on malformed input. Ignoring a bad date
    would silently drop the filter and hand back the whole table, which the
    model would then describe as if it were the requested range — worse than
    telling it the date was wrong so it can retry.
    """
    if not value:
        return None
    try:
        d = datetime.strptime(str(value).strip()[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        raise BadDate(f"'{value}' is not a valid date. Use YYYY-MM-DD.")
    return d + timedelta(hours=23, minutes=59, seconds=59) if end_of_day else d


def _to_local(dt, tz_offset):
    """Stored UTC instant -> the user's local wall clock (naive)."""
    if dt is None:
        return None
    naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
    return naive - timedelta(minutes=tz_offset)


def _to_utc(local_dt, tz_offset):
    """Local wall clock -> UTC instant, for comparing against stored values."""
    if local_dt is None:
        return None
    return (local_dt + timedelta(minutes=tz_offset)).replace(tzinfo=timezone.utc)


def _match(records, names, attr):
    """Resolve model-supplied names against decrypted values, case-insensitively.

    Names only exist in plaintext after the ORM decrypts them, so this filtering
    cannot be pushed into SQL.
    """
    if not names:
        return records
    wanted = {n.strip().lower() for n in names if n and n.strip()}
    if not wanted:
        return records
    return [r for r in records if (getattr(r, attr) or "").strip().lower() in wanted]


def _table(columns, rows, truncated=False, total=None):
    out = {"columns": columns, "rows": rows, "row_count": len(rows)}
    if truncated:
        out["truncated"] = True
        out["note"] = (
            f"Showing the first {len(rows)} of {total} matching rows. "
            "Narrow the date range or filter by name to see the rest."
        )
    return out


# ──────────────────────────────────────────────
# Tool implementations
# ──────────────────────────────────────────────

def _list_tracked_items(db, user_id, tz_offset, kind="all"):
    sections = {}

    if kind in ("allergen", "all"):
        rows = []
        for a in db.query(Allergen).filter(Allergen.user_id == user_id).all():
            logs = db.query(AllergenLog).filter(
                AllergenLog.allergen_id == a.allergen_id
            ).all()
            if not logs:
                continue
            days = [_to_local(l.date_time, tz_offset) for l in logs if l.date_time]
            rows.append([
                a.allergen_name,
                len(logs),
                min(days).strftime("%Y-%m-%d") if days else None,
                max(days).strftime("%Y-%m-%d") if days else None,
            ])
        rows.sort(key=lambda r: -r[1])
        sections["allergens"] = _table(["name", "entries", "first", "last"], rows)

    if kind in ("symptom", "all"):
        rows = []
        for s in db.query(Symptom).filter(Symptom.user_id == user_id).all():
            logs = db.query(SymptomLog).filter(
                SymptomLog.symptom_id == s.symptom_id
            ).all()
            if not logs:
                continue
            days = [_to_local(l.date_time, tz_offset) for l in logs if l.date_time]
            rows.append([
                s.symptom_name,
                s.symptom_group,
                len(logs),
                min(days).strftime("%Y-%m-%d") if days else None,
                max(days).strftime("%Y-%m-%d") if days else None,
            ])
        rows.sort(key=lambda r: -r[2])
        sections["symptoms"] = _table(
            ["name", "group", "entries", "first", "last"], rows
        )

    if kind in ("medication", "all"):
        rows = []
        for m in db.query(Medication).filter(Medication.user_id == user_id).all():
            regs = db.query(MedicationRegimen).filter(
                MedicationRegimen.medication_id == m.medication_id
            ).all()
            rows.append([
                m.medication_name,
                len(regs),
                min((r.start_date for r in regs), default=None),
                max((r.end_date or r.start_date for r in regs), default=None),
            ])
        sections["medications"] = _table(
            ["name", "regimens", "first", "last"], rows
        )

    return sections


def _query_logs(db, user_id, tz_offset, kind, names=None, date_from=None,
                date_to=None, min_intensity=None, limit=100):
    limit = max(1, min(int(limit or 100), MAX_ROWS))
    from_utc = _to_utc(_parse_day(date_from), tz_offset)
    to_utc = _to_utc(_parse_day(date_to, end_of_day=True), tz_offset)

    if kind == "allergen":
        lookup = {
            a.allergen_id: a.allergen_name
            for a in _match(
                db.query(Allergen).filter(Allergen.user_id == user_id).all(),
                names, "allergen_name",
            )
        }
        units = {u.unit_id: u.unit_name for u in db.query(Unit).all()}
        q = db.query(AllergenLog).filter(
            AllergenLog.user_id == user_id,
            AllergenLog.allergen_id.in_(lookup.keys() or [-1]),
        )
        if from_utc:
            q = q.filter(AllergenLog.date_time >= from_utc)
        if to_utc:
            q = q.filter(AllergenLog.date_time <= to_utc)

        logs = q.order_by(AllergenLog.date_time.desc()).all()
        rows = [
            [
                _to_local(l.date_time, tz_offset).strftime("%Y-%m-%d"),
                _to_local(l.date_time, tz_offset).strftime("%H:%M"),
                lookup.get(l.allergen_id),
                l.quantity,
                units.get(l.unit_id),
            ]
            for l in logs[:limit]
        ]
        return _table(
            ["date", "time", "allergen", "quantity", "unit"],
            rows, truncated=len(logs) > limit, total=len(logs),
        )

    lookup = {
        s.symptom_id: s.symptom_name
        for s in _match(
            db.query(Symptom).filter(Symptom.user_id == user_id).all(),
            names, "symptom_name",
        )
    }
    q = db.query(SymptomLog).filter(
        SymptomLog.user_id == user_id,
        SymptomLog.symptom_id.in_(lookup.keys() or [-1]),
    )
    if from_utc:
        q = q.filter(SymptomLog.date_time >= from_utc)
    if to_utc:
        q = q.filter(SymptomLog.date_time <= to_utc)
    if min_intensity is not None:
        q = q.filter(SymptomLog.symptom_intensity >= int(min_intensity))

    logs = q.order_by(SymptomLog.date_time.desc()).all()
    rows = [
        [
            _to_local(l.date_time, tz_offset).strftime("%Y-%m-%d"),
            _to_local(l.date_time, tz_offset).strftime("%H:%M"),
            lookup.get(l.symptom_id),
            l.symptom_intensity,
            _INTENSITY_LABELS.get(l.symptom_intensity, "?"),
        ]
        for l in logs[:limit]
    ]
    return _table(
        ["date", "time", "symptom", "intensity", "severity"],
        rows, truncated=len(logs) > limit, total=len(logs),
    )


def _aggregate_logs(db, user_id, tz_offset, kind, group_by,
                    names=None, date_from=None, date_to=None):
    from_utc = _to_utc(_parse_day(date_from), tz_offset)
    to_utc = _to_utc(_parse_day(date_to, end_of_day=True), tz_offset)

    if kind == "allergen":
        lookup = {
            a.allergen_id: a.allergen_name
            for a in _match(
                db.query(Allergen).filter(Allergen.user_id == user_id).all(),
                names, "allergen_name",
            )
        }
        q = db.query(AllergenLog).filter(
            AllergenLog.user_id == user_id,
            AllergenLog.allergen_id.in_(lookup.keys() or [-1]),
        )
        if from_utc:
            q = q.filter(AllergenLog.date_time >= from_utc)
        if to_utc:
            q = q.filter(AllergenLog.date_time <= to_utc)
        entries = [
            (_to_local(l.date_time, tz_offset), lookup.get(l.allergen_id), None)
            for l in q.all() if l.date_time
        ]
    else:
        lookup = {
            s.symptom_id: s.symptom_name
            for s in _match(
                db.query(Symptom).filter(Symptom.user_id == user_id).all(),
                names, "symptom_name",
            )
        }
        q = db.query(SymptomLog).filter(
            SymptomLog.user_id == user_id,
            SymptomLog.symptom_id.in_(lookup.keys() or [-1]),
        )
        if from_utc:
            q = q.filter(SymptomLog.date_time >= from_utc)
        if to_utc:
            q = q.filter(SymptomLog.date_time <= to_utc)
        entries = [
            (_to_local(l.date_time, tz_offset), lookup.get(l.symptom_id),
             l.symptom_intensity)
            for l in q.all() if l.date_time
        ]

    keyers = {
        "day":     lambda d, n: d.strftime("%Y-%m-%d"),
        "week":    lambda d, n: (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d"),
        "month":   lambda d, n: d.strftime("%Y-%m"),
        "weekday": lambda d, n: d.strftime("%A"),
        "hour":    lambda d, n: f"{d.hour:02d}:00",
        "item":    lambda d, n: n,
    }
    keyer = keyers.get(group_by)
    if keyer is None:
        return {"error": f"Unknown group_by '{group_by}'."}

    buckets = {}
    for dt, name, intensity in entries:
        key = keyer(dt, name)
        b = buckets.setdefault(key, {"count": 0, "intensities": []})
        b["count"] += 1
        if intensity is not None:
            b["intensities"].append(intensity)

    if group_by == "weekday":
        order = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]
        keys = [k for k in order if k in buckets]
    elif group_by == "item":
        keys = sorted(buckets, key=lambda k: -buckets[k]["count"])
    else:
        keys = sorted(buckets)

    if kind == "symptom":
        rows = [
            [k, buckets[k]["count"],
             round(sum(buckets[k]["intensities"]) / len(buckets[k]["intensities"]), 2)
             if buckets[k]["intensities"] else None]
            for k in keys
        ]
        return _table([group_by, "count", "mean_intensity"], rows)

    rows = [[k, buckets[k]["count"]] for k in keys]
    return _table([group_by, "count"], rows)


def _get_checkins(db, user_id, tz_offset, date_from=None, date_to=None, fields=None):
    wanted = [f for f in (fields or _CHECKIN_FIELDS) if f in _CHECKIN_FIELDS]
    if not wanted:
        wanted = _CHECKIN_FIELDS

    q = db.query(DailyCheckin).filter(DailyCheckin.user_id == user_id)
    # checkin_date is already the user's LOCAL calendar date, so compare it
    # against the model's plain date rather than a UTC instant.
    d_from = _parse_day(date_from)
    d_to = _parse_day(date_to)
    if d_from:
        q = q.filter(DailyCheckin.checkin_date >= d_from.date())
    if d_to:
        q = q.filter(DailyCheckin.checkin_date <= d_to.date())

    records = q.order_by(
        DailyCheckin.checkin_date.desc(), DailyCheckin.period
    ).all()

    rows = [
        [str(c.checkin_date), c.period] + [getattr(c, f, None) for f in wanted]
        for c in records[:MAX_ROWS]
    ]
    return _table(
        ["date", "period"] + wanted,
        rows, truncated=len(records) > MAX_ROWS, total=len(records),
    )


_DISPATCH = {
    "list_tracked_items": _list_tracked_items,
    "query_logs": _query_logs,
    "aggregate_logs": _aggregate_logs,
    "get_checkins": _get_checkins,
}


def run_tool(name, args, db, user_id, tz_offset=0):
    """Execute one model-requested tool.

    user_id and tz_offset come from the authenticated request, never from the
    model. An exception is returned as an error payload rather than raised, so
    the model can correct itself instead of the whole turn failing.
    """
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"Unknown tool '{name}'."}
    try:
        return fn(db, user_id, tz_offset, **(args or {}))
    except BadDate as exc:
        return {"error": str(exc)}
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:
        logger.exception("tool %s failed", name)
        return {"error": f"{name} failed: {exc}"}
