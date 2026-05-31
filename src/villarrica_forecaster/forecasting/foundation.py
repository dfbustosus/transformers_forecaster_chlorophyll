from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.io import utc_now_iso, write_csv, write_json

PREDICTION_COLUMNS = [
    "run_id",
    "station_id",
    "station_name",
    "model",
    "model_family",
    "model_identifier",
    "model_version",
    "origin_date",
    "target_date",
    "horizon",
    "context_start",
    "context_end",
    "context_length_used",
    "y_true",
    "y_true_observed",
    "y_pred",
    "q10",
    "q50",
    "q90",
    "target_is_direct_observation",
    "target_is_imputed",
    "target_imputation_method",
    "target_is_iqr_outlier",
    "target_is_outlier_removed",
    "prediction_source",
    "training_site",
    "evaluation_site",
]


@dataclass(frozen=True)
class ForecastOrigin:
    station_id: str
    station_name: str
    origin_date: pd.Timestamp
    context_start: pd.Timestamp
    context_end: pd.Timestamp
    context_length_used: int
    first_target_date: pd.Timestamp
    last_target_date: pd.Timestamp


def foundation_cache_path(config: dict[str, Any]) -> Path:
    raw = Path(
        config["forecast"].get(
            "foundation_prediction_cache", "data/processed/foundation_model_predictions.csv"
        )
    )
    if raw.is_absolute():
        return raw
    return Path(config["_repo_root"]) / raw


def load_foundation_daily_target(config: dict[str, Any]) -> pd.DataFrame:
    """Load the daily target used by forecast generation and evaluation.

    The full daily table provides historical context before 2024. When configured,
    the accepted observed-preserving 2024 reference replaces the 2024 target segment
    so model contexts, truths, and figure traces use the same data product that was
    visually accepted before forecast reruns.
    """

    processed_dir = path_from_config(config, "processed_data")
    daily = pd.read_csv(processed_dir / "daily_chl_a.csv", parse_dates=["date"])
    if not bool(config.get("forecast", {}).get("use_realistic_imputation_reference", False)):
        return daily
    reference_path = processed_dir / "realistic_imputed_chl_a_2024.csv"
    if not reference_path.exists():
        return daily
    reference = pd.read_csv(reference_path, parse_dates=["date"])
    return apply_realistic_imputation_reference(daily, reference)


