# app/api/routes/plot_event_series.py

import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from io import BytesIO
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Symptom, Medication, MedicationRegimen, DailyCheckin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])

_INTENSITY_LABELS = {0: "None", 1: "Mild", 2: "Moderate", 3: "Severe"}
_INTENSITY_COLORS = {0: "#4caf50", 1: "#f59e0b", 2: "#f97316", 3: "#ef4444"}

_COL1 = "#2563eb"   # blue  – variable 1
_COL2 = "#ea580c"   # orange – variable 2

_CHECKIN_VARS = {"sleep", "mood", "fatigue", "gut", "stress",
                 "headache", "headache_overnight", "brain_fog", "tinnitus", "visual_disturbance",
                 "training", "virus"}
_CHECKIN_POINT_COLORS = {0: "#4caf50", 1: "#f59e0b", 2: "#ef4444"}
_CHECKIN_YTICK_LABELS = ["Low", "Med", "High"]


# ──────────────────────────────────────────────
# Data helpers
# ──────────────────────────────────────────────

def _parse_date(date_str: Optional[str], end_of_day: bool = False, tz_offset_minutes: int = 0) -> Optional[datetime]:
    """Parse a YYYY-MM-DD string as local midnight (or end-of-day) in UTC.

    tz_offset_minutes is the value of JS Date.getTimezoneOffset() — the number of
    minutes that must be added to local time to get UTC (negative for east-of-UTC
    zones, e.g. NZ UTC+12 → -720).  Adding it converts local midnight to UTC.
    """
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        if end_of_day:
            d = d.replace(hour=23, minute=59, second=59)
        return (d + timedelta(minutes=tz_offset_minutes)).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _get_allergen_data(db, user_id, name, from_dt, to_dt):
    allergen = db.query(Allergen).filter(
        Allergen.user_id == user_id, Allergen.allergen_name == name
    ).first()
    if not allergen:
        raise HTTPException(404, f"Allergen '{name}' not found")

    q = db.query(AllergenLog).filter(
        AllergenLog.user_id == user_id,
        AllergenLog.allergen_id == allergen.allergen_id,
    )
    if from_dt:
        q = q.filter(AllergenLog.date_time >= from_dt)
    if to_dt:
        q = q.filter(AllergenLog.date_time <= to_dt)

    logs = q.order_by(AllergenLog.date_time).all()
    if not logs:
        raise HTTPException(404, f"No events for allergen '{name}' in the selected range")
    return [log.date_time for log in logs], [log.quantity for log in logs]


def _get_medication_data(db, user_id, name, from_dt, to_dt):
    """Return a step-function (dates, doses) representing total daily dose over time."""
    med = db.query(Medication).filter(
        Medication.user_id == user_id,
        Medication.medication_name == name,
    ).first()
    if not med:
        raise HTTPException(404, f"Medication '{name}' not found")

    regimens = (
        db.query(MedicationRegimen)
        .filter(
            MedicationRegimen.user_id == user_id,
            MedicationRegimen.medication_id == med.medication_id,
        )
        .order_by(MedicationRegimen.start_date, MedicationRegimen.regimen_id)
        .all()
    )
    if not regimens:
        raise HTTPException(404, f"No regimen data for medication '{name}'")

    # Collect every date where total dose might change
    change_dates = set()
    for r in regimens:
        change_dates.add(r.start_date)
        if r.end_date:
            change_dates.add(r.end_date)
    change_dates = sorted(change_dates)

    # Sum all doses that are active on each change date
    step_dates, step_doses = [], []
    for d in change_dates:
        total = sum(
            r.dose for r in regimens
            if r.start_date <= d and (r.end_date is None or r.end_date > d)
        )
        step_dates.append(datetime(d.year, d.month, d.day, tzinfo=timezone.utc))
        step_doses.append(total)

    # Cap with today if the last regimen is still open
    if regimens[-1].end_date is None:
        step_dates.append(datetime.now(timezone.utc))
        step_doses.append(step_doses[-1])

    # Apply optional date-range filter
    if from_dt or to_dt:
        pairs = [
            (d, v) for d, v in zip(step_dates, step_doses)
            if (not from_dt or d >= from_dt) and (not to_dt or d <= to_dt)
        ]
        if not pairs:
            raise HTTPException(404, f"No regimen data for '{name}' in the selected range")
        step_dates, step_doses = zip(*pairs)
        step_dates, step_doses = list(step_dates), list(step_doses)

    return step_dates, step_doses


def _get_symptom_data(db, user_id, name, from_dt, to_dt):
    symptom = db.query(Symptom).filter(
        Symptom.user_id == user_id, Symptom.symptom_name == name
    ).first()
    if not symptom:
        raise HTTPException(404, f"Symptom '{name}' not found")

    q = db.query(SymptomLog).filter(
        SymptomLog.user_id == user_id,
        SymptomLog.symptom_id == symptom.symptom_id,
    )
    if from_dt:
        q = q.filter(SymptomLog.date_time >= from_dt)
    if to_dt:
        q = q.filter(SymptomLog.date_time <= to_dt)

    logs = q.order_by(SymptomLog.date_time).all()
    if not logs:
        raise HTTPException(404, f"No events for symptom '{name}' in the selected range")
    return [log.date_time for log in logs], [log.symptom_intensity for log in logs]


