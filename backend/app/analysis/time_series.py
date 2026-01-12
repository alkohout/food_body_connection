def time_series(db: 'Session', current_user: int, allergen_name: str):
    """
    Basic time series plot.
    """
    try:
        # --- Load data ---
        allergen_events = get_all_allergen_events_df(db, current_user, allergen_name)
        symptom_events = get_all_symptom_events_df(db, current_user)

        # Floor to days
        symptom_events["days"] = symptom_events["date_time"].dt.floor("D")
        allergen_events["days"] = allergen_events["date_time"].dt.floor("D")

        # --- Aggregate symptoms per day ---
        daily_symptoms = (
            symptom_events
            .groupby("days")
            .agg(
                symptom_count=("symptom_id", "count"),
                mean_severity=("symptom_intensity", "mean")
            )
            .reset_index()
        )

        # --- Ensure continuous date range ---
        full_days = pd.date_range(
            start=daily_symptoms["days"].min(),
            end=daily_symptoms["days"].max(),
            freq="D"
        )

        daily_symptoms = (
            daily_symptoms
            .set_index("days")
            .reindex(full_days, fill_value=0)
            .rename_axis("days")
            .reset_index()
        )

        exposure_days = allergen_events["days"].unique()

        # --- Plot ---
        plt.figure(figsize=(10, 6))

        plt.plot(
            daily_symptoms["days"],
            daily_symptoms["symptom_count"],
            label="Symptoms",
            linewidth=2
        )

        for d in exposure_days:
            plt.axvline(d, linestyle="--", alpha=0.3)

        plt.title(f"Symptoms over time with {allergen_name} exposure")
        plt.xlabel("Date")
        plt.ylabel("Symptom count")
        plt.legend()
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close()
        buf.seek(0)
        return buf

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
