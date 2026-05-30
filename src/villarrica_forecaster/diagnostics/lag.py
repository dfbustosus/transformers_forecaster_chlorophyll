from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.io import write_csv


def build_lag_outputs(config: dict[str, Any]) -> dict[str, Path]:
    tables_dir = path_from_config(config, "tables")
    predictions = pd.read_csv(
        tables_dir / "forecast_predictions_long.csv", parse_dates=["target_date"]
    )
    threshold = float(config["thresholds"]["chlorophyll_warning_ug_l"])
    diagnostics = lag_diagnostics(predictions, horizon=7, threshold=threshold, max_lag_days=14)
    correlations = lag_correlation_table(predictions, horizon=7, max_lag_days=14)
    return {
        "lag_diagnostics_d7": write_csv(diagnostics, tables_dir / "lag_diagnostics_d7.csv"),
        "lag_correlation_by_model_d7": write_csv(
            correlations, tables_dir / "lag_correlation_by_model_d7.csv"
        ),
    }


def lag_correlation_table(
    predictions: pd.DataFrame, horizon: int, max_lag_days: int
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    subset = predictions[predictions["horizon"].astype(int).eq(horizon)].copy()
    if subset.empty:
        return _empty_lag_correlation_frame()
    subset["target_date"] = pd.to_datetime(subset["target_date"])
    for keys, group in subset.groupby(["station_id", "station_name", "model"], dropna=False):
        station_id, station_name, model = keys
        clean = group[["target_date", "y_true", "y_pred"]].dropna().copy()
        clean["y_true"] = clean["y_true"].astype(float)
        clean["y_pred"] = clean["y_pred"].astype(float)
        for lag in range(-max_lag_days, max_lag_days + 1):
            shifted = clean[["target_date", "y_pred"]].copy()
            shifted["target_date"] = shifted["target_date"] + pd.to_timedelta(lag, unit="D")
            merged = clean[["target_date", "y_true"]].merge(shifted, on="target_date", how="inner")
            corr = _pearson(merged["y_true"], merged["y_pred"]) if len(merged) >= 3 else np.nan
            rows.append(
                {
                    "station_id": station_id,
                    "station_name": station_name,
                    "model": model,
                    "horizon": horizon,
                    "lag_days": lag,
                    "pearson_correlation": corr,
                    "n_aligned": int(len(merged)),
                }
            )
    return pd.DataFrame.from_records(rows)


def lag_diagnostics(
    predictions: pd.DataFrame, horizon: int, threshold: float, max_lag_days: int
) -> pd.DataFrame:
    corr_table = lag_correlation_table(predictions, horizon=horizon, max_lag_days=max_lag_days)
    if corr_table.empty:
        return _empty_lag_diagnostic_frame()
    rows: list[dict[str, Any]] = []
    subset = predictions[predictions["horizon"].astype(int).eq(horizon)].copy()
    subset["target_date"] = pd.to_datetime(subset["target_date"])
    for keys, corr_group in corr_table.groupby(
        ["station_id", "station_name", "model"], dropna=False
    ):
        station_id, station_name, model = keys
        valid_corr = corr_group.dropna(subset=["pearson_correlation"])
        if valid_corr.empty:
            best_lag = np.nan
            best_corr = np.nan
            corr_lag0 = np.nan
        else:
            max_corr = float(valid_corr["pearson_correlation"].max())
            ranked = (
                valid_corr[valid_corr["pearson_correlation"] >= max_corr - 1e-12]
                .assign(abs_lag=valid_corr["lag_days"].abs())
                .sort_values(["abs_lag", "lag_days"], ascending=[True, True])
            )
            best = ranked.iloc[0]
            best_lag = int(best["lag_days"])
            best_corr = float(best["pearson_correlation"])
            lag0 = valid_corr[valid_corr["lag_days"].eq(0)]
            corr_lag0 = float(lag0["pearson_correlation"].iloc[0]) if not lag0.empty else np.nan
        group = subset[
            subset["station_id"].eq(station_id)
            & subset["station_name"].eq(station_name)
            & subset["model"].eq(model)
        ].sort_values("target_date")
        peak_error = _peak_date_error_days(group)
        onset_error = _onset_date_error_days(group, threshold=threshold)
        rows.append(
            {
                "station_id": station_id,
                "station_name": station_name,
                "model": model,
                "horizon": horizon,
                "best_lag_days": best_lag,
                "best_lag_correlation": best_corr,
                "lag0_correlation": corr_lag0,
                "best_correlation_occurs_at_lag0": bool(best_lag == 0)
                if not pd.isna(best_lag)
                else False,
                "peak_date_error_days": peak_error,
                "event_onset_error_days_at_threshold": onset_error,
                "threshold_ug_l": threshold,
            }
        )
    return pd.DataFrame.from_records(rows).sort_values(["station_id", "model"])


def _pearson(a: pd.Series, b: pd.Series) -> float:
    if a.nunique(dropna=True) < 2 or b.nunique(dropna=True) < 2:
        return float("nan")
    return float(a.corr(b))


def _peak_date_error_days(group: pd.DataFrame) -> float:
    if group.empty:
        return float("nan")
    true_peak_date = group.loc[group["y_true"].astype(float).idxmax(), "target_date"]
    pred_peak_date = group.loc[group["y_pred"].astype(float).idxmax(), "target_date"]
    return float((pred_peak_date - true_peak_date).days)


def _onset_date_error_days(group: pd.DataFrame, threshold: float) -> float:
    observed = group[group["y_true"].astype(float) >= threshold]
    predicted = group[group["y_pred"].astype(float) >= threshold]
    if observed.empty or predicted.empty:
        return float("nan")
    return float((predicted["target_date"].iloc[0] - observed["target_date"].iloc[0]).days)


def _empty_lag_correlation_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "station_id",
            "station_name",
            "model",
            "horizon",
            "lag_days",
            "pearson_correlation",
            "n_aligned",
        ]
    )


def _empty_lag_diagnostic_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "station_id",
            "station_name",
            "model",
            "horizon",
            "best_lag_days",
            "best_lag_correlation",
            "lag0_correlation",
            "best_correlation_occurs_at_lag0",
            "peak_date_error_days",
            "event_onset_error_days_at_threshold",
            "threshold_ug_l",
        ]
    )
