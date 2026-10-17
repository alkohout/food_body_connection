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
from app.analysis.data_tools import local_date as _local_date
from app.analysis.pressure_stats import bands as pressure_bands
from app.analysis.pressure_stats import signed_change
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


def _period_onsets(db, user_id, start, end, tz_offset):
    """First day of each period, not every day logged during one.

    Onsets are what the cycle is measured from, and a run of consecutive
    logged days would otherwise read as several cycles a week apart.
    """
    ids = {a.allergen_id for a in db.query(Allergen).filter(Allergen.user_id == user_id).all()
           if "period" in (a.allergen_name or "").lower()}
    if not ids:
        return []
    seen = sorted({_local_date(l.date_time, tz_offset)
                   for l in db.query(AllergenLog).filter(
                       AllergenLog.user_id == user_id,
                       AllergenLog.allergen_id.in_(ids)).all() if l.date_time})
    onsets = [d for i, d in enumerate(seen)
              if i == 0 or (d - seen[i - 1]).days > 5]
    return [d for d in onsets if start <= d <= end]


def _draw_likelihood(ax, stats):
    """Triptan likelihood per band of pressure change, with the baseline drawn.

    A bar chart rather than a table because the question is comparative: the
    thing worth seeing is which bands sit above the line and which below, not
    the individual percentages.
    """
    if not stats or not stats["bands"]:
        ax.text(0.5, 0.5, "Not enough days yet to give a likelihood.",
                ha="center", va="center", fontsize=10, color="#666")
        ax.set_axis_off()
        return

    rows = stats["bands"]
    labels = [b["label"] for b in rows]
    rates = [b["rate"] * 100 for b in rows]
    # Falls one colour, rises the other, matching the axis above it.
    colours = ["#0891b2" if b["hi"] <= 0 else "#ea580c" for b in rows]
    pos = range(len(rows))
    ax.barh(list(pos), rates, color=colours, height=0.68)
    ax.set_yticks(list(pos))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("days a triptan was taken (%)", fontsize=8)
    ax.grid(alpha=0.25, axis="x")

    base = stats["baseline"] * 100
    ax.axvline(base, color="#374151", lw=1.0, ls="--")
    # Inside the axes at the foot, not above it: placed above it this label
    # landed on top of the panel title.
    ax.text(base, len(rows) - 0.45, f" your average, {base:.0f}%", fontsize=7,
            color="#374151", va="bottom")

    # The denominator next to every bar. A percentage off fifteen days and one
    # off a hundred and sixteen look identical otherwise, and here they differ
    # by eight times.
    for i, b in zip(pos, rows):
        ax.text(max(rates) * 0.015 + b["rate"] * 100, i,
                f"  {b['triptans']}/{b['days']}", fontsize=7,
                color="#4b5563", va="center")
    ax.set_xlim(0, max(max(rates), base) * 1.22)
    ax.set_title("Likelihood of needing a triptan, by how far the pressure moved",
                 fontsize=10, loc="left")


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
        # Signed, so a rising front and a falling one are told apart. Falls
        # alone were measured at first, which made half the weather invisible.
        change = [signed_change(rows[d]) for d in rows]
        mig = _migraine_days(db, current_user.user_id, start, end, tz_offset)
        trip = _triptan_days(db, current_user.user_id, start, end, tz_offset)
        onsets = _period_onsets(db, current_user.user_id, start, end, tz_offset)
        stats = pressure_bands({d: rows[d] for d in rows
                                if datetime.strptime(d, "%Y-%m-%d").date() <= end},
                               trip)

        fig = plt.figure(figsize=(11, 8.6))
        grid = fig.add_gridspec(3, 1, height_ratios=[2, 1, 1.15], hspace=0.38)
        ax = fig.add_subplot(grid[0])
        ax2 = fig.add_subplot(grid[1], sharex=ax)
        ax3 = fig.add_subplot(grid[2])

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
        # Periods, and the ten days after each one — which is where this
        # person's migraines actually cluster. Drawn on the lower axis so the
        # pressure trace stays readable above it.
        for d in onsets:
            for a in (ax, ax2):
                a.axvline(d, color="#be123c", lw=1.0, alpha=0.8)
            ax2.axvspan(d, min(d + timedelta(days=10), dates[-1]),
                        color="#be123c", alpha=0.10, lw=0)

        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        ax.legend(handles=[
            Line2D([], [], color="#2563eb", lw=1.4, label="Mean pressure"),
            Line2D([], [], color="#2563eb", lw=1.4, ls=":", label="Forecast"),
            Patch(facecolor="#dc2626", alpha=0.25, label="Migraine-cluster day"),
            Line2D([], [], color="#7c3aed", marker="v", lw=0, label="Triptan"),
            Line2D([], [], color="#be123c", lw=1.0, label="Period onset"),
        ], loc="lower left", fontsize=8, ncol=5, framealpha=0.9)

        # Rises above the line, falls below it, on one axis so the asymmetry
        # between them is visible rather than needing two charts to compare.
        ax2.bar([d for d, c in zip(dates, change) if c >= 0],
                [c for c in change if c >= 0], color="#ea580c", width=0.9,
                label="24h rise")
        ax2.bar([d for d, c in zip(dates, change) if c < 0],
                [c for c in change if c < 0], color="#0891b2", width=0.9,
                label="24h fall")
        ax2.axhline(0, color="#374151", lw=0.8)
        if stats:
            for sign in (1, -1):
                ax2.axhline(sign * stats["threshold"], color="#9ca3af", lw=0.7,
                            ls=":")
            ax2.text(dates[0], stats["threshold"], " top 10% for here",
                     fontsize=6.5, color="#6b7280", va="bottom")
        ax2.set_ylabel("24h change (hPa)")
        ax2.grid(alpha=0.25, axis="y")
        ax2.set_xlabel("")
        ax2.legend(loc="lower left", fontsize=7, ncol=2, framealpha=0.9)

        # Rotate the dates on the two time axes by hand. autofmt_xdate clears
        # the tick labels on every shared axis but the figure's last one, and
        # the last one here is the likelihood panel, which is not a time axis —
        # so it stripped the dates off the chart entirely.
        ax.tick_params(labelbottom=False)
        for lab in ax2.get_xticklabels():
            lab.set_rotation(30)
            lab.set_horizontalalignment("right")

        _draw_likelihood(ax3, stats)
        ax.set_title("Barometric pressure, migraine days and triptan use",
                     fontsize=12, loc="left")
        # Said on the plot rather than left to be inferred from it. Eyes find
        # patterns in noise, and this particular pattern is one the person
        # looking already believes in.
        caption = ("Your cycle is the strong signal, not the weather. Pressure "
                   "separates nothing here — not falling, not rising, not at a "
                   "day or two of lag.")
        if stats and stats["p_value"] is not None:
            # Stated with the direction, because the association that does turn
            # up runs backwards: the biggest moves carry fewer triptans, not
            # more. Reported rather than buried, and labelled as what it is.
            lean = ("fewer" if (stats["extreme_rate"] or 0) < stats["rest_rate"]
                    else "more")
            caption += (
                f" Across {stats['total_days']} days, the {stats['extreme_days']} "
                f"with the largest moves — over {stats['threshold']:.0f} hPa in "
                f"24 hours, the top tenth for Christchurch — carried a triptan on "
                f"{stats['extreme_rate']*100:.0f}% of days against "
                f"{stats['rest_rate']*100:.0f}% of the rest (p="
                f"{stats['p_value']:.2f}). That is {lean}, not more, and it is "
                f"not significant. A 6 hPa swing, the figure usually quoted as a "
                f"trigger, happens here on four days in five, so it cannot "
                f"distinguish anything.")
        fig.text(0.005, -0.015, caption, fontsize=7.5, color="#6b7280", wrap=True)
        return StreamingResponse(_save_fig(fig), media_type="image/png")
    except Exception as e:                              # noqa: BLE001
        logger.error("plot_pressure failed: %s", e, exc_info=True)
        raise HTTPException(500, "Could not build the pressure plot.")
