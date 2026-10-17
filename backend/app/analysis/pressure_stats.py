"""How often a triptan follows a given change in barometric pressure.

The plot put the two series side by side so the question could be looked at.
This answers it with numbers: for each band of 24-hour pressure change, how
many days fell in that band and on how many of them was a triptan taken.

Two things make the naive version of this misleading, and both are handled
here.

The first is direction. Only falls were measured at first, because that is how
the trigger is usually described, which left a rising front looking identical
to a flat day. Rises are measured the same way now and carry the opposite
sign, so a band can be read as "pressure moved this far, this way".

The second is that "a big change" has to mean big *here*. In Christchurch a
6 hPa swing happens on four days in five, so a threshold set from the general
literature puts almost every day on the trigger side of the line and leaves
nothing to compare against. The bands are therefore cut from the person's own
local distribution, and a band is only called extreme if it is in the top
decile of what this city actually does.
"""
import logging

from scipy.stats import fisher_exact

logger = logging.getLogger(__name__)

# Enough days that a percentage means something. Below this the answer is
# "not yet", which is more useful than a number built from a handful of days.
MIN_DAYS = 60


def signed_change(row) -> float:
    """The day's dominant 24-hour movement, negative for a fall.

    A day can both rise and fall; the larger of the two is what the day was
    like. Taking the net change instead would score a day that fell 10 hPa and
    recovered as nothing happening, which is the exact shape being asked about.
    """
    drop = row.get("drop24", 0.0) or 0.0
    rise = row.get("rise24", 0.0) or 0.0
    return rise if rise >= drop else -drop


def _percentile(values, pct):
    """Nearest-rank percentile, so no numpy import for four numbers."""
    if not values:
        return 0.0
    ordered = sorted(values)
    i = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[i]


def bands(rows, triptan_days, lag=0):
    """Triptan likelihood per band of signed 24-hour pressure change.

    `rows` maps an ISO date to a daily pressure row; `triptan_days` is a set of
    dates a triptan was taken. `lag` asks the question a day or two later, in
    case the response is not the same day.

    Returns a dict with the bands, the baseline rate, and a Fisher exact test
    of the most extreme days against all the rest. `None` when there is not
    enough data to say anything.
    """
    from datetime import date, timedelta

    days = []
    for iso, row in rows.items():
        try:
            d = date.fromisoformat(iso)
        except ValueError:
            continue
        days.append((d, signed_change(row)))
    if len(days) < MIN_DAYS:
        return None

    moves = [abs(c) for _, c in days]
    p50 = _percentile(moves, 50)
    # Chosen by rank rather than by value. Comparing against the 90th
    # percentile looks equivalent and is not: when a tenth or more of the days
    # sit on exactly that value — which a coarse or flat distribution does —
    # every one of them lands on the extreme side and there is nothing left to
    # compare against. Taking the top tenth of days by size always leaves a
    # remainder.
    ranked = sorted(moves, reverse=True)
    top = max(1, round(0.10 * len(ranked)))
    p90 = ranked[top - 1]

    # Cut from the local distribution: a quiet day, an ordinary move, and a
    # move in the top tenth of what this place does.
    edges = [(-999.0, -p90, f"fall over {p90:.0f}"),
             (-p90, -p50, f"fall {p50:.0f}-{p90:.0f}"),
             (-p50, 0.0, f"fall under {p50:.0f}"),
             (0.0, p50, f"rise under {p50:.0f}"),
             (p50, p90, f"rise {p50:.0f}-{p90:.0f}"),
             (p90, 999.0, f"rise over {p90:.0f}")]

    out = []
    for lo, hi, label in edges:
        sel = [d for d, c in days if lo <= c < hi]
        if not sel:
            continue
        hits = sum(1 for d in sel if (d + timedelta(days=lag)) in triptan_days)
        out.append({"label": label, "lo": lo, "hi": hi, "days": len(sel),
                    "triptans": hits, "rate": hits / len(sel)})

    total = len(days)
    base = sum(1 for d, _ in days if (d + timedelta(days=lag)) in triptan_days)

    # The extreme days against everything else. One test, stated once: running
    # it at every threshold and every lag and then reporting the smallest p is
    # how noise gets published.
    extreme = [d for d, c in days if abs(c) >= p90]
    rest = [d for d, c in days if abs(c) < p90]
    a = sum(1 for d in extreme if (d + timedelta(days=lag)) in triptan_days)
    c_ = sum(1 for d in rest if (d + timedelta(days=lag)) in triptan_days)
    p = None
    if extreme and rest:
        try:
            _, p = fisher_exact([[a, len(extreme) - a], [c_, len(rest) - c_]])
        except ValueError as exc:
            logger.warning("pressure fisher test failed: %s", exc)

    return {
        "bands": out,
        "baseline": base / total if total else 0.0,
        "total_days": total,
        "triptan_days": base,
        "threshold": round(p90, 1),
        "median_move": round(p50, 1),
        "extreme_rate": a / len(extreme) if extreme else None,
        "rest_rate": c_ / len(rest) if rest else None,
        "extreme_days": len(extreme),
        "p_value": p,
        "lag": lag,
    }
