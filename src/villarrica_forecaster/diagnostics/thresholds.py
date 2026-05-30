from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.io import write_csv


def build_threshold_outputs(config: dict[str, Any]) -> dict[str, Path]:
    tables_dir = path_from_config(config, "tables")
    processed_dir = path_from_config(config, "processed_data")
    predictions = pd.read_csv(tables_dir / "forecast_predictions_long.csv")
    daily = pd.read_csv(processed_dir / "daily_chl_a.csv")
    threshold = float(config["thresholds"]["chlorophyll_warning_ug_l"])
    direct_mask = predictions.get(
        "target_is_direct_observation", pd.Series(False, index=predictions.index)
    )
    observed_predictions = predictions[
        direct_mask.astype(bool)
        & predictions.get("y_true_observed", pd.Series(index=predictions.index)).notna()
    ].copy()
    if not observed_predictions.empty:
        observed_predictions["y_true"] = observed_predictions["y_true_observed"].astype(float)
    metrics = threshold_warning_metrics(observed_predictions, threshold=threshold)
    metrics["truth_scope"] = "observed_targets_only"
    all_target_metrics = threshold_warning_metrics(predictions, threshold=threshold)
    all_target_metrics["truth_scope"] = "processed_all_targets"
    event_summary = threshold_event_summary(daily, threshold=threshold)
    event_inventory = threshold_event_inventory(daily, threshold=threshold)
    return {
        "threshold_warning_metrics": write_csv(
            metrics, tables_dir / "threshold_warning_metrics.csv"
        ),
        "threshold_warning_metrics_all_targets": write_csv(
            all_target_metrics, tables_dir / "threshold_warning_metrics_all_targets.csv"
        ),
        "threshold_event_inventory": write_csv(
            event_inventory, tables_dir / "threshold_event_inventory.csv"
        ),
        "threshold_event_summary": write_csv(
            event_summary, tables_dir / "threshold_event_summary.csv"
        ),
    }


def threshold_warning_metrics(predictions: pd.DataFrame, threshold: float) -> pd.DataFrame:
    if predictions.empty:
        return _empty_threshold_warning_metrics_frame()
    rows: list[dict[str, Any]] = []
    groups = predictions.groupby(["station_id", "station_name", "model", "horizon"], dropna=False)
    for keys, group in groups:
        station_id, station_name, model, horizon = keys
        observed_event = group["y_true"].astype(float) >= threshold
        predicted_event = group["y_pred"].astype(float) >= threshold
        tp = int((observed_event & predicted_event).sum())
        fp = int((~observed_event & predicted_event).sum())
        tn = int((~observed_event & ~predicted_event).sum())
        fn = int((observed_event & ~predicted_event).sum())
        rows.append(
            {
                "station_id": station_id,
                "station_name": station_name,
                "model": model,
                "horizon": int(horizon),
                "threshold_ug_l": threshold,
                "n": int(len(group)),
                "true_positive": tp,
                "false_positive": fp,
                "true_negative": tn,
                "false_negative": fn,
                "sensitivity_pod": _safe_divide(tp, tp + fn),
                "specificity_tnr": _safe_divide(tn, tn + fp),
                "precision_ppv": _safe_divide(tp, tp + fp),
                "f1_score": _safe_divide(2 * tp, 2 * tp + fp + fn),
                "false_alarm_ratio": _safe_divide(fp, tp + fp),
                "missed_event_rate": _safe_divide(fn, tp + fn),
                "overall_accuracy": _safe_divide(tp + tn, tp + fp + tn + fn),
                "observed_event_count": int(observed_event.sum()),
                "predicted_event_count": int(predicted_event.sum()),
            }
        )
    return pd.DataFrame.from_records(rows).sort_values(["station_id", "model", "horizon"])


def _empty_threshold_warning_metrics_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "station_id",
            "station_name",
            "model",
            "horizon",
            "threshold_ug_l",
            "n",
            "true_positive",
            "false_positive",
            "true_negative",
            "false_negative",
            "sensitivity_pod",
            "specificity_tnr",
            "precision_ppv",
            "f1_score",
            "false_alarm_ratio",
            "missed_event_rate",
            "overall_accuracy",
            "observed_event_count",
            "predicted_event_count",
        ]
    )


