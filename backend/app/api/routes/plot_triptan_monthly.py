import logging
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.table_class import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/plot_triptan_monthly")
def plot_triptan_monthly(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.user_id != 4:
        raise HTTPException(status_code=403, detail="Not available for this user.")

    rows = db.execute(text("""
        SELECT DATE_TRUNC('month', al.date_time) AS month_start,
               COUNT(*) AS count
        FROM allergen_log al
        JOIN allergen a ON a.allergen_id = al.allergen_id
        WHERE al.user_id = :uid
          AND a.user_id  = :uid
          AND a.allergen_name = 'Triptan'
          AND al.date_time IS NOT NULL
        GROUP BY DATE_TRUNC('month', al.date_time)
        ORDER BY month_start
    """), {"uid": current_user.user_id}).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No Triptan data found.")

    df = pd.DataFrame(rows, columns=["month_start", "count"])
    df["month_start"] = pd.to_datetime(df["month_start"])
    df["label"] = df["month_start"].dt.strftime("%b %Y")

    avg = df["count"].mean()

    fig, ax = plt.subplots(figsize=(max(8, len(df) * 0.8), 5))

    bars = ax.bar(df["label"], df["count"], color="#d97706", edgecolor="white", width=0.6)

    ax.axhline(avg, color="#6b7280", linestyle="--", linewidth=1.2, label=f"Average ({avg:.1f})")

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

    return StreamingResponse(buf, media_type="image/png")
