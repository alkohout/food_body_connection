# app/api/routes/plot_event_series.py

import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
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


@router.get("/plot_event_series")
def plot_event_series(
    item_type: str = Query(..., alias="type"),
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return a time-series scatter plot for a single allergen or symptom.

    Parameters
    ----------
    type : str
        Either "allergen" or "symptom".
    name : str
        Name of the allergen or symptom to plot.

    Returns
    -------
    StreamingResponse (image/png)
    """
    if item_type not in ("allergen", "symptom"):
        raise HTTPException(400, "type must be 'allergen' or 'symptom'")

    try:
        if item_type == "allergen":
            buf = _plot_allergen_series(db, current_user.user_id, name)
        else:
            buf = _plot_symptom_series(db, current_user.user_id, name)
        return StreamingResponse(buf, media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("plot_event_series failed")
        raise HTTPException(500, f"Failed to generate plot: {e}")


def _plot_allergen_series(db: Session, user_id: int, allergen_name: str) -> BytesIO:
    allergen = (
        db.query(Allergen)
        .filter(Allergen.user_id == user_id, Allergen.allergen_name == allergen_name)
        .first()
    )
    if not allergen:
        raise HTTPException(404, f"Allergen '{allergen_name}' not found")

    logs = (
        db.query(AllergenLog)
        .filter(AllergenLog.user_id == user_id, AllergenLog.allergen_id == allergen.allergen_id)
        .order_by(AllergenLog.date_time)
        .all()
    )
    if not logs:
        raise HTTPException(404, f"No events found for allergen '{allergen_name}'")

    dates = [log.date_time for log in logs]
    quantities = [log.quantity for log in logs]
    has_quantity = any(q is not None for q in quantities)

    fig, ax = plt.subplots(figsize=(10, 3.5))

    if has_quantity:
        ys = [q if q is not None else 0 for q in quantities]
        ax.vlines(dates, 0, ys, color="#2563eb", alpha=0.25, linewidth=1.2)
        ax.scatter(dates, ys, color="#2563eb", alpha=0.8, s=45, zorder=3)
        ax.set_ylabel("Quantity")
        ax.set_ylim(bottom=0)
    else:
        ax.scatter(dates, [1] * len(dates), color="#2563eb", alpha=0.85,
                   s=80, marker="|", linewidths=2.5)
        ax.set_yticks([])
        ax.set_ylabel("")

    ax.set_title(f"Allergen exposures: {allergen_name}", fontsize=13)
    ax.set_xlabel("Date")
    ax.grid(axis="x", alpha=0.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
    fig.autofmt_xdate(rotation=30, ha="right")
    plt.tight_layout()

    return _save_fig(fig)


def _plot_symptom_series(db: Session, user_id: int, symptom_name: str) -> BytesIO:
    symptom = (
        db.query(Symptom)
        .filter(Symptom.user_id == user_id, Symptom.symptom_name == symptom_name)
        .first()
    )
    if not symptom:
        raise HTTPException(404, f"Symptom '{symptom_name}' not found")

    logs = (
        db.query(SymptomLog)
        .filter(SymptomLog.user_id == user_id, SymptomLog.symptom_id == symptom.symptom_id)
        .order_by(SymptomLog.date_time)
        .all()
    )
    if not logs:
        raise HTTPException(404, f"No events found for symptom '{symptom_name}'")

    dates = [log.date_time for log in logs]
    intensities = [log.symptom_intensity for log in logs]
    colors = [_INTENSITY_COLORS.get(i, "#9ca3af") for i in intensities]

    fig, ax = plt.subplots(figsize=(10, 3.5))

    ax.vlines(dates, 0, intensities, color="#9ca3af", alpha=0.3, linewidth=1.2)
    ax.scatter(dates, intensities, c=colors, s=60, alpha=0.9,
               edgecolors="white", linewidth=0.5, zorder=3)

    ax.set_yticks([0, 1, 2, 3])
    ax.set_yticklabels([_INTENSITY_LABELS[i] for i in range(4)])
    ax.set_ylim(-0.4, 3.4)
    ax.set_title(f"Symptom: {symptom_name}", fontsize=13)
    ax.set_xlabel("Date")
    ax.grid(axis="x", alpha=0.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
    fig.autofmt_xdate(rotation=30, ha="right")
    plt.tight_layout()

    return _save_fig(fig)


def _save_fig(fig) -> BytesIO:
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
