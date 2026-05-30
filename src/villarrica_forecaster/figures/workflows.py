from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.figures.common import apply_manuscript_style, save_figure
from villarrica_forecaster.io import utc_now_iso, write_json


def build_workflow_figures(config: dict[str, Any]) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    for key, value in figure_02_preprocessing_workflow(config).items():
        outputs[f"figure_02_{key}"] = value
    for key, value in figure_methodology_end_to_end(config).items():
        outputs[f"figure_methodology_{key}"] = value
    return outputs


def figure_02_preprocessing_workflow(config: dict[str, Any]) -> dict[str, Path]:
    """Write and render Figure 2 from Mermaid sequence-diagram source."""

    figures_dir = path_from_config(config, "figures")
    figures_dir.mkdir(parents=True, exist_ok=True)
    stem = "figure_02_preprocessing_workflow"
    mermaid_path = figures_dir / f"{stem}.mmd"
    svg_path = figures_dir / f"{stem}.svg"
    png_path = figures_dir / f"{stem}.png"
    metadata_path = figures_dir / f"{stem}.metadata.json"
    css_path = Path(config["_repo_root"]) / "configs" / "figure_02_mermaid.css"
    mermaid_path.write_text(figure_02_mermaid_source(), encoding="utf-8")
    render_results = _render_mermaid(mermaid_path, svg_path, png_path, css_path, config)
    write_json(
        {
            "created_utc": utc_now_iso(),
            "script": "src/villarrica_forecaster/figures/workflows.py",
            "source_data": str(mermaid_path),
            "style_css": str(css_path),
            "purpose": "Mermaid sequence-diagram recreation of manuscript Figure 2 for reviewer response R3.9.",
            "renderer": render_results,
        },
        metadata_path,
    )
    return {"mmd": mermaid_path, "svg": svg_path, "png": png_path, "metadata": metadata_path}


def figure_02_mermaid_source() -> str:
    """Return Mermaid source for the manuscript-style preprocessing sequence diagram."""

    return """%%{init: {"theme": "base", "themeVariables": {"fontFamily": "Arial", "fontSize": "18px", "primaryColor": "#F7FBFF", "primaryBorderColor": "#2F4858", "primaryTextColor": "#1F2933", "lineColor": "#33658A", "actorBorder": "#2F4858", "actorBkg": "#E8F1F2", "actorTextColor": "#1F2933", "activationBkgColor": "#D7EAF3", "activationBorderColor": "#33658A", "noteBkgColor": "#FFF3BF", "noteBorderColor": "#E0A800"}, "sequence": {"diagramMarginX": 18, "diagramMarginY": 18, "actorMargin": 38, "messageMargin": 40, "mirrorActors": true, "bottomMarginAdj": 12, "useMaxWidth": true, "rightAngles": false}}}%%
sequenceDiagram
    autonumber
    box rgba(232, 241, 242, 0.75) Data acquisition and provenance
    participant RD as Raw Data
    participant PP as Preprocessor
    end
    box rgba(255, 243, 191, 0.65) Gap handling and signal processing
    participant IM as Imputation Module
    participant SF as Signal Filter
    end
    box rgba(214, 234, 248, 0.70) Feature/model input construction
    participant FE as Feature Engineer
    participant TR as Transformer
    participant MI as Model Input
    end

    rect rgba(232, 241, 242, 0.35)
    RD->>PP: Tabular time series with station/date/value fields
    activate PP
    PP->>PP: Parse dates, normalize units, and validate flags
    PP->>PP: Resample to daily frequency
    PP->>PP: Identify missing days and invalid sentinel values
    end
    rect rgba(255, 243, 191, 0.35)
    PP->>IM: Request gap filling for missing daily values
    activate IM
    IM->>IM: Compute day-of-year or monthly baseline from available history
    IM-->>PP: Return filled series with imputation_method flags
    deactivate IM
    PP->>PP: Preserve observed-value and source-count masks
    PP->>SF: Send filled series for optional smoothing
    deactivate PP
    activate SF
    SF->>SF: Apply Savitzky-Golay filter when configured
    SF-->>FE: Return processed series plus smoothing flags
    deactivate SF
    end
    rect rgba(214, 234, 248, 0.35)
    activate FE
    FE->>FE: Add calendar, day-of-year, and cyclical encodings
    FE->>TR: Request model-ready normalization
    deactivate FE
    activate TR
    TR->>TR: Check variance and optional log transform
    TR->>MI: Build context window and forecast horizon tensors
    deactivate TR
    activate MI
    MI->>MI: Store model input with provenance and preprocessing masks
    deactivate MI
    end
"""


