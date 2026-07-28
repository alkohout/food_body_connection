# app/api/routes/plot_time_series_analysis.py
#
# Cross-correlation analysis between two logged variables (allergen or symptom).
#
# Method
# ------
# 1. Resample both event series onto a shared 12-hourly grid (fill gaps with 0).
# 2. Compute Pearson r at lags –7 d to +7 d (in 12 h steps).
#    Positive lag k  →  variable 1 occurred k×12 h *before* variable 2.
# 3. Plot CCF bars, ±95 % CI bands, highlighted peak, plain-English summary.

import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.api.routes.plot_event_series import (
    _get_allergen_data,
    _get_symptom_data,
    _parse_date,
    _save_fig,
)
from app.models.table_class import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


# ──────────────────────────────────────────────
# Peri-event time histogram
# ──────────────────────────────────────────────

def _naive(d):
    return pd.Timestamp(d.replace(tzinfo=None) if getattr(d, "tzinfo", None) else d)


def _dedupe_by_day(dates, tz_offset: int = 0):
    """Collapse anchor events that fall on the same local calendar day.

    A cyclical anchor like Period is logged once per cycle, but the same onset
    occasionally gets entered twice.  Left alone, each duplicate counts as a
    separate anchor, which inflates n_anchors and dilutes every rate.
    Keeps the earliest timestamp for each day.  Returns a sorted list.
    """
    by_day = {}
    for d in sorted(_naive(x) for x in dates):
        day = (d - pd.Timedelta(minutes=tz_offset)).normalize()
        if day not in by_day:
            by_day[day] = d
    return [by_day[k] for k in sorted(by_day)]


def _peri_event(anchor_dates, target_dates, window_days: int):
    """
    For each anchor event, count how many target events fall on each
    relative day (–window to +window).  Returns rates normalised by
    the number of anchor events, plus the overall baseline rate.
    """
    anchors = [_naive(d) for d in anchor_dates]
    targets = [_naive(d) for d in target_dates]
    n_anchors = len(anchors)

    days   = list(range(-window_days, window_days + 1))
    counts = {d: 0 for d in days}

    for anchor in anchors:
        for target in targets:
            delta = (target - anchor).total_seconds() / 86400  # fractional days
            day_bin = int(np.floor(delta))
            if -window_days <= day_bin <= window_days:
                counts[day_bin] += 1

    rates = [counts[d] / n_anchors for d in days]

    # Overall baseline: mean target events per day across the full span
    all_ts = anchors + targets
    span   = max((max(all_ts) - min(all_ts)).days, 1)
    baseline = len(targets) / span

    return days, rates, n_anchors, baseline


def _current_phase(anchors, now_utc):
    """Locate 'now' on the peri-event axis.

    anchors must already be deduped and sorted (naive UTC timestamps).

    The cycle length is the median gap between consecutive anchors, which lets
    us place today either after the most recent anchor or before the next
    expected one — whichever is nearer.  Relative day uses the same
    floor-of-fractional-days convention as _peri_event, so the marker lines up
    with the bar that describes it.

    Returns None when there is too little history, or when the anchor data is
    too stale for a projection to mean anything.
    """
    if len(anchors) < 3:
        return None

    gaps = [(b - a).days for a, b in zip(anchors, anchors[1:])]
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return None

    cycle = int(np.median(gaps))
    if cycle < 1:
        return None

    last = anchors[-1]
    days_since = int(np.floor((now_utc - last).total_seconds() / 86400))
    if days_since < 0:
        return None                      # anchor in the future — nothing to project from

    # Anchor history that stops more than two cycles back is stale (usually a
    # date filter ending in the past); a projection off it would be fiction.
    if days_since > 2 * cycle:
        return None

    next_expected = last + pd.Timedelta(days=cycle)
    days_until = int(np.ceil((next_expected - now_utc).total_seconds() / 86400))

    if days_until < 0:
        # Overdue: the next anchor was expected already.
        return {"rel_day": days_since, "phase": "after", "cycle": cycle,
                "days_since": days_since, "days_until": days_until, "overdue": True}

    if days_since <= days_until:
        return {"rel_day": days_since, "phase": "after", "cycle": cycle,
                "days_since": days_since, "days_until": days_until, "overdue": False}

    return {"rel_day": -days_until, "phase": "before", "cycle": cycle,
            "days_since": days_since, "days_until": days_until, "overdue": False}


