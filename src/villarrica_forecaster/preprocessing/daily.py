from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.io import write_csv, write_json


def southern_hemisphere_season(month: int) -> str:
    """Return the meteorological season used for Lake Villarrica summaries."""

    if month in {12, 1, 2}:
        return "Summer"
    if month in {3, 4, 5}:
        return "Autumn"
    if month in {6, 7, 8}:
        return "Winter"
    return "Spring"


def build_daily_chlorophyll(config: dict[str, Any]) -> dict[str, Path]:
    processed_dir = path_from_config(config, "processed_data")
    tables_dir = path_from_config(config, "tables")
    canonical_path = processed_dir / "canonical_observations.csv"
    canonical = pd.read_csv(canonical_path)
    daily = build_daily_chlorophyll_frame(canonical, config)
    paths = {
        "daily_chl_a": write_csv(daily, processed_dir / "daily_chl_a.csv"),
        "preprocessing_footprint": write_csv(
            preprocessing_footprint(daily), tables_dir / "preprocessing_footprint.csv"
        ),
        "preprocessing_footprint_by_month": write_csv(
            preprocessing_footprint_by_month(daily),
            tables_dir / "preprocessing_footprint_by_month.csv",
        ),
    }
    paths["daily_chl_a_manifest"] = write_json(
        {
            "source": "data/processed/canonical_observations.csv",
            "output": "data/processed/daily_chl_a.csv",
            "rules": {
                "chlorophyll_variable": config["preprocessing"]["chlorophyll_variable"],
                "statistic": config["preprocessing"]["statistic"],
                "iqr_multiplier": config["preprocessing"]["iqr_multiplier"],
                "interpolation_limit_days": config["preprocessing"]["interpolation_limit_days"],
                "savgol_window_days": config["preprocessing"]["savgol_window_days"],
                "savgol_polyorder": config["preprocessing"]["savgol_polyorder"],
                "remove_iqr_outliers": config["preprocessing"].get("remove_iqr_outliers", False),
                "use_smoothed_for_forecast": config["preprocessing"].get(
                    "use_smoothed_for_forecast", False
                ),
            },
        },
        processed_dir / "daily_chl_a_manifest.json",
    )
    return paths