def _render_mermaid(
    mermaid_path: Path, svg_path: Path, png_path: Path, css_path: Path, config: dict[str, Any]
) -> dict[str, Any]:
    repo_root = Path(config["_repo_root"])
    cli = _mermaid_cli_command(repo_root)
    commands = [
        [
            *cli,
            "--input",
            str(mermaid_path),
            "--output",
            str(svg_path),
            "--backgroundColor",
            "white",
            "--cssFile",
            str(css_path),
            "--width",
            "1600",
        ],
        [
            *cli,
            "--input",
            str(mermaid_path),
            "--output",
            str(png_path),
            "--backgroundColor",
            "white",
            "--width",
            "1600",
            "--scale",
            "2",
            "--cssFile",
            str(css_path),
        ],
    ]
    executed: list[list[str]] = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        executed.append(command)
        if completed.stderr.strip():
            print(completed.stderr.strip())
    return {"command": executed, "source": str(mermaid_path), "css": str(css_path)}


def _mermaid_cli_command(repo_root: Path) -> list[str]:
    local_mmdc = repo_root / "node_modules" / ".bin" / "mmdc"
    if local_mmdc.exists():
        return [str(local_mmdc)]
    global_mmdc = shutil.which("mmdc")
    if global_mmdc:
        return [global_mmdc]
    npx = shutil.which("npx")
    if npx:
        return [npx, "-y", "@mermaid-js/mermaid-cli@11.15.0"]
    raise RuntimeError(
        "Mermaid rendering requires node/npm. Install Node.js and run "
        "`npm install`, or provide a global `mmdc` executable."
    )


def figure_methodology_end_to_end(config: dict[str, Any]) -> dict[str, Path]:
    apply_manuscript_style()
    fig, ax = plt.subplots(figsize=(12, 6.4))
    ax.axis("off")
    rows = [
        [
            "Raw acquisition\nstation spreadsheets",
            "Data inventory\nhashes + date coverage",
            "Canonical table\nstation/date/variable/value",
            "Quality validation\nunits + plausibility flags",
        ],
        [
            "Daily Chl-a series\nobserved/imputed masks",
            "Preprocessing variants\noutlier/interp/climatology/SG",
            "Forecast evaluation\nrolling origin horizons",
            "Diagnostics\nlag, threshold, uncertainty",
        ],
        [
            "Figures 4–7\nsource tables + vector exports",
            "Reviewer matrix\nartifact-linked responses",
            "Needs-author-input log\nmissing satellite/model inputs",
            "Manuscript revisions\nclaim support or reduction",
        ],
    ]
    for row_idx, row in enumerate(rows):
        y = 0.78 - row_idx * 0.30
        for col_idx, label in enumerate(row):
            x = 0.05 + col_idx * 0.24
            _box(ax, x, y, label, width=0.19, height=0.16)
            if col_idx < len(row) - 1:
                _arrow(ax, (x + 0.19, y + 0.08), (x + 0.24, y + 0.08))
        if row_idx < len(rows) - 1:
            _arrow(ax, (0.91, y), (0.05, y - 0.14), connectionstyle="arc3,rad=-0.35")
    ax.set_title("End-to-end reproducible methodology for reviewer-resolution outputs")
    return save_figure(
        fig,
        config,
        "figure_methodology_end_to_end",
        {
            "script": "src/villarrica_forecaster/figures/workflows.py",
            "purpose": "Methodology flowchart requested by Reviewer 3 comment 10.",
        },
    )


def _box(ax: plt.Axes, x: float, y: float, text: str, width: float, height: float) -> None:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.018",
        linewidth=1.1,
        edgecolor="#2F4858",
        facecolor="#E8F1F2",
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height / 2, text, ha="center", va="center", linespacing=1.25)


def _arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    connectionstyle: str = "arc3,rad=0.0",
) -> None:
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=1,
        color="#33658A",
        connectionstyle=connectionstyle,
    )
    ax.add_patch(arrow)
