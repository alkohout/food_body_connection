# app/api/routes/plot_event_series.py

import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.table_class import User, AllergenLog, SymptomLog, Allergen, Symptom

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])

_INTENSITY_LABELS = {0: "None", 1: "Mild", 2: "Moderate", 3: "Severe"}
_INTENSITY_COLORS = {0: "#4caf50", 1: "#f59e0b", 2: "#f97316", 3: "#ef4444"}


def _parse_date(date_str: Optional[str], end_of_day: bool = False) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        if end_of_day:
            d = d.replace(hour=23, minute=59, second=59)
        return d.replace(tzinfo=timezone.utc)
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


def _draw_panel(ax, dates, values, item_type, name, color):
    if item_type == "allergen":
        non_null = [q for q in values if q is not None]
        has_varied = len(set(non_null)) > 1 if non_null else False

        if has_varied:
            ys = [q if q is not None else 0 for q in values]
            ax.vlines(dates, 0, ys, color=color, alpha=0.25, linewidth=1.2)
            ax.scatter(dates, ys, color=color, alpha=0.8, s=45, zorder=3)
            ax.set_ylabel("Quantity")
            ax.set_ylim(bottom=0)
        else:
            ax.vlines(dates, 0, 1, color=color, alpha=0.6, linewidth=2)
            ax.set_ylim(0, 1.4)
            ax.set_yticks([])
            for spine in ("left", "right", "top"):
                ax.spines[spine].set_visible(False)

        ax.set_title(f"Allergen: {name}", fontsize=11, loc="left", pad=4)

    else:  # symptom
        point_colors = [_INTENSITY_COLORS.get(i, "#9ca3af") for i in values]
        ax.vlines(dates, 0, values, color="#9ca3af", alpha=0.3, linewidth=1.2)
        ax.scatter(dates, values, c=point_colors, s=60, alpha=0.9,
                   edgecolors="white", linewidth=0.5, zorder=3)
        ax.set_yticks([0, 1, 2, 3])
        ax.set_yticklabels([_INTENSITY_LABELS[i] for i in range(4)])
        ax.set_ylim(-0.4, 3.4)
        ax.set_title(f"Symptom: {name}", fontsize=11, loc="left", pad=4)

    ax.grid(axis="x", alpha=0.15)


def _save_fig(fig) -> BytesIO:
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


@router.get("/plot_event_series")
def plot_event_series(
    item_type: str = Query(..., alias="type"),
    name: str = Query(..., min_length=1),
    type2: Optional[str] = Query(None),
    name2: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return a time-series plot for one or two variables (allergen or symptom),
    optionally filtered to a date range.

    Query params
    ------------
    type        : "allergen" | "symptom"
    name        : variable name
    type2       : optional second type
    name2       : optional second name
    date_from   : YYYY-MM-DD (inclusive)
    date_to     : YYYY-MM-DD (inclusive)
    """
    if item_type not in ("allergen", "symptom"):
        raise HTTPException(400, "type must be 'allergen' or 'symptom'")
    if type2 and type2 not in ("allergen", "symptom"):
        raise HTTPException(400, "type2 must be 'allergen' or 'symptom'")

    from_dt = _parse_date(date_from)
    to_dt   = _parse_date(date_to, end_of_day=True)

    try:
        # --- Variable 1 ---
        if item_type == "allergen":
            dates1, values1 = _get_allergen_data(db, current_user.user_id, name, from_dt, to_dt)
        else:
            dates1, values1 = _get_symptom_data(db, current_user.user_id, name, from_dt, to_dt)

        # --- Variable 2 (optional) ---
        has_second = bool(type2 and name2)
        if has_second:
            if type2 == "allergen":
                dates2, values2 = _get_allergen_data(db, current_user.user_id, name2, from_dt, to_dt)
            else:
                dates2, values2 = _get_symptom_data(db, current_user.user_id, name2, from_dt, to_dt)

        # --- Build figure ---
        if has_second:
            fig, (ax1, ax2) = plt.subplots(
                2, 1, figsize=(10, 5.5), sharex=True,
                gridspec_kw={"hspace": 0.55},
            )
            _draw_panel(ax1, dates1, values1, item_type, name, "#2563eb")
            _draw_panel(ax2, dates2, values2, type2, name2, "#ea580c")
            ax2.set_xlabel("Date")
            ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
            fig.autofmt_xdate(rotation=30, ha="right")
        else:
            fig, ax = plt.subplots(figsize=(10, 3.5))
            _draw_panel(ax, dates1, values1, item_type, name, "#2563eb")
            ax.set_xlabel("Date")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
            fig.autofmt_xdate(rotation=30, ha="right")

        plt.tight_layout()
        return StreamingResponse(_save_fig(fig), media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("plot_event_series failed")
        raise HTTPException(500, f"Failed to generate plot: {e}")
