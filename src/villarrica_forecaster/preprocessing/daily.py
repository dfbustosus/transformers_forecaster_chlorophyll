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
    reports_dir = path_from_config(config, "reports")
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
        "chlorophyll_invalid_values": write_csv(
            chlorophyll_invalid_values(canonical), tables_dir / "chlorophyll_invalid_values.csv"
        ),
        "chlorophyll_spike_review": write_csv(
            chlorophyll_spike_review(canonical, config), tables_dir / "chlorophyll_spike_review.csv"
        ),
        "duplicate_station_date_statistic": write_csv(
            duplicate_station_date_statistic(canonical),
            tables_dir / "duplicate_station_date_statistic.csv",
        ),
        "cross_station_identical_values": write_csv(
            cross_station_identical_values(canonical),
            tables_dir / "cross_station_identical_values.csv",
        ),
        "climatology_source_counts": write_csv(
            climatology_source_counts(daily), tables_dir / "climatology_source_counts.csv"
        ),
        "masked_observed_holdout": write_csv(
            masked_observed_holdout(canonical, config), tables_dir / "masked_observed_holdout.csv"
        ),
        "smoothing_peak_attenuation": write_csv(
            smoothing_peak_attenuation(daily), tables_dir / "smoothing_peak_attenuation.csv"
        ),
        "data_qa_blockers": write_csv(
            data_qa_blockers(canonical, daily), reports_dir / "data_qa_blockers.csv"
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
                "compute_smoothed_variant": config["preprocessing"].get(
                    "compute_smoothed_variant", False
                ),
                "climatology_window_days": config["preprocessing"].get(
                    "climatology_window_days", 15
                ),
                "climatology_min_observations": config["preprocessing"].get(
                    "climatology_min_observations", 3
                ),
                "monthly_min_observations": config["preprocessing"].get(
                    "monthly_min_observations", 3
                ),
                "climatology_temporality": config["preprocessing"].get(
                    "climatology_temporality", "historical_only"
                ),
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
    if "is_model_eligible" in valid.columns:
        valid = valid[valid["is_model_eligible"].astype(bool)].copy()
    if "date_validation_status" in valid.columns:
        valid = valid[~valid["date_validation_status"].eq("missing_date_column")].copy()
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
    for column, default in {
        "source_file": "unknown",
        "source_row": 0,
        "source_sheet": "unknown",
    }.items():
        if column not in valid.columns:
            valid[column] = default
    grouped = (
        valid.groupby(["station_id", "station_name", "date"], as_index=False)
        .agg(
            chl_a_observed=("value", "mean"),
            source_count=("value", "size"),
            daily_value_min=("value", "min"),
            daily_value_max=("value", "max"),
            daily_value_std=("value", "std"),
            source_file_count=("source_file", "nunique"),
            source_files=("source_file", _join_unique_strings),
            source_rows=("source_row", _join_source_rows),
            source_sheets=("source_sheet", _join_unique_strings),
        )
        .sort_values(["station_id", "date"])
    )
    grouped["daily_value_std"] = grouped["daily_value_std"].fillna(0.0)
    grouped["daily_aggregation_method"] = np.where(
        grouped["source_count"].gt(1), "mean_of_same_day_sources", "single_source"
    )
    grouped = _add_grouped_cross_station_duplicate_flags(grouped)

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
            compute_smoothed_variant=bool(prep.get("compute_smoothed_variant", False)),
            climatology_window_days=int(prep.get("climatology_window_days", 15)),
            climatology_min_observations=int(prep.get("climatology_min_observations", 3)),
            monthly_min_observations=int(prep.get("monthly_min_observations", 3)),
            spike_review_delta_ug_l=float(prep.get("spike_review_delta_ug_l", 15.0)),
            high_chl_threshold_ug_l=float(prep.get("high_chl_threshold_ug_l", 10.0)),
            bloom_range_threshold_ug_l=float(prep.get("bloom_range_threshold_ug_l", 30.0)),
            strict_outlier_quarantine=bool(prep.get("strict_outlier_quarantine", False)),
            quarantine_iqr_high_chl=bool(prep.get("quarantine_iqr_high_chl", False)),
            quarantine_bloom_range=bool(prep.get("quarantine_bloom_range", False)),
            quarantine_cross_station_duplicates=bool(
                prep.get("quarantine_cross_station_duplicates", False)
            ),
            quarantine_abrupt_transitions=bool(prep.get("quarantine_abrupt_transitions", False)),
        )
        frames.append(station_daily)
    output = pd.concat(frames, ignore_index=True)
    output = _add_cross_station_duplicate_flags(output)
    for column in ("date", "previous_observation_date", "next_observation_date"):
        if column in output.columns:
            output[column] = _date_series_to_string(output[column])
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
    compute_smoothed_variant: bool,
    climatology_window_days: int,
    climatology_min_observations: int,
    monthly_min_observations: int,
    spike_review_delta_ug_l: float,
    high_chl_threshold_ug_l: float,
    bloom_range_threshold_ug_l: float,
    strict_outlier_quarantine: bool,
    quarantine_iqr_high_chl: bool,
    quarantine_bloom_range: bool,
    quarantine_cross_station_duplicates: bool,
    quarantine_abrupt_transitions: bool,
) -> pd.DataFrame:
    observed = observed.sort_values("date").set_index("date")
    full_index = pd.date_range(observed.index.min(), observed.index.max(), freq="D")
    daily = observed.reindex(full_index)
    daily.index.name = "date"
    daily["station_id"] = station_id
    daily["station_name"] = station_name
    daily["source_count"] = daily["source_count"].fillna(0).astype(int)
    daily["source_observation_count"] = daily["source_count"]
    daily["source_file_count"] = daily["source_file_count"].fillna(0).astype(int)
    for column in ("source_files", "source_rows", "source_sheets", "daily_aggregation_method"):
        daily[column] = daily[column].fillna("")
    for column in ("daily_value_min", "daily_value_max", "daily_value_std"):
        daily[column] = daily[column].astype(float)
    if "is_cross_station_duplicate_candidate" not in daily.columns:
        daily["is_cross_station_duplicate_candidate"] = False
    daily["is_cross_station_duplicate_candidate"] = daily[
        "is_cross_station_duplicate_candidate"
    ].map(lambda value: str(value).lower() == "true" or value is True)
    daily["is_direct_observation"] = daily["chl_a_observed"].notna()
    daily["is_satellite_derived"] = False
    daily["chl_a_unit"] = "ug/L"

    outlier_mask = _iqr_outlier_mask(daily["chl_a_observed"], multiplier=iqr_multiplier)
    daily["is_iqr_outlier"] = outlier_mask.fillna(False)
    daily["is_high_chl"] = daily["chl_a_observed"].ge(high_chl_threshold_ug_l).fillna(False)
    daily["is_bloom_range_chl"] = (
        daily["chl_a_observed"].ge(bloom_range_threshold_ug_l).fillna(False)
    )
    daily = _add_abrupt_transition_flags(daily, spike_review_delta_ug_l=spike_review_delta_ug_l)
    exclusion = _qc_exclusion_mask(
        daily,
        remove_iqr_outliers=remove_iqr_outliers,
        strict_outlier_quarantine=strict_outlier_quarantine,
        quarantine_iqr_high_chl=quarantine_iqr_high_chl,
        quarantine_bloom_range=quarantine_bloom_range,
        quarantine_cross_station_duplicates=quarantine_cross_station_duplicates,
        quarantine_abrupt_transitions=quarantine_abrupt_transitions,
    )
    daily["qc_exclusion_reason"] = exclusion["reason"]
    daily["is_qc_excluded_from_model"] = exclusion["mask"]
    daily["is_outlier_removed"] = daily["is_qc_excluded_from_model"]
    daily["chl_a_clean"] = daily["chl_a_observed"].mask(daily["is_qc_excluded_from_model"])
    daily["is_missing_before_imputation"] = daily["chl_a_clean"].isna()
    daily["is_iqr_outlier_retained"] = daily["is_iqr_outlier"] & ~daily["is_outlier_removed"]
    daily = _add_gap_metadata(daily)

    interpolated = daily["chl_a_clean"].interpolate(method="time", limit_area="inside")
    daily["_interpolated_candidate"] = interpolated
    daily["is_interpolated"] = (
        daily["chl_a_clean"].isna()
        & interpolated.notna()
        & daily["gap_length_days"].le(interpolation_limit_days)
    )

    filled = daily["chl_a_clean"].copy()
    method = pd.Series("observed", index=daily.index, dtype="object")
    imputation_source_count = pd.Series(0, index=daily.index, dtype="int64")
    imputation_window_days = pd.Series(0, index=daily.index, dtype="int64")
    imputation_confidence = pd.Series("observed", index=daily.index, dtype="object")
    filled = filled.where(~daily["is_interpolated"], interpolated)
    method = method.mask(daily["is_interpolated"], "linear_interpolation")
    imputation_source_count = imputation_source_count.mask(daily["is_interpolated"], 2)
    imputation_window_days = imputation_window_days.mask(
        daily["is_interpolated"], daily["gap_length_days"].fillna(0).astype(int)
    )
    imputation_confidence = imputation_confidence.mask(daily["is_interpolated"], "high_short_gap")

    remaining = filled.isna()
    for timestamp in daily.index[remaining]:
        replacement = _historical_replacement(
            clean=daily["chl_a_clean"],
            timestamp=timestamp,
            climatology_window_days=climatology_window_days,
            climatology_min_observations=climatology_min_observations,
            monthly_min_observations=monthly_min_observations,
        )
        filled.loc[timestamp] = replacement["value"]
        method.loc[timestamp] = replacement["method"]
        imputation_source_count.loc[timestamp] = int(replacement["source_count"])
        imputation_window_days.loc[timestamp] = int(replacement["window_days"])
        imputation_confidence.loc[timestamp] = str(replacement["confidence"])

    method = method.mask(daily["is_outlier_removed"], "iqr_outlier_removed_then_imputed")
    daily["chl_a_filled"] = filled
    daily["is_imputed"] = ~daily["is_direct_observation"] | daily["is_outlier_removed"]
    daily["imputation_method"] = method
    daily["imputation_source_count"] = imputation_source_count.astype(int)
    daily["climatology_source_count"] = np.where(
        daily["imputation_method"].str.contains("historical", na=False),
        daily["imputation_source_count"],
        0,
    ).astype(int)
    daily["climatology_window_days"] = imputation_window_days.astype(int)
    daily["imputation_confidence"] = imputation_confidence
    daily["is_low_support_imputation"] = daily["is_imputed"] & daily["imputation_source_count"].lt(
        climatology_min_observations
    )
    daily["is_hpbr_imputed"] = daily["imputation_method"].str.contains("historical", na=False)
    daily["preprocessing_stage"] = np.select(
        [
            daily["is_direct_observation"] & ~daily["is_outlier_removed"],
            daily["is_interpolated"],
            daily["is_hpbr_imputed"],
            daily["is_imputed"],
        ],
        ["observed", "short_gap_interpolated", "historical_imputed", "other_imputed"],
        default="unknown",
    )

    if compute_smoothed_variant and savgol_window_days > 0:
        daily["chl_a_smoothed"] = _smooth_series(
            daily["chl_a_filled"], window_days=savgol_window_days, polyorder=savgol_polyorder
        )
        daily["has_smoothed_variant"] = daily["chl_a_smoothed"].notna()
        diagnostic_method = f"savitzky_golay_w{savgol_window_days}_p{savgol_polyorder}"
    else:
        daily["chl_a_smoothed"] = np.nan
        daily["has_smoothed_variant"] = False
        diagnostic_method = "none"
    daily["smoothing_delta"] = daily["chl_a_smoothed"] - daily["chl_a_filled"]
    daily["abs_smoothing_delta"] = daily["smoothing_delta"].abs()
    daily["is_smoothed"] = bool(use_smoothed_for_forecast) & daily["has_smoothed_variant"]
    daily["smoothing_method"] = np.where(daily["is_smoothed"], diagnostic_method, "none")
    daily["chl_a_model"] = (
        daily["chl_a_smoothed"] if use_smoothed_for_forecast else daily["chl_a_filled"]
    )
    daily["season"] = [southern_hemisphere_season(int(month)) for month in daily.index.month]
    return daily.reset_index().drop(columns=["_interpolated_candidate"])


