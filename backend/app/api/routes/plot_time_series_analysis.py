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


def _local_naive(d, tz_offset: int = 0):
    """A stored UTC timestamp as the user's local wall-clock time (naive).

    tz_offset is JS Date.getTimezoneOffset() — minutes to add to local time to
    reach UTC (NZ = -720), so local = utc - tz_offset.
    """
    return _naive(d) - pd.Timedelta(minutes=tz_offset)


def _local_day(d, tz_offset: int = 0):
    """Normalise a timestamp to the user's local calendar day.

    Everything downstream of this — peri-event bins, cycle length, the TODAY
    marker and the headache forecast — works in whole local days.  Health events
    are recorded at daily resolution, so "the day after my period started" must
    mean the same thing everywhere regardless of clock time.
    """
    return _local_naive(d, tz_offset).normalize()


def _anchor_days(dates, tz_offset: int = 0):
    """Sorted unique local calendar days on which an anchor event was logged.

    A cyclical anchor like Period is logged once per cycle, but the same onset
    occasionally gets entered twice.  Left alone, each duplicate counts as a
    separate anchor, which inflates n_anchors and dilutes every rate.
    """
    return sorted({_local_day(d, tz_offset) for d in dates})


def _peri_event(anchor_days, target_dates, window_days: int, tz_offset: int = 0):
    """
    For each anchor event, count how many target events fall on each
    relative day (–window to +window).  Returns rates normalised by
    the number of anchor events, plus the overall baseline rate.

    Bins are whole local calendar days: an event logged the day after an anchor
    lands in bin +1 whatever the clock times were.  Binning on raw timestamp
    deltas instead would put an event 23 h later in bin 0 and one 25 h later in
    bin +1, which does not match how the days were actually recorded.
    """
    targets   = [_local_day(d, tz_offset) for d in target_dates]
    n_anchors = len(anchor_days)

    days   = list(range(-window_days, window_days + 1))
    counts = {d: 0 for d in days}

    all_days = list(anchor_days) + targets
    obs_start, obs_end = min(all_days), max(all_days)

    # Not every anchor can contribute to every bin.  The most recent anchor has
    # no data yet for the days after it — they are still in the future — so
    # dividing those bins by the full anchor count understates them by roughly
    # one anchor's worth.  Count, per bin, how many anchors were actually
    # observable there and normalise by that instead.
    observable = {d: 0 for d in days}
    for anchor in anchor_days:
        for k in days:
            if obs_start <= anchor + pd.Timedelta(days=k) <= obs_end:
                observable[k] += 1

    for anchor in anchor_days:
        for target in targets:
            day_bin = (target - anchor).days
            if -window_days <= day_bin <= window_days:
                counts[day_bin] += 1

    rates = [
        counts[d] / observable[d] if observable[d] else float("nan")
        for d in days
    ]

    # Overall baseline: mean target events per day across the full span
    span     = max((obs_end - obs_start).days, 1)
    baseline = len(targets) / span

    return days, rates, n_anchors, baseline, observable


def cycle_length(anchor_days):
    """Typical gap between consecutive anchor events, in whole local days.

    The median rather than the mean: with a handful of cycles one unusually
    long or short gap would drag a mean noticeably, and a cycle length is a
    typical value rather than a total to be averaged.  Zero-length gaps are
    dropped — they mean the same onset was logged twice, not a real cycle.

    Shared by the peri-event marker, the headache forecast and /analysis/stats
    so all three agree on when the next event is due.  Returns None when there
    is not enough history.
    """
    gaps = [(b - a).days for a, b in zip(anchor_days, anchor_days[1:])]
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return None
    return int(np.median(gaps))


