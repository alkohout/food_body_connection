# app/api/routes/plot_headache_forecast.py
#
# Forward-looking traffic-light calendar: likelihood of a headache day for each
# of the next N days.
#
# Method
# ------
# 1. Take the cyclical anchor (Period) and collapse it to one event per local day.
# 2. Cycle length = median gap between consecutive anchors.
# 3. For every completed cycle, record which cycle-days carried a target event.
#    That gives P(event | cycle day) — an empirical, per-day hit rate.
# 4. Smooth circularly by ±1 day: adjacent cycle days are not independent, and
#    with < 10 cycles a single bin is far too noisy on its own.
# 5. Project forward from the last anchor and colour each future date by how its
#    probability compares with the user's own overall daily rate.
#
# The output is deliberately three coarse bands. With a handful of cycles the
# per-day estimates carry wide confidence intervals — enough to rank days, not
# enough to quote a percentage at anyone.

import logging
import traceback
from io import BytesIO
from datetime import datetime, timezone
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.api.routes.plot_event_series import _get_allergen_data, _get_symptom_data, _save_fig
from app.api.routes.plot_time_series_analysis import _local_day, cycle_length
from app.database import get_db
from app.models.table_class import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])

BAND_COLORS = {
    "low":      "#86c98a",
    "moderate": "#f2c14e",
    "high":     "#e06666",
    "unknown":  "#e8e8e8",
}
BAND_LABELS = {"low": "Low", "moderate": "Moderate", "high": "High"}

# Minimum completed cycles before a forecast means anything at all.
MIN_CYCLES = 4


def _local_days(dates, tz_offset: int):
    """Normalise event timestamps to the user's local calendar day."""
    return {_local_day(d, tz_offset) for d in dates}


def _cycle_profile(anchor_days, event_days, cycle: int):
    """Empirical P(event) for each cycle day 0 … cycle-1.

    Only completed cycles (those with a following anchor) contribute, so a
    part-finished current cycle cannot drag the estimate around.  Cycles shorter
    than the median leave their tail bins unobserved rather than counting them
    as misses — otherwise short cycles would fake a quiet end-of-cycle.
    """
    hits   = np.zeros(cycle)
    totals = np.zeros(cycle)

    for start, nxt in zip(anchor_days, anchor_days[1:]):
        length = (nxt - start).days
        for k in range(min(cycle, length)):
            totals[k] += 1
            if (start + pd.Timedelta(days=k)) in event_days:
                hits[k] += 1

    with np.errstate(invalid="ignore", divide="ignore"):
        p_raw = np.where(totals > 0, hits / np.maximum(totals, 1), np.nan)

    # Circular ±1 smoothing — the cycle wraps, so day 0's neighbours are the
    # last cycle day and day 1.
    p_smooth = np.array([
        np.nanmean([p_raw[(k - 1) % cycle], p_raw[k], p_raw[(k + 1) % cycle]])
        for k in range(cycle)
    ])

    overall = hits.sum() / totals.sum() if totals.sum() else 0.0
    n_cycles = int(totals.max()) if totals.size else 0
    return p_smooth, totals, overall, n_cycles


def _band(p: float, overall: float) -> str:
    """Rank a day against the user's own average day."""
    if np.isnan(p):
        return "unknown"
    if overall <= 0:
        return "low"
    if p >= overall * 1.5:
        return "high"
    if p >= overall * 0.75:
        return "moderate"
    return "low"


def _message_fig(text: str) -> BytesIO:
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=11,
            color="#666", wrap=True)
    ax.set_axis_off()
    return _save_fig(fig)


