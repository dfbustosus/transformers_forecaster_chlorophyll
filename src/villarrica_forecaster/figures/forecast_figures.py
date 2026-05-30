from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.figures.common import apply_manuscript_style, save_figure, station_label
from villarrica_forecaster.io import write_csv

METRICS = ["MAPE", "MSE", "RMSE", "Bias", "MedianAbsoluteError", "MAE"]


def build_forecast_figures(config: dict[str, Any]) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    for station_id, figure_number in [("la_poza", "04"), ("pucon", "05")]:
        for key, value in metric_figure(config, station_id, figure_number).items():
            outputs[f"figure_{figure_number}_{key}"] = value
    for station_id, figure_number in [("la_poza", "06"), ("pucon", "07")]:
        for key, value in trajectory_figure(config, station_id, figure_number).items():
            outputs[f"figure_{figure_number}_{key}"] = value
    return outputs


def metric_figure(config: dict[str, Any], station_id: str, figure_number: str) -> dict[str, Path]:
    tables_dir = path_from_config(config, "tables")
    metrics = pd.read_csv(tables_dir / "forecast_metrics_by_horizon.csv")
    required_models = _required_foundation_figure_models(config)
    station_metrics = metrics[metrics["station_id"].eq(station_id)].copy()
    source = station_metrics[station_metrics["model"].isin(required_models)].copy()
    missing_models = sorted(set(required_models) - set(source.get("model", pd.Series(dtype=str))))
    source_path = write_csv(source, tables_dir / f"figure_{figure_number}_source.csv")
    stem = f"figure_{figure_number}_forecast_metrics_{station_id}"
    if source.empty or missing_models:
        _remove_existing_figure_exports(config, stem)
        status_path = _write_blocked_figure_status(
            config,
            figure_number=figure_number,
            station_id=station_id,
            source_path=source_path,
            reason=(
                "No complete validated TimesFM/Chronos rolling-origin metrics were available. "
                f"Missing required model(s): {', '.join(missing_models) or 'all'}. "
                "Figure generation is blocked rather than drawing local-baseline results."
            ),
        )
        return {"status": status_path, "source": source_path}
    apply_manuscript_style()
    fig, axes = plt.subplots(3, 2, figsize=(11, 8), sharex=True)
    axes = axes.ravel()
    for ax, metric in zip(axes, METRICS, strict=True):
        for model, group in source.groupby("model"):
            group = group.sort_values("horizon")
            ax.plot(
                group["horizon"],
                group[metric],
                marker="o",
                linewidth=1.2,
                markersize=3,
                label=model,
            )
        ax.set_title(f"{metric} by forecast horizon")
        ax.set_xlabel("Forecast horizon (days)")
        ax.set_ylabel(metric)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.suptitle(f"Forecast metrics comparison — {station_label(station_id)}")
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])
    return save_figure(
        fig,
        config,
        stem,
        {
            "script": "src/villarrica_forecaster/figures/forecast_figures.py",
            "source_data": str(source_path),
            "station_id": station_id,
            "models_plotted": required_models,
            "scientific_note": "Generated from validated rolling-origin foundation-model predictions only.",
        },
    )