def _join_unique_strings(values: pd.Series) -> str:
    return "; ".join(sorted({str(value) for value in values.dropna() if str(value)}))


def _join_source_rows(values: pd.Series) -> str:
    rows: list[str] = []
    for value in values.dropna():
        try:
            rows.append(str(int(value)))
        except (TypeError, ValueError):
            rows.append(str(value))
    return "; ".join(rows)


def _add_grouped_cross_station_duplicate_flags(grouped: pd.DataFrame) -> pd.DataFrame:
    frame = grouped.copy()
    frame["is_cross_station_duplicate_candidate"] = False
    if frame.empty:
        return frame
    frame["_rounded_chl"] = frame["chl_a_observed"].round(6)
    station_counts = frame.groupby(["date", "_rounded_chl"])["station_id"].transform("nunique")
    frame["is_cross_station_duplicate_candidate"] = station_counts.gt(1)
    return frame.drop(columns=["_rounded_chl"])


def _qc_exclusion_mask(
    daily: pd.DataFrame,
    *,
    remove_iqr_outliers: bool,
    strict_outlier_quarantine: bool,
    quarantine_iqr_high_chl: bool,
    quarantine_bloom_range: bool,
    quarantine_cross_station_duplicates: bool,
    quarantine_abrupt_transitions: bool,
) -> pd.DataFrame:
    mask = pd.Series(False, index=daily.index)
    reasons = pd.Series("", index=daily.index, dtype="object")

    def add_reason(condition: pd.Series, reason: str) -> None:
        nonlocal mask, reasons
        condition = condition.fillna(False).astype(bool)
        mask |= condition
        reasons = reasons.mask(condition & reasons.eq(""), reason)
        reasons = reasons.mask(
            condition & reasons.ne("") & ~reasons.str.contains(reason, regex=False),
            reasons + ";" + reason,
        )

    add_reason(daily["is_iqr_outlier"] & bool(remove_iqr_outliers), "iqr_outlier")
    if strict_outlier_quarantine:
        add_reason(
            daily["is_iqr_outlier"] & daily["is_high_chl"] & bool(quarantine_iqr_high_chl),
            "iqr_high_chl_quarantine",
        )
        add_reason(
            daily["is_bloom_range_chl"] & bool(quarantine_bloom_range),
            "bloom_range_requires_confirmation",
        )
        add_reason(
            daily["is_cross_station_duplicate_candidate"]
            & bool(quarantine_cross_station_duplicates),
            "cross_station_duplicate_quarantine",
        )
        add_reason(
            daily["is_abrupt_observed_transition"] & bool(quarantine_abrupt_transitions),
            "abrupt_transition_quarantine",
        )
    return pd.DataFrame({"mask": mask & daily["is_direct_observation"], "reason": reasons})