@router.get("/plot_peri_event")
def plot_peri_event(
    item_type:   str = Query(..., alias="type"),
    name:        str = Query(..., min_length=1),
    type2:       str = Query(...),
    name2:       str = Query(..., min_length=1),
    window_days: int = Query(15, ge=1, le=30),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    tz_offset: int = Query(0),
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """
    Peri-event time histogram.

    Variable 2 is the sparse 'anchor' event (e.g. Period).
    Variable 1 is the target event whose rate is measured around each anchor
    (e.g. Triptan).

    Returns a bar chart of mean target events per day at each relative day
    (–window_days … +window_days), with a dashed baseline rate line and a
    marker showing where today sits in the current cycle.
    """
    if item_type not in ("allergen", "symptom"):
        raise HTTPException(400, "type must be 'allergen' or 'symptom'")
    if type2 not in ("allergen", "symptom"):
        raise HTTPException(400, "type2 must be 'allergen' or 'symptom'")

    from_dt = _parse_date(date_from, tz_offset_minutes=tz_offset)
    to_dt   = _parse_date(date_to, end_of_day=True, tz_offset_minutes=tz_offset)

    try:
        fetch1 = _get_allergen_data if item_type == "allergen" else _get_symptom_data
        fetch2 = _get_allergen_data if type2      == "allergen" else _get_symptom_data

        # variable 1 = target, variable 2 = anchor
        dates1, values1 = fetch1(db, current_user.user_id, name,  from_dt, to_dt)
        dates2, _       = fetch2(db, current_user.user_id, name2, from_dt, to_dt)

        if len(dates2) < 2:
            raise HTTPException(
                400,
                f"Need at least 2 '{name2}' events to run peri-event analysis."
            )

        anchors = _dedupe_by_day(dates2, tz_offset)

        days, rates, n_anchors, baseline = _peri_event(anchors, dates1, window_days)

        now_utc = _naive(datetime.now(timezone.utc))
        phase   = _current_phase(anchors, now_utc)

        # ── Interpretation ──────────────────────────────────────────
        max_rate = max(rates) if rates else 0
        max_day  = days[rates.index(max_rate)] if rates else 0

        if baseline > 0 and max_rate > baseline * 1.5:
            where = (
                f"{abs(max_day)} day(s) before" if max_day < 0
                else f"on the same day as" if max_day == 0
                else f"{max_day} day(s) after"
            )
            pct = (max_rate - baseline) / baseline * 100
            summary = (
                f"Peak usage {where} {name2}  "
                f"({pct:.0f} % above baseline,  r̄ = {max_rate:.2f} events/day)"
            )
        else:
            summary = f"No clear clustering of {name} around {name2} events."

        # ── Where are we now in the cycle? ──────────────────────────
        now_line = None
        if phase:
            rel = phase["rel_day"]
            if phase["phase"] == "after":
                where_now = (
                    f"today is the day of {name2}" if rel == 0
                    else f"{rel} day(s) after {name2}"
                )
            else:
                where_now = f"{abs(rel)} day(s) before the next expected {name2}"

            if -window_days <= rel <= window_days:
                rate_now = rates[days.index(rel)]
                if baseline > 0:
                    ratio = rate_now / baseline
                    risk = (
                        f"{ratio:.1f}× baseline" if ratio >= 1
                        else f"{ratio:.1f}× baseline (below average)"
                    )
                else:
                    risk = f"{rate_now:.2f} events/day"
                now_line = (
                    f"You are here: {where_now} "
                    f"(cycle ≈ {phase['cycle']} days).  "
                    f"Expected {name}: {rate_now:.2f}/day — {risk}"
                )
            else:
                now_line = (
                    f"You are here: {where_now} "
                    f"(cycle ≈ {phase['cycle']} days) — outside the ±{window_days} day window"
                )

            if phase["overdue"]:
                now_line += f".  Next {name2} is overdue by {abs(phase['days_until'])} day(s)"

        # ── Plot ────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(10, 4.2))

        bar_colors = ["#1d4ed8" if d == 0 else "#3b82f6" for d in days]
        ax.bar(days, rates, width=0.75, color=bar_colors, alpha=0.75, zorder=3)

        ax.axhline(baseline, color="#9ca3af", linestyle="--", linewidth=1.5,
                   label=f"Baseline  ({baseline:.2f} events/day)")
        ax.axvline(0, color="black", linewidth=0.7, alpha=0.3)

        # Highlight the peak bar
        ax.bar([max_day], [max_rate], width=0.75, color="#1d4ed8",
               alpha=1.0, edgecolor="black", linewidth=1.2, zorder=4)

        # "You are here" marker
        if phase and -window_days <= phase["rel_day"] <= window_days:
            rel = phase["rel_day"]
            ax.axvline(rel, color="#059669", linewidth=2.2, zorder=6,
                       label=f"Today  (day {rel:+d})")
            ax.annotate(
                "TODAY",
                xy=(rel, 0.98), xycoords=("data", "axes fraction"),
                ha="center", va="top", fontsize=8, fontweight="bold",
                color="#059669", zorder=7,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                          edgecolor="#059669", linewidth=0.8, alpha=0.95),
            )

        # A ±15 day window is 31 bars — thin the tick labels so they stay legible,
        # always keeping 0 on the axis.
        step  = 1 if window_days <= 7 else (2 if window_days <= 15 else 5)
        ax.set_xticks([d for d in days if d % step == 0])
        ax.tick_params(axis="x", labelsize=8)
        ax.set_xlabel(f"Days relative to {name2}  (0 = day of event)", fontsize=9)
        ax.set_ylabel(f"Mean {name} events / day")
        ax.set_title(
            f"Peri-event analysis:  {name}  around  {name2}  "
            f"(n = {n_anchors} anchor events)",
            fontsize=12,
        )
        ax.legend(frameon=False, fontsize=8, loc="upper right")
        ax.grid(axis="y", alpha=0.2)
        ax.set_ylim(bottom=0)

        if now_line:
            fig.text(0.5, 0.075, summary, ha="center", fontsize=9,
                     color="#374151", style="italic")
            fig.text(0.5, 0.012, now_line, ha="center", fontsize=9.5,
                     color="#059669", fontweight="bold")
            rect = [0, 0.13, 1, 1]
        else:
            fig.text(0.5, 0.01, summary, ha="center", fontsize=9,
                     color="#374151", style="italic")
            rect = [0, 0.06, 1, 1]

        plt.tight_layout(rect=rect)
        return StreamingResponse(_save_fig(fig), media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("plot_peri_event failed")
        raise HTTPException(500, f"Failed to generate plot: {e}")

_BIN_FREQ   = "12h"   # time-grid resolution
_MAX_LAG    = 14      # ±14 bins = ±7 days


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _to_series(dates, values, item_type, idx: pd.DatetimeIndex) -> pd.Series:
    """Bin event data onto a regular grid and fill gaps with 0."""
    if not dates:
        return pd.Series(0.0, index=idx)

    naive = [d.replace(tzinfo=None) if getattr(d, "tzinfo", None) else d for d in dates]

    if item_type == "allergen":
        vals = [1.0 if v is None else float(v) for v in values]
    else:
        vals = [float(v) for v in values]

    df = pd.DataFrame({"dt": pd.to_datetime(naive), "val": vals})
    s  = df.set_index("dt")["val"].resample(_BIN_FREQ).sum()
    return s.reindex(idx, fill_value=0.0)


def _ccf(s1: pd.Series, s2: pd.Series, max_lag: int):
    """Pearson r at each lag in [–max_lag, +max_lag]."""
    lags  = list(range(-max_lag, max_lag + 1))
    corrs = [float(s1.corr(s2.shift(-k)) or 0.0) for k in lags]
    return lags, corrs


def _lag_label(lag_hours: float) -> str:
    if abs(lag_hours) < 24:
        return f"{abs(lag_hours):.0f} h"
    return f"{abs(lag_hours) / 24:.1f} days"


# ──────────────────────────────────────────────
# Route
# ──────────────────────────────────────────────

@router.get("/plot_cross_correlation")
def plot_cross_correlation(
    item_type: str = Query(..., alias="type"),
    name:      str = Query(..., min_length=1),
    type2:     str = Query(...),
    name2:     str = Query(..., min_length=1),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    if item_type not in ("allergen", "symptom"):
        raise HTTPException(400, "type must be 'allergen' or 'symptom'")
    if type2 not in ("allergen", "symptom"):
        raise HTTPException(400, "type2 must be 'allergen' or 'symptom'")

    from_dt = _parse_date(date_from)
    to_dt   = _parse_date(date_to, end_of_day=True)

    try:
        fetch1 = _get_allergen_data if item_type == "allergen" else _get_symptom_data
        fetch2 = _get_allergen_data if type2      == "allergen" else _get_symptom_data

        dates1, values1 = fetch1(db, current_user.user_id, name,  from_dt, to_dt)
        dates2, values2 = fetch2(db, current_user.user_id, name2, from_dt, to_dt)

        # Build shared 12-hourly grid
        all_naive = [
            d.replace(tzinfo=None) if getattr(d, "tzinfo", None) else d
            for d in list(dates1) + list(dates2)
        ]
        grid_start = pd.Timestamp(min(all_naive)).floor("D")
        grid_end   = pd.Timestamp(max(all_naive)).ceil("D") + pd.Timedelta(days=1)
        idx = pd.date_range(grid_start, grid_end, freq=_BIN_FREQ)

        min_bins = _MAX_LAG * 3
        if len(idx) < min_bins:
            raise HTTPException(
                400,
                f"Need at least {min_bins * 0.5:.0f} days of overlapping data "
                "to compute cross-correlation. Try a wider date range."
            )

        s1 = _to_series(dates1, values1, item_type, idx)
        s2 = _to_series(dates2, values2, type2,     idx)

        max_lag = min(_MAX_LAG, len(idx) // 3)
        lags, corrs = _ccf(s1, s2, max_lag)

        lag_hours = [k * 12 for k in lags]     # convert bins → hours
        ci = 1.96 / np.sqrt(max(len(s1), 1))   # ±95 % CI

        # Peak
        peak_i     = int(np.argmax(np.abs(corrs)))
        peak_h     = lag_hours[peak_i]
        peak_r     = corrs[peak_i]
        significant = abs(peak_r) > ci

        if not significant:
            summary = "No significant correlation detected within the 95 % confidence interval."
        elif peak_h > 0:
            summary = (
                f"Peak at +{_lag_label(peak_h)}: {name} may lead {name2} "
                f"by ~{_lag_label(peak_h)}  (r = {peak_r:+.2f})"
            )
        elif peak_h < 0:
            summary = (
                f"Peak at −{_lag_label(peak_h)}: {name2} may lead {name} "
                f"by ~{_lag_label(abs(peak_h))}  (r = {peak_r:+.2f})"
            )
        else:
            summary = f"Strongest same-time association  (r = {peak_r:+.2f})"

        # ── Plot ──────────────────────────────
        fig, ax = plt.subplots(figsize=(10, 4.2))

        bar_colors = ["#2563eb" if c >= 0 else "#ef4444" for c in corrs]
        ax.bar(lag_hours, corrs, width=9, color=bar_colors, alpha=0.65, zorder=3)

        # Highlight peak
        ax.bar(
            [peak_h], [peak_r], width=9,
            color="#2563eb" if peak_r >= 0 else "#ef4444",
            alpha=1.0, edgecolor="black", linewidth=1.2, zorder=4,
        )

        # CI bands
        ax.axhline( ci, color="#9ca3af", linestyle="--", linewidth=1, label="95 % CI")
        ax.axhline(-ci, color="#9ca3af", linestyle="--", linewidth=1)
        ax.axhline(0, color="black", linewidth=0.6)
        ax.axvline(0, color="black", linewidth=0.5, alpha=0.25)

        ax.set_title(f"Cross-Correlation:  {name}  ×  {name2}", fontsize=12)
        ax.set_xlabel(
            "Lag (hours)\n"
            f"← {name2} leads    |    {name} leads →",
            fontsize=9, labelpad=6,
        )
        ax.set_ylabel("Correlation  (r)")
        ax.set_ylim(-1.05, 1.05)
        ax.legend(frameon=False, fontsize=8, loc="upper right")
        ax.grid(axis="y", alpha=0.2)

        # Plain-English finding below the axes
        fig.text(
            0.5, 0.01, summary,
            ha="center", fontsize=9, color="#374151", style="italic",
        )

        plt.tight_layout(rect=[0, 0.06, 1, 1])   # leave room for fig.text
        return StreamingResponse(_save_fig(fig), media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("plot_cross_correlation failed")
        raise HTTPException(500, f"Failed to generate plot: {e}")