@router.get("/plot_headache_forecast")
def plot_headache_forecast(
    target_type: str = Query("symptom"),
    target:      str = Query("Headache"),
    anchor_type: str = Query("allergen"),
    anchor:      str = Query("Period"),
    days_ahead:  int = Query(14, ge=7, le=35),
    tz_offset:   int = Query(0),
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Traffic-light calendar of predicted headache likelihood, starting today.

    The forecast is anchored on a cyclical event (Period by default). Each future
    date is mapped to its position in the projected cycle and coloured by the
    historical hit rate at that position.
    """
    if target_type not in ("allergen", "symptom"):
        raise HTTPException(400, "target_type must be 'allergen' or 'symptom'")
    if anchor_type not in ("allergen", "symptom"):
        raise HTTPException(400, "anchor_type must be 'allergen' or 'symptom'")

    try:
        fetch_t = _get_allergen_data if target_type == "allergen" else _get_symptom_data
        fetch_a = _get_allergen_data if anchor_type == "allergen" else _get_symptom_data

        # A user with no Period/Headache history is the normal case, not an
        # error — show them why the panel is empty instead of a 404.
        try:
            target_dates, _ = fetch_t(db, current_user.user_id, target, None, None)
            anchor_dates, _ = fetch_a(db, current_user.user_id, anchor, None, None)
        except HTTPException as exc:
            if exc.status_code == 404:
                return StreamingResponse(_message_fig(
                    f"This forecast needs both a '{anchor}' and a '{target}' log.\n\n"
                    f"{exc.detail}"
                ), media_type="image/png")
            raise

        event_days  = _local_days(target_dates, tz_offset)
        anchor_days = sorted(_local_days(anchor_dates, tz_offset))

        if len(anchor_days) < MIN_CYCLES + 1:
            return StreamingResponse(_message_fig(
                f"Not enough {anchor} history to forecast.\n"
                f"Need at least {MIN_CYCLES + 1} logged {anchor} events "
                f"(currently {len(anchor_days)})."
            ), media_type="image/png")

        cycle = cycle_length(anchor_days)
        if not cycle or cycle < 7:
            return StreamingResponse(_message_fig(
                f"{anchor} events are too close together to form a cycle."
            ), media_type="image/png")

        p_smooth, totals, overall, n_cycles = _cycle_profile(
            anchor_days, event_days, cycle
        )
        if n_cycles < MIN_CYCLES:
            return StreamingResponse(_message_fig(
                f"Only {n_cycles} completed {anchor} cycle(s) available.\n"
                f"Need at least {MIN_CYCLES} to forecast."
            ), media_type="image/png")

        # ── Project forward ────────────────────────────────────────
        now_local = _local_day(datetime.now(timezone.utc), tz_offset)
        last_anchor = anchor_days[-1]

        # Predicted next anchor — roll forward in case the last one is stale.
        next_anchor = last_anchor
        while next_anchor <= now_local:
            next_anchor = next_anchor + pd.Timedelta(days=cycle)

        dates = [now_local + pd.Timedelta(days=i) for i in range(days_ahead)]
        info  = []
        for d in dates:
            cd   = (d - last_anchor).days % cycle
            p    = p_smooth[cd]
            info.append({
                "date": d,
                "cycle_day": cd,
                "p": p,
                "band": _band(p, overall),
                # Beyond the predicted next period the cycle-length error
                # (±2 days here) smears the estimate onto the wrong days.
                "uncertain": d > next_anchor,
            })

        # ── Render ─────────────────────────────────────────────────
        start_grid = dates[0] - pd.Timedelta(days=dates[0].dayofweek)  # snap to Monday
        end_grid   = dates[-1] + pd.Timedelta(days=(6 - dates[-1].dayofweek))
        grid_dates = pd.date_range(start_grid, end_grid, freq="D")
        n_weeks    = len(grid_dates) // 7

        by_date = {i["date"]: i for i in info}

        shows_anchor    = any(i["date"] == next_anchor for i in info)
        shows_uncertain = any(i["uncertain"] for i in info)

        fig, ax = plt.subplots(figsize=(9.0, 1.18 * n_weeks + 1.5))
        fig.patch.set_facecolor("white")

        cell = 1.0
        for idx, d in enumerate(grid_dates):
            row, col = divmod(idx, 7)
            y = (n_weeks - 1 - row) * cell
            x = col * cell

            item = by_date.get(d)
            color = BAND_COLORS[item["band"]] if item else "#fafafa"

            ax.add_patch(mpatches.FancyBboxPatch(
                (x, y), cell * 0.9, cell * 0.9,
                boxstyle="round,pad=0.02",
                facecolor=color,
                edgecolor="#9aa0a6" if item else "#eeeeee",
                linewidth=0.8,
                hatch="///" if (item and item["uncertain"]) else None,
                alpha=1.0,
            ))

            # Day-of-month number
            ax.text(x + cell * 0.45, y + cell * 0.60, f"{d.day}",
                    ha="center", va="center", fontsize=10.5,
                    fontweight="bold" if item else "normal",
                    color="#202124" if item else "#cccccc")

            if item:
                ax.text(x + cell * 0.45, y + cell * 0.26,
                        BAND_LABELS[item["band"]],
                        ha="center", va="center", fontsize=6.5, color="#3c4043")

            # Today
            if item and d == dates[0]:
                ax.add_patch(mpatches.FancyBboxPatch(
                    (x, y), cell * 0.9, cell * 0.9,
                    boxstyle="round,pad=0.02",
                    facecolor="none", edgecolor="#1a73e8", linewidth=2.4, zorder=5,
                ))
            # Predicted period start
            if item and d == next_anchor:
                ax.text(x + cell * 0.80, y + cell * 0.78, "◆",
                        ha="center", va="center", fontsize=9,
                        color="#8e24aa", zorder=6)

        for i, lbl in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            ax.text(i * cell + cell * 0.45, n_weeks * cell + 0.12, lbl,
                    ha="center", va="bottom", fontsize=8, color="#777")

        ax.set_xlim(-0.15, 7 * cell + 0.05)
        ax.set_ylim(-0.15, n_weeks * cell + 0.55)
        ax.set_aspect("equal")
        ax.axis("off")

        month_span = dates[0].strftime("%b %Y")
        if dates[-1].strftime("%b %Y") != month_span:
            month_span += " – " + dates[-1].strftime("%b %Y")
        ax.set_title(
            f"{target} likelihood — next {days_ahead} days  ({month_span})",
            fontsize=12.5, fontweight="bold", pad=16, color="#202124",
        )

        legend_items = [
            mpatches.Patch(facecolor=BAND_COLORS["low"],      edgecolor="#9aa0a6", label="Low"),
            mpatches.Patch(facecolor=BAND_COLORS["moderate"], edgecolor="#9aa0a6", label="Moderate"),
            mpatches.Patch(facecolor=BAND_COLORS["high"],     edgecolor="#9aa0a6", label="High"),
        ]
        if shows_uncertain:
            legend_items.append(
                mpatches.Patch(facecolor="white", edgecolor="#9aa0a6", hatch="///",
                               label="Beyond next predicted period")
            )
        ax.legend(handles=legend_items, loc="upper center",
                  bbox_to_anchor=(0.5, -0.01), ncol=len(legend_items), fontsize=7.5,
                  frameon=False)

        pct_hi = sum(1 for i in info if i["band"] == "high")
        caption = (
            f"Based on {n_cycles} completed cycles (median {cycle} days) · "
            f"your overall rate {overall*100:.0f}% of days · "
            f"{pct_hi} high-risk day(s) ahead"
        )
        if shows_anchor:
            caption += f" · ◆ = predicted next {anchor}"
        else:
            caption += f" · next {anchor} expected {next_anchor.strftime('%-d %b')}"
        fig.text(0.5, 0.012, caption, ha="center", fontsize=7.8, color="#5f6368")
        fig.text(0.5, -0.012,
                 "Pattern from a small number of cycles — indicative only, not a prediction.",
                 ha="center", fontsize=7.2, color="#9aa0a6", style="italic")

        plt.tight_layout(rect=[0, 0.05, 1, 1])
        return StreamingResponse(_save_fig(fig), media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("plot_headache_forecast failed: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(500, f"Failed to generate forecast: {e}")