def _date_series_to_string(values: pd.Series) -> pd.Series:
    dates = pd.to_datetime(values, errors="coerce")
    output = dates.dt.date.astype("string")
    return output.fillna("")


def _add_cross_station_duplicate_flags(daily: pd.DataFrame) -> pd.DataFrame:
    frame = daily.copy()
    frame["is_cross_station_duplicate_candidate"] = False
    observed = frame[frame["is_direct_observation"] & frame["chl_a_observed"].notna()].copy()
    if observed.empty:
        return frame
    observed["rounded_value"] = observed["chl_a_observed"].round(6)
    counts = observed.groupby(["date", "rounded_value"])["station_id"].transform("nunique")
    duplicate_index = observed[counts.gt(1)].index
    frame.loc[duplicate_index, "is_cross_station_duplicate_candidate"] = True
    return frame


def _add_gap_metadata(daily: pd.DataFrame) -> pd.DataFrame:
    frame = daily.copy()
    clean = frame["chl_a_clean"]
    index_series = pd.Series(frame.index, index=frame.index)
    observed_dates = index_series.where(clean.notna())
    previous_dates = observed_dates.ffill()
    next_dates = observed_dates.bfill()
    frame["previous_observation_date"] = previous_dates
    frame["next_observation_date"] = next_dates
    frame["days_since_last_observation"] = (index_series - previous_dates).dt.days
    frame["days_until_next_observation"] = (next_dates - index_series).dt.days
    missing = clean.isna()
    gap_groups = missing.ne(missing.shift(fill_value=False)).cumsum().where(missing)
    frame["gap_length_days"] = missing.groupby(gap_groups).transform("sum").fillna(0).astype(int)
    frame.loc[~missing, "gap_length_days"] = 0
    return frame


