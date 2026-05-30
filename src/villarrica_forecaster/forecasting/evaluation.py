from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.forecasting.foundation import (
    empty_prediction_frame,
    foundation_cache_path,
    validate_foundation_prediction_table,
    write_forecast_origin_plan,
)
from villarrica_forecaster.io import write_csv, write_json

LOCAL_BASELINE_MODELS = (
    "Persistence",
    "Rolling Mean 7d",
    "DOY Climatology",
    "Seasonal Naive",
    "SES alpha=0.3",
    "Linear Trend 30d",
)


def mean_absolute_percentage_error(y_true: pd.Series, y_pred: pd.Series) -> float:
    mask = y_true.abs() > 1e-12
    if not mask.any():
        return float("nan")
    return float(((y_true[mask] - y_pred[mask]).abs() / y_true[mask].abs()).mean() * 100.0)


def metric_summary(group: pd.DataFrame) -> pd.Series:
    y_true = group["y_true"].astype(float)
    y_pred = group["y_pred"].astype(float)
    error = y_pred - y_true
    return pd.Series(
        {
            "n": int(len(group)),
            "MAPE": mean_absolute_percentage_error(y_true, y_pred),
            "MSE": float(np.mean(error**2)),
            "RMSE": float(np.sqrt(np.mean(error**2))),
            "Bias": float(np.mean(error)),
            "MedianAbsoluteError": float(np.median(np.abs(error))),
            "MAE": float(np.mean(np.abs(error))),
        }
    )


def build_forecast_outputs(config: dict[str, Any]) -> dict[str, Path]:
    processed_dir = path_from_config(config, "processed_data")
    tables_dir = path_from_config(config, "tables")
    reports_dir = path_from_config(config, "reports")
    daily = pd.read_csv(processed_dir / "daily_chl_a.csv", parse_dates=["date"])
    origin_plan_paths = write_forecast_origin_plan(config)
    cached_path = foundation_cache_path(config)
    allow_baseline_fallback = bool(config["forecast"].get("allow_local_baseline_fallback", False))
    blockers: list[dict[str, str]] = []
    if cached_path.exists():
        predictions = pd.read_csv(cached_path, parse_dates=["origin_date", "target_date"])
        validation_errors = validate_foundation_prediction_table(predictions, daily, config)
        if validation_errors:
            blockers.append(
                {
                    "blocker": "invalid_foundation_prediction_cache",
                    "detail": " | ".join(validation_errors),
                    "required_action": "Regenerate data/processed/foundation_model_predictions.csv with one row per station, origin date, model, and horizon 1-30.",
                }
            )
            predictions = empty_prediction_frame()
            prediction_source = "invalid_foundation_model_cache_blocked"
        else:
            prediction_source = "cached_foundation_model_predictions"
    elif allow_baseline_fallback:
        predictions = rolling_origin_baseline_predictions(daily, config)
        prediction_source = "local_baseline_models_explicitly_enabled"
    else:
        predictions = empty_prediction_frame()
        prediction_source = "blocked_missing_foundation_model_predictions"
        blockers.append(
            {
                "blocker": "missing_foundation_model_predictions",
                "detail": f"No cache found at {cached_path} and local baseline fallback is disabled.",
                "required_action": "Run TimesFM/Chronos rolling-origin inference with `poetry run villarrica-run-foundation --config configs/project.toml`, or provide a validated cache at data/processed/foundation_model_predictions.csv.",
            }
        )

    metrics = metrics_by_horizon(predictions)
    observed_metrics = observed_only_metrics_by_horizon(predictions)
    stratified_metrics = gap_stratified_metrics_by_horizon(predictions)
    paths = {
        **origin_plan_paths,
        "forecast_predictions_long": write_csv(
            _date_columns_to_string(predictions), tables_dir / "forecast_predictions_long.csv"
        ),
        "forecast_metrics_by_horizon": write_csv(
            metrics, tables_dir / "forecast_metrics_by_horizon.csv"
        ),
        "observed_only_forecast_metrics": write_csv(
            observed_metrics, tables_dir / "observed_only_forecast_metrics.csv"
        ),
        "gap_stratified_forecast_metrics": write_csv(
            stratified_metrics, tables_dir / "gap_stratified_forecast_metrics.csv"
        ),
        "forecast_model_blockers": write_csv(
            pd.DataFrame.from_records(
                blockers,
                columns=["blocker", "detail", "required_action"],
            ),
            reports_dir / "forecast_model_blockers.csv",
        ),
    }
    paths["forecast_evaluation_manifest"] = write_json(
        {
            "prediction_source": prediction_source,
            "cached_prediction_path_checked": "data/processed/foundation_model_predictions.csv",
            "allow_local_baseline_fallback": allow_baseline_fallback,
            "local_baseline_models": list(LOCAL_BASELINE_MODELS) if allow_baseline_fallback else [],
            "horizons": config["forecast"]["horizons"],
            "prediction_length_days": config["forecast"].get("prediction_length_days", 30),
            "context_length_days": config["forecast"].get("context_length_days", 1024),
            "test_fraction": config["forecast"]["test_fraction"],
            "additional_reviewer_metrics": [
                "outputs/tables/observed_only_forecast_metrics.csv",
                "outputs/tables/gap_stratified_forecast_metrics.csv",
            ],
            "scientific_limitation": (
                "Manuscript Figure 4 requires actual TimesFM/Chronos rolling-origin predictions. "
                "Local baselines are not used unless allow_local_baseline_fallback is explicitly true."
            ),
            "blockers": blockers,
        },
        processed_dir / "forecast_evaluation_manifest.json",
    )
    return paths


