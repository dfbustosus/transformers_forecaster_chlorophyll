from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.figures.common import apply_manuscript_style, save_figure
from villarrica_forecaster.io import write_csv


def build_preprocessing_qa_figures(config: dict[str, Any]) -> dict[str, Path]:
    if not bool(config.get("figures", {}).get("generate_preprocessing_qa", False)):
        return {}
    outputs: dict[str, Path] = {}
    for key, value in preprocessing_observed_imputed_timeline(config).items():
        outputs[f"preprocessing_timeline_{key}"] = value
    for key, value in spike_review_timeline(config).items():
        outputs[f"spike_review_{key}"] = value
    for key, value in data_first_2024_reference_figure(config).items():
        outputs[f"data_first_2024_reference_{key}"] = value
    return outputs


def data_first_2024_reference_figure(config: dict[str, Any]) -> dict[str, Path]:
    processed_dir = path_from_config(config, "processed_data")
    tables_dir = path_from_config(config, "tables")
    daily = pd.read_csv(processed_dir / "daily_chl_a.csv", parse_dates=["date"])
    start = pd.Timestamp("2024-01-01")
    end = pd.Timestamp("2024-12-31")
    daily_2024 = daily[daily["date"].between(start, end)].copy()
    source_columns = [
        "date",
        "station_id",
        "station_name",
        "chl_a_observed",
        "chl_a_model",
        "is_direct_observation",
        "is_qc_excluded_from_model",
        "qc_exclusion_reason",
        "is_interpolated",
        "is_hpbr_imputed",
        "is_low_support_imputation",
        "imputation_method",
    ]
    source = daily_2024[source_columns].copy()
    source["date"] = source["date"].dt.date.astype(str)
    source_path = write_csv(source, tables_dir / "data_first_2024_reference_source.csv")

    apply_manuscript_style()
    plt.rcParams.update(
        {
            "figure.titlesize": 14,
            "figure.titleweight": "bold",
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
        }
    )
    stations = list(
        daily_2024[["station_id", "station_name"]].drop_duplicates().itertuples(index=False)
    )
    fig, axes = plt.subplots(len(stations), 1, figsize=(13.5, 4.2 * len(stations)), sharex=True)
    if len(stations) == 1:
        axes = [axes]
    for ax, station in zip(axes, stations, strict=True):
        frame = daily_2024[daily_2024["station_id"].eq(station.station_id)].sort_values("date")
        direct = frame[frame["is_direct_observation"] & ~frame["is_qc_excluded_from_model"]]
        qc_excluded = frame[frame["is_qc_excluded_from_model"]]
        hpbr = frame[frame["is_hpbr_imputed"]]
        ax.plot(
            frame["date"],
            frame["chl_a_model"],
            color="#4D4D4D",
            linewidth=1.4,
            label="daily reconstructed model target",
        )
        ax.scatter(
            direct["date"],
            direct["chl_a_observed"],
            s=28,
            color="#1F78B4",
            edgecolors="black",
            linewidths=0.3,
            label="direct observation retained",
            zorder=3,
        )
        ax.scatter(
            qc_excluded["date"],
            qc_excluded["chl_a_observed"],
            s=34,
            facecolors="none",
            edgecolors="#D73027",
            linewidths=1.1,
            label="direct observation excluded from model",
            zorder=4,
        )
        ax.scatter(
            hpbr["date"],
            hpbr["chl_a_model"],
            s=12,
            color="#BDBDBD",
            alpha=0.55,
            label="historical/imputed target day",
            zorder=2,
        )
        ax.set_title(f"{station.station_name}: 2024 data reference before any forecasting")
        ax.set_ylabel("Chlorophyll-a (µg/L)")
        ax.set_ylim(bottom=0)
        ax.legend(loc="upper right", ncol=2, fontsize=8)
    axes[-1].set_xlabel("Date")
    fig.suptitle("Data-first QA: 2024 Chl-a reference lines and excluded raw observations")
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    return save_figure(
        fig,
        config,
        "data_first_2024_reference",
        {
            "script": "src/villarrica_forecaster/figures/preprocessing_qa.py",
            "source_data": str(source_path),
            "purpose": "Data-only QA figure used before rerunning any forecast models.",
        },
    ) | {"source": source_path}


