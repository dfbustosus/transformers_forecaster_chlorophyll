from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.io import utc_now_iso, write_json


def apply_manuscript_style() -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 7,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "figure.titlesize": 12,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "savefig.bbox": "tight",
        }
    )


def save_figure(
    fig: plt.Figure, config: dict[str, Any], stem: str, metadata: dict[str, Any]
) -> dict[str, Path]:
    figures_dir = path_from_config(config, "figures")
    figures_dir.mkdir(parents=True, exist_ok=True)
    dpi = int(config.get("figures", {}).get("dpi", 400))
    png = figures_dir / f"{stem}.png"
    svg = figures_dir / f"{stem}.svg"
    meta = figures_dir / f"{stem}.metadata.json"
    fig.savefig(png, dpi=dpi)
    fig.savefig(svg)
    write_json({"created_utc": utc_now_iso(), **metadata}, meta)
    plt.close(fig)
    return {"png": png, "svg": svg, "metadata": meta}


def station_label(station_id: str) -> str:
    return {"pucon": "Pucón", "la_poza": "La Poza"}.get(station_id, station_id)
