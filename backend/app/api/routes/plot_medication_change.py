# app/api/routes/plot_medication_change.py
#
# Did something change when a medication dose changed?
#
# Method
# ------
# 1. Rebuild the total daily dose for a medication as a step function over time
#    (regimens overlap — an evening and a morning dose are separate rows).
# 2. Find the points where that total changes. Each is a candidate intervention.
# 3. Around the chosen change, compare the target event rate in equal-length
#    windows before and after, and report the rate ratio with an exact Poisson
#    confidence interval.
#
# Equal windows matter: comparing "the 6 months before" with "the 5 weeks since"
# would compare a rate against a rate measured over a completely different span,
# and any seasonal or cyclical drift would land entirely on one side.
#
# This is observational and uncontrolled. Nothing here establishes that the dose
# change caused the difference — the plot says so, because a large percentage
# drop is exactly the kind of number that gets over-read.

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from scipy.stats import beta as beta_dist
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.api.routes.plot_event_series import (
    _get_allergen_data,
    _get_symptom_data,
    _save_fig,
)
from app.api.routes.plot_time_series_analysis import _local_day
from app.database import get_db
from app.models.table_class import Medication, MedicationRegimen, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])

_COL_EVENT = "#2563eb"   # target events
_COL_DOSE = "#ea580c"    # medication dose
_COL_BEFORE = "#6b7280"  # before-window mean
_COL_AFTER = "#059669"   # after-window mean

MIN_WINDOW_DAYS = 14


# ──────────────────────────────────────────────
# Dose reconstruction
# ──────────────────────────────────────────────

def _dose_steps(regimens):
    """Total daily dose at each point where any regimen starts or ends.

    A medication can have several concurrent regimens (a morning dose and an
    evening dose are separate rows), so the meaningful quantity is their sum,
    not any single row's dose.
    """
    boundaries = sorted({
        d for r in regimens for d in (r.start_date, r.end_date) if d
    })
    steps = []
    for d in boundaries:
        total = sum(
            r.dose for r in regimens
            if r.start_date <= d and (r.end_date is None or r.end_date > d)
        )
        steps.append((d, float(total)))
    return steps


def _dose_changes(steps):
    """Points where the total daily dose actually moves."""
    changes = []
    for (d_prev, v_prev), (d_next, v_next) in zip(steps, steps[1:]):
        if v_next != v_prev:
            changes.append({"date": d_next, "from": v_prev, "to": v_next})
    return changes


# ──────────────────────────────────────────────
# Rate comparison
# ──────────────────────────────────────────────

def _rate_ratio_ci(before_count, after_count, window_days):
    """Exact 95% CI for the ratio of two Poisson rates over equal exposure.

    Conditional on the total, the after-count is binomial, so an exact interval
    comes from the Beta quantiles. Equal windows make the exposure ratio 1, so
    the odds transform gives the rate ratio directly.
    """
    total = before_count + after_count
    if total == 0:
        return None, None
    lo_p = beta_dist.ppf(0.025, after_count, before_count + 1) if after_count else 0.0
    hi_p = beta_dist.ppf(0.975, after_count + 1, before_count) if before_count else 1.0
    lo = lo_p / (1 - lo_p) if lo_p < 1 else float("inf")
    hi = hi_p / (1 - hi_p) if hi_p < 1 else float("inf")
    return lo, hi


def _daily_counts(event_days, start, end):
    """Events per calendar day across [start, end)."""
    span = (end - start).days
    counts = np.zeros(max(span, 0))
    for d in event_days:
        idx = (d - start).days
        if 0 <= idx < span:
            counts[idx] += 1
    return counts


# ──────────────────────────────────────────────
# Route
# ──────────────────────────────────────────────