def _add_abrupt_transition_flags(
    daily: pd.DataFrame, spike_review_delta_ug_l: float
) -> pd.DataFrame:
    frame = daily.copy()
    observed = frame[frame["is_direct_observation"]].copy()
    observed["previous_direct_value"] = observed["chl_a_observed"].shift(1)
    observed["previous_direct_date"] = pd.Series(observed.index, index=observed.index).shift(1)
    observed["direct_gap_days"] = (
        pd.Series(observed.index, index=observed.index) - observed["previous_direct_date"]
    ).dt.days
    observed["direct_delta"] = observed["chl_a_observed"] - observed["previous_direct_value"]
    frame["previous_direct_value"] = np.nan
    frame["direct_gap_days"] = np.nan
    frame["direct_delta"] = np.nan
    frame.loc[observed.index, "previous_direct_value"] = observed["previous_direct_value"]
    frame.loc[observed.index, "direct_gap_days"] = observed["direct_gap_days"]
    frame.loc[observed.index, "direct_delta"] = observed["direct_delta"]
    frame["is_abrupt_observed_transition"] = (
        frame["direct_gap_days"].eq(1) & frame["direct_delta"].abs().ge(spike_review_delta_ug_l)
    ).fillna(False)
    return frame


def _historical_replacement(
    clean: pd.Series,
    timestamp: pd.Timestamp,
    climatology_window_days: int,
    climatology_min_observations: int,
    monthly_min_observations: int,
) -> dict[str, Any]:
    prior = clean[clean.index < timestamp].dropna().astype(float)
    if prior.empty:
        return {
            "value": np.nan,
            "method": "unfilled_no_prior_observation",
            "source_count": 0,
            "window_days": 0,
            "confidence": "missing",
        }
    doy_distances = _circular_dayofyear_distance(prior.index.dayofyear, timestamp.dayofyear)
    doy_candidate = prior[doy_distances <= climatology_window_days]
    if len(doy_candidate) >= climatology_min_observations:
        return {
            "value": float(doy_candidate.median()),
            "method": "historical_doy_window_median",
            "source_count": int(len(doy_candidate)),
            "window_days": int(climatology_window_days),
            "confidence": "medium_historical_doy",
        }
    month_candidate = prior[prior.index.month == timestamp.month]
    if len(month_candidate) >= monthly_min_observations:
        return {
            "value": float(month_candidate.median()),
            "method": "historical_month_median",
            "source_count": int(len(month_candidate)),
            "window_days": 31,
            "confidence": "medium_historical_month",
        }
    return {
        "value": float(prior.median()),
        "method": "historical_station_median_low_support",
        "source_count": int(len(prior)),
        "window_days": 0,
        "confidence": "low_historical_station",
    }


