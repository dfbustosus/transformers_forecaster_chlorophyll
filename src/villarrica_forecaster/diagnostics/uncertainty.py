from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.io import write_csv


def build_uncertainty_outputs(config: dict[str, Any]) -> dict[str, Path]:
    tables_dir = path_from_config(config, "tables")
    predictions = pd.read_csv(tables_dir / "forecast_predictions_long.csv")
    with_intervals = empirical_residual_intervals(
        predictions,
        allow_residual_fallback=bool(
            config["forecast"].get("allow_local_baseline_fallback", False)
        ),
    )
    coverage = interval_coverage(with_intervals)
    return {
        "forecast_predictions_with_intervals": write_csv(
            with_intervals, tables_dir / "forecast_predictions_with_intervals.csv"
        ),
        "uncertainty_coverage": write_csv(coverage, tables_dir / "uncertainty_coverage.csv"),
    }


def empirical_residual_intervals(
    predictions: pd.DataFrame, *, allow_residual_fallback: bool = False
) -> pd.DataFrame:
    """Prepare 10/50/90 intervals for evaluation without fabricating manuscript evidence.

    Cached TimesFM/Chronos quantiles are evaluated directly. Residual-derived intervals
    are only created when local-baseline fallback is explicitly enabled, so strict
    manuscript runs do not synthesize uncertainty bounds that were not produced by the
    foundation models.
    """

    if predictions.empty:
        return predictions.copy()
    frame = predictions.copy()
    existing_quantiles = all(column in frame.columns for column in ("q10", "q50", "q90"))
    if existing_quantiles and frame[["q10", "q50", "q90"]].notna().any(axis=None):
        frame["interval_method"] = "cached_foundation_model_quantiles"
        frame["interval_role"] = "evaluation"
        return frame
    if not allow_residual_fallback:
        frame["q10"] = pd.NA
        frame["q50"] = frame.get("y_pred", pd.Series(pd.NA, index=frame.index))
        frame["q90"] = pd.NA
        frame["interval_method"] = "blocked_missing_foundation_quantiles"
        frame["interval_role"] = "blocked"
        return frame
    frame["residual"] = frame["y_true"].astype(float) - frame["y_pred"].astype(float)
    frame["q10"] = pd.NA
    frame["q50"] = frame["y_pred"].astype(float)
    frame["q90"] = pd.NA
    frame["interval_method"] = "empirical_residual_interval_split_calibration_local_baseline"
    frame["interval_role"] = "evaluation"
    for _keys, group in frame.groupby(["station_id", "model", "horizon"], dropna=False):
        group = group.sort_values("target_date") if "target_date" in group else group
        split = max(1, int(len(group) * 0.5))
        calibration = group.iloc[:split]
        residuals = calibration["residual"].astype(float)
        low = residuals.quantile(0.10)
        high = residuals.quantile(0.90)
        idx = group.index
        frame.loc[calibration.index, "interval_role"] = "calibration"
        frame.loc[idx, "q10"] = frame.loc[idx, "y_pred"].astype(float) + float(low)
        frame.loc[idx, "q90"] = frame.loc[idx, "y_pred"].astype(float) + float(high)
    frame["q10"] = frame["q10"].astype(float).clip(lower=0)
    frame["q90"] = frame["q90"].astype(float).clip(lower=0)
    return frame


def interval_coverage(predictions: pd.DataFrame) -> pd.DataFrame:
    if predictions.empty:
        return _empty_coverage_frame()
    frame = predictions.copy()
    if "interval_role" in frame.columns:
        frame = frame[frame["interval_role"].eq("evaluation")].copy()
    required = ["y_true", "q10", "q90"]
    if any(column not in frame.columns for column in required):
        return _empty_coverage_frame()
    frame = frame.dropna(subset=required)
    if frame.empty:
        return _empty_coverage_frame()
    frame["covered_10_90"] = (frame["y_true"].astype(float) >= frame["q10"].astype(float)) & (
        frame["y_true"].astype(float) <= frame["q90"].astype(float)
    )
    rows = (
        frame.groupby(
            ["station_id", "station_name", "model", "horizon", "interval_method"], dropna=False
        )
        .agg(n=("covered_10_90", "size"), coverage_10_90=("covered_10_90", "mean"))
        .reset_index()
    )
    rows["nominal_coverage"] = 0.80
    rows["coverage_error"] = rows["coverage_10_90"] - rows["nominal_coverage"]
    return rows.sort_values(["station_id", "model", "horizon"])


def _empty_coverage_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "station_id",
            "station_name",
            "model",
            "horizon",
            "interval_method",
            "n",
            "coverage_10_90",
            "nominal_coverage",
            "coverage_error",
        ]
    )
