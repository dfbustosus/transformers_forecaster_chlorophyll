from __future__ import annotations

import pandas as pd

from villarrica_forecaster.diagnostics.lag import lag_diagnostics
from villarrica_forecaster.diagnostics.thresholds import (
    threshold_event_inventory,
    threshold_warning_metrics,
)
from villarrica_forecaster.diagnostics.uncertainty import (
    empirical_residual_intervals,
    interval_coverage,
)


def test_threshold_warning_metrics_counts_confusion_matrix() -> None:
    predictions = pd.DataFrame(
        [
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "model": "A",
                "horizon": 1,
                "y_true": 12,
                "y_pred": 11,
            },
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "model": "A",
                "horizon": 1,
                "y_true": 12,
                "y_pred": 1,
            },
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "model": "A",
                "horizon": 1,
                "y_true": 1,
                "y_pred": 12,
            },
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "model": "A",
                "horizon": 1,
                "y_true": 1,
                "y_pred": 1,
            },
        ]
    )
    metrics = threshold_warning_metrics(predictions, threshold=10.0).iloc[0]
    assert metrics["true_positive"] == 1
    assert metrics["false_negative"] == 1
    assert metrics["false_positive"] == 1
    assert metrics["true_negative"] == 1
    assert metrics["f1_score"] == 0.5


def test_lag_diagnostics_identifies_lag_zero_when_series_match() -> None:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    predictions = pd.DataFrame(
        {
            "station_id": "pucon",
            "station_name": "Pucón",
            "model": "A",
            "horizon": 7,
            "target_date": dates,
            "y_true": range(10),
            "y_pred": range(10),
        }
    )
    diagnostics = lag_diagnostics(predictions, horizon=7, threshold=8.0, max_lag_days=2)
    assert int(diagnostics.iloc[0]["best_lag_days"]) == 0
    assert bool(diagnostics.iloc[0]["best_correlation_occurs_at_lag0"])


def test_threshold_event_inventory_builds_contiguous_events() -> None:
    daily = pd.DataFrame(
        {
            "station_id": "pucon",
            "station_name": "Pucón",
            "date": pd.date_range("2024-01-01", periods=5, freq="D").astype(str),
            "is_direct_observation": [True] * 5,
            "chl_a_observed": [1.0, 12.0, 13.0, 1.0, 15.0],
            "chl_a_model": [1.0, 12.0, 13.0, 1.0, 15.0],
        }
    )
    events = threshold_event_inventory(daily, threshold=10.0)
    observed = events[events["source_scope"].eq("observed_direct")]
    assert len(observed) == 2
    assert set(observed["duration_days"]) == {1, 2}


def test_uncertainty_coverage_uses_evaluation_split_only() -> None:
    predictions = pd.DataFrame(
        {
            "station_id": ["pucon"] * 6,
            "station_name": ["Pucón"] * 6,
            "model": ["A"] * 6,
            "horizon": [1] * 6,
            "target_date": pd.date_range("2024-01-01", periods=6, freq="D").astype(str),
            "y_true": [1, 2, 3, 4, 5, 6],
            "y_pred": [1, 2, 3, 4, 4, 4],
        }
    )
    with_intervals = empirical_residual_intervals(predictions, allow_residual_fallback=True)
    assert set(with_intervals["interval_role"]) == {"calibration", "evaluation"}
    coverage = interval_coverage(with_intervals)
    assert int(coverage.iloc[0]["n"]) == 3


def test_uncertainty_does_not_fabricate_quantiles_when_fallback_disabled() -> None:
    predictions = pd.DataFrame(
        {
            "station_id": ["pucon"],
            "station_name": ["Pucón"],
            "model": ["TimesFM"],
            "horizon": [1],
            "y_true": [1.0],
            "y_pred": [1.1],
        }
    )
    with_intervals = empirical_residual_intervals(predictions)
    coverage = interval_coverage(with_intervals)

    assert with_intervals.loc[0, "interval_method"] == "blocked_missing_foundation_quantiles"
    assert pd.isna(with_intervals.loc[0, "q10"])
    assert coverage.empty


def test_empty_forecast_diagnostics_keep_stable_headers() -> None:
    empty_predictions = pd.DataFrame(
        columns=[
            "station_id",
            "station_name",
            "model",
            "horizon",
            "target_date",
            "y_true",
            "y_pred",
        ]
    )

    lag = lag_diagnostics(empty_predictions, horizon=7, threshold=10.0, max_lag_days=2)
    threshold = threshold_warning_metrics(empty_predictions, threshold=10.0)
    coverage = interval_coverage(empty_predictions)

    assert "best_lag_days" in lag.columns
    assert "sensitivity_pod" in threshold.columns
    assert "coverage_10_90" in coverage.columns