def _circular_dayofyear_distance(days: pd.Index, target_day: int) -> np.ndarray:
    day_values = np.asarray(days, dtype=int)
    raw_distance = np.abs(day_values - int(target_day))
    return np.minimum(raw_distance, 366 - raw_distance)


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
        low_support_imputation_count=("is_low_support_imputation", "sum"),
        cross_station_duplicate_candidate_count=("is_cross_station_duplicate_candidate", "sum"),
        abrupt_transition_count=("is_abrupt_observed_transition", "sum"),
        high_chl_count=("is_high_chl", "sum"),
        bloom_range_chl_count=("is_bloom_range_chl", "sum"),
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
        "low_support_imputation_count",
        "cross_station_duplicate_candidate_count",
        "abrupt_transition_count",
        "high_chl_count",
        "bloom_range_chl_count",
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
        low_support_imputation_count=("is_low_support_imputation", "sum"),
        cross_station_duplicate_candidate_count=("is_cross_station_duplicate_candidate", "sum"),
    ).reset_index()


def chlorophyll_invalid_values(canonical: pd.DataFrame) -> pd.DataFrame:
    if canonical.empty:
        return pd.DataFrame()
    frame = canonical[
        canonical["variable"].eq("chlorophyll_a") & ~canonical["quality_flag"].eq("ok")
    ].copy()
    return frame.sort_values(["station_id", "date", "statistic", "source_file", "source_row"])