def _get_checkin_data(db, user_id, variable_name, from_dt, to_dt):
    if variable_name not in _CHECKIN_VARS:
        raise HTTPException(400, f"Unknown check-in variable '{variable_name}'")

    q = db.query(DailyCheckin).filter(DailyCheckin.user_id == user_id)
    if from_dt:
        q = q.filter(DailyCheckin.checkin_date >= from_dt.date())
    if to_dt:
        q = q.filter(DailyCheckin.checkin_date <= to_dt.date())

    records = q.order_by(DailyCheckin.checkin_date, DailyCheckin.period).all()

    dates, values = [], []
    for r in records:
        val = getattr(r, variable_name)
        if val is None:
            continue
        # Use stored local datetime if available, else fall back to reconstructed UTC
        if r.checkin_datetime:
            dt = r.checkin_datetime
        else:
            hour = 8 if r.period == "morning" else 20
            dt = datetime(r.checkin_date.year, r.checkin_date.month, r.checkin_date.day,
                          hour, 0, 0, tzinfo=timezone.utc)
        dates.append(dt)
        values.append(val)

    if not dates:
        raise HTTPException(404, f"No check-in data for '{variable_name}' in the selected range")

    return dates, values


# ──────────────────────────────────────────────
# Drawing helpers
# ──────────────────────────────────────────────

def _is_binary(values):
    non_null = [v for v in values if v is not None]
    return len(set(non_null)) <= 1 if non_null else True


def _draw_primary(ax, dates, values, item_type, color):
    """Variable 1 — vertical lines on the left y-axis."""
    if item_type == "allergen":
        if _is_binary(values):
            ax.vlines(dates, 0, 1, color=color, alpha=0.55, linewidth=2)
            ax.set_ylim(0, 1.4)
            ax.set_yticks([])
            ax.spines["left"].set_visible(False)
        else:
            ys = [q if q is not None else 0 for q in values]
            ax.vlines(dates, 0, ys, color=color, alpha=0.25, linewidth=1.2)
            ax.scatter(dates, ys, color=color, alpha=0.8, s=45, zorder=3)
            ax.set_ylim(bottom=0)
            ax.set_ylabel("Quantity", color=color)
            ax.tick_params(axis="y", colors=color)
    else:
        point_colors = [_INTENSITY_COLORS.get(i, "#9ca3af") for i in values]
        ax.vlines(dates, 0, values, color="#9ca3af", alpha=0.25, linewidth=1.2)
        ax.scatter(dates, values, c=point_colors, s=55, alpha=0.9,
                   edgecolors="white", linewidth=0.5, zorder=3)
        ax.set_yticks([0, 1, 2, 3])
        ax.set_yticklabels([_INTENSITY_LABELS[i] for i in range(4)], color=color)
        ax.set_ylim(-0.4, 3.4)
        ax.tick_params(axis="y", colors=color)


def _draw_secondary(ax, dates, values, item_type, color):
    """Variable 2 — diamond markers only on the right y-axis."""
    if item_type == "allergen":
        if _is_binary(values):
            ax.scatter(dates, [0.5] * len(dates), color=color, alpha=0.8,
                       s=70, marker="D", edgecolors="white", linewidth=0.5, zorder=4)
            ax.set_ylim(0, 1.4)
            ax.set_yticks([])
            ax.spines["right"].set_visible(False)
        else:
            ys = [q if q is not None else 0 for q in values]
            ax.scatter(dates, ys, color=color, alpha=0.8, s=60, marker="D",
                       edgecolors="white", linewidth=0.5, zorder=4)
            ax.set_ylim(bottom=0)
            ax.set_ylabel("Quantity", color=color)
            ax.tick_params(axis="y", colors=color)
    else:
        point_colors = [_INTENSITY_COLORS.get(i, "#9ca3af") for i in values]
        ax.scatter(dates, values, c=point_colors, s=70, alpha=0.85, marker="D",
                   edgecolors="white", linewidth=0.5, zorder=4)
        ax.set_yticks([0, 1, 2, 3])
        ax.set_yticklabels([_INTENSITY_LABELS[i] for i in range(4)], color=color)
        ax.set_ylim(-0.4, 3.4)
        ax.tick_params(axis="y", colors=color)


def _draw_medication(ax, dates, doses, color, ylabel="Daily dose (mg)"):
    """Medication step function — shared by primary and secondary axes."""
    ax.step(dates, doses, where="post", color=color, linewidth=2.5, alpha=0.85)
    ax.set_ylabel(ylabel, color=color)
    ax.tick_params(axis="y", colors=color)
    ax.set_ylim(bottom=0)


