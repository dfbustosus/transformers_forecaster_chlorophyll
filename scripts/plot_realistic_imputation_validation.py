from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from villarrica_forecaster.config import load_config, path_from_config
from villarrica_forecaster.figures.common import apply_manuscript_style
from villarrica_forecaster.io import utc_now_iso, write_csv


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot one validation figure for the realistic 2024 Chl-a imputation."
    )
    parser.add_argument("--config", default="configs/project.toml")
    args = parser.parse_args()
    config = load_config(args.config)
    processed_dir = path_from_config(config, "processed_data")
    tables_dir = path_from_config(config, "tables")
    figures_dir = path_from_config(config, "figures")
    source_path = processed_dir / "realistic_imputed_chl_a_2024.csv"
    data = pd.read_csv(source_path, parse_dates=["date"])
    write_csv(_source_for_plot(data), tables_dir / "realistic_imputation_validation_source.csv")
    figures_dir.mkdir(parents=True, exist_ok=True)
    figure_paths = _plot(data, figures_dir)
    metadata = {
        "created_utc": utc_now_iso(),
        "script": "scripts/plot_realistic_imputation_validation.py",
        "source_data": str(source_path),
        "output_source_table": str(tables_dir / "realistic_imputation_validation_source.csv"),
        "purpose": "Single data-validation figure for 2024 realistic Chl-a imputation before any forecast rerun.",
        "smoothing": "none",
        "observed_values_preserved": True,
    }
    figure_paths["metadata"].write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    for kind, path in figure_paths.items():
        print(f"{kind}: {path}")
    return 0


def _source_for_plot(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    frame["date"] = frame["date"].dt.date.astype(str)
    return frame[
        [
            "date",
            "station_id",
            "station_name",
            "chl_a_observed",
            "chl_a_imputed",
            "is_observed",
            "imputation_method",
            "nearest_observation_gap_days",
            "gap_length_days",
            "imputation_uncertainty_proxy",
        ]
    ]


def _plot(data: pd.DataFrame, figures_dir: Path) -> dict[str, Path]:
    apply_manuscript_style()
    plt.rcParams.update(
        {
            "figure.titlesize": 15,
            "figure.titleweight": "bold",
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "legend.fontsize": 8,
        }
    )
    stations = list(data[["station_id", "station_name"]].drop_duplicates().itertuples(index=False))
    fig, axes = plt.subplots(len(stations), 1, figsize=(14, 4.6 * len(stations)), sharex=True)
    if len(stations) == 1:
        axes = [axes]
    colors = {"la_poza": "#2B8CBE", "pucon": "#F28E2B"}
    for ax, station in zip(axes, stations, strict=True):
        frame = data[data["station_id"].eq(station.station_id)].sort_values("date")
        observed = frame[frame["is_observed"]]
        short_gap = frame[frame["imputation_method"].str.contains("pchip", case=False, na=False)]
        long_gap = frame[
            frame["imputation_method"].str.contains("seasonal_harmonic", case=False, na=False)
        ]
        color = colors.get(station.station_id, "#2B8CBE")
        uncertainty = frame["imputation_uncertainty_proxy"].astype(float)
        lower = (frame["chl_a_imputed"].astype(float) - uncertainty).clip(lower=0.0)
        upper = frame["chl_a_imputed"].astype(float) + uncertainty
        ax.fill_between(
            frame["date"],
            lower,
            upper,
            color=color,
            alpha=0.12,
            label="imputation uncertainty proxy",
        )
        ax.plot(
            frame["date"],
            frame["chl_a_imputed"],
            color=color,
            linewidth=1.5,
            label="realistic imputed daily Chl-a",
        )
        ax.scatter(
            observed["date"],
            observed["chl_a_observed"],
            s=28,
            facecolors="white",
            edgecolors="black",
            linewidths=0.8,
            label="direct observations preserved",
            zorder=4,
        )
        ax.scatter(
            short_gap["date"],
            short_gap["chl_a_imputed"],
            s=12,
            color="#4DAF4A",
            alpha=0.45,
            label="short-gap PCHIP fills",
            zorder=3,
        )
        ax.scatter(
            long_gap["date"],
            long_gap["chl_a_imputed"],
            s=10,
            color="#984EA3",
            alpha=0.35,
            label="seasonal/harmonic fills",
            zorder=2,
        )
        ax.set_title(f"{station.station_name}: 2024 realistic Chl-a imputation validation")
        ax.set_ylabel("Chlorophyll-a (µg/L)")
        ax.set_ylim(bottom=0)
        ax.legend(loc="upper right", ncol=2)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.tick_params(axis="x", rotation=35)
    axes[-1].set_xlabel("Date")
    fig.suptitle("Realistic 2024 Chl-a imputation validation — data only, no forecasting")
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    png = figures_dir / "realistic_imputation_validation.png"
    svg = figures_dir / "realistic_imputation_validation.svg"
    metadata = figures_dir / "realistic_imputation_validation.metadata.json"
    fig.savefig(png, dpi=400)
    fig.savefig(svg)
    plt.close(fig)
    return {"png": png, "svg": svg, "metadata": metadata}


if __name__ == "__main__":
    raise SystemExit(main())