def trajectory_figure(
    config: dict[str, Any], station_id: str, figure_number: str
) -> dict[str, Path]:
    tables_dir = path_from_config(config, "tables")
    processed_dir = path_from_config(config, "processed_data")
    predictions = pd.read_csv(
        tables_dir / "forecast_predictions_long.csv", parse_dates=["target_date"]
    )
    daily = pd.read_csv(processed_dir / "daily_chl_a.csv", parse_dates=["date"])
    station_predictions = predictions[predictions["station_id"].eq(station_id)].copy()
    models = _required_foundation_figure_models(config)
    missing_models = sorted(
        set(models) - set(station_predictions.get("model", pd.Series(dtype=str)))
    )
    horizons = [1, 7, 14, 28]
    source = station_predictions[
        station_predictions["model"].isin(models) & station_predictions["horizon"].isin(horizons)
    ].copy()
    source_path = write_csv(
        _date_to_string(source), tables_dir / f"figure_{figure_number}_source.csv"
    )
    stem = f"figure_{figure_number}_forecasts_{station_id}"
    if source.empty or missing_models:
        _remove_existing_figure_exports(config, stem)
        status_path = _write_blocked_figure_status(
            config,
            figure_number=figure_number,
            station_id=station_id,
            source_path=source_path,
            reason=(
                "No complete validated TimesFM/Chronos trajectory predictions were available. "
                f"Missing required model(s): {', '.join(missing_models) or 'all'}. "
                "Figure generation is blocked rather than drawing local-baseline results."
            ),
        )
        return {"status": status_path, "source": source_path}

    observed = daily[daily["station_id"].eq(station_id)].sort_values("date")
    if not source.empty:
        min_date = source["target_date"].min()
        max_date = source["target_date"].max()
        observed = observed[observed["date"].between(min_date, max_date)]

    apply_manuscript_style()
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True, sharey=True)
    axes = axes.ravel()
    model_styles = [("#D62728", "o"), ("#2CA02C", "s"), ("#9467BD", "^")]
    for ax, horizon in zip(axes, horizons, strict=True):
        ax.plot(
            observed["date"],
            observed["chl_a_model"],
            color="#1F77B4",
            linewidth=1.2,
            label="Observed/processed",
        )
        horizon_df = source[source["horizon"].eq(horizon)]
        for (model, group), (color, marker) in zip(
            horizon_df.groupby("model"), model_styles, strict=False
        ):
            group = group.sort_values("target_date")
            ax.scatter(
                group["target_date"],
                group["y_pred"],
                s=12,
                color=color,
                marker=marker,
                label=model,
                alpha=0.8,
            )
        ax.set_title(f"Chl-a forecast comparison — D{horizon}")
        ax.set_ylabel("Chl-a (µg/L)")
        ax.tick_params(axis="x", rotation=35)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.suptitle(f"Forecast trajectories — {station_label(station_id)}")
    fig.tight_layout(rect=[0, 0.07, 1, 0.94])
    return save_figure(
        fig,
        config,
        stem,
        {
            "script": "src/villarrica_forecaster/figures/forecast_figures.py",
            "source_data": str(source_path),
            "station_id": station_id,
            "models_plotted": models,
            "scientific_note": "Generated from validated rolling-origin foundation-model predictions only.",
        },
    )


def _required_foundation_figure_models(config: dict[str, Any]) -> list[str]:
    preferred = [str(model) for model in config["forecast"].get("preferred_trajectory_models", [])]
    if preferred:
        return preferred
    return [
        str(model["label"])
        for model in config.get("foundation_models", {}).values()
        if model.get("enabled", True)
    ]


def _remove_existing_figure_exports(config: dict[str, Any], stem: str) -> None:
    figures_dir = path_from_config(config, "figures")
    for suffix in (".png", ".svg", ".metadata.json"):
        path = figures_dir / f"{stem}{suffix}"
        if path.exists():
            path.unlink()


def _write_blocked_figure_status(
    config: dict[str, Any], figure_number: str, station_id: str, source_path: Path, reason: str
) -> Path:
    tables_dir = path_from_config(config, "tables")
    status = pd.DataFrame(
        [
            {
                "figure": f"Figure {int(figure_number)}",
                "station_id": station_id,
                "status": "blocked_missing_foundation_predictions",
                "reason": reason,
                "source_table": str(source_path),
                "required_action": "Generate or provide data/processed/foundation_model_predictions.csv with daily origins and horizons 1-30 for TimesFM/Chronos.",
            }
        ]
    )
    return write_csv(status, tables_dir / f"figure_{figure_number}_status.csv")


def _date_to_string(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in ["origin_date", "target_date"]:
        if column in output:
            output[column] = pd.to_datetime(output[column]).dt.date.astype(str)
    return output
