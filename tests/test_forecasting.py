from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from villarrica_forecaster.figures.forecast_figures import metric_figure, trajectory_figure
from villarrica_forecaster.forecasting.cross_site import cross_site_dayofyear_transfer
from villarrica_forecaster.forecasting.evaluation import (
    build_forecast_outputs,
    mean_absolute_percentage_error,
    metrics_by_horizon,
    observed_only_metrics_by_horizon,
)
from villarrica_forecaster.forecasting.foundation import (
    PREDICTION_COLUMNS,
    apply_realistic_imputation_reference,
    build_forecast_origin_plan,
    validate_foundation_prediction_table,
)


def test_mean_absolute_percentage_error() -> None:
    y_true = pd.Series([1.0, 2.0, 4.0])
    y_pred = pd.Series([1.0, 1.0, 5.0])
    assert round(mean_absolute_percentage_error(y_true, y_pred), 6) == round(
        (0 + 0.5 + 0.25) / 3 * 100, 6
    )


def test_metrics_by_horizon_basic() -> None:
    predictions = pd.DataFrame(
        [
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "model": "A",
                "horizon": 1,
                "y_true": 1.0,
                "y_pred": 2.0,
            },
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "model": "A",
                "horizon": 1,
                "y_true": 3.0,
                "y_pred": 2.0,
            },
        ]
    )
    metrics = metrics_by_horizon(predictions)
    row = metrics.iloc[0]
    assert row["n"] == 2
    assert row["MAE"] == 1.0
    assert row["Bias"] == 0.0


def test_observed_only_metrics_use_raw_observed_truth() -> None:
    predictions = pd.DataFrame(
        [
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "model": "A",
                "horizon": 1,
                "y_true": 99.0,
                "y_true_observed": 10.0,
                "y_pred": 8.0,
                "target_is_direct_observation": True,
                "target_is_outlier_removed": False,
            }
        ]
    )
    metrics = observed_only_metrics_by_horizon(predictions)
    assert metrics.iloc[0]["MAE"] == 2.0
    assert metrics.iloc[0]["evaluation_subset"] == "observed_targets_only"


def test_cross_site_dayofyear_transfer_outputs_both_directions() -> None:
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    daily = pd.DataFrame(
        {
            "station_id": ["pucon"] * 40 + ["la_poza"] * 40,
            "date": list(dates) + list(dates),
            "chl_a_model": list(range(40)) + list(range(1, 41)),
        }
    )
    metrics = cross_site_dayofyear_transfer(daily, test_fraction=0.25)
    pairs = set(zip(metrics["train_site"], metrics["test_site"], strict=True))
    assert pairs == {("pucon", "la_poza"), ("la_poza", "pucon")}
    assert set(metrics["validation_scope"]) == {"local_baseline_transfer_not_foundation_model"}


def test_foundation_origin_plan_uses_daily_origins_and_prediction_length(tmp_path: Path) -> None:
    config = _foundation_test_config(tmp_path, prediction_length=30, periods=100)
    daily = _foundation_daily_fixture(periods=100)
    plan = build_forecast_origin_plan(daily, config)

    assert not plan.empty
    assert set(plan["prediction_length_days"]) == {30}
    origin_dates = pd.to_datetime(plan["origin_date"])
    assert origin_dates.diff().dropna().dt.days.eq(1).all()
    assert (
        (pd.to_datetime(plan["first_target_date"]) - pd.to_datetime(plan["origin_date"]))
        .dt.days.eq(1)
        .all()
    )
    assert (
        (pd.to_datetime(plan["last_target_date"]) - pd.to_datetime(plan["origin_date"]))
        .dt.days.eq(30)
        .all()
    )


def test_validate_foundation_prediction_cache_accepts_complete_grid(tmp_path: Path) -> None:
    config = _foundation_test_config(tmp_path)
    daily = _foundation_daily_fixture()
    predictions = _complete_foundation_predictions(daily, config)

    errors = validate_foundation_prediction_table(predictions, daily, config)

    assert errors == []


def test_validate_foundation_prediction_cache_rejects_baseline_or_missing_model(
    tmp_path: Path,
) -> None:
    config = _foundation_test_config(tmp_path)
    daily = _foundation_daily_fixture()
    predictions = _complete_foundation_predictions(daily, config)
    predictions = predictions[predictions["model"].eq("TimesFM")].copy()
    predictions["prediction_source"] = "local_baseline"

    errors = validate_foundation_prediction_table(predictions, daily, config)

    assert any("local-baseline" in error for error in errors)
    assert any("Expected exactly enabled foundation models" in error for error in errors)


def test_validate_foundation_prediction_cache_requires_full_origin_model_horizon_grid(
    tmp_path: Path,
) -> None:
    config = _foundation_test_config(tmp_path)
    daily = _foundation_daily_fixture()
    predictions = _complete_foundation_predictions(daily, config).iloc[:-1].copy()

    errors = validate_foundation_prediction_table(predictions, daily, config)

    assert any("station/origin/model/horizon" in error for error in errors)