def duplicate_station_date_statistic(canonical: pd.DataFrame) -> pd.DataFrame:
    if canonical.empty:
        return pd.DataFrame()
    chl = canonical[canonical["variable"].eq("chlorophyll_a")].copy()
    grouped = chl.groupby(["station_id", "station_name", "date", "statistic"], dropna=False)
    rows = grouped.agg(
        n_rows=("value", "size"),
        n_unique_values=("value", "nunique"),
        min_value=("value", "min"),
        max_value=("value", "max"),
        quality_flags=("quality_flag", _join_unique_strings),
        source_files=("source_file", _join_unique_strings),
        source_rows=("source_row", _join_source_rows),
    ).reset_index()
    rows = rows[rows["n_rows"].gt(1)].copy()
    rows["resolution_status"] = np.where(
        rows["n_unique_values"].gt(1), "conflicting_duplicate_values", "identical_duplicate_values"
    )
    return rows.sort_values(["station_id", "date", "statistic"])


def cross_station_identical_values(canonical: pd.DataFrame) -> pd.DataFrame:
    if canonical.empty:
        return pd.DataFrame()
    chl = canonical[
        canonical["variable"].eq("chlorophyll_a") & canonical["quality_flag"].eq("ok")
    ].copy()
    chl["rounded_value"] = chl["value"].round(6)
    grouped = chl.groupby(["date", "statistic", "rounded_value"], dropna=False)
    rows = grouped.agg(
        station_count=("station_id", "nunique"),
        station_ids=("station_id", _join_unique_strings),
        source_files=("source_file", _join_unique_strings),
        source_rows=("source_row", _join_source_rows),
        row_count=("value", "size"),
    ).reset_index()
    rows = rows[rows["station_count"].gt(1)].copy()
    rows = rows.rename(columns={"rounded_value": "value"})
    return rows.sort_values(["date", "statistic", "value"])


def climatology_source_counts(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    columns = [
        "station_id",
        "station_name",
        "date",
        "imputation_method",
        "imputation_source_count",
        "climatology_source_count",
        "climatology_window_days",
        "imputation_confidence",
        "is_low_support_imputation",
        "chl_a_filled",
    ]
    frame = daily[daily["is_hpbr_imputed"] | daily["is_low_support_imputation"]].copy()
    return frame[columns].sort_values(["station_id", "date"])


def smoothing_peak_attenuation(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty or "abs_smoothing_delta" not in daily.columns:
        return pd.DataFrame()
    frame = daily[daily["has_smoothed_variant"].fillna(False)].copy()
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "station_id",
                "station_name",
                "date",
                "chl_a_filled",
                "chl_a_smoothed",
                "smoothing_delta",
                "abs_smoothing_delta",
                "is_high_chl",
                "is_direct_observation",
            ]
        )
    return frame.sort_values("abs_smoothing_delta", ascending=False)[
        [
            "station_id",
            "station_name",
            "date",
            "chl_a_filled",
            "chl_a_smoothed",
            "smoothing_delta",
            "abs_smoothing_delta",
            "is_high_chl",
            "is_direct_observation",
        ]
    ]