def build_daily_chlorophyll_frame(canonical: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    prep = config["preprocessing"]
    variable = prep["chlorophyll_variable"]
    statistic = prep["statistic"]
    valid = canonical[
        canonical["variable"].eq(variable)
        & canonical["statistic"].eq(statistic)
        & canonical["quality_flag"].eq("ok")
    ].copy()
    if valid.empty:
        return pd.DataFrame(
            columns=[
                "station_id",
                "station_name",
                "date",
                "chl_a_observed",
                "chl_a_clean",
                "chl_a_filled",
                "chl_a_smoothed",
                "chl_a_model",
                "chl_a_unit",
                "source_count",
                "is_direct_observation",
                "is_iqr_outlier",
                "is_outlier_removed",
                "is_imputed",
                "imputation_method",
                "is_interpolated",
                "is_smoothed",
                "smoothing_method",
                "season",
            ]
        )

    valid["date"] = pd.to_datetime(valid["date"])
    grouped = (
        valid.groupby(["station_id", "station_name", "date"], as_index=False)
        .agg(chl_a_observed=("value", "mean"), source_count=("value", "size"))
        .sort_values(["station_id", "date"])
    )

    frames: list[pd.DataFrame] = []
    for (station_id, station_name), station_df in grouped.groupby(["station_id", "station_name"]):
        station_daily = _complete_station_daily_series(
            station_id=station_id,
            station_name=station_name,
            observed=station_df,
            iqr_multiplier=float(prep["iqr_multiplier"]),
            interpolation_limit_days=int(prep["interpolation_limit_days"]),
            savgol_window_days=int(prep["savgol_window_days"]),
            savgol_polyorder=int(prep["savgol_polyorder"]),
            remove_iqr_outliers=bool(prep.get("remove_iqr_outliers", False)),
            use_smoothed_for_forecast=bool(prep["use_smoothed_for_forecast"]),
        )
        frames.append(station_daily)
    output = pd.concat(frames, ignore_index=True)
    output["date"] = pd.to_datetime(output["date"]).dt.date.astype(str)
    return output.sort_values(["station_id", "date"]).reset_index(drop=True)


def _complete_station_daily_series(
    station_id: str,
    station_name: str,
    observed: pd.DataFrame,
    iqr_multiplier: float,
    interpolation_limit_days: int,
    savgol_window_days: int,
    savgol_polyorder: int,
    remove_iqr_outliers: bool,
    use_smoothed_for_forecast: bool,
) -> pd.DataFrame:
    observed = observed.sort_values("date").set_index("date")
    full_index = pd.date_range(observed.index.min(), observed.index.max(), freq="D")
    daily = observed.reindex(full_index)
    daily.index.name = "date"
    daily["station_id"] = station_id
    daily["station_name"] = station_name
    daily["source_count"] = daily["source_count"].fillna(0).astype(int)
    daily["is_direct_observation"] = daily["chl_a_observed"].notna()
    daily["chl_a_unit"] = "ug/L"

    outlier_mask = _iqr_outlier_mask(daily["chl_a_observed"], multiplier=iqr_multiplier)
    daily["is_iqr_outlier"] = outlier_mask.fillna(False)
    daily["is_outlier_removed"] = daily["is_iqr_outlier"] & remove_iqr_outliers
    daily["chl_a_clean"] = daily["chl_a_observed"].mask(daily["is_outlier_removed"])

    interpolated = daily["chl_a_clean"].interpolate(
        method="time", limit=interpolation_limit_days, limit_area="inside"
    )
    daily["_interpolated_candidate"] = interpolated
    daily["is_interpolated"] = daily["chl_a_clean"].isna() & interpolated.notna()

    filled = daily["chl_a_clean"].copy()
    method = pd.Series("observed", index=daily.index, dtype="object")
    filled = filled.where(~daily["is_interpolated"], interpolated)
    method = method.mask(daily["is_interpolated"], "linear_interpolation")

    remaining = filled.isna()
    doy_means = daily["chl_a_clean"].groupby(daily.index.dayofyear).mean()
    month_means = daily["chl_a_clean"].groupby(daily.index.month).mean()
    station_median = (
        float(daily["chl_a_clean"].median()) if daily["chl_a_clean"].notna().any() else np.nan
    )
    doy_values = daily.index.dayofyear.map(doy_means).astype(float)
    month_values = daily.index.month.map(month_means).astype(float)

    use_doy = remaining & ~pd.isna(doy_values)
    filled = filled.mask(use_doy, doy_values)
    method = method.mask(use_doy, "dayofyear_climatology")
    remaining = filled.isna()

    use_month = remaining & ~pd.isna(month_values)
    filled = filled.mask(use_month, month_values)
    method = method.mask(use_month, "monthly_climatology")
    remaining = filled.isna()

    if remaining.any() and not np.isnan(station_median):
        filled = filled.mask(remaining, station_median)
        method = method.mask(remaining, "station_median")

    method = method.mask(daily["is_outlier_removed"], "iqr_outlier_removed_then_imputed")
    daily["chl_a_filled"] = filled
    daily["is_imputed"] = ~daily["is_direct_observation"] | daily["is_outlier_removed"]
    daily["imputation_method"] = method

    daily["chl_a_smoothed"] = _smooth_series(
        daily["chl_a_filled"], window_days=savgol_window_days, polyorder=savgol_polyorder
    )
    daily["is_smoothed"] = daily["chl_a_smoothed"].notna()
    daily["smoothing_method"] = np.where(
        daily["is_smoothed"], f"savitzky_golay_w{savgol_window_days}_p{savgol_polyorder}", "none"
    )
    daily["chl_a_model"] = (
        daily["chl_a_smoothed"] if use_smoothed_for_forecast else daily["chl_a_filled"]
    )
    daily["season"] = [southern_hemisphere_season(int(month)) for month in daily.index.month]
    return daily.reset_index().drop(columns=["_interpolated_candidate"])


def _iqr_outlier_mask(series: pd.Series, multiplier: float) -> pd.Series:
    observed = series.dropna()
    if observed.size < 4:
        return pd.Series(False, index=series.index)
    q1 = observed.quantile(0.25)
    q3 = observed.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0 or pd.isna(iqr):
        return pd.Series(False, index=series.index)
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return (series < lower) | (series > upper)


def _smooth_series(series: pd.Series, window_days: int, polyorder: int) -> pd.Series:
    values = series.astype(float)
    if values.notna().sum() < max(window_days, polyorder + 2):
        return values
    window = window_days if window_days % 2 == 1 else window_days + 1
    if window > len(values):
        window = len(values) if len(values) % 2 == 1 else len(values) - 1
    if window <= polyorder:
        return values
    smoothed = savgol_filter(
        values.to_numpy(), window_length=window, polyorder=polyorder, mode="interp"
    )
    smoothed = np.clip(smoothed, a_min=0, a_max=None)
    return pd.Series(smoothed, index=series.index)


def preprocessing_footprint(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    grouped = daily.groupby(["station_id", "station_name"], dropna=False)
    rows = grouped.agg(
        modeled_daily_count=("date", "size"),
        direct_observation_count=("is_direct_observation", "sum"),
        outlier_removed_count=("is_outlier_removed", "sum"),
        iqr_outlier_flag_count=("is_iqr_outlier", "sum"),
        imputed_count=("is_imputed", "sum"),
        interpolated_count=("is_interpolated", "sum"),
        smoothed_count=("is_smoothed", "sum"),
        source_observation_count=("source_count", "sum"),
        date_min=("date", "min"),
        date_max=("date", "max"),
    ).reset_index()
    for column in (
        "direct_observation_count",
        "outlier_removed_count",
        "iqr_outlier_flag_count",
        "imputed_count",
        "interpolated_count",
        "smoothed_count",
    ):
        rows[column.replace("_count", "_proportion")] = rows[column] / rows["modeled_daily_count"]
    return rows


def preprocessing_footprint_by_month(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    frame = daily.copy()
    frame["month"] = pd.to_datetime(frame["date"]).dt.to_period("M").astype(str)
    grouped = frame.groupby(["station_id", "station_name", "month"], dropna=False)
    return grouped.agg(
        modeled_daily_count=("date", "size"),
        direct_observation_count=("is_direct_observation", "sum"),
        imputed_count=("is_imputed", "sum"),
        interpolated_count=("is_interpolated", "sum"),
        iqr_outlier_flag_count=("is_iqr_outlier", "sum"),
        outlier_removed_count=("is_outlier_removed", "sum"),
    ).reset_index()