def apply_realistic_imputation_reference(daily: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Overlay the accepted 2024 realistic-imputation table onto daily_chl_a."""

    if daily.empty or reference.empty:
        return daily.copy()
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    ref = reference.copy()
    ref["date"] = pd.to_datetime(ref["date"])
    ref_columns = [
        "station_id",
        "date",
        "chl_a_observed",
        "is_observed",
        "source_observation_count",
        "source_files",
        "source_rows",
        "chl_a_imputed",
        "imputation_method",
        "is_imputed",
        "is_short_gap_imputed",
        "is_long_gap_imputed",
    ]
    available_ref_columns = [column for column in ref_columns if column in ref.columns]
    merged = frame.merge(
        ref[available_ref_columns],
        on=["station_id", "date"],
        how="left",
        suffixes=("", "_realistic"),
    )
    mask = merged["chl_a_imputed"].notna() if "chl_a_imputed" in merged.columns else pd.Series(False, index=merged.index)
    if not bool(mask.any()):
        return frame

    observed_value_column = _merged_reference_column(merged, "chl_a_observed")
    observed_flag_column = _merged_reference_column(merged, "is_observed")
    imputed_flag_column = _merged_reference_column(merged, "is_imputed")
    short_gap_column = _merged_reference_column(merged, "is_short_gap_imputed")
    method_column = _merged_reference_column(merged, "imputation_method")
    source_count_column = _merged_reference_column(merged, "source_observation_count")
    frame.loc[mask, "chl_a_model"] = merged.loc[mask, "chl_a_imputed"].astype(float).to_numpy()
    if "chl_a_filled" in frame.columns:
        frame.loc[mask, "chl_a_filled"] = merged.loc[mask, "chl_a_imputed"].astype(float).to_numpy()
    if observed_value_column in merged.columns:
        observed_values = pd.to_numeric(
            merged.loc[mask, observed_value_column], errors="coerce"
        ).to_numpy(dtype=float)
        if "chl_a_clean" in frame.columns:
            frame.loc[mask, "chl_a_clean"] = observed_values
        frame.loc[mask, "chl_a_observed"] = observed_values

    observed = (
        _as_bool_series(merged[observed_flag_column])
        if observed_flag_column in merged
        else pd.Series(False, index=merged.index)
    )
    imputed = (
        _as_bool_series(merged[imputed_flag_column])
        if imputed_flag_column in merged
        else ~observed
    )
    short_gap = (
        _as_bool_series(merged[short_gap_column])
        if short_gap_column in merged
        else pd.Series(False, index=merged.index)
    )
    frame.loc[mask, "is_direct_observation"] = observed.loc[mask].to_numpy()
    frame.loc[mask, "is_imputed"] = imputed.loc[mask].to_numpy()
    if "is_interpolated" in frame.columns:
        frame.loc[mask, "is_interpolated"] = short_gap.loc[mask].to_numpy()
    if "imputation_method" in frame.columns and method_column in merged.columns:
        frame.loc[mask, "imputation_method"] = merged.loc[mask, method_column].to_numpy()
    if source_count_column in merged.columns:
        count_values = merged.loc[mask, source_count_column].fillna(0).astype(int).to_numpy()
        if "source_observation_count" in frame.columns:
            frame.loc[mask, "source_observation_count"] = count_values
        if "source_count" in frame.columns:
            frame.loc[mask, "source_count"] = count_values
    for column in ("source_files", "source_rows"):
        source_column = _merged_reference_column(merged, column)
        if source_column in merged.columns and column in frame.columns:
            frame.loc[mask, column] = merged.loc[mask, source_column].fillna("").to_numpy()
    for column, value in {
        "is_smoothed": False,
        "has_smoothed_variant": False,
        "is_outlier_removed": False,
        "is_qc_excluded_from_model": False,
    }.items():
        if column in frame.columns:
            frame.loc[mask, column] = value
    if "smoothing_method" in frame.columns:
        frame.loc[mask, "smoothing_method"] = "none"
    frame.loc[mask, "foundation_target_source"] = "realistic_imputed_chl_a_2024"
    frame.loc[~mask, "foundation_target_source"] = frame.loc[
        ~mask, "foundation_target_source"
    ].fillna("daily_chl_a_context")
    return frame


def _merged_reference_column(merged: pd.DataFrame, column: str) -> str:
    suffixed = f"{column}_realistic"
    if suffixed in merged.columns:
        return suffixed
    return column


def empty_prediction_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=PREDICTION_COLUMNS)


def enabled_foundation_models(config: dict[str, Any]) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for key, value in config.get("foundation_models", {}).items():
        model = dict(value)
        model["model_key"] = key
        if bool(model.get("enabled", True)):
            models.append(model)
    return models


def build_forecast_origin_plan(daily: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    origins = list(iter_forecast_origins(daily, config))
    rows = [
        {
            "station_id": origin.station_id,
            "station_name": origin.station_name,
            "origin_date": origin.origin_date.date().isoformat(),
            "context_start": origin.context_start.date().isoformat(),
            "context_end": origin.context_end.date().isoformat(),
            "context_length_used": origin.context_length_used,
            "first_target_date": origin.first_target_date.date().isoformat(),
            "last_target_date": origin.last_target_date.date().isoformat(),
            "prediction_length_days": int(config["forecast"].get("prediction_length_days", 30)),
        }
        for origin in origins
    ]
    return pd.DataFrame.from_records(rows)


def iter_forecast_origins(daily: pd.DataFrame, config: dict[str, Any]) -> list[ForecastOrigin]:
    prediction_length = int(config["forecast"].get("prediction_length_days", 30))
    test_fraction = float(config["forecast"].get("test_fraction", 0.20))
    min_train = int(config["forecast"].get("minimum_training_days", 30))
    context_length = int(config["forecast"].get("context_length_days", 1024))
    target_start = config["forecast"].get("evaluation_target_start")
    target_end = config["forecast"].get("evaluation_target_end")
    origins: list[ForecastOrigin] = []
    for (station_id, station_name), station in daily.groupby(["station_id", "station_name"]):
        station = station.sort_values("date").reset_index(drop=True)
        if len(station) <= min_train + prediction_length:
            continue
        if target_start and target_end:
            origin_positions = _explicit_target_window_origin_positions(
                station,
                target_start=str(target_start),
                target_end=str(target_end),
                prediction_length=prediction_length,
                min_train=min_train,
            )
        else:
            test_start_pos = max(min_train, int(np.floor(len(station) * (1.0 - test_fraction))))
            origin_positions = range(test_start_pos - 1, len(station) - prediction_length)
        for origin_pos in origin_positions:
            context_start_pos = max(0, origin_pos - context_length + 1)
            origins.append(
                ForecastOrigin(
                    station_id=str(station_id),
                    station_name=str(station_name),
                    origin_date=pd.Timestamp(station.loc[origin_pos, "date"]),
                    context_start=pd.Timestamp(station.loc[context_start_pos, "date"]),
                    context_end=pd.Timestamp(station.loc[origin_pos, "date"]),
                    context_length_used=int(origin_pos - context_start_pos + 1),
                    first_target_date=pd.Timestamp(station.loc[origin_pos + 1, "date"]),
                    last_target_date=pd.Timestamp(
                        station.loc[origin_pos + prediction_length, "date"]
                    ),
                )
            )
    return origins


def _explicit_target_window_origin_positions(
    station: pd.DataFrame,
    *,
    target_start: str,
    target_end: str,
    prediction_length: int,
    min_train: int,
) -> range:
    dates = pd.to_datetime(station["date"])
    target_start_ts = pd.Timestamp(target_start)
    target_end_ts = pd.Timestamp(target_end)
    origin_start_ts = target_start_ts - pd.Timedelta(days=1)
    origin_end_ts = target_end_ts - pd.Timedelta(days=prediction_length)
    start_candidates = station.index[dates.ge(origin_start_ts)]
    end_candidates = station.index[dates.le(origin_end_ts)]
    if start_candidates.empty or end_candidates.empty:
        return range(0, 0)
    start_pos = max(int(start_candidates.min()), min_train - 1)
    end_pos = min(int(end_candidates.max()), len(station) - prediction_length - 1)
    if end_pos < start_pos:
        return range(0, 0)
    return range(start_pos, end_pos + 1)


def write_forecast_origin_plan(config: dict[str, Any]) -> dict[str, Path]:
    daily = load_foundation_daily_target(config)
    tables_dir = path_from_config(config, "tables")
    plan = build_forecast_origin_plan(daily, config)
    return {
        "foundation_forecast_origin_plan": write_csv(
            plan, tables_dir / "foundation_forecast_origin_plan.csv"
        )
    }


def validate_foundation_prediction_table(
    predictions: pd.DataFrame, daily: pd.DataFrame, config: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    missing = [column for column in PREDICTION_COLUMNS if column not in predictions.columns]
    if missing:
        errors.append(f"Missing prediction columns: {', '.join(missing)}")
        return errors
    if predictions.empty:
        errors.append("Prediction table is empty.")
        return errors

    prediction_length = int(config["forecast"].get("prediction_length_days", 30))
    expected_horizons = set(range(1, prediction_length + 1))
    configured_horizons = {int(horizon) for horizon in config["forecast"].get("horizons", [])}
    if configured_horizons and configured_horizons != expected_horizons:
        errors.append(
            "forecast.horizons must be exactly the daily 1-"
            f"{prediction_length} horizon contract for manuscript foundation figures."
        )

    frame = _normalise_prediction_dates(predictions)
    bad_date_columns = [
        column
        for column in ("origin_date", "target_date", "context_start", "context_end")
        if frame[column].eq("NaT").any()
    ]
    if bad_date_columns:
        errors.append(f"Invalid date values in columns: {', '.join(bad_date_columns)}")
        return errors
    if frame["horizon"].isna().any():
        errors.append("Invalid or missing horizon values in prediction cache.")
        return errors
    actual_horizons = set(frame["horizon"].astype(int).unique())
    if actual_horizons != expected_horizons:
        errors.append(
            f"Expected every horizon 1-{max(expected_horizons)}; got {sorted(actual_horizons)}"
        )

    expected_models = _expected_model_specs(config)
    expected_model_labels = set(expected_models)
    actual_model_labels = set(frame["model"].dropna().astype(str).unique())
    if actual_model_labels != expected_model_labels:
        errors.append(
            "Expected exactly enabled foundation models "
            f"{sorted(expected_model_labels)}; got {sorted(actual_model_labels)}"
        )
    for model_label, spec in expected_models.items():
        rows = frame[frame["model"].astype(str).eq(model_label)]
        if rows.empty:
            continue
        families = set(rows["model_family"].dropna().astype(str).unique())
        if families != {str(spec["family"])}:
            errors.append(
                f"Model {model_label} must have family {spec['family']}; got {sorted(families)}"
            )
        identifiers = set(rows["model_identifier"].dropna().astype(str).unique())
        if identifiers != {str(spec["model_identifier"])}:
            errors.append(
                "Model "
                f"{model_label} must use identifier {spec['model_identifier']}; got {sorted(identifiers)}"
            )
    blocked_sources = frame[
        frame["prediction_source"].astype(str).str.contains("baseline", case=False, na=False)
    ]
    if not blocked_sources.empty:
        errors.append("Prediction cache contains local-baseline prediction_source values.")

    duplicate_key = ["station_id", "model", "origin_date", "horizon"]
    duplicate_count = int(frame.duplicated(duplicate_key).sum())
    if duplicate_count:
        errors.append(
            f"Prediction cache contains {duplicate_count} duplicate station/model/origin/horizon rows."
        )

    expected_origins = build_forecast_origin_plan(daily, config)
    if not expected_origins.empty:
        expected_origin_keys = expected_origins[["station_id", "origin_date"]].drop_duplicates()
        actual_origin_keys = frame[["station_id", "origin_date"]].drop_duplicates()
        missing_origins = _missing_key_count(
            expected_origin_keys, actual_origin_keys, ["station_id", "origin_date"]
        )
        if missing_origins:
            errors.append(f"Missing {missing_origins} expected station/origin forecasts.")

        expected_grid = expected_origin_keys.merge(
            pd.DataFrame({"model": sorted(expected_model_labels)}), how="cross"
        ).merge(pd.DataFrame({"horizon": sorted(expected_horizons)}), how="cross")
        actual_grid = frame[["station_id", "origin_date", "model", "horizon"]].drop_duplicates()
        missing_grid = _missing_key_count(
            expected_grid, actual_grid, ["station_id", "origin_date", "model", "horizon"]
        )
        if missing_grid:
            errors.append(
                f"Missing {missing_grid} expected station/origin/model/horizon prediction rows."
            )

        expected_context = expected_origins[
            ["station_id", "origin_date", "context_start", "context_end", "context_length_used"]
        ].copy()
        with_expected_context = frame.merge(
            expected_context,
            on=["station_id", "origin_date"],
            how="left",
            suffixes=("", "_expected"),
        )
        context_mismatches = (
            with_expected_context["context_start"].ne(
                with_expected_context["context_start_expected"]
            )
            | with_expected_context["context_end"].ne(with_expected_context["context_end_expected"])
            | with_expected_context["context_length_used"]
            .astype("Int64")
            .ne(with_expected_context["context_length_used_expected"].astype("Int64"))
        )
        if bool(context_mismatches.fillna(True).any()):
            errors.append("Context metadata do not match the expected origin plan.")

    expected_target_date = pd.to_datetime(frame["origin_date"]) + pd.to_timedelta(
        frame["horizon"].astype(int), unit="D"
    )
    if not (pd.to_datetime(frame["target_date"]) == expected_target_date).all():
        errors.append("Some target_date values do not equal origin_date + horizon days.")
    bad_target_dates = frame[
        pd.to_datetime(frame["target_date"]) <= pd.to_datetime(frame["origin_date"])
    ]
    if not bad_target_dates.empty:
        errors.append("Some target_date values are not after origin_date.")

    errors.extend(_validate_targets_against_daily(frame, daily))
    return errors


def run_foundation_forecasts(
    config: dict[str, Any], model_labels: set[str] | None = None
) -> dict[str, Path]:
    """Run enabled TimesFM/Chronos models for every daily origin and cache predictions.

    This function intentionally fails loudly if optional model dependencies or model
    downloads are unavailable. It never silently substitutes baselines for foundation
    models.
    """

    daily = load_foundation_daily_target(config)
    random_seed = int(config["forecast"].get("random_seed", 0))
    _apply_random_seed(random_seed)
    models = enabled_foundation_models(config)
    if model_labels is not None:
        models = [model for model in models if str(model["label"]) in model_labels]
    if not models:
        raise RuntimeError("No enabled foundation models selected in config.")
    run_config = _config_limited_to_models(config, models)

    input_hash = _foundation_input_hash(config)
    config_hash = _stable_hash(
        run_config.get("forecast", {}), run_config.get("foundation_models", {})
    )
    run_id = f"foundation_{utc_now_iso().replace(':', '').replace('-', '').replace('+0000', 'Z')}"
    records: list[dict[str, Any]] = []
    for model in models:
        print(
            f"[{model['label']}] loading {model['family']} checkpoint {model['model_identifier']}",
            flush=True,
        )
        forecaster = _load_model(model, config)
        print(f"[{model['label']}] model loaded", flush=True)
        records.extend(_predict_model_for_all_origins(forecaster, model, daily, config, run_id))

    predictions = pd.DataFrame.from_records(records, columns=PREDICTION_COLUMNS)
    cache_path = foundation_cache_path(config)
    errors = validate_foundation_prediction_table(predictions, daily, run_config)
    if errors:
        raise RuntimeError("Invalid foundation prediction output: " + " | ".join(errors))
    if model_labels is not None and cache_path.exists():
        predictions = _merge_with_existing_cache(predictions, cache_path)
    paths = {"foundation_model_predictions": write_csv(predictions, cache_path)}
    prediction_output_hash = _file_sha256(cache_path)
    paths["foundation_model_run_metadata"] = write_json(
        {
            "run_id": run_id,
            "created_at": utc_now_iso(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "git_commit": _git_commit(Path(config["_repo_root"])),
            "package_versions": _package_versions(["timesfm", "chronos-forecasting", "torch"]),
            "models": models,
            "random_seed": random_seed,
            "input_data_hash": input_hash,
            "config_hash": config_hash,
            "prediction_output_path": str(cache_path),
            "prediction_output_hash": prediction_output_hash,
        },
        path_from_config(config, "processed_data") / f"{run_id}_metadata.json",
    )
    return paths


def _predict_model_for_all_origins(
    forecaster: Any,
    model: dict[str, Any],
    daily: pd.DataFrame,
    config: dict[str, Any],
    run_id: str,
) -> list[dict[str, Any]]:
    prediction_length = int(config["forecast"].get("prediction_length_days", 30))
    context_length = int(config["forecast"].get("context_length_days", 1024))
    records: list[dict[str, Any]] = []
    partial_path = _partial_prediction_path(config, model)
    completed = _completed_partial_origins(partial_path, model, prediction_length)
    if completed:
        print(
            f"[{model['label']}] resuming from {partial_path} with "
            f"{len(completed)} completed origins",
            flush=True,
        )
    for (station_id, station_name), station in daily.groupby(["station_id", "station_name"]):
        station = station.sort_values("date").set_index("date")
        values = station["chl_a_model"].astype(float)
        origins = list(iter_forecast_origins(daily[daily["station_id"].eq(station_id)], config))
        origins = [
            origin
            for origin in origins
            if (station_id, str(model["label"]), origin.origin_date.date().isoformat())
            not in completed
        ]
        batch_size = int(
            model.get("batch_size", config["forecast"].get("foundation_batch_size", 8))
        )
        origin_batches = _chunks(origins, batch_size)
        print(
            f"[{model['label']}] {station_name}: {len(origins)} origins, "
            f"{len(origin_batches)} batches, batch_size={batch_size}",
            flush=True,
        )
        for batch_number, origin_batch in enumerate(origin_batches, start=1):
            if batch_number == 1 or batch_number == len(origin_batches) or batch_number % 10 == 0:
                print(
                    f"[{model['label']}] {station_name}: running batch "
                    f"{batch_number}/{len(origin_batches)}",
                    flush=True,
                )
            contexts = [
                values.loc[: origin.origin_date].tail(context_length).to_numpy(dtype=float)
                for origin in origin_batch
            ]
            batch_forecast = forecaster.predict_batch(
                contexts=contexts, prediction_length=prediction_length
            )
            for origin_index, origin in enumerate(origin_batch):
                records_for_origin = _prediction_records_for_origin(
                    batch_forecast=batch_forecast,
                    origin_index=origin_index,
                    origin=origin,
                    station=station,
                    station_id=station_id,
                    station_name=station_name,
                    model=model,
                    run_id=run_id,
                    prediction_length=prediction_length,
                )
                records.extend(records_for_origin)
                _append_partial_prediction_records(partial_path, records_for_origin)
    if partial_path.exists():
        partial = pd.read_csv(partial_path)
        return partial[partial["model"].astype(str).eq(str(model["label"]))][
            PREDICTION_COLUMNS
        ].to_dict("records")
    return records


def _prediction_records_for_origin(
    *,
    batch_forecast: dict[str, Any],
    origin_index: int,
    origin: ForecastOrigin,
    station: pd.DataFrame,
    station_id: str,
    station_name: str,
    model: dict[str, Any],
    run_id: str,
    prediction_length: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for horizon in range(1, prediction_length + 1):
        target_date = origin.origin_date + pd.Timedelta(days=horizon)
        target_row = station.loc[target_date]
        records.append(
            {
                "run_id": run_id,
                "station_id": station_id,
                "station_name": station_name,
                "model": model["label"],
                "model_family": model["family"],
                "model_identifier": model["model_identifier"],
                "model_version": str(batch_forecast.get("model_version", "unknown")),
                "origin_date": origin.origin_date.date().isoformat(),
                "target_date": target_date.date().isoformat(),
                "horizon": horizon,
                "context_start": origin.context_start.date().isoformat(),
                "context_end": origin.context_end.date().isoformat(),
                "context_length_used": origin.context_length_used,
                "y_true": float(target_row["chl_a_model"]),
                "y_true_observed": _nullable_float(target_row.get("chl_a_observed")),
                "y_pred": max(float(batch_forecast["point"][origin_index, horizon - 1]), 0.0),
                "q10": _nullable_float(
                    _array_value(batch_forecast.get("q10"), origin_index, horizon - 1)
                ),
                "q50": _nullable_float(
                    _array_value(batch_forecast.get("q50"), origin_index, horizon - 1)
                ),
                "q90": _nullable_float(
                    _array_value(batch_forecast.get("q90"), origin_index, horizon - 1)
                ),
                "target_is_direct_observation": bool(
                    target_row.get("is_direct_observation", False)
                ),
                "target_is_imputed": bool(target_row.get("is_imputed", False)),
                "target_imputation_method": str(target_row.get("imputation_method", "unknown")),
                "target_is_iqr_outlier": bool(target_row.get("is_iqr_outlier", False)),
                "target_is_outlier_removed": bool(target_row.get("is_outlier_removed", False)),
                "prediction_source": "foundation_model_runtime",
                "training_site": station_id,
                "evaluation_site": station_id,
            }
        )
    return records


def _merge_with_existing_cache(new_predictions: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    existing = pd.read_csv(cache_path)
    selected_models = set(new_predictions["model"].dropna().astype(str).unique())
    existing = existing[~existing["model"].astype(str).isin(selected_models)].copy()
    return pd.concat([existing, new_predictions], ignore_index=True)[PREDICTION_COLUMNS]


def _partial_prediction_path(config: dict[str, Any], model: dict[str, Any]) -> Path:
    label = str(model["label"]).lower().replace(" ", "_").replace("/", "_")
    input_hash = _foundation_input_hash(config)[:12]
    return (
        path_from_config(config, "processed_data")
        / f"foundation_model_predictions_{label}_{input_hash}_partial.csv"
    )


def _completed_partial_origins(
    partial_path: Path, model: dict[str, Any], prediction_length: int
) -> set[tuple[str, str, str]]:
    if not partial_path.exists():
        return set()
    partial = pd.read_csv(partial_path)
    if partial.empty:
        return set()
    partial = partial[partial["model"].astype(str).eq(str(model["label"]))].copy()
    if partial.empty:
        return set()
    counts = partial.groupby(["station_id", "model", "origin_date"], dropna=False)[
        "horizon"
    ].nunique()
    completed = counts[counts >= prediction_length]
    return {
        (str(station_id), str(model_label), str(origin_date))
        for station_id, model_label, origin_date in completed.index
    }


def _append_partial_prediction_records(partial_path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame.from_records(records, columns=PREDICTION_COLUMNS)
    frame.to_csv(partial_path, mode="a", header=not partial_path.exists(), index=False)


class _TimesFmForecaster:
    def __init__(self, model: dict[str, Any], prediction_length: int, context_length: int) -> None:
        import timesfm

        self._timesfm = timesfm
        self.version = _package_versions(["timesfm"]).get("timesfm", "unknown")
        self._model = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                backend=str(model.get("backend", "cpu")),
                per_core_batch_size=1,
                horizon_len=prediction_length,
                context_len=context_length,
                num_layers=50,
                use_positional_embedding=False,
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                huggingface_repo_id=str(model["model_identifier"])
            ),
        )
        self._freq = int(model.get("frequency", 0))

    def predict_batch(
        self, contexts: list[np.ndarray], prediction_length: int
    ) -> dict[str, np.ndarray | str]:
        point, quantiles = self._model.forecast(contexts, freq=[self._freq] * len(contexts))
        point_values = np.asarray(point)[:, :prediction_length]
        output: dict[str, np.ndarray | str] = {
            "point": point_values,
            "q50": point_values,
            "model_version": self.version,
        }
        if quantiles is not None:
            quantile_array = np.asarray(quantiles)
            if quantile_array.ndim == 3 and quantile_array.shape[2] >= 10:
                output["q10"] = quantile_array[:, :prediction_length, 1]
                output["q50"] = quantile_array[:, :prediction_length, 5]
                output["q90"] = quantile_array[:, :prediction_length, 9]
            elif quantile_array.ndim == 3 and quantile_array.shape[2] >= 9:
                output["q10"] = quantile_array[:, :prediction_length, 0]
                output["q50"] = quantile_array[:, :prediction_length, 4]
                output["q90"] = quantile_array[:, :prediction_length, 8]
        return output


class _ChronosForecaster:
    def __init__(self, model: dict[str, Any]) -> None:
        import torch
        from chronos import BaseChronosPipeline

        self._torch = torch
        self.version = _package_versions(["chronos-forecasting", "torch"]).get(
            "chronos-forecasting", "unknown"
        )
        self._num_samples = int(model.get("num_samples", 64))
        dtype_name = str(model.get("precision", "float32"))
        dtype = getattr(torch, dtype_name)
        self._pipeline = BaseChronosPipeline.from_pretrained(
            str(model["model_identifier"]),
            device_map=str(model.get("device", "cpu")),
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        )

    def predict_batch(
        self, contexts: list[np.ndarray], prediction_length: int
    ) -> dict[str, np.ndarray | str]:
        tensors = [self._torch.tensor(context, dtype=self._torch.float32) for context in contexts]
        try:
            forecast = self._pipeline.predict(
                tensors, prediction_length=prediction_length, num_samples=self._num_samples
            )
        except TypeError:
            forecast = self._pipeline.predict(tensors, prediction_length=prediction_length)
        values = _as_numpy_forecast(forecast)
        if values.ndim == 3:
            return {
                "point": np.median(values, axis=1),
                "q10": np.quantile(values, 0.10, axis=1),
                "q50": np.quantile(values, 0.50, axis=1),
                "q90": np.quantile(values, 0.90, axis=1),
                "model_version": self.version,
            }
        if values.ndim == 2:
            return {"point": values, "q50": values, "model_version": self.version}
        raise ValueError(f"Unexpected Chronos forecast shape: {values.shape}")


def _load_model(model: dict[str, Any], config: dict[str, Any]) -> Any:
    prediction_length = int(config["forecast"].get("prediction_length_days", 30))
    context_length = int(config["forecast"].get("context_length_days", 1024))
    family = str(model["family"])
    if family == "timesfm":
        return _TimesFmForecaster(
            model, prediction_length=prediction_length, context_length=context_length
        )
    if family == "chronos":
        return _ChronosForecaster(model)
    raise ValueError(f"Unsupported foundation model family: {family}")


def _expected_model_specs(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(model["label"]): model for model in enabled_foundation_models(config)}


def _config_limited_to_models(
    config: dict[str, Any], models: list[dict[str, Any]]
) -> dict[str, Any]:
    selected_labels = {str(model["label"]) for model in models}
    run_config = dict(config)
    foundation_models: dict[str, Any] = {}
    for key, value in config.get("foundation_models", {}).items():
        model = dict(value)
        model["enabled"] = str(model.get("label")) in selected_labels
        foundation_models[key] = model
    run_config["foundation_models"] = foundation_models
    return run_config


def _chunks(items: list[ForecastOrigin], size: int) -> list[list[ForecastOrigin]]:
    size = max(size, 1)
    return [items[index : index + size] for index in range(0, len(items), size)]


def _array_value(array: object, row: int, column: int) -> object:
    if array is None:
        return None
    values = np.asarray(array)
    if values.ndim != 2:
        return None
    return values[row, column]


def _as_numpy_forecast(forecast: Any) -> np.ndarray:
    if isinstance(forecast, list):
        arrays = []
        for item in forecast:
            if hasattr(item, "detach"):
                arrays.append(item.detach().cpu().numpy())
            else:
                arrays.append(np.asarray(item))
        return np.stack(arrays)
    if hasattr(forecast, "detach"):
        return forecast.detach().cpu().numpy()
    return np.asarray(forecast)


def _normalise_prediction_dates(predictions: pd.DataFrame) -> pd.DataFrame:
    frame = predictions.copy()
    for column in ("origin_date", "target_date", "context_start", "context_end"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.date.astype(str)
    frame["horizon"] = pd.to_numeric(frame["horizon"], errors="coerce").astype("Int64")
    return frame


def _missing_key_count(expected: pd.DataFrame, actual: pd.DataFrame, keys: list[str]) -> int:
    missing = (
        expected[keys]
        .drop_duplicates()
        .merge(actual[keys].drop_duplicates(), on=keys, how="left", indicator=True)
    )
    return int(missing[missing["_merge"].eq("left_only")].shape[0])


def _validate_targets_against_daily(predictions: pd.DataFrame, daily: pd.DataFrame) -> list[str]:
    daily_targets = daily.copy()
    daily_targets["target_date"] = pd.to_datetime(daily_targets["date"]).dt.date.astype(str)
    target_columns = [
        "station_id",
        "target_date",
        "chl_a_model",
        "chl_a_observed",
        "is_direct_observation",
        "is_imputed",
        "imputation_method",
        "is_iqr_outlier",
        "is_outlier_removed",
    ]
    available_target_columns = [
        column for column in target_columns if column in daily_targets.columns
    ]
    merged = predictions.merge(
        daily_targets[available_target_columns], on=["station_id", "target_date"], how="left"
    )
    errors: list[str] = []
    missing_target_count = (
        int(merged["chl_a_model"].isna().sum()) if "chl_a_model" in merged else len(merged)
    )
    if missing_target_count:
        errors.append(f"{missing_target_count} prediction rows do not match a daily target row.")
        return errors
    if not np.allclose(
        merged["y_true"].astype(float), merged["chl_a_model"].astype(float), equal_nan=True
    ):
        errors.append("Cached y_true values do not match daily_chl_a.csv chl_a_model targets.")
    if "chl_a_observed" in merged:
        cache_observed = pd.to_numeric(merged["y_true_observed"], errors="coerce")
        daily_observed = pd.to_numeric(merged["chl_a_observed"], errors="coerce")
        if not np.allclose(cache_observed, daily_observed, equal_nan=True):
            errors.append("Cached y_true_observed values do not match daily_chl_a.csv.")
    bool_checks = {
        "target_is_direct_observation": "is_direct_observation",
        "target_is_imputed": "is_imputed",
        "target_is_iqr_outlier": "is_iqr_outlier",
        "target_is_outlier_removed": "is_outlier_removed",
    }
    for cache_column, daily_column in bool_checks.items():
        if (
            daily_column in merged
            and not (
                _as_bool_series(merged[cache_column]).to_numpy()
                == _as_bool_series(merged[daily_column]).to_numpy()
            ).all()
        ):
            errors.append(f"Cached {cache_column} values do not match {daily_column}.")
    if "imputation_method" in merged:
        cache_method = merged["target_imputation_method"].fillna("").astype(str)
        daily_method = merged["imputation_method"].fillna("").astype(str)
        if not (cache_method.to_numpy() == daily_method.to_numpy()).all():
            errors.append("Cached target_imputation_method values do not match daily_chl_a.csv.")
    return errors


def _apply_random_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
    except ImportError:
        pass


def _as_bool_series(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values.fillna(False).astype(bool)
    clean = values.where(values.notna(), False)
    return clean.map(
        lambda value: str(value).strip().lower() in {"1", "true", "t", "yes", "y"}
    )


def _git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _foundation_input_hash(config: dict[str, Any]) -> str:
    processed_dir = path_from_config(config, "processed_data")
    payload: dict[str, Any] = {
        "daily_chl_a": _file_sha256(processed_dir / "daily_chl_a.csv"),
        "use_realistic_imputation_reference": bool(
            config.get("forecast", {}).get("use_realistic_imputation_reference", False)
        ),
    }
    reference_path = processed_dir / "realistic_imputed_chl_a_2024.csv"
    if payload["use_realistic_imputation_reference"] and reference_path.exists():
        payload["realistic_imputed_chl_a_2024"] = _file_sha256(reference_path)
    return _stable_hash(payload)


def _stable_hash(*objects: Any) -> str:
    payload = json.dumps(objects, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _package_versions(packages: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    return versions


def _nullable_float(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
