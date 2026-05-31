from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.figures.common import apply_manuscript_style, save_figure, station_label
from villarrica_forecaster.forecasting.foundation import load_foundation_daily_target
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
    _remove_blocked_figure_status(config, figure_number)
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
    predictions = pd.read_csv(
        tables_dir / "forecast_predictions_long.csv", parse_dates=["target_date"]
    )
    daily = load_foundation_daily_target(config)
    station_predictions = predictions[predictions["station_id"].eq(station_id)].copy()
    models = _required_foundation_figure_models(config)
    missing_models = sorted(
        set(models) - set(station_predictions.get("model", pd.Series(dtype=str)))
    )
    horizons = [1, 7, 14, 28]
    source = station_predictions[
        station_predictions["model"].isin(models) & station_predictions["horizon"].isin(horizons)
    ].copy()
    source = _filter_trajectory_window(source, config)
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
    _remove_blocked_figure_status(config, figure_number)

    observed = daily[daily["station_id"].eq(station_id)].sort_values("date")
    observed = _filter_observed_window(observed, config)

    apply_manuscript_style()
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.titleweight": "bold",
            "figure.titlesize": 14,
            "figure.titleweight": "bold",
            "legend.fontsize": 7,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linestyle": "-",
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.2), sharex=True, sharey=True)
    axes = axes.ravel()
    model_styles = {
        "TimesFM": {"color": "#D73027", "marker": "o", "label": "TimesFM"},
        "Chronos Large": {"color": "#1A9850", "marker": "s", "label": "Chronos"},
    }
    y_upper = _trajectory_y_upper(observed, source)
    for ax, horizon in zip(axes, horizons, strict=True):
        ax.plot(
            observed["date"],
            observed["chl_a_model"],
            color="#2B8CBE",
            linewidth=1.45,
            label="Observed",
            zorder=2,
        )
        horizon_df = source[source["horizon"].eq(horizon)]
        for model in models:
            group = horizon_df[horizon_df["model"].eq(model)].sort_values("target_date")
            if group.empty:
                continue
            style = model_styles.get(model, {"color": "#9467BD", "marker": "^", "label": model})
            horizon_label = _horizon_label(horizon)
            group = group.sort_values("target_date")
            ax.scatter(
                group["target_date"],
                group["y_pred"],
                s=18,
                color=style["color"],
                marker=style["marker"],
                edgecolors="black",
                linewidths=0.35,
                label=f"{style['label']} D{horizon} ({horizon_label})",
                alpha=0.9,
                zorder=3,
            )
        ax.set_title(f"Chlorophyll-a Forecast Comparison - D{horizon} ({horizon_label})")
        ax.set_ylabel("Chlorophyll-a (µg/L)")
        ax.set_xlabel("Date")
        ax.set_ylim(bottom=0, top=y_upper)
        ax.legend(loc="upper right", frameon=True)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.tick_params(axis="x", rotation=45)
    fig.suptitle(
        "Time Series Forecast Comparison: TimesFM vs Chronos Large\n"
        f"{_trajectory_station_title(station_id)} - Chlorophyll-a Predictions"
    )
    fig.tight_layout(rect=[0, 0.02, 1, 0.92], h_pad=2.2, w_pad=2.0)
    return save_figure(
        fig,
        config,
        stem,
        {
            "script": "src/villarrica_forecaster/figures/forecast_figures.py",
            "source_data": str(source_path),
            "station_id": station_id,
            "models_plotted": models,
            "target_window": _trajectory_target_window(config),
            "scientific_note": "Generated from validated rolling-origin foundation-model predictions only; styled to match the original manuscript trajectory panels.",
        },
    )


def _filter_trajectory_window(source: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    start, end = _trajectory_target_window(config)
    if source.empty or not start or not end:
        return source
    target = pd.to_datetime(source["target_date"])
    return source[target.between(pd.Timestamp(start), pd.Timestamp(end))].copy()


def _filter_observed_window(observed: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    start, end = _trajectory_target_window(config)
    if observed.empty or not start or not end:
        return observed
    return observed[observed["date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()


def _trajectory_target_window(config: dict[str, Any]) -> tuple[str | None, str | None]:
    forecast = config.get("forecast", {})
    return (
        forecast.get("trajectory_figure_target_start") or forecast.get("evaluation_target_start"),
        forecast.get("trajectory_figure_target_end") or forecast.get("evaluation_target_end"),
    )


def _horizon_label(horizon: int) -> str:
    return "1-day" if int(horizon) == 1 else f"{int(horizon)}-day"


def _trajectory_station_title(station_id: str) -> str:
    return {"la_poza": "Poza Dataset", "pucon": "Pucon"}.get(station_id, station_label(station_id))


def _trajectory_y_upper(observed: pd.DataFrame, source: pd.DataFrame) -> float:
    maxima = []
    if not observed.empty:
        maxima.append(float(pd.to_numeric(observed["chl_a_model"], errors="coerce").max()))
    if not source.empty:
        maxima.append(float(pd.to_numeric(source["y_pred"], errors="coerce").max()))
        maxima.append(float(pd.to_numeric(source["y_true"], errors="coerce").max()))
    max_value = max([value for value in maxima if pd.notna(value)] or [3.0])
    if max_value <= 3.5:
        return 3.6
    if max_value <= 4.0:
        return 4.1
    return min(max_value * 1.12, 6.0)


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


def _remove_blocked_figure_status(config: dict[str, Any], figure_number: str) -> None:
    status_path = path_from_config(config, "tables") / f"figure_{figure_number}_status.csv"
    if status_path.exists():
        status_path.unlink()


def _date_to_string(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in ["origin_date", "target_date"]:
        if column in output:
            output[column] = pd.to_datetime(output[column]).dt.date.astype(str)
    return output