def _safe_divide(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else float("nan")


def threshold_event_summary(daily: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in daily.groupby(["station_id", "station_name"], dropna=False):
        station_id, station_name = keys
        observed = group[group["is_direct_observation"].astype(bool)]
        rows.append(
            {
                "station_id": station_id,
                "station_name": station_name,
                "threshold_ug_l": threshold,
                "modeled_daily_count": int(len(group)),
                "direct_observation_count": int(len(observed)),
                "observed_exceedance_count": int(
                    (observed["chl_a_observed"].astype(float) >= threshold).sum()
                ),
                "processed_model_exceedance_count": int(
                    (group["chl_a_model"].astype(float) >= threshold).sum()
                ),
                "max_observed_chl_a": float(observed["chl_a_observed"].astype(float).max()),
                "max_model_chl_a": float(group["chl_a_model"].astype(float).max()),
            }
        )
    return pd.DataFrame.from_records(rows)


def threshold_event_inventory(daily: pd.DataFrame, threshold: float) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for keys, group in daily.groupby(["station_id", "station_name"], dropna=False):
        station_id, station_name = keys
        station = group.copy()
        station["date"] = pd.to_datetime(station["date"])
        series_specs = [
            (
                "observed_direct",
                station[station["is_direct_observation"].astype(bool)][
                    ["date", "chl_a_observed"]
                ].rename(columns={"chl_a_observed": "chl_a"}),
            ),
            (
                "processed_model_series",
                station[["date", "chl_a_model"]].rename(columns={"chl_a_model": "chl_a"}),
            ),
        ]
        for source_scope, values in series_specs:
            values = values.dropna(subset=["chl_a"]).sort_values("date")
            for event_id, event in enumerate(
                _contiguous_events(values, threshold=threshold), start=1
            ):
                peak_idx = event["chl_a"].astype(float).idxmax()
                records.append(
                    {
                        "station_id": station_id,
                        "station_name": station_name,
                        "source_scope": source_scope,
                        "event_id": f"{station_id}_{source_scope}_{event_id:03d}",
                        "threshold_ug_l": threshold,
                        "start_date": event["date"].min().date().isoformat(),
                        "end_date": event["date"].max().date().isoformat(),
                        "duration_days": int((event["date"].max() - event["date"].min()).days + 1),
                        "observation_count": int(len(event)),
                        "peak_date": event.loc[peak_idx, "date"].date().isoformat(),
                        "peak_chl_a": float(event.loc[peak_idx, "chl_a"]),
                    }
                )
    columns = [
        "station_id",
        "station_name",
        "source_scope",
        "event_id",
        "threshold_ug_l",
        "start_date",
        "end_date",
        "duration_days",
        "observation_count",
        "peak_date",
        "peak_chl_a",
    ]
    return pd.DataFrame.from_records(records, columns=columns)


def _contiguous_events(values: pd.DataFrame, threshold: float) -> list[pd.DataFrame]:
    exceedances = values[values["chl_a"].astype(float) >= threshold].copy()
    if exceedances.empty:
        return []
    groups = (exceedances["date"].diff().dt.days.fillna(1).ne(1)).cumsum()
    return [event for _, event in exceedances.groupby(groups)]


def event_lead_time_summary(predictions: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Summarize lead horizons that first predicted each observed exceedance date."""

    if predictions.empty:
        return pd.DataFrame()
    events = predictions[predictions["y_true"].astype(float) >= threshold]
    if events.empty:
        return pd.DataFrame(
            columns=["station_id", "model", "target_date", "first_detected_horizon", "detected"]
        )
    events = events.copy()
    events["detected"] = events["y_pred"].astype(float) >= threshold
    first = (
        events[events["detected"]]
        .groupby(["station_id", "model", "target_date"], dropna=False)["horizon"]
        .min()
        .reset_index(name="first_detected_horizon")
    )
    all_events = events[["station_id", "model", "target_date"]].drop_duplicates()
    output = all_events.merge(first, how="left", on=["station_id", "model", "target_date"])
    output["detected"] = ~output["first_detected_horizon"].isna()
    output["first_detected_horizon"] = output["first_detected_horizon"].replace({np.nan: ""})
    return output