def _current_phase(anchor_days, today_local):
    """Locate today on the peri-event axis.

    anchor_days must be sorted unique local calendar days (see _anchor_days),
    and today_local the user's local calendar day.  All arithmetic is in whole
    days, matching _peri_event's bins, so the marker lines up with the bar that
    describes it.

    The cycle length is the median gap between consecutive anchors, which lets
    us place today either after the most recent anchor or before the next
    expected one — whichever is nearer.

    Returns None when there is too little history, or when the anchor data is
    too stale for a projection to mean anything.
    """
    if len(anchor_days) < 3:
        return None

    cycle = cycle_length(anchor_days)
    if not cycle or cycle < 1:
        return None

    last = anchor_days[-1]
    days_since = (today_local - last).days
    if days_since < 0:
        return None                      # anchor in the future — nothing to project from

    # Anchor history that stops more than two cycles back is stale (usually a
    # date filter ending in the past); a projection off it would be fiction.
    if days_since > 2 * cycle:
        return None

    next_expected = last + pd.Timedelta(days=cycle)
    days_until = (next_expected - today_local).days

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

        anchors = _anchor_days(dates2, tz_offset)

        days, rates, n_anchors, baseline, observable = _peri_event(
            anchors, dates1, window_days, tz_offset
        )

        today_local = _local_day(datetime.now(timezone.utc), tz_offset)
        phase       = _current_phase(anchors, today_local)

        # ── Interpretation ──────────────────────────────────────────
        finite = [r for r in rates if not np.isnan(r)]
        if not finite:
            raise HTTPException(
                400, "No overlapping data between the two variables in this window."
            )

        max_rate = max(finite)
        # Several days can share the peak; naming only the first is misleading.
        peak_days = [d for d, r in zip(days, rates)
                     if not np.isnan(r) and r == max_rate]
        max_day = peak_days[0]

        def _describe(d):
            return (f"{abs(d)} day(s) before" if d < 0
                    else "on the same day as" if d == 0
                    else f"{d} day(s) after")

        if baseline > 0 and max_rate > baseline * 1.5:
            if len(peak_days) == 1:
                where = _describe(max_day)
            else:
                joined = ", ".join(f"{d:+d}" for d in peak_days)
                where = f"equally at days {joined} relative to"
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

            in_window = -window_days <= rel <= window_days
            rate_now  = rates[days.index(rel)] if in_window else float("nan")

            if not in_window:
                now_line = (
                    f"You are here: {where_now} "
                    f"(cycle ≈ {phase['cycle']} days) — outside the ±{window_days} day window"
                )
            elif np.isnan(rate_now):
                now_line = (
                    f"You are here: {where_now} "
                    f"(cycle ≈ {phase['cycle']} days) — no comparable history at this point yet"
                )
            else:
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

            if phase["overdue"]:
                now_line += f".  Next {name2} is overdue by {abs(phase['days_until'])} day(s)"

        # ── Plot ────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(10, 4.2))

        bar_colors = ["#1d4ed8" if d == 0 else "#3b82f6" for d in days]
        ax.bar(days, rates, width=0.75, color=bar_colors, alpha=0.75, zorder=3)

        # Only flag bins resting on materially less evidence.  Nearly every bin
        # misses the odd anchor at the edges of the data; hatching a one-cycle
        # shortfall would mark almost the whole chart and mean nothing.
        thin = [d for d in days if 0 < observable[d] <= n_anchors - 2]
        if thin:
            ax.bar(thin, [rates[days.index(d)] for d in thin], width=0.75,
                   color="none", edgecolor="#1e3a8a", hatch="///",
                   linewidth=0.0, zorder=3.5,
                   label=f"≤ {n_anchors - 2} cycles of data")

        ax.axhline(baseline, color="#9ca3af", linestyle="--", linewidth=1.5,
                   label=f"Baseline  ({baseline:.2f} events/day)")
        ax.axvline(0, color="black", linewidth=0.7, alpha=0.3)

        # Highlight the peak bar(s) — there can be a tie
        ax.bar(peak_days, [max_rate] * len(peak_days), width=0.75, color="#1d4ed8",
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
        cover = [v for v in observable.values() if v]
        cover_note = (
            f"{min(cover)}–{max(cover)} cycles per bin" if min(cover) != max(cover)
            else f"{max(cover)} cycles per bin"
        )
        ax.set_title(
            f"Peri-event analysis:  {name}  around  {name2}  "
            f"(n = {n_anchors} anchors, {cover_note})",
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

def _to_series(dates, values, item_type, idx: pd.DatetimeIndex, tz_offset: int = 0) -> pd.Series:
    """Bin event data onto a regular grid and fill gaps with 0."""
    if not dates:
        return pd.Series(0.0, index=idx)

    naive = [_local_naive(d, tz_offset) for d in dates]

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
    tz_offset: int = Query(0),
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    if item_type not in ("allergen", "symptom"):
        raise HTTPException(400, "type must be 'allergen' or 'symptom'")
    if type2 not in ("allergen", "symptom"):
        raise HTTPException(400, "type2 must be 'allergen' or 'symptom'")

    from_dt = _parse_date(date_from, tz_offset_minutes=tz_offset)
    to_dt   = _parse_date(date_to, end_of_day=True, tz_offset_minutes=tz_offset)

    try:
        fetch1 = _get_allergen_data if item_type == "allergen" else _get_symptom_data
        fetch2 = _get_allergen_data if type2      == "allergen" else _get_symptom_data

        dates1, values1 = fetch1(db, current_user.user_id, name,  from_dt, to_dt)
        dates2, values2 = fetch2(db, current_user.user_id, name2, from_dt, to_dt)

        # Build shared 12-hourly grid, anchored to the user's local midnight so
        # the two half-day bins line up with their day rather than UTC's.
        all_naive = [_local_naive(d, tz_offset) for d in list(dates1) + list(dates2)]
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

        s1 = _to_series(dates1, values1, item_type, idx, tz_offset)
        s2 = _to_series(dates2, values2, type2,     idx, tz_offset)

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
