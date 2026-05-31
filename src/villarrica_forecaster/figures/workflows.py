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
    """Write and render Figure 2 from a Mermaid sequence-diagram source."""

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
            "renderer": render_results,
            "purpose": "Mermaid sequence-diagram recreation of manuscript Figure 2 for reviewer response R3.9, updated with code-backed provenance, QA gates, observed-preserving imputation, and forecast-blocking evidence.",
            "reviewer_comments_addressed": ["R1.3", "R1.4", "R3.5", "R3.9"],
        },
        metadata_path,
    )
    return {"mmd": mermaid_path, "svg": svg_path, "png": png_path, "metadata": metadata_path}


def figure_02_mermaid_source() -> str:
    """Return Mermaid source for the manuscript preprocessing sequence diagram."""

    return """%%{init: {"theme": "base", "htmlLabels": true, "securityLevel": "loose", "themeVariables": {"fontFamily": "Inter, Arial, Helvetica, sans-serif", "fontSize": "16px", "primaryTextColor": "#0F172A", "lineColor": "#334155", "actorBkg": "#F8FAFC", "actorBorder": "#334155", "actorTextColor": "#0F172A", "activationBkgColor": "#E0F2FE", "activationBorderColor": "#0284C7", "noteBkgColor": "#FFF7ED", "noteBorderColor": "#F97316", "noteTextColor": "#431407"}, "sequence": {"diagramMarginX": 18, "diagramMarginY": 20, "actorMargin": 30, "messageMargin": 28, "mirrorActors": true, "bottomMarginAdj": 10, "useMaxWidth": true, "rightAngles": false}}}%%
sequenceDiagram
    title Figure 2. Reproducible Chl-a preprocessing sequence and QA gate

    box rgba(255, 247, 237, 0.58) Raw data and provenance
    participant RD as Raw data
    participant IP as Ingestion<br/>provenance
    end

    box rgba(239, 246, 255, 0.58) Canonical target construction
    participant DT as Daily target<br/>builder
    end

    box rgba(245, 243, 255, 0.58) QA control and imputation
    participant QG as Data-QA<br/>gate
    participant IM as Imputation<br/>module
    end

    box rgba(236, 253, 245, 0.58) Model readiness
    participant FE as Feature builder
    participant MI as Model input
    end

    RD->>IP: Submit immutable HTML-XLS/XLSX station workbooks
    activate IP
    IP->>IP: Discover HTML-XLS/XLSX files and infer station from path
    IP->>IP: Compute SHA-256 hashes and retain file, sheet, row provenance
    alt Pucón mixed Excel serial dates detected and chronological repair is valid
        IP->>IP: Repair serial dates to Spanish DMY and preserve raw_date_value
    else Dates parse cleanly
        IP->>IP: Preserve parsed date and validation status
    end
    Note over IP: Evidence: data_inventory.csv<br/>raw_file_manifest.json<br/>mixed_date_encoding_audit.csv
    IP->>DT: Emit canonical station-date-variable observations
    deactivate IP

    activate DT
    DT->>DT: Normalize variables, statistics, units, and quality flags
    DT->>DT: Apply is_model_eligible and model_exclusion_reason filters
    DT->>DT: Aggregate station-day Chl-a means with source_count and source rows
    DT->>DT: Mark observed, missing, duplicate, spike, and outlier states
    Note over DT: Evidence: daily_chl_a.csv<br/>preprocessing_footprint.csv<br/>duplicate/spike review tables
    DT->>QG: Submit daily target plus QA evidence
    deactivate DT

    activate QG
    alt P0 blockers remain unresolved
        QG-->>MI: Block forecast reruns and manuscript model figures
        Note over QG: Current status: forecasts stay blocked until QA is accepted.
    else QA accepted for model construction
        QG->>IM: Authorize observed-preserving 2024 reference construction
    end
    deactivate QG

    activate IM
    IM->>IM: Preserve direct 2024 observations exactly with no smoothing or overwriting
    IM->>IM: Fill short bracketed gaps with PCHIP when both neighbors exist and gap ≤ 10 days
    IM->>IM: Fill long gaps with prior-year circular DOY climatology, harmonic Huber fit, and analog residuals
    IM->>IM: Apply boundary blending, cap imputed values only, and keep Savitzky-Golay out of final target
    Note over IM: Evidence: realistic_imputed_chl_a_2024.csv<br/>realistic_imputation_diagnostics.csv<br/>realistic_imputation_validation.png/.svg
    IM->>FE: Provide accepted target with imputation flags
    deactivate IM

    activate FE
    FE->>FE: Add calendar and cyclical covariates without changing target values
    FE->>MI: Build context windows, forecast horizons, and quantile contract
    deactivate FE

    activate MI
    MI->>MI: Validate strict cache schema before TimesFM/Chronos forecast figures are regenerated
    Note over MI: Model cache is regenerated only after QA acceptance.<br/>Reviewer matrix links each artifact to manuscript sections.
    deactivate MI
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
            "1500",
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
            "1500",
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
