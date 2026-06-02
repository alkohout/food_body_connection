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