@router.get("/plot_medication_change")
def plot_medication_change(
    medication:  str = Query(..., min_length=1),
    target_type: str = Query("allergen"),
    target:      str = Query(..., min_length=1),
    change_date: Optional[str] = Query(
        None, description="YYYY-MM-DD of the dose change; defaults to the most recent."
    ),
    window_days: Optional[int] = Query(
        None, ge=MIN_WINDOW_DAYS, le=180,
        description="Comparison window each side; defaults to the largest that fits.",
    ),
    tz_offset:   int = Query(0),
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Target event rate around a change in a medication's total daily dose."""
    if target_type not in ("allergen", "symptom"):
        raise HTTPException(400, "target_type must be 'allergen' or 'symptom'")

    try:
        med = next(
            (m for m in db.query(Medication)
             .filter(Medication.user_id == current_user.user_id).all()
             if (m.medication_name or "").strip().lower() == medication.strip().lower()),
            None,
        )
        if med is None:
            raise HTTPException(404, f"Medication '{medication}' not found")

        regimens = (
            db.query(MedicationRegimen)
            .filter(
                MedicationRegimen.user_id == current_user.user_id,
                MedicationRegimen.medication_id == med.medication_id,
            )
            .order_by(MedicationRegimen.start_date)
            .all()
        )
        if not regimens:
            raise HTTPException(404, f"No dose history recorded for '{medication}'")

        steps = _dose_steps(regimens)
        changes = _dose_changes(steps)
        if not changes:
            raise HTTPException(
                400,
                f"'{med.medication_name}' has no recorded dose changes — there is "
                "nothing to compare before and after.",
            )

        if change_date:
            try:
                wanted = datetime.strptime(change_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(400, "change_date must be YYYY-MM-DD")
            change = next((c for c in changes if c["date"] == wanted), None)
            if change is None:
                available = ", ".join(str(c["date"]) for c in changes)
                raise HTTPException(
                    400, f"No dose change on {wanted}. Available: {available}"
                )
        else:
            change = changes[-1]

        # ── Target events ───────────────────────────────────────────
        fetch = _get_allergen_data if target_type == "allergen" else _get_symptom_data
        dates, _ = fetch(db, current_user.user_id, target, None, None)
        event_days = sorted(_local_day(d, tz_offset).date() for d in dates)
        if not event_days:
            raise HTTPException(404, f"No '{target}' events logged")

        cp = change["date"]
        today = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=tz_offset)
        ).date()

        # Windows are matched to each other so the two rates share identical
        # exposure, and bounded by the observation period — not by the last
        # event. Ending the after-window at the final target event would throw
        # away the event-free days that follow, which are the whole point when
        # a treatment is working, and would guarantee an event on the window's
        # last day, biasing the after-rate upward.
        avail_before = (cp - event_days[0]).days
        avail_after = (today - cp).days
        usable = min(avail_before, avail_after)

        if usable < MIN_WINDOW_DAYS:
            raise HTTPException(
                400,
                f"Only {max(avail_before, 0)} days of '{target}' data before and "
                f"{max(avail_after, 0)} days after {cp}. Need at least "
                f"{MIN_WINDOW_DAYS} on each side to compare.",
            )

        window = min(window_days, usable) if window_days else usable
        capped = bool(window_days and window_days > usable)

        b_start, b_end = cp - timedelta(days=window), cp
        a_start, a_end = cp, cp + timedelta(days=window)

        before_count = sum(1 for d in event_days if b_start <= d < b_end)
        after_count = sum(1 for d in event_days if a_start <= d < a_end)
        rate_b = before_count / window
        rate_a = after_count / window
        ratio = (rate_a / rate_b) if rate_b else None
        ci_lo, ci_hi = _rate_ratio_ci(before_count, after_count, window)

        # ── Plot ────────────────────────────────────────────────────
        fig, (ax_dose, ax_evt) = plt.subplots(
            2, 1, figsize=(11, 6.4), sharex=True,
            gridspec_kw={"height_ratios": [1, 2.4], "hspace": 0.12},
        )

        # Dose staircase, extended to today so the current dose is visible
        step_x = [d for d, _ in steps] + [today]
        step_y = [v for _, v in steps] + [steps[-1][1]]
        ax_dose.step(step_x, step_y, where="post", color=_COL_DOSE, linewidth=2.2)
        ax_dose.fill_between(step_x, 0, step_y, step="post",
                             color=_COL_DOSE, alpha=0.12)
        ax_dose.set_ylabel(f"{med.medication_name}\ndaily dose", fontsize=9)
        ax_dose.set_ylim(bottom=0)
        ax_dose.grid(axis="y", alpha=0.2)
        ax_dose.set_title(
            f"{target} around a {med.medication_name} dose change "
            f"({change['from']:g} → {change['to']:g} on {cp:%d %b %Y})",
            fontsize=12.5, fontweight="bold", pad=12,
        )

        # Daily counts + 7-day rolling rate
        plot_start = min(event_days[0], b_start)
        plot_end = max(today, a_end)
        counts = _daily_counts(event_days, plot_start, plot_end + timedelta(days=1))
        days_axis = [plot_start + timedelta(days=i) for i in range(len(counts))]

        ax_evt.bar(days_axis, counts, width=1.0, color=_COL_EVENT,
                   alpha=0.28, zorder=2)
        if len(counts) >= 7:
            rolling = np.convolve(counts, np.ones(7) / 7, mode="same")
            ax_evt.plot(days_axis, rolling, color=_COL_EVENT, linewidth=1.8,
                        zorder=4, label=f"{target} (7-day average)")

        # Matched comparison windows
        ax_evt.axvspan(b_start, b_end, color=_COL_BEFORE, alpha=0.10, zorder=1)
        ax_evt.axvspan(a_start, a_end, color=_COL_AFTER, alpha=0.10, zorder=1)
        ax_evt.hlines(rate_b, b_start, b_end, color=_COL_BEFORE, linewidth=2.4,
                      linestyle="--", zorder=5,
                      label=f"Before: {rate_b:.2f}/day  ({before_count} in {window} d)")
        ax_evt.hlines(rate_a, a_start, a_end, color=_COL_AFTER, linewidth=2.4,
                      linestyle="--", zorder=5,
                      label=f"After: {rate_a:.2f}/day  ({after_count} in {window} d)")

        for ax in (ax_dose, ax_evt):
            ax.axvline(cp, color=_COL_DOSE, linewidth=2.0, zorder=6)
        ax_dose.annotate(
            "DOSE CHANGE", xy=(cp, 0.97), xycoords=("data", "axes fraction"),
            ha="center", va="top", fontsize=7.5, fontweight="bold",
            color=_COL_DOSE, zorder=7,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor=_COL_DOSE, linewidth=0.8, alpha=0.95),
        )

        ax_evt.set_ylabel(f"{target} events / day")
        ax_evt.set_ylim(bottom=0)
        ax_evt.grid(axis="y", alpha=0.2)
        ax_evt.legend(frameon=False, fontsize=8, loc="upper left", ncol=1)
        ax_evt.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
        fig.autofmt_xdate(rotation=0, ha="center")

        # ── Verdict ─────────────────────────────────────────────────
        if ratio is None:
            headline = f"No {target} logged in the {window} days before the change."
            caveat = ""
        else:
            direction = "lower" if ratio < 1 else "higher"
            pct = abs(1 - ratio) * 100
            headline = (
                f"{target} was {pct:.0f}% {direction} after the change "
                f"({rate_b:.2f} → {rate_a:.2f} per day)"
            )
            if ci_lo is not None and ci_hi is not None:
                hi_txt = "∞" if np.isinf(ci_hi) else f"{ci_hi:.2f}"
                spans_one = ci_lo <= 1.0 <= ci_hi
                headline += f".  Rate ratio {ratio:.2f}  (95% CI {ci_lo:.2f}–{hi_txt})"
                caveat = (
                    "The confidence interval includes 1.0, so a difference this size "
                    "is still consistent with chance — suggestive, not established."
                    if spans_one else
                    "The confidence interval excludes 1.0, so the difference is "
                    "unlikely to be chance alone — but this is observational, not a "
                    "controlled trial."
                )
            else:
                caveat = "Too few events to put an interval on this."

        note = (
            f"Matched {window}-day windows either side of the change"
            + (f" (capped by available data; you asked for {window_days})" if capped else "")
            + ".  Other things may have changed at the same time."
        )

        fig.text(0.5, 0.075, headline, ha="center", fontsize=10,
                 fontweight="bold", color="#1f2937")
        if caveat:
            fig.text(0.5, 0.040, caveat, ha="center", fontsize=8.5, color="#b45309")
        fig.text(0.5, 0.010, note, ha="center", fontsize=7.8,
                 color="#6b7280", style="italic")

        plt.tight_layout(rect=[0, 0.11, 1, 1])
        return StreamingResponse(_save_fig(fig), media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("plot_medication_change failed")
        raise HTTPException(500, f"Failed to generate plot: {e}")


@router.get("/medication_changes")
def medication_changes(
    tz_offset:   int = Query(0),
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Dose changes available to plot, so the UI can offer only real ones."""
    out = []
    for med in db.query(Medication).filter(
        Medication.user_id == current_user.user_id
    ).all():
        regimens = (
            db.query(MedicationRegimen)
            .filter(
                MedicationRegimen.user_id == current_user.user_id,
                MedicationRegimen.medication_id == med.medication_id,
            )
            .order_by(MedicationRegimen.start_date)
            .all()
        )
        changes = _dose_changes(_dose_steps(regimens))
        if changes:
            out.append({
                "medication": med.medication_name,
                "changes": [
                    {
                        "date": str(c["date"]),
                        "from": c["from"],
                        "to": c["to"],
                        "label": f"{c['from']:g} → {c['to']:g} on {c['date']}",
                    }
                    for c in changes
                ],
            })
    return out
