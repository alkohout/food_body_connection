# backend/app/utils/definitions.py

from datetime import timedelta

# --- Causal windows ---
# These are relative to allergen exposure event
CAUSAL_WINDOW = timedelta(hours=0), timedelta(hours=24)    # 0–24 hours after exposure
CONTROL_WINDOW = timedelta(hours=-48), timedelta(hours=-24) # 24–48 hours before exposure

# For reference, you can add labels
WINDOW_LABELS = {
    "causal": "0–24h after allergen",
    "control": "24–48h before allergen"
}


