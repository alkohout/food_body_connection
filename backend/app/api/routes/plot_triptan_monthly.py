import logging
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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

    from app.models.table_class import Allergen, AllergenLog

    # Find triptan allergen_id in Python (name is encrypted, can't filter in SQL)
    allergens = db.query(Allergen).filter(Allergen.user_id == current_user.user_id).all()
    triptan = next((a for a in allergens if a.allergen_name.lower() == "triptan"), None)
    if not triptan:
        raise HTTPException(status_code=404, detail="No Triptan data found.")

    log_rows = (
        db.query(AllergenLog.date_time)
        .filter(
            AllergenLog.user_id == current_user.user_id,
            AllergenLog.allergen_id == triptan.allergen_id,
            AllergenLog.date_time.isnot(None),
        )
        .all()
    )

    if not log_rows:
        raise HTTPException(status_code=404, detail="No Triptan data found.")

    df = pd.DataFrame(log_rows, columns=["date_time"])
    df["date_time"] = pd.to_datetime(df["date_time"])
    df["month_start"] = df["date_time"].dt.to_period("M").dt.to_timestamp()
    df = df.groupby("month_start").size().reset_index(name="count").sort_values("month_start")

    df["label"] = df["month_start"].dt.strftime("%b %Y")

    current_month = pd.Timestamp.now().to_period("M").to_timestamp()
    df["is_current"] = df["month_start"] == current_month

    # Average excludes the current (incomplete) month
    complete = df[~df["is_current"]]
    avg = complete["count"].mean() if not complete.empty else 0

    fig, ax = plt.subplots(figsize=(max(8, len(df) * 0.8), 5))

    colors  = ["#d97706" if not cur else "#d97706" for cur in df["is_current"]]
    alphas  = [1.0       if not cur else 0.35       for cur in df["is_current"]]

    bars = ax.bar(df["label"], df["count"], color=colors, edgecolor="white",
                  width=0.6, alpha=1.0)
    for bar, alpha in zip(bars, alphas):
        bar.set_alpha(alpha)

    ax.axhline(avg, color="#6b7280", linestyle="--", linewidth=1.2,
               label=f"Average excl. current month ({avg:.1f})")

    for bar, val, is_cur in zip(bars, df["count"], df["is_current"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.15,
            str(int(val)) + ("*" if is_cur else ""),
            ha="center", va="bottom", fontsize=9,
            color="#9ca3af" if is_cur else "#374151"
        )

    if df["is_current"].any():
        ax.annotate("* month in progress", xy=(1, 0), xycoords="axes fraction",
                    ha="right", va="bottom", fontsize=8, color="#9ca3af",
                    xytext=(0, -38), textcoords="offset points")

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