def test_validate_foundation_prediction_cache_rejects_nonfinite_context(
    tmp_path: Path,
) -> None:
    config = _foundation_test_config(tmp_path)
    daily = _foundation_daily_fixture()
    daily.loc[2, "chl_a_model"] = None
    predictions = _complete_foundation_predictions(daily, config)

    errors = validate_foundation_prediction_table(predictions, daily, config)

    assert any("Non-finite chl_a_model values" in error for error in errors)


def test_validate_foundation_prediction_cache_rejects_stale_run_metadata(
    tmp_path: Path,
) -> None:
    config = _foundation_test_config(tmp_path)
    daily = _foundation_daily_fixture()
    processed_dir = Path(config["resolved_paths"]["processed_data"])
    processed_dir.mkdir(parents=True)
    daily.to_csv(processed_dir / "daily_chl_a.csv", index=False)
    (processed_dir / "test_run_metadata.json").write_text(
        json.dumps({"run_id": "test_run", "input_data_hash": "stale"}), encoding="utf-8"
    )
    predictions = _complete_foundation_predictions(daily, config)

    errors = validate_foundation_prediction_table(predictions, daily, config)

    assert any("Foundation prediction cache is stale" in error for error in errors)


def test_realistic_reference_overrides_2024_foundation_target_values() -> None:
    daily = _foundation_daily_fixture(periods=5)
    reference = pd.DataFrame(
        {
            "station_id": ["pucon"],
            "station_name": ["Pucón"],
            "date": ["2024-01-03"],
            "chl_a_observed": [None],
            "is_observed": [False],
            "source_observation_count": [0],
            "source_files": [""],
            "source_rows": [""],
            "chl_a_imputed": [7.5],
            "imputation_method": ["historical_seasonal_harmonic_analog_residual"],
            "is_imputed": [True],
            "is_short_gap_imputed": [False],
            "is_long_gap_imputed": [True],
        }
    )

    updated = apply_realistic_imputation_reference(daily, reference)
    row = updated[pd.to_datetime(updated["date"]).eq(pd.Timestamp("2024-01-03"))].iloc[0]

    assert row["chl_a_model"] == 7.5
    assert bool(row["is_imputed"])
    assert not bool(row["is_direct_observation"])
    assert row["imputation_method"] == "historical_seasonal_harmonic_analog_residual"
    assert row["foundation_target_source"] == "realistic_imputed_chl_a_2024"


def test_build_forecast_outputs_blocks_missing_foundation_cache(tmp_path: Path) -> None:
    config = _foundation_test_config(tmp_path)
    daily = _foundation_daily_fixture()
    processed_dir = Path(config["resolved_paths"]["processed_data"])
    processed_dir.mkdir(parents=True)
    daily.to_csv(processed_dir / "daily_chl_a.csv", index=False)

    outputs = build_forecast_outputs(config)
    blockers = pd.read_csv(outputs["forecast_model_blockers"])
    metrics = pd.read_csv(outputs["forecast_metrics_by_horizon"])
    predictions = pd.read_csv(outputs["forecast_predictions_long"])
    manifest = json.loads((processed_dir / "forecast_evaluation_manifest.json").read_text())

    assert blockers.loc[0, "blocker"] == "missing_foundation_model_predictions"
    assert metrics.empty
    assert predictions.empty
    assert manifest["prediction_source"] == "blocked_missing_foundation_model_predictions"
    assert manifest["allow_local_baseline_fallback"] is False


def test_metric_figure_blocks_and_removes_stale_exports_for_baseline_metrics(
    tmp_path: Path,
) -> None:
    config = _foundation_test_config(tmp_path)
    tables_dir = Path(config["resolved_paths"]["tables"])
    figures_dir = Path(config["resolved_paths"]["figures"])
    tables_dir.mkdir(parents=True)
    figures_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "model": "Persistence",
                "horizon": 1,
                "n": 1,
                "MAPE": 1.0,
                "MSE": 1.0,
                "RMSE": 1.0,
                "Bias": 0.0,
                "MedianAbsoluteError": 1.0,
                "MAE": 1.0,
            }
        ]
    ).to_csv(tables_dir / "forecast_metrics_by_horizon.csv", index=False)
    stem = "figure_04_forecast_metrics_pucon"
    for suffix in (".png", ".svg", ".metadata.json"):
        (figures_dir / f"{stem}{suffix}").write_text("stale baseline artifact")

    outputs = metric_figure(config, station_id="pucon", figure_number="04")
    status = pd.read_csv(outputs["status"])
    source = pd.read_csv(outputs["source"])

    assert status.loc[0, "status"] == "blocked_missing_foundation_predictions"
    assert source.empty
    assert not any((figures_dir / f"{stem}{suffix}").exists() for suffix in (".png", ".svg"))