def preprocessing_observed_imputed_timeline(config: dict[str, Any]) -> dict[str, Path]:
    processed_dir = path_from_config(config, "processed_data")
    tables_dir = path_from_config(config, "tables")
    daily = pd.read_csv(processed_dir / "daily_chl_a.csv", parse_dates=["date"])
    source_columns = [
        "date",
        "station_id",
        "station_name",
        "chl_a_observed",
        "chl_a_model",
        "is_direct_observation",
        "is_interpolated",
        "is_hpbr_imputed",
        "is_low_support_imputation",
        "is_cross_station_duplicate_candidate",
        "is_abrupt_observed_transition",
        "imputation_method",
        "imputation_source_count",
    ]
    source = daily[source_columns].copy()
    source["date"] = source["date"].dt.date.astype(str)
    source_path = write_csv(
        source, tables_dir / "preprocessing_observed_imputed_timeline_source.csv"
    )

    apply_manuscript_style()
    stations = list(daily[["station_id", "station_name"]].drop_duplicates().itertuples(index=False))
    fig, axes = plt.subplots(len(stations), 1, figsize=(13, 3.9 * len(stations)), sharex=True)
    if len(stations) == 1:
        axes = [axes]
    for ax, station in zip(axes, stations, strict=True):
        frame = daily[daily["station_id"].eq(station.station_id)].sort_values("date")
        observed = frame[frame["is_direct_observation"]]
        low_support = frame[frame["is_low_support_imputation"]]
        interpolated = frame[frame["is_interpolated"]]
        duplicate = frame[frame["is_cross_station_duplicate_candidate"]]
        ax.plot(frame["date"], frame["chl_a_model"], color="#2F4858", lw=1.2, label="model input")
        ax.scatter(
            observed["date"],
            observed["chl_a_observed"],
            s=14,
            color="#1f77b4",
            alpha=0.75,
            label="direct observation",
        )
        ax.scatter(
            interpolated["date"],
            interpolated["chl_a_model"],
            s=20,
            marker="s",
            color="#ffbf00",
            alpha=0.8,
            label="short-gap interpolation",
        )
        ax.scatter(
            low_support["date"],
            low_support["chl_a_model"],
            s=18,
            marker="x",
            color="#d62728",
            alpha=0.75,
            label="low-support imputation",
        )
        ax.scatter(
            duplicate["date"],
            duplicate["chl_a_model"],
            s=36,
            facecolors="none",
            edgecolors="#7b2cbf",
            linewidths=1.1,
            label="cross-station duplicate candidate",
        )
        ax.axhline(
            float(config["thresholds"].get("chlorophyll_warning_ug_l", 10.0)),
            color="#aa0000",
            linestyle="--",
            lw=0.9,
            label="10 µg/L threshold",
        )
        ax.set_title(f"{station.station_name}: observed, imputed, and flagged Chl-a")
        ax.set_ylabel("Chl-a (µg/L)")
        ax.legend(loc="upper right", fontsize=8, ncol=2)
    axes[-1].set_xlabel("Date")
    return save_figure(
        fig,
        config,
        "preprocessing_observed_imputed_timeline",
        {
            "script": "src/villarrica_forecaster/figures/preprocessing_qa.py",
            "source_data": str(source_path),
            "purpose": "QA timeline showing observed, imputed, low-support, and duplicate-candidate Chl-a values.",
        },
    ) | {"source": source_path}


def spike_review_timeline(config: dict[str, Any]) -> dict[str, Path]:
    processed_dir = path_from_config(config, "processed_data")
    tables_dir = path_from_config(config, "tables")
    daily = pd.read_csv(processed_dir / "daily_chl_a.csv", parse_dates=["date"])
    spike_path = tables_dir / "chlorophyll_spike_review.csv"
    spikes = (
        pd.read_csv(spike_path, parse_dates=["date"]) if spike_path.exists() else pd.DataFrame()
    )
    source = daily[
        daily["is_high_chl"]
        | daily["is_abrupt_observed_transition"]
        | daily["is_cross_station_duplicate_candidate"]
    ].copy()
    source["date"] = source["date"].dt.date.astype(str)
    source_path = write_csv(source, tables_dir / "spike_review_timeline_source.csv")

    apply_manuscript_style()
    stations = list(daily[["station_id", "station_name"]].drop_duplicates().itertuples(index=False))
    fig, axes = plt.subplots(len(stations), 1, figsize=(13, 3.6 * len(stations)), sharex=True)
    if len(stations) == 1:
        axes = [axes]
    for ax, station in zip(axes, stations, strict=True):
        frame = daily[daily["station_id"].eq(station.station_id)].sort_values("date")
        station_spikes = (
            spikes[spikes["station_id"].eq(station.station_id)] if not spikes.empty else spikes
        )
        ax.plot(frame["date"], frame["chl_a_model"], color="#9aa0a6", lw=0.9, label="model input")
        ax.scatter(
            frame.loc[frame["is_high_chl"], "date"],
            frame.loc[frame["is_high_chl"], "chl_a_model"],
            color="#d55e00",
            s=28,
            label="high Chl-a retained",
        )
        ax.scatter(
            frame.loc[frame["is_abrupt_observed_transition"], "date"],
            frame.loc[frame["is_abrupt_observed_transition"], "chl_a_model"],
            color="#cc0000",
            marker="x",
            s=44,
            label="abrupt transition review",
        )
        if not station_spikes.empty:
            ax.set_title(
                f"{station.station_name}: {len(station_spikes)} spike/high-value review rows"
            )
        else:
            ax.set_title(f"{station.station_name}: no spike-review rows")
        ax.set_ylabel("Chl-a (µg/L)")
        ax.legend(loc="upper right", fontsize=8)
    axes[-1].set_xlabel("Date")
    return save_figure(
        fig,
        config,
        "spike_review_timeline",
        {
            "script": "src/villarrica_forecaster/figures/preprocessing_qa.py",
            "source_data": str(source_path),
            "spike_review_table": str(spike_path),
            "purpose": "Reviewer-facing visual QA of retained high Chl-a and abrupt-transition review candidates.",
        },
    ) | {"source": source_path}
