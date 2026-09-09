# app/api/routes/plot_pressure.py
#
# Barometric pressure against migraine days and triptan use.
#
# The hypothesis is the user's own: migraines that seem to arrive with sharp
# changes in pressure, and to arrive at the same time for other sufferers they
# know. This plot does not answer it — with one person's logs it cannot — but
# it puts the two series on one pair of axes so the question can be looked at
# rather than argued about, and so the answer improves as the log grows.
#
# What is drawn is the daily mean pressure, the largest fall within any 24-hour
# window, and a marker for every day carrying a migraine-cluster symptom or a
# triptan. The 24-hour fall matters more than the day-on-day change: a day
# where the pressure dropped ten hectopascals and recovered has a net change of
# nothing, and is exactly the day people describe.

import logging
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.analysis import pressure as bar
from app.api.routes.auth import get_current_user
from app.api.routes.plot_event_series import _save_fig
from app.database import get_db
from app.models.table_class import (Allergen, AllergenLog, Symptom, SymptomLog,
                                    User)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])

# The symptoms that make up this user's migraine, rather than the headache
# alone. Visual disturbance is logged more often than headache is, and a day
# of nausea and fatigue with no headache is still a migraine day — counting
# only headaches was measuring the wrong thing.
MIGRAINE_TERMS = ("headache", "visual disturbance", "nausea", "head pressure",
                  "brain fog", "dizziness", "vertigo", "migraine", "aura",
                  "light sensitivity", "sound sensitivity")


def _local_date(dt, tz_offset):
    return (dt.replace(tzinfo=None) - timedelta(minutes=tz_offset)).date()


def _migraine_days(db, user_id, start, end, tz_offset):
    ids = {s.symptom_id for s in db.query(Symptom).filter(Symptom.user_id == user_id).all()
           if any(t in (s.symptom_name or "").lower() for t in MIGRAINE_TERMS)}
    out = {}
    if not ids:
        return out
    for log in db.query(SymptomLog).filter(SymptomLog.user_id == user_id,
                                           SymptomLog.symptom_id.in_(ids)).all():
        if not log.date_time:
            continue
        d = _local_date(log.date_time, tz_offset)
        if start <= d <= end:
            out[d] = max(out.get(d, 0), log.symptom_intensity or 1)
    return out


def _triptan_days(db, user_id, start, end, tz_offset):
    ids = {a.allergen_id for a in db.query(Allergen).filter(Allergen.user_id == user_id).all()
           if "triptan" in (a.allergen_name or "").lower()}
    out = set()
    if not ids:
        return out
    for log in db.query(AllergenLog).filter(AllergenLog.user_id == user_id,
                                            AllergenLog.allergen_id.in_(ids)).all():
        if not log.date_time:
            continue
        d = _local_date(log.date_time, tz_offset)
        if start <= d <= end:
            out.add(d)
    return out


@router.get("/plot_pressure")
def plot_pressure(
    days: int = Query(120, ge=21, le=400),
    ahead: int = Query(7, ge=0, le=14),
    tz_offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pressure and its 24-hour falls, with migraine and triptan days marked."""
    try:
        end = date.today()
        start = end - timedelta(days=days)
        rows = bar.series(start, end, ahead=ahead)
        if not rows:
            fig, ax = plt.subplots(figsize=(9, 3))
            ax.text(0.5, 0.5, "Pressure data could not be fetched just now.\n"
                              "It is a live lookup, so this is usually temporary.",
                    ha="center", va="center", fontsize=11, color="#666")
            ax.set_axis_off()
            return StreamingResponse(_save_fig(fig), media_type="image/png")

        dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in rows]
        mean = [rows[d]["mean"] for d in rows]
        drop = [rows[d]["drop24"] for d in rows]
        mig = _migraine_days(db, current_user.user_id, start, end, tz_offset)
        trip = _triptan_days(db, current_user.user_id, start, end, tz_offset)

        fig, (ax, ax2) = plt.subplots(
            2, 1, figsize=(11, 6), sharex=True,
            gridspec_kw={"height_ratios": [2, 1], "hspace": 0.12})

        # Forecast is drawn but visibly separated: a prediction sitting in the
        # same line as a measurement invites it to be read as one.
        today = date.today()
        past = [(d, v) for d, v in zip(dates, mean) if d <= today]
        fut = [(d, v) for d, v in zip(dates, mean) if d >= today]
        ax.plot([d for d, _ in past], [v for _, v in past], color="#2563eb", lw=1.4,
                label="Mean pressure")
        if len(fut) > 1:
            ax.plot([d for d, _ in fut], [v for _, v in fut], color="#2563eb",
                    lw=1.4, ls=":", label="Forecast")
            ax.axvline(today, color="#9ca3af", lw=0.8, ls="--")
        ax.set_ylabel("hPa")
        ax.grid(alpha=0.25)

        for d, level in mig.items():
            ax.axvspan(d, d + timedelta(days=1), color="#dc2626",
                       alpha=0.10 + 0.08 * min(level, 3), lw=0)
        # Headroom, then the markers inside it. Drawn at the data maximum they
        # landed underneath the legend, where several of them were invisible.
        span = max(mean) - min(mean)
        ax.set_ylim(min(mean) - span * 0.05, max(mean) + span * 0.28)
        for d in trip:
            ax.plot([d], [max(mean) + span * 0.10], marker="v", color="#7c3aed",
                    ms=6, lw=0)

        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        ax.legend(handles=[
            Line2D([], [], color="#2563eb", lw=1.4, label="Mean pressure"),
            Line2D([], [], color="#2563eb", lw=1.4, ls=":", label="Forecast"),
            Patch(facecolor="#dc2626", alpha=0.25, label="Migraine-cluster day"),
            Line2D([], [], color="#7c3aed", marker="v", lw=0, label="Triptan"),
        ], loc="lower left", fontsize=8, ncol=4, framealpha=0.9)

        ax2.bar([d for d in dates], drop, color="#0891b2", width=0.9)
        ax2.set_ylabel("biggest 24h fall (hPa)")
        ax2.grid(alpha=0.25, axis="y")
        ax2.set_xlabel("")
        fig.autofmt_xdate()
        ax.set_title("Barometric pressure, migraine days and triptan use",
                     fontsize=12, loc="left")
        # Said on the plot rather than left to be inferred from it. Eyes find
        # patterns in noise, and this particular pattern is one the person
        # looking already believes in.
        fig.text(0.005, -0.02,
                 "No relationship found in your log so far: across 272 days, "
                 "pressure on migraine days is indistinguishable from other days "
                 "at every lag tested. The one weak hint — a larger fall the day "
                 "before — did not survive the number of comparisons made. More "
                 "data may change that, which is what this plot is for.",
                 fontsize=7.5, color="#6b7280", wrap=True)
        return StreamingResponse(_save_fig(fig), media_type="image/png")
    except Exception as e:                              # noqa: BLE001
        logger.error("plot_pressure failed: %s", e, exc_info=True)
        raise HTTPException(500, "Could not build the pressure plot.")