def test_trajectory_figure_blocks_and_removes_stale_exports_for_baseline_predictions(
    tmp_path: Path,
) -> None:
    config = _foundation_test_config(tmp_path)
    tables_dir = Path(config["resolved_paths"]["tables"])
    figures_dir = Path(config["resolved_paths"]["figures"])
    processed_dir = Path(config["resolved_paths"]["processed_data"])
    tables_dir.mkdir(parents=True)
    figures_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "model": "Persistence",
                "horizon": 1,
                "target_date": "2024-01-02",
                "y_true": 1.0,
                "y_pred": 1.0,
            }
        ]
    ).to_csv(tables_dir / "forecast_predictions_long.csv", index=False)
    _foundation_daily_fixture().to_csv(processed_dir / "daily_chl_a.csv", index=False)
    stem = "figure_07_forecasts_pucon"
    for suffix in (".png", ".svg", ".metadata.json"):
        (figures_dir / f"{stem}{suffix}").write_text("stale baseline artifact")

    outputs = trajectory_figure(config, station_id="pucon", figure_number="07")
    status = pd.read_csv(outputs["status"])
    source = pd.read_csv(outputs["source"])

    assert status.loc[0, "status"] == "blocked_missing_foundation_predictions"
    assert source.empty
    assert not any((figures_dir / f"{stem}{suffix}").exists() for suffix in (".png", ".svg"))


def _foundation_test_config(
    tmp_path: Path, *, prediction_length: int = 3, periods: int = 12
) -> dict:
    test_fraction = 0.5 if prediction_length >= 30 else 0.25
    return {
        "_repo_root": str(tmp_path),
        "resolved_paths": {
            "processed_data": str(tmp_path / "data" / "processed"),
            "tables": str(tmp_path / "outputs" / "tables"),
            "reports": str(tmp_path / "reports"),
            "figures": str(tmp_path / "figures"),
        },
        "forecast": {
            "horizons": list(range(1, prediction_length + 1)),
            "prediction_length_days": prediction_length,
            "context_length_days": 10,
            "test_fraction": test_fraction,
            "minimum_training_days": 5,
            "random_seed": 20260530,
            "allow_local_baseline_fallback": False,
            "foundation_prediction_cache": "data/processed/foundation_model_predictions.csv",
            "preferred_trajectory_models": ["TimesFM", "Chronos Large"],
        },
        "foundation_models": {
            "timesfm_test": {
                "enabled": True,
                "label": "TimesFM",
                "family": "timesfm",
                "model_identifier": "google/timesfm-test",
            },
            "chronos_test": {
                "enabled": True,
                "label": "Chronos Large",
                "family": "chronos",
                "model_identifier": "amazon/chronos-test",
            },
        },
    }


def _foundation_daily_fixture(periods: int = 12) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=periods, freq="D")
    return pd.DataFrame(
        {
            "station_id": ["pucon"] * periods,
            "station_name": ["Pucón"] * periods,
            "date": dates,
            "chl_a_model": [float(value) for value in range(periods)],
            "chl_a_observed": [float(value) for value in range(periods)],
            "is_direct_observation": [True] * periods,
            "is_imputed": [False] * periods,
            "imputation_method": ["observed"] * periods,
            "is_iqr_outlier": [False] * periods,
            "is_outlier_removed": [False] * periods,
        }
    )


def _complete_foundation_predictions(daily: pd.DataFrame, config: dict) -> pd.DataFrame:
    plan = build_forecast_origin_plan(daily, config)
    daily_targets = daily.copy()
    daily_targets["date"] = pd.to_datetime(daily_targets["date"])
    records = []
    models = [dict(model) for model in config["foundation_models"].values()]
    for _, origin in plan.iterrows():
        origin_date = pd.Timestamp(origin["origin_date"])
        for model in models:
            for horizon in config["forecast"]["horizons"]:
                target_date = origin_date + pd.Timedelta(days=int(horizon))
                target_row = daily_targets[
                    daily_targets["date"].eq(target_date)
                    & daily_targets["station_id"].eq(origin["station_id"])
                ].iloc[0]
                y_pred = float(target_row["chl_a_model"]) + 0.1
                records.append(
                    {
                        "run_id": "test_run",
                        "station_id": origin["station_id"],
                        "station_name": origin["station_name"],
                        "model": model["label"],
                        "model_family": model["family"],
                        "model_identifier": model["model_identifier"],
                        "model_version": "test",
                        "origin_date": origin_date.date().isoformat(),
                        "target_date": target_date.date().isoformat(),
                        "horizon": int(horizon),
                        "context_start": origin["context_start"],
                        "context_end": origin["context_end"],
                        "context_length_used": int(origin["context_length_used"]),
                        "y_true": float(target_row["chl_a_model"]),
                        "y_true_observed": float(target_row["chl_a_observed"]),
                        "y_pred": y_pred,
                        "q10": y_pred - 0.2,
                        "q50": y_pred,
                        "q90": y_pred + 0.2,
                        "target_is_direct_observation": bool(target_row["is_direct_observation"]),
                        "target_is_imputed": bool(target_row["is_imputed"]),
                        "target_imputation_method": str(target_row["imputation_method"]),
                        "target_is_iqr_outlier": bool(target_row["is_iqr_outlier"]),
                        "target_is_outlier_removed": bool(target_row["is_outlier_removed"]),
                        "prediction_source": "foundation_model_runtime",
                        "training_site": origin["station_id"],
                        "evaluation_site": origin["station_id"],
                    }
                )
    return pd.DataFrame.from_records(records, columns=PREDICTION_COLUMNS)