def _draw_checkin_primary(ax, dates, values, color):
    point_colors = [_CHECKIN_POINT_COLORS.get(v, "#9ca3af") for v in values]
    ax.plot(dates, values, color=color, alpha=0.25, linewidth=1.2, zorder=2)
    ax.scatter(dates, values, c=point_colors, s=55, alpha=0.9,
               edgecolors="white", linewidth=0.5, zorder=3)
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(_CHECKIN_YTICK_LABELS, color=color)
    ax.set_ylim(-0.4, 2.4)
    ax.tick_params(axis="y", colors=color)


def _draw_checkin_secondary(ax, dates, values, color):
    point_colors = [_CHECKIN_POINT_COLORS.get(v, "#9ca3af") for v in values]
    ax.plot(dates, values, color=color, alpha=0.25, linewidth=1.2, zorder=2)
    ax.scatter(dates, values, c=point_colors, s=70, alpha=0.85, marker="D",
               edgecolors="white", linewidth=0.5, zorder=4)
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(_CHECKIN_YTICK_LABELS, color=color)
    ax.set_ylim(-0.4, 2.4)
    ax.tick_params(axis="y", colors=color)


def _save_fig(fig) -> BytesIO:
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ──────────────────────────────────────────────
# Route
# ──────────────────────────────────────────────

@router.get("/plot_event_series")
def plot_event_series(
    item_type: str = Query(..., alias="type"),
    name: str = Query(..., min_length=1),
    type2: Optional[str] = Query(None),
    name2: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    tz_offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return a time-series plot for one or two variables.

    With two variables they are layered on the same figure:
      - Variable 1 (blue)  : vertical lines on the left y-axis
      - Variable 2 (orange): diamond markers on a twin right y-axis
    """
    _VALID = ("allergen", "symptom", "medication", "checkin")
    if item_type not in _VALID:
        raise HTTPException(400, f"type must be one of {_VALID}")
    if type2 and type2 not in _VALID:
        raise HTTPException(400, f"type2 must be one of {_VALID}")

    from_dt = _parse_date(date_from, tz_offset_minutes=tz_offset)
    to_dt   = _parse_date(date_to, end_of_day=True, tz_offset_minutes=tz_offset)

    try:
        def _fetch(t, n):
            if t == "allergen":
                return _get_allergen_data(db, current_user.user_id, n, from_dt, to_dt)
            elif t == "symptom":
                return _get_symptom_data(db, current_user.user_id, n, from_dt, to_dt)
            elif t == "checkin":
                return _get_checkin_data(db, current_user.user_id, n, from_dt, to_dt)
            else:
                return _get_medication_data(db, current_user.user_id, n, from_dt, to_dt)

        def _draw_primary_ax(ax, dates, values, t, color):
            if t == "medication":
                _draw_medication(ax, dates, values, color)
            elif t == "checkin":
                _draw_checkin_primary(ax, dates, values, color)
            else:
                _draw_primary(ax, dates, values, t, color)

        def _draw_secondary_ax(ax, dates, values, t, color):
            if t == "medication":
                _draw_medication(ax, dates, values, color)
            elif t == "checkin":
                _draw_checkin_secondary(ax, dates, values, color)
            else:
                _draw_secondary(ax, dates, values, t, color)

        # Variable 1
        dates1, values1 = _fetch(item_type, name)

        has_second = bool(type2 and name2)

        if has_second:
            # Variable 2
            dates2, values2 = _fetch(type2, name2)

            fig, ax1 = plt.subplots(figsize=(10, 4))
            _draw_primary_ax(ax1, dates1, values1, item_type, _COL1)

            ax2 = ax1.twinx()
            _draw_secondary_ax(ax2, dates2, values2, type2, _COL2)

            # Legend — use a step line marker for medication, diamond for others
            def _legend_handle(t, color, label):
                if t == "medication":
                    return Line2D([0], [0], color=color, linewidth=2.5, label=label)
                elif t == "allergen":
                    return Line2D([0], [0], color=color, linewidth=2.5, label=label)
                else:
                    return Line2D([0], [0], color=color, marker="D", linestyle="None",
                                  markersize=7, markeredgecolor="white",
                                  markeredgewidth=0.5, label=label)

            legend_handles = [
                _legend_handle(item_type, _COL1, f"{item_type.title()}: {name}"),
                _legend_handle(type2, _COL2, f"{type2.title()}: {name2}"),
            ]
            ax1.legend(handles=legend_handles, frameon=False,
                       loc="upper left", fontsize=9)

            ax1.set_xlabel("Date")
            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
            ax1.grid(axis="x", alpha=0.15)

        else:
            # Single variable
            type_label = item_type.title()
            fig, ax1 = plt.subplots(figsize=(10, 3.5))
            _draw_primary_ax(ax1, dates1, values1, item_type, _COL1)
            ax1.set_title(f"{type_label}: {name}", fontsize=11, loc="left", pad=4)
            ax1.set_xlabel("Date")
            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
            ax1.grid(axis="x", alpha=0.15)

        fig.autofmt_xdate(rotation=30, ha="right")
        plt.tight_layout()
        return StreamingResponse(_save_fig(fig), media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("plot_event_series failed")
        raise HTTPException(500, f"Failed to generate plot: {e}")
