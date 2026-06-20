import logging
import traceback
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.database import get_db
from app.models.table_class import SymptomLog, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])

# Color for each intensity level and "no data"
COLORS = {
    -1: "#f0f0f0",   # no data
     0: "#c8e6c9",   # logged, no symptoms
     1: "#fff59d",   # mild
     2: "#ffb74d",   # moderate
     3: "#ef5350",   # severe
}


@router.get("/plot_symptom_calendar")
def plot_symptom_calendar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        rows = (
            db.query(SymptomLog.date_time, SymptomLog.symptom_intensity)
            .filter(SymptomLog.user_id == current_user.user_id)
            .all()
        )

        if not rows:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, "No symptom data yet.\nStart logging symptoms to see your calendar here.",
                    ha="center", va="center", fontsize=12, color="#666")
            ax.set_axis_off()
            buf = BytesIO()
            plt.savefig(buf, format="png", bbox_inches="tight", dpi=120)
            plt.close(fig)
            buf.seek(0)
            return StreamingResponse(buf, media_type="image/png")

        df = pd.DataFrame(rows, columns=["date_time", "intensity"])
        df["date"] = pd.to_datetime(df["date_time"]).dt.normalize()

        # Max intensity per day
        daily_max = df.groupby("date")["intensity"].max()

        # Build 52-week grid ending today
        today = pd.Timestamp.now().normalize()
        start = today - pd.Timedelta(weeks=52) + pd.Timedelta(days=1)
        # Snap start back to the Monday of that week
        start = start - pd.Timedelta(days=start.dayofweek)
        all_dates = pd.date_range(start=start, end=today, freq="D")

        intensity_map = daily_max.to_dict()
        values = [intensity_map.get(d, -1) for d in all_dates]

        # Reshape into (7 rows=days, N cols=weeks)
        n_weeks = len(all_dates) // 7 + (1 if len(all_dates) % 7 else 0)
        # Pad to full grid
        pad = n_weeks * 7 - len(all_dates)
        padded_dates = [None] * pad + list(all_dates)
        padded_values = [-1] * pad + values

        grid_vals = np.array(padded_values, dtype=float).reshape(n_weeks, 7).T
        grid_dates = np.array(padded_dates).reshape(n_weeks, 7).T

        fig, ax = plt.subplots(figsize=(14, 3.5))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

        cell_size = 1.0
        for week in range(n_weeks):
            for dow in range(7):
                val = int(grid_vals[dow, week])
                color = COLORS.get(val, COLORS[-1])
                rect = mpatches.FancyBboxPatch(
                    (week * cell_size, (6 - dow) * cell_size),
                    cell_size * 0.88, cell_size * 0.88,
                    boxstyle="round,pad=0.05",
                    facecolor=color, edgecolor="white", linewidth=1,
                )
                ax.add_patch(rect)

        # Month labels along the top
        month_positions = {}
        for week in range(n_weeks):
            d = grid_dates[0, week]
            if d is not None and d.day <= 7:
                month_positions[week] = d.strftime("%b")

        for week, label in month_positions.items():
            ax.text(week * cell_size + cell_size * 0.44, 7.3 * cell_size,
                    label, ha="center", va="bottom", fontsize=8, color="#555")

        # Day-of-week labels on left
        dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, lbl in enumerate(dow_labels):
            ax.text(-0.6, (6 - i) * cell_size + cell_size * 0.44,
                    lbl, ha="right", va="center", fontsize=7.5, color="#777")

        ax.set_xlim(-1, n_weeks * cell_size + 0.2)
        ax.set_ylim(-0.5, 8 * cell_size)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title("Symptom Calendar — last 52 weeks", fontsize=13,
                     fontweight="bold", pad=20, color="#222")

        # Legend
        legend_items = [
            mpatches.Patch(facecolor=COLORS[-1], edgecolor="#ccc", label="No data"),
            mpatches.Patch(facecolor=COLORS[0],  edgecolor="#ccc", label="None logged"),
            mpatches.Patch(facecolor=COLORS[1],  edgecolor="#ccc", label="Mild"),
            mpatches.Patch(facecolor=COLORS[2],  edgecolor="#ccc", label="Moderate"),
            mpatches.Patch(facecolor=COLORS[3],  edgecolor="#ccc", label="Severe"),
        ]
        ax.legend(handles=legend_items, loc="lower right", fontsize=8,
                  framealpha=0.9, ncol=5, bbox_to_anchor=(1, -0.15))

        plt.tight_layout()
        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=130)
        plt.close(fig)
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        logger.error("plot_symptom_calendar failed: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to generate symptom calendar")
