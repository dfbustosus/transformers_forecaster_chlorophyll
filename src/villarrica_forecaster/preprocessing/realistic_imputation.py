from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.io import write_csv, write_json


@dataclass(frozen=True)
class ImputationSettings:
    start: str
    end: str
    doy_bandwidth_days: int
    short_gap_days: int
    harmonics: int
    analog_residual_weight: float
    cap_quantile: float
    cap_multiplier: float
    boundary_blend_days: int


def build_realistic_imputation_outputs(config: dict[str, Any]) -> dict[str, Path]:
    processed_dir = path_from_config(config, "processed_data")
    tables_dir = path_from_config(config, "tables")
    canonical = pd.read_csv(processed_dir / "canonical_observations.csv", parse_dates=["date"])
    imputed = build_realistic_imputed_reference_2024(canonical, config)
    diagnostics = realistic_imputation_diagnostics(imputed)
    paths = {
        "realistic_imputed_chl_a_2024": write_csv(
            imputed, processed_dir / "realistic_imputed_chl_a_2024.csv"
        ),
        "realistic_imputed_chl_a_2024_source": write_csv(
            imputed, tables_dir / "realistic_imputed_chl_a_2024_source.csv"
        ),
        "realistic_imputation_diagnostics": write_csv(
            diagnostics, tables_dir / "realistic_imputation_diagnostics.csv"
        ),
    }
    paths["realistic_imputation_manifest"] = write_json(
        {
            "description": "Observed-preserving daily 2024 Chl-a imputation using bracketed short-gap PCHIP plus prior-year circular day-of-year climatology, harmonic robust regression, deterministic analog residuals, and boundary blending to avoid artificial jumps at observation edges.",
            "observed_values_preserved": True,
            "smoothing": "none",
            "forecast_status": "data_imputation_only_not_a_model_forecast",
            "outputs": {key: str(value) for key, value in paths.items()},
        },
        processed_dir / "realistic_imputation_manifest.json",
    )
    return paths


