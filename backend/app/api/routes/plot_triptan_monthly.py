import logging
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.plot_cache import cached_png
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.table_class import Allergen, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/plot_triptan_monthly")
def plot_triptan_monthly(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_id != 4:
        raise HTTPException(status_code=403, detail="Not available for this user.")

    uid = current_user.user_id

    # Resolve triptan allergen_id in Python (name is encrypted)
    allergens = db.query(Allergen).filter(Allergen.user_id == uid).all()
    triptan = next((a for a in allergens if a.allergen_name.lower() == "triptan"), None)
    if not triptan:
        raise HTTPException(status_code=404, detail="No Triptan data found.")

    aid = triptan.allergen_id

    def generate() -> BytesIO:
        # Push groupby to SQL — returns one row per month instead of every log entry
        rows = db.execute(text("""
            SELECT DATE_TRUNC('month', date_time) AS month_start, COUNT(*) AS cnt
            FROM allergen_log
            WHERE user_id = :uid AND allergen_id = :aid AND date_time IS NOT NULL
            GROUP BY DATE_TRUNC('month', date_time)
            ORDER BY month_start
        """), {"uid": uid, "aid": aid}).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No Triptan data found.")

        df = pd.DataFrame([(r.month_start, r.cnt) for r in rows], columns=["month_start", "count"])
        df["month_start"] = pd.to_datetime(df["month_start"])
        df["label"] = df["month_start"].dt.strftime("%b %Y")

        now = pd.Timestamp.now()
        current_month = now.to_period("M").to_timestamp()
        df["is_current"] = df["month_start"] == current_month

        days_in_month = (current_month + pd.offsets.MonthEnd(1)).day
        current_alpha = max(0.2, now.day / days_in_month)

        # Exclude current (incomplete) month and Dec 2025 (partial launch month)
        exclude = df["is_current"] | (df["month_start"] == pd.Timestamp("2025-12-01"))
        complete = df[~exclude]
        avg = complete["count"].mean() if not complete.empty else 0

        fig, ax = plt.subplots(figsize=(max(8, len(df) * 0.8), 5))

        bars = ax.bar(df["label"], df["count"], color="#d97706", edgecolor="white", width=0.6)
        for bar, is_cur in zip(bars, df["is_current"]):
            bar.set_alpha(current_alpha if is_cur else 1.0)

        ax.axhline(avg, color="#6b7280", linestyle="--", linewidth=1.2,
                   label=f"Average excl. current month ({avg:.1f})")

        for bar, val in zip(bars, df["count"]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.15,
                str(int(val)),
                ha="center", va="bottom", fontsize=9, color="#374151"
            )

        ax.set_xlabel("Month", fontsize=11)
        ax.set_ylabel("Triptan uses", fontsize=11)
        ax.set_title("Triptan Usage per Month", fontsize=13, fontweight="bold")
        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax.legend(fontsize=9)
        plt.xticks(rotation=45, ha="right", fontsize=9)
        plt.tight_layout()

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=130)
        plt.close(fig)
        buf.seek(0)
        return buf

    return cached_png(f"triptan_monthly_{uid}", generate, background_tasks)