def rolling_origin_baseline_predictions(
    daily: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    horizons = [int(h) for h in config["forecast"]["horizons"]]
    test_fraction = float(config["forecast"]["test_fraction"])
    min_train = int(config["forecast"]["minimum_training_days"])
    records: list[dict[str, Any]] = []
    for (station_id, station_name), station in daily.groupby(["station_id", "station_name"]):
        station = station.sort_values("date").set_index("date")
        series = station["chl_a_model"].astype(float)
        if series.size < min_train + max(horizons):
            continue
        test_start_position = max(min_train, int(np.floor(series.size * (1.0 - test_fraction))))
        max_horizon = max(horizons)
        for origin_pos in range(test_start_position - 1, series.size - max_horizon):
            origin_date = series.index[origin_pos]
            context = series.iloc[: origin_pos + 1]
            for horizon in horizons:
                target_pos = origin_pos + horizon
                if target_pos >= series.size:
                    continue
                target_date = series.index[target_pos]
                y_true = float(series.iloc[target_pos])
                target_row = station.loc[target_date]
                for model in LOCAL_BASELINE_MODELS:
                    y_pred = _predict_model(model, context, target_date, horizon)
                    records.append(
                        {
                            "station_id": station_id,
                            "station_name": station_name,
                            "model": model,
                            "origin_date": origin_date,
                            "target_date": target_date,
                            "horizon": horizon,
                            "y_true": y_true,
                            "y_true_observed": _nullable_float(target_row.get("chl_a_observed")),
                            "y_pred": max(float(y_pred), 0.0),
                            "target_is_direct_observation": bool(
                                target_row.get("is_direct_observation", False)
                            ),
                            "target_is_imputed": bool(target_row.get("is_imputed", False)),
                            "target_imputation_method": str(
                                target_row.get("imputation_method", "unknown")
                            ),
                            "target_is_iqr_outlier": bool(target_row.get("is_iqr_outlier", False)),
                            "target_is_outlier_removed": bool(
                                target_row.get("is_outlier_removed", False)
                            ),
                            "prediction_source": "local_baseline",
                        }
                    )
    return pd.DataFrame.from_records(records)


def _predict_model(
    model: str, context: pd.Series, target_date: pd.Timestamp, horizon: int
) -> float:
    context = context.dropna().astype(float)
    if context.empty:
        return 0.0
    if model == "Persistence":
        return float(context.iloc[-1])
    if model == "Rolling Mean 7d":
        return float(context.tail(7).mean())
    if model == "DOY Climatology":
        return _doy_or_month_climatology(context, target_date)
    if model == "Seasonal Naive":
        prior_date = target_date - pd.Timedelta(days=365)
        if prior_date in context.index:
            return float(context.loc[prior_date])
        return _doy_or_month_climatology(context, target_date)
    if model == "SES alpha=0.3":
        return _simple_exponential_smoothing_level(context, alpha=0.3)
    if model == "Linear Trend 30d":
        window = context.tail(30)
        if window.size < 2:
            return float(context.iloc[-1])
        x = np.arange(window.size, dtype=float)
        slope, intercept = np.polyfit(x, window.to_numpy(dtype=float), deg=1)
        return float(intercept + slope * (window.size - 1 + horizon))
    raise ValueError(f"Unknown local baseline model: {model}")


def _doy_or_month_climatology(context: pd.Series, target_date: pd.Timestamp) -> float:
    same_doy = context[context.index.dayofyear == target_date.dayofyear]
    if not same_doy.empty:
        return float(same_doy.mean())
    same_month = context[context.index.month == target_date.month]
    if not same_month.empty:
        return float(same_month.mean())
    return float(context.median())


def _simple_exponential_smoothing_level(context: pd.Series, alpha: float) -> float:
    level = float(context.iloc[0])
    for value in context.iloc[1:]:
        level = alpha * float(value) + (1 - alpha) * level
    return level


def metrics_by_horizon(predictions: pd.DataFrame) -> pd.DataFrame:
    if predictions.empty:
        return pd.DataFrame(
            columns=[
                "station_id",
                "station_name",
                "model",
                "horizon",
                "n",
                "MAPE",
                "MSE",
                "RMSE",
                "Bias",
                "MedianAbsoluteError",
                "MAE",
            ]
        )
    metrics = (
        predictions.groupby(["station_id", "station_name", "model", "horizon"], dropna=False)[
            ["y_true", "y_pred"]
        ]
        .apply(metric_summary)
        .reset_index()
    )
    return metrics.sort_values(["station_id", "model", "horizon"]).reset_index(drop=True)


def observed_only_metrics_by_horizon(predictions: pd.DataFrame) -> pd.DataFrame:
    if predictions.empty or "y_true_observed" not in predictions.columns:
        return _empty_observed_only_metrics_frame()
    observed = predictions[
        predictions["target_is_direct_observation"].astype(bool)
        & predictions["y_true_observed"].notna()
        & ~predictions.get("target_is_outlier_removed", False).astype(bool)
    ].copy()
    if observed.empty:
        return _empty_observed_only_metrics_frame()
    observed["y_true"] = observed["y_true_observed"].astype(float)
    metrics = metrics_by_horizon(observed)
    metrics["evaluation_subset"] = "observed_targets_only"
    return metrics


def gap_stratified_metrics_by_horizon(predictions: pd.DataFrame) -> pd.DataFrame:
    if predictions.empty or "target_imputation_method" not in predictions.columns:
        return _empty_gap_stratified_metrics_frame()
    frame = predictions.copy()
    frame["target_data_class"] = frame["target_is_direct_observation"].map(
        {True: "direct_observation", False: "gap_filled_or_missing_observation"}
    )
    rows = (
        frame.groupby(
            ["station_id", "station_name", "model", "horizon", "target_data_class"],
            dropna=False,
        )[["y_true", "y_pred"]]
        .apply(metric_summary)
        .reset_index()
    )
    return rows.sort_values(["station_id", "model", "horizon", "target_data_class"])


def _empty_observed_only_metrics_frame() -> pd.DataFrame:
    frame = metrics_by_horizon(pd.DataFrame())
    frame["evaluation_subset"] = pd.Series(dtype=str)
    return frame


def _empty_gap_stratified_metrics_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "station_id",
            "station_name",
            "model",
            "horizon",
            "target_data_class",
            "n",
            "MAPE",
            "MSE",
            "RMSE",
            "Bias",
            "MedianAbsoluteError",
            "MAE",
        ]
    )


def _nullable_float(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_columns_to_string(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in ("origin_date", "target_date"):
        if column in output.columns:
            output[column] = pd.to_datetime(output[column]).dt.date.astype(str)
    return output