def build_realistic_imputed_reference_2024(
    canonical: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    prep = config["preprocessing"]
    settings = _settings(prep)
    chl = canonical[
        canonical["variable"].eq(prep["chlorophyll_variable"])
        & canonical["statistic"].eq(prep["statistic"])
        & canonical["quality_flag"].eq("ok")
    ].copy()
    if "is_model_eligible" in chl.columns:
        chl = chl[chl["is_model_eligible"].astype(bool)].copy()
    if chl.empty:
        return pd.DataFrame()
    chl["date"] = pd.to_datetime(chl["date"])
    grouped = (
        chl.groupby(["station_id", "station_name", "date"], as_index=False)
        .agg(
            chl_a_observed=("value", "mean"),
            source_observation_count=("value", "size"),
            source_files=("source_file", _join_unique),
            source_rows=("source_row", _join_rows),
        )
        .sort_values(["station_id", "date"])
    )
    frames = [
        _station_realistic_imputation(station_id, station_name, station, settings)
        for (station_id, station_name), station in grouped.groupby(["station_id", "station_name"])
    ]
    output = pd.concat(frames, ignore_index=True)
    output["date"] = pd.to_datetime(output["date"]).dt.date.astype(str)
    return output.sort_values(["station_id", "date"]).reset_index(drop=True)


def _station_realistic_imputation(
    station_id: str, station_name: str, station: pd.DataFrame, settings: ImputationSettings
) -> pd.DataFrame:
    target_index = pd.date_range(settings.start, settings.end, freq="D")
    observed_all = station.set_index("date").sort_index()["chl_a_observed"].astype(float)
    observed_2024 = observed_all.reindex(target_index)
    historical_observed = _historical_training_series(observed_all, target_index)
    cap = _imputation_cap(observed_2024, historical_observed, settings)
    historical_training = historical_observed.clip(lower=0.0, upper=cap)

    frame = pd.DataFrame(index=target_index)
    frame.index.name = "date"
    frame["station_id"] = station_id
    frame["station_name"] = station_name
    frame["chl_a_observed"] = observed_2024
    frame["is_observed"] = observed_2024.notna()
    frame["source_observation_count"] = (
        station.set_index("date")["source_observation_count"]
        .reindex(target_index)
        .fillna(0)
        .astype(int)
    )
    frame["source_files"] = (
        station.set_index("date")["source_files"].reindex(target_index).fillna("")
    )
    frame["source_rows"] = station.set_index("date")["source_rows"].reindex(target_index).fillna("")

    climatology = _doy_kernel_mean(historical_training, target_index, settings.doy_bandwidth_days)
    harmonic = _harmonic_huber(historical_training, target_index, settings.harmonics).clip(0.0, cap)
    pchip = _pchip(observed_2024.dropna(), target_index, extrapolate=False).clip(0.0, cap)
    residual = _analog_residual(
        historical_training, target_index, settings.doy_bandwidth_days
    ).clip(-0.45 * cap, 0.45 * cap)
    nearest_gap = _nearest_observation_gap_days(observed_2024.dropna(), target_index)
    gap_length = _missing_gap_length_days(observed_2024)

    short_gap = _bracketed_short_gap_mask(observed_2024, settings.short_gap_days)
    long_gap = observed_2024.isna() & ~short_gap
    imputed = observed_2024.copy()
    short_gap_value = (0.88 * pchip + 0.12 * climatology).fillna(
        0.70 * climatology + 0.30 * harmonic
    )
    imputed = imputed.mask(short_gap, short_gap_value)
    long_gap_value = (
        0.62 * climatology + 0.30 * harmonic + settings.analog_residual_weight * residual
    )
    long_gap_value = _apply_observation_boundary_blend(
        long_gap_value, observed_2024, settings.boundary_blend_days
    )
    imputed = imputed.mask(long_gap, long_gap_value)
    fallback = _fallback_imputation_series(
        long_gap_value, climatology, harmonic, historical_training
    )
    imputed = imputed.fillna(fallback).clip(lower=0.0)
    imputed = imputed.mask(observed_2024.notna(), observed_2024)
    imputed = imputed.mask(observed_2024.isna(), imputed.clip(upper=cap))

    frame["chl_a_imputed"] = imputed
    frame["doy_kernel_climatology"] = climatology
    frame["harmonic_huber"] = harmonic
    frame["pchip_short_gap"] = pchip
    frame["analog_residual"] = residual
    frame["nearest_observation_gap_days"] = nearest_gap
    frame["gap_length_days"] = gap_length
    frame["imputation_cap"] = cap
    frame["historical_source_observation_count"] = int(historical_training.dropna().shape[0])
    frame["boundary_blend_days"] = settings.boundary_blend_days
    frame["imputation_method"] = np.select(
        [frame["is_observed"], short_gap, long_gap],
        [
            "observed",
            "shape_preserving_pchip_bracketed_short_gap",
            "historical_seasonal_harmonic_analog_residual",
        ],
        default="fallback_interpolation",
    )
    frame["is_imputed"] = ~frame["is_observed"]
    frame["is_short_gap_imputed"] = short_gap
    frame["is_long_gap_imputed"] = long_gap
    frame["imputation_uncertainty_proxy"] = np.select(
        [frame["is_observed"], short_gap, long_gap],
        [0.0, 0.15, 0.40],
        default=0.50,
    )
    return frame.reset_index()


def _settings(prep: dict[str, Any]) -> ImputationSettings:
    return ImputationSettings(
        start=str(prep.get("realistic_imputation_start", "2024-01-01")),
        end=str(prep.get("realistic_imputation_end", "2024-12-31")),
        doy_bandwidth_days=int(prep.get("realistic_imputation_doy_bandwidth_days", 24)),
        short_gap_days=int(prep.get("realistic_imputation_short_gap_days", 10)),
        harmonics=int(prep.get("realistic_imputation_harmonics", 4)),
        analog_residual_weight=float(prep.get("realistic_imputation_analog_residual_weight", 0.28)),
        cap_quantile=float(prep.get("realistic_imputation_cap_quantile", 0.97)),
        cap_multiplier=float(prep.get("realistic_imputation_cap_multiplier", 1.12)),
        boundary_blend_days=int(prep.get("realistic_imputation_boundary_blend_days", 21)),
    )


def _imputation_cap(
    observed_2024: pd.Series, observed_all: pd.Series, settings: ImputationSettings
) -> float:
    observed = observed_2024.dropna().astype(float)
    if observed.empty:
        observed = observed_all.dropna().astype(float)
    if observed.empty:
        return 5.0
    quantile_cap = float(observed.quantile(settings.cap_quantile)) * settings.cap_multiplier
    return max(quantile_cap, float(observed.max()))


def _historical_training_series(
    observed_all: pd.Series, target_index: pd.DatetimeIndex
) -> pd.Series:
    """Use prior years for seasonal structure, falling back only when unavoidable."""

    target_start = target_index.min()
    historical = observed_all[observed_all.index < target_start].dropna().astype(float)
    if len(historical) >= 8:
        return historical
    outside_target = observed_all[~observed_all.index.isin(target_index)].dropna().astype(float)
    if len(outside_target) >= 8:
        return outside_target
    return observed_all.dropna().astype(float)


def _doy_kernel_mean(
    training: pd.Series, target_index: pd.DatetimeIndex, bandwidth_days: int
) -> pd.Series:
    training = training.dropna().astype(float)
    if training.empty:
        return pd.Series(np.nan, index=target_index)
    source_doy = training.index.dayofyear.to_numpy()
    source_values = training.to_numpy(dtype=float)
    values: list[float] = []
    for day in target_index.dayofyear:
        distance = np.minimum(np.abs(source_doy - int(day)), 366 - np.abs(source_doy - int(day)))
        local = distance <= bandwidth_days * 2.5
        if not local.any():
            values.append(float(np.nanmedian(source_values)))
            continue
        weights = np.exp(-0.5 * (distance[local] / max(bandwidth_days, 1)) ** 2)
        values.append(float(np.average(source_values[local], weights=weights)))
    return pd.Series(values, index=target_index)


def _harmonic_huber(
    training: pd.Series, target_index: pd.DatetimeIndex, harmonics: int
) -> pd.Series:
    training = training.dropna().astype(float)
    if len(training) < max(8, harmonics * 2 + 2):
        return pd.Series(
            float(training.median()) if not training.empty else np.nan, index=target_index
        )
    x_train = _harmonic_features(training.index, harmonics)
    y_train = np.log1p(training.to_numpy(dtype=float).clip(min=0.0))
    try:
        model = make_pipeline(StandardScaler(), HuberRegressor(alpha=0.01, epsilon=1.35))
        model.fit(x_train, y_train)
    except ValueError:
        model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        model.fit(x_train, y_train)
    return pd.Series(
        np.expm1(model.predict(_harmonic_features(target_index, harmonics))).clip(min=0.0),
        index=target_index,
    )


def _harmonic_features(index: pd.DatetimeIndex, harmonics: int) -> np.ndarray:
    day = index.dayofyear.to_numpy(dtype=float)
    ordinal = index.map(pd.Timestamp.toordinal).to_numpy(dtype=float)
    trend = (ordinal - pd.Timestamp("2024-01-01").toordinal()) / 365.25
    features = [trend]
    for k in range(1, harmonics + 1):
        angle = 2.0 * np.pi * k * day / 365.25
        features.extend([np.sin(angle), np.cos(angle)])
    return np.column_stack(features)


def _pchip(
    series: pd.Series, target_index: pd.DatetimeIndex, *, extrapolate: bool = False
) -> pd.Series:
    series = series.dropna().astype(float)
    if len(series) < 2:
        return pd.Series(float(series.median()) if not series.empty else np.nan, index=target_index)
    x = series.index.map(pd.Timestamp.toordinal).to_numpy(dtype=float)
    y = series.to_numpy(dtype=float)
    order = np.argsort(x)
    x_unique, unique_idx = np.unique(x[order], return_index=True)
    y_unique = y[order][unique_idx]
    interpolator = PchipInterpolator(x_unique, y_unique, extrapolate=extrapolate)
    target_x = target_index.map(pd.Timestamp.toordinal).to_numpy(dtype=float)
    return pd.Series(interpolator(target_x), index=target_index)


def _bracketed_short_gap_mask(observed: pd.Series, max_gap_days: int) -> pd.Series:
    missing = observed.isna()
    if not missing.any() or observed.notna().sum() < 2:
        return pd.Series(False, index=observed.index)
    index_series = pd.Series(observed.index, index=observed.index)
    observed_dates = index_series.where(observed.notna())
    previous_dates = observed_dates.ffill()
    next_dates = observed_dates.bfill()
    gap_length = _missing_gap_length_days(observed)
    return missing & previous_dates.notna() & next_dates.notna() & gap_length.le(max_gap_days)


def _missing_gap_length_days(observed: pd.Series) -> pd.Series:
    missing = observed.isna()
    groups = missing.ne(missing.shift(fill_value=False)).cumsum().where(missing)
    gap_length = missing.groupby(groups).transform("sum").fillna(0).astype(int)
    gap_length.loc[~missing] = 0
    return gap_length


def _fallback_imputation_series(
    primary: pd.Series, climatology: pd.Series, harmonic: pd.Series, historical_training: pd.Series
) -> pd.Series:
    fallback = primary.copy()
    fallback = fallback.fillna(0.70 * climatology + 0.30 * harmonic)
    fallback = fallback.fillna(climatology)
    fallback = fallback.fillna(harmonic)
    if fallback.isna().any():
        default = float(historical_training.median()) if not historical_training.empty else 0.0
        fallback = fallback.fillna(default)
    return fallback


def _apply_observation_boundary_blend(
    candidate: pd.Series, observed: pd.Series, blend_days: int
) -> pd.Series:
    """Blend long-gap estimates near observed edges to avoid artificial discontinuities."""

    if blend_days <= 0 or observed.notna().sum() == 0:
        return candidate
    blended = candidate.copy()
    missing = observed.isna()
    if not missing.any():
        return blended
    index_series = pd.Series(observed.index, index=observed.index)
    observed_dates = index_series.where(observed.notna())
    previous_dates = observed_dates.ffill()
    next_dates = observed_dates.bfill()
    previous_values = observed.ffill()
    next_values = observed.bfill()
    days_since = (index_series - previous_dates).dt.days
    days_until = (next_dates - index_series).dt.days

    near_previous = missing & previous_dates.notna() & days_since.le(blend_days)
    near_next = missing & next_dates.notna() & days_until.le(blend_days)
    use_previous = near_previous & (~near_next | days_since.le(days_until))
    use_next = near_next & ~use_previous

    previous_alpha = (days_since / blend_days).clip(lower=0.0, upper=1.0)
    blended.loc[use_previous] = (1.0 - previous_alpha.loc[use_previous]) * previous_values.loc[
        use_previous
    ] + previous_alpha.loc[use_previous] * candidate.loc[use_previous]
    next_alpha = (days_until / blend_days).clip(lower=0.0, upper=1.0)
    blended.loc[use_next] = (
        next_alpha.loc[use_next] * candidate.loc[use_next]
        + (1.0 - next_alpha.loc[use_next]) * next_values.loc[use_next]
    )
    return blended


def _analog_residual(
    training: pd.Series, target_index: pd.DatetimeIndex, bandwidth_days: int
) -> pd.Series:
    training = training.dropna().astype(float)
    if training.empty:
        return pd.Series(0.0, index=target_index)
    baseline_at_training = _doy_kernel_mean(training, training.index, bandwidth_days)
    residuals = training - baseline_at_training
    source_doy = residuals.index.dayofyear.to_numpy()
    source_residuals = residuals.to_numpy(dtype=float)
    values: list[float] = []
    for day in target_index.dayofyear:
        distance = np.minimum(np.abs(source_doy - int(day)), 366 - np.abs(source_doy - int(day)))
        nearest = np.argsort(distance)[: min(5, len(distance))]
        weights = 1.0 / (distance[nearest] + 1.0)
        values.append(float(np.average(source_residuals[nearest], weights=weights)))
    return pd.Series(values, index=target_index)


def _nearest_observation_gap_days(observed: pd.Series, target_index: pd.DatetimeIndex) -> pd.Series:
    observed = observed.dropna()
    if observed.empty:
        return pd.Series(np.inf, index=target_index)
    obs_ord = observed.index.map(pd.Timestamp.toordinal).to_numpy(dtype=float)
    target_ord = target_index.map(pd.Timestamp.toordinal).to_numpy(dtype=float)
    return pd.Series(
        np.min(np.abs(target_ord[:, None] - obs_ord[None, :]), axis=1), index=target_index
    )


def realistic_imputation_diagnostics(imputed: pd.DataFrame) -> pd.DataFrame:
    if imputed.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for (station_id, station_name), station in imputed.groupby(["station_id", "station_name"]):
        direct = station[station["is_observed"]]
        series = station["chl_a_imputed"].astype(float)
        observed_diff_std = float(direct["chl_a_observed"].astype(float).diff().std())
        imputed_diff_std = float(series.diff().std())
        rows.append(
            {
                "station_id": station_id,
                "station_name": station_name,
                "day_count": int(len(station)),
                "observed_day_count": int(station["is_observed"].sum()),
                "imputed_day_count": int(station["is_imputed"].sum()),
                "max_observed": float(direct["chl_a_observed"].max())
                if not direct.empty
                else np.nan,
                "max_imputed_series": float(series.max()),
                "mean_imputed_series": float(series.mean()),
                "observed_daily_diff_std": observed_diff_std,
                "imputed_daily_diff_std": imputed_diff_std,
                "diff_std_ratio_imputed_to_observed": imputed_diff_std / observed_diff_std
                if observed_diff_std and not np.isnan(observed_diff_std)
                else np.nan,
                "method_counts": "; ".join(
                    f"{method}:{count}"
                    for method, count in station["imputation_method"].value_counts().items()
                ),
            }
        )
    return pd.DataFrame.from_records(rows)


def _join_unique(values: pd.Series) -> str:
    return "; ".join(sorted({str(value) for value in values.dropna() if str(value)}))


def _join_rows(values: pd.Series) -> str:
    rows: list[str] = []
    for value in values.dropna():
        try:
            rows.append(str(int(value)))
        except (TypeError, ValueError):
            rows.append(str(value))
    return "; ".join(rows)