def data_qa_blockers(canonical: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not canonical.empty and "model_exclusion_reason" in canonical.columns:
        collision_rows = canonical[
            canonical["model_exclusion_reason"]
            .fillna("")
            .str.contains("same_raw_file_assigned_to_multiple_stations", regex=False)
        ]
        if not collision_rows.empty:
            rows.append(
                {
                    "blocker_id": "station_assignment_hash_collision",
                    "severity": "P0",
                    "scope": "raw_to_canonical",
                    "affected_rows": int(len(collision_rows)),
                    "evidence": "outputs/tables/raw_file_hash_collisions.csv",
                    "action": "Quarantine identical raw files assigned to multiple stations until author confirms station provenance.",
                    "forecast_allowed": False,
                }
            )
    if not canonical.empty and "date_validation_status" in canonical.columns:
        review_dates = canonical[
            canonical["date_validation_status"].eq("review_mixed_or_nonmonotonic_source_dates")
        ]
        if not review_dates.empty:
            rows.append(
                {
                    "blocker_id": "mixed_or_nonmonotonic_source_dates",
                    "severity": "P0",
                    "scope": "raw_to_canonical",
                    "affected_rows": int(len(review_dates)),
                    "evidence": "outputs/tables/mixed_date_encoding_audit.csv",
                    "action": "Resolve or document mixed Excel-serial/slash date ordering before using the source for manuscript forecasts.",
                    "forecast_allowed": False,
                }
            )
    if not daily.empty:
        footprint = preprocessing_footprint(daily)
        for _, row in footprint.iterrows():
            station = str(row["station_id"])
            if float(row.get("imputed_proportion", 0.0)) > 0.5:
                rows.append(
                    {
                        "blocker_id": "imputation_dominates_daily_target",
                        "severity": "P0",
                        "scope": station,
                        "affected_rows": int(row["imputed_count"]),
                        "evidence": "outputs/tables/preprocessing_footprint.csv",
                        "action": "Do not present daily forecasts as observed-series forecasts; reduce target to observed/short-gap windows or explicitly label reconstruction-dominated sections.",
                        "forecast_allowed": False,
                    }
                )
            if int(row.get("cross_station_duplicate_candidate_count", 0)) > 0:
                rows.append(
                    {
                        "blocker_id": "cross_station_duplicate_model_dates",
                        "severity": "P0",
                        "scope": station,
                        "affected_rows": int(row["cross_station_duplicate_candidate_count"]),
                        "evidence": "outputs/tables/cross_station_identical_values.csv",
                        "action": "Exclude or author-confirm long cross-station identical runs before training/evaluating station-specific models.",
                        "forecast_allowed": False,
                    }
                )
            if int(row.get("outlier_removed_count", 0)) > 0:
                rows.append(
                    {
                        "blocker_id": "qc_replaced_direct_observations",
                        "severity": "P1",
                        "scope": station,
                        "affected_rows": int(row["outlier_removed_count"]),
                        "evidence": "outputs/tables/chlorophyll_spike_review.csv",
                        "action": "Review each excluded direct observation and classify as confirmed artifact, confirmed bloom, or unresolved.",
                        "forecast_allowed": False,
                    }
                )
    return pd.DataFrame.from_records(
        rows,
        columns=[
            "blocker_id",
            "severity",
            "scope",
            "affected_rows",
            "evidence",
            "action",
            "forecast_allowed",
        ],
    )


def chlorophyll_spike_review(canonical: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    if canonical.empty:
        return pd.DataFrame()
    prep = config["preprocessing"]
    delta_threshold = float(prep.get("spike_review_delta_ug_l", 15.0))
    ratio_threshold = float(prep.get("spike_review_ratio", 8.0))
    high_threshold = float(prep.get("high_chl_threshold_ug_l", 10.0))
    chl = canonical[
        canonical["variable"].eq("chlorophyll_a")
        & canonical["statistic"].eq(prep.get("statistic", "mean"))
        & canonical["quality_flag"].eq("ok")
    ].copy()
    if chl.empty:
        return pd.DataFrame()
    chl["date"] = pd.to_datetime(chl["date"])
    daily = (
        chl.groupby(["station_id", "station_name", "date"], as_index=False)
        .agg(
            value=("value", "mean"),
            source_files=("source_file", _join_unique_strings),
            source_rows=("source_row", _join_source_rows),
            source_count=("value", "size"),
        )
        .sort_values(["station_id", "date"])
    )
    rows: list[pd.DataFrame] = []
    for _, group in daily.groupby("station_id", dropna=False):
        group = group.sort_values("date").copy()
        group["prev_date"] = group["date"].shift(1)
        group["prev_value"] = group["value"].shift(1)
        group["next_date"] = group["date"].shift(-1)
        group["next_value"] = group["value"].shift(-1)
        group["gap_days_prev"] = (group["date"] - group["prev_date"]).dt.days
        group["diff_prev"] = group["value"] - group["prev_value"]
        group["ratio_prev"] = group["value"] / group["prev_value"].replace(0, np.nan)
        group["abs_diff_prev"] = group["diff_prev"].abs()
        group["spike_rule"] = ""
        high = group["value"].ge(high_threshold)
        abrupt = group["gap_days_prev"].le(1) & group["abs_diff_prev"].ge(delta_threshold)
        ratio = group["ratio_prev"].ge(ratio_threshold) | group["ratio_prev"].le(
            1 / ratio_threshold
        )
        group.loc[high, "spike_rule"] = "high_chl_review"
        group.loc[abrupt, "spike_rule"] = group.loc[abrupt, "spike_rule"].mask(
            group.loc[abrupt, "spike_rule"].eq(""), "abrupt_transition_review"
        )
        group.loc[ratio, "spike_rule"] = group.loc[ratio, "spike_rule"].mask(
            group.loc[ratio, "spike_rule"].eq(""), "large_ratio_change_review"
        )
        rows.append(group[group["spike_rule"].ne("")])
    if not rows:
        return pd.DataFrame()
    output = pd.concat(rows, ignore_index=True)
    for column in ("date", "prev_date", "next_date"):
        output[column] = _date_series_to_string(output[column])
    return output[
        [
            "station_id",
            "station_name",
            "date",
            "value",
            "prev_date",
            "prev_value",
            "next_date",
            "next_value",
            "diff_prev",
            "ratio_prev",
            "gap_days_prev",
            "source_files",
            "source_rows",
            "source_count",
            "spike_rule",
        ]
    ].sort_values(["station_id", "date"])


def masked_observed_holdout(canonical: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    if canonical.empty:
        return pd.DataFrame()
    prep = config["preprocessing"]
    chl = canonical[
        canonical["variable"].eq("chlorophyll_a")
        & canonical["statistic"].eq(prep.get("statistic", "mean"))
        & canonical["quality_flag"].eq("ok")
    ].copy()
    if chl.empty:
        return pd.DataFrame()
    chl["date"] = pd.to_datetime(chl["date"])
    observed = (
        chl.groupby(["station_id", "station_name", "date"], as_index=False)
        .agg(value=("value", "mean"))
        .sort_values(["station_id", "date"])
    )
    rows: list[dict[str, Any]] = []
    for (station_id, station_name), group in observed.groupby(["station_id", "station_name"]):
        series = group.set_index("date")["value"].sort_index()
        for timestamp, actual in series.items():
            train = series.drop(index=timestamp)
            replacement = _historical_replacement(
                clean=train,
                timestamp=timestamp,
                climatology_window_days=int(prep.get("climatology_window_days", 15)),
                climatology_min_observations=int(prep.get("climatology_min_observations", 3)),
                monthly_min_observations=int(prep.get("monthly_min_observations", 3)),
            )
            predicted = replacement["value"]
            rows.append(
                {
                    "station_id": station_id,
                    "station_name": station_name,
                    "date": timestamp.date().isoformat(),
                    "actual_chl_a": float(actual),
                    "reconstructed_chl_a": predicted,
                    "absolute_error": abs(float(actual) - predicted)
                    if not pd.isna(predicted)
                    else np.nan,
                    "method": replacement["method"],
                    "source_count": replacement["source_count"],
                    "confidence": replacement["confidence"],
                }
            )
    return pd.DataFrame.from_records(rows).sort_values(["station_id", "date"])
