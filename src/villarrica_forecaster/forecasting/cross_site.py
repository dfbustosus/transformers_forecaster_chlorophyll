from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.forecasting.evaluation import metric_summary
from villarrica_forecaster.forecasting.foundation import load_foundation_daily_target
from villarrica_forecaster.io import write_csv


def build_cross_site_outputs(config: dict[str, Any]) -> dict[str, Path]:
    tables_dir = path_from_config(config, "tables")
    daily = load_foundation_daily_target(config)
    results = cross_site_dayofyear_transfer(
        daily, test_fraction=float(config["forecast"]["test_fraction"])
    )
    return {"cross_site_validation": write_csv(results, tables_dir / "cross_site_validation.csv")}


def cross_site_dayofyear_transfer(daily: pd.DataFrame, test_fraction: float) -> pd.DataFrame:
    """Evaluate station-to-station transfer with a transparent DOY climatology baseline.

    This is not a replacement for foundation-model cross-site validation. It provides a
    reproducible lower-bound transfer artifact from the local data available now.
    """

    stations = {
        station_id: frame.sort_values("date").set_index("date")["chl_a_model"].astype(float)
        for station_id, frame in daily.groupby("station_id")
    }
    records: list[dict[str, Any]] = []
    for train_site, train_series in stations.items():
        train_series = train_series.dropna()
        if train_series.empty:
            continue
        for test_site, test_series in stations.items():
            if train_site == test_site:
                continue
            test_series = test_series.dropna()
            if test_series.empty:
                continue
            start = int(np.floor(test_series.size * (1.0 - test_fraction)))
            for target_date, y_true in test_series.iloc[start:].items():
                y_pred = _source_climatology_prediction(train_series, target_date)
                records.append(
                    {
                        "train_site": train_site,
                        "test_site": test_site,
                        "model": "Transferred DOY climatology",
                        "target_date": target_date,
                        "horizon": 1,
                        "y_true": float(y_true),
                        "y_pred": max(float(y_pred), 0.0),
                    }
                )
    predictions = pd.DataFrame.from_records(records)
    if predictions.empty:
        return pd.DataFrame()
    metrics = (
        predictions.groupby(["train_site", "test_site", "model", "horizon"], dropna=False)[
            ["y_true", "y_pred"]
        ]
        .apply(metric_summary)
        .reset_index()
    )
    metrics["validation_scope"] = "local_baseline_transfer_not_foundation_model"
    return metrics


def _source_climatology_prediction(source: pd.Series, target_date: pd.Timestamp) -> float:
    same_doy = source[source.index.dayofyear == target_date.dayofyear]
    if not same_doy.empty:
        return float(same_doy.mean())
    same_month = source[source.index.month == target_date.month]
    if not same_month.empty:
        return float(same_month.mean())
    return float(source.median())
