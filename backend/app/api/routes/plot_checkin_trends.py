import logging
import traceback
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.plot_cache import cached_png
from app.database import get_db
from app.models.table_class import DailyCheckin, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])

VARS = {
    "mood":    ("Mood",    "#4e9af1", "solid"),
    "sleep":   ("Sleep",   "#a78bfa", "solid"),
    "fatigue": ("Fatigue", "#f97316", "dashed"),
    "gut":     ("Gut",     "#10b981", "dashed"),
    "stress":  ("Stress",  "#ef4444", "dashed"),
}


@router.get("/plot_checkin_trends")
def plot_checkin_trends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.user_id

    def generate() -> BytesIO:
        rows = (
            db.query(DailyCheckin)
            .filter(DailyCheckin.user_id == uid)
            .order_by(DailyCheckin.checkin_date)
            .all()
        )

        if not rows:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, "No check-in data yet.\nStart your daily check-ins to see trends here.",
                    ha="center", va="center", fontsize=12, color="#666")
            ax.set_axis_off()
            buf = BytesIO()
            plt.savefig(buf, format="png", bbox_inches="tight", dpi=120)
            plt.close(fig)
            buf.seek(0)
            return buf

        records = [
            {
                "date": r.checkin_date,
                "mood": r.mood,
                "sleep": r.sleep if r.period == "morning" else None,
                "fatigue": r.fatigue,
                "gut": r.gut,
                "stress": r.stress,
            }
            for r in rows
        ]
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])

        # Daily average per variable (sleep: morning only)
        daily = df.groupby("date").agg(
            mood=("mood", "mean"),
            sleep=("sleep", "mean"),
            fatigue=("fatigue", "mean"),
            gut=("gut", "mean"),
            stress=("stress", "mean"),
        ).reset_index()

        # 7-day rolling average for smoothing
        for col in ["mood", "sleep", "fatigue", "gut", "stress"]:
            daily[f"{col}_smooth"] = daily[col].rolling(7, min_periods=1, center=True).mean()

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
        fig.suptitle("Daily Wellbeing Trends (7-day average)", fontsize=14, fontweight="bold")

        # Top panel: mood & sleep (higher = better)
        for key in ["mood", "sleep"]:
            label, color, _ = VARS[key]
            ax1.plot(daily["date"], daily[f"{key}_smooth"], color=color, linewidth=2, label=label)
            ax1.scatter(daily["date"], daily[key], color=color, alpha=0.15, s=15)

        ax1.set_ylabel("Score  (0 Poor → 2 Good)")
        ax1.set_ylim(-0.2, 2.4)
        ax1.set_yticks([0, 1, 2])
        ax1.set_yticklabels(["Poor / None", "Okay / Mild", "Good / Bad"])
        ax1.legend(loc="upper left", fontsize=9)
        ax1.set_title("Mood & Sleep", fontsize=10, color="#444")
        ax1.grid(axis="y", linestyle="--", alpha=0.4)

        # Bottom panel: fatigue, gut, stress (lower = better)
        for key in ["fatigue", "gut", "stress"]:
            label, color, _ = VARS[key]
            ax2.plot(daily["date"], daily[f"{key}_smooth"], color=color, linewidth=2, label=label)
            ax2.scatter(daily["date"], daily[key], color=color, alpha=0.15, s=15)

        ax2.set_ylabel("Score  (0 None → 2 Bad)")
        ax2.set_ylim(-0.2, 2.4)
        ax2.set_yticks([0, 1, 2])
        ax2.set_yticklabels(["None", "Mild", "Bad"])
        ax2.legend(loc="upper left", fontsize=9)
        ax2.set_title("Fatigue, Gut & Stress", fontsize=10, color="#444")
        ax2.grid(axis="y", linestyle="--", alpha=0.4)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax2.xaxis.set_major_locator(mdates.MonthLocator())
        plt.xticks(rotation=30, ha="right")

        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=120)
        plt.close(fig)
        buf.seek(0)
        return buf

    try:
        return cached_png(f"checkin_trends_{uid}", generate)
    except Exception as e:
        logger.error("plot_checkin_trends failed: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
