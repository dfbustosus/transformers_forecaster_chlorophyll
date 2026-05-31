from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from villarrica_forecaster.config import path_from_config
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
            "purpose": "Publication-facing Mermaid sequence diagram for manuscript Figure 2, showing the reproducible Lake Villarrica Chl-a preprocessing, reconstruction, forecast-input, and evidence workflow.",
            "reviewer_comments_addressed": ["R1.3", "R1.4", "R3.5", "R3.9"],
        },
        metadata_path,
    )
    return {"mmd": mermaid_path, "svg": svg_path, "png": png_path, "metadata": metadata_path}


def figure_methodology_end_to_end(config: dict[str, Any]) -> dict[str, Path]:
    """Write and render the reviewer-requested end-to-end methodology roadmap."""

    figures_dir = path_from_config(config, "figures")
    figures_dir.mkdir(parents=True, exist_ok=True)
    stem = "figure_methodology_end_to_end"
    mermaid_path = figures_dir / f"{stem}.mmd"
    svg_path = figures_dir / f"{stem}.svg"
    png_path = figures_dir / f"{stem}.png"
    metadata_path = figures_dir / f"{stem}.metadata.json"
    css_path = Path(config["_repo_root"]) / "configs" / "methodology_flowchart_mermaid.css"

    mermaid_path.write_text(methodology_flowchart_mermaid_source(), encoding="utf-8")
    render_results = _render_mermaid(
        mermaid_path, svg_path, png_path, css_path, config, width="1900"
    )
    write_json(
        {
            "created_utc": utc_now_iso(),
            "script": "src/villarrica_forecaster/figures/workflows.py",
            "source_data": str(mermaid_path),
            "style_css": str(css_path),
            "renderer": render_results,
            "purpose": "End-to-end methodology roadmap requested by Reviewer 3 comment 10, rendered with Node/Mermaid from version-controlled source.",
            "reviewer_comments_addressed": ["R3.10"],
            "scientific_note": "The forecast-model box states the actual reproducible input contract: TimesFM and Chronos use univariate Chl-a context windows; satellite products require separate matchup/inversion validation before direct feature-ingestion claims.",
        },
        metadata_path,
    )
    return {"mmd": mermaid_path, "svg": svg_path, "png": png_path, "metadata": metadata_path}


def figure_02_mermaid_source() -> str:
    """Return Mermaid source for the manuscript preprocessing sequence diagram."""

    return """%%{init: {"theme": "base", "htmlLabels": true, "securityLevel": "loose", "themeVariables": {"fontFamily": "Inter, Arial, Helvetica, sans-serif", "fontSize": "16px", "primaryTextColor": "#0F172A", "lineColor": "#334155", "actorBkg": "#F8FAFC", "actorBorder": "#334155", "actorTextColor": "#0F172A", "activationBkgColor": "#E0F2FE", "activationBorderColor": "#0284C7", "noteBkgColor": "#F8FAFC", "noteBorderColor": "#94A3B8", "noteTextColor": "#334155"}, "sequence": {"diagramMarginX": 18, "diagramMarginY": 18, "actorMargin": 32, "messageMargin": 28, "mirrorActors": true, "bottomMarginAdj": 10, "useMaxWidth": true, "rightAngles": false}}}%%
sequenceDiagram
    title Figure 2. Reproducible preprocessing and forecast-input workflow for Lake Villarrica Chl-a

    box rgba(255, 247, 237, 0.58) Data acquisition and provenance
    participant RD as Raw station<br/>workbooks
    participant PV as Provenance<br/>registry
    end

    box rgba(239, 246, 255, 0.58) Canonical target construction
    participant CN as Canonical<br/>observations
    participant TG as Daily Chl-a<br/>target
    end

    box rgba(245, 243, 255, 0.58) Gap-aware target reconstruction
    participant RC as Reconstruction<br/>module
    end

    box rgba(236, 253, 245, 0.58) Model input and reviewer evidence
    participant FE as Feature and<br/>context builder
    participant FM as TimesFM /<br/>Chronos
    participant EV as Reproducible<br/>outputs
    end

    RD->>PV: Register immutable HTML-XLS/XLSX files from Pucón and La Poza
    activate PV
    PV->>PV: Assign station, sheet, row, and SHA-256 source provenance
    PV->>PV: Harmonize date encodings and retain raw_date_value and date_parse_method
    PV->>CN: Emit station-date-variable records with units and source lineage
    deactivate PV

    activate CN
    CN->>CN: Normalize Chl-a statistics, units, and quality flags
    CN->>CN: Retain model-eligibility and exclusion metadata for every row
    CN->>TG: Pass eligible Chl-a observations with provenance columns
    deactivate CN

    activate TG
    TG->>TG: Aggregate station-day means and source_count
    TG->>TG: Preserve observed, missing, duplicate, spike, and outlier masks
    TG->>RC: Send daily target plus preprocessing footprint
    deactivate TG

    activate RC
    RC->>RC: Preserve direct 2024 observations exactly
    RC->>RC: Fill short bracketed gaps with PCHIP when neighboring observations exist
    RC->>RC: Reconstruct long gaps from prior-year DOY climatology, harmonic Huber fit, and analog residuals
    RC->>RC: Blend gap boundaries and cap imputed values only, with no smoothing in the final target
    RC->>FE: Deliver accepted target with observed/imputed flags and uncertainty proxy
    deactivate RC

    activate FE
    FE->>FE: Add calendar and cyclical covariates without changing Chl-a target values
    FE->>FE: Build context windows, horizon grid, quantile contract, and cache schema
    FE->>FM: Run rolling-origin foundation-model forecasts
    deactivate FE

    activate FM
    FM->>FM: Generate point and q10/q50/q90 forecasts for horizons 1–30 days
    FM->>EV: Return predictions, interval estimates, and runtime metadata
    deactivate FM

    activate EV
    EV->>EV: Export source tables, figures, diagnostics, and reviewer-response matrix
    Note over EV: Outputs include data inventory, preprocessing footprint,<br/>realistic-imputation validation, forecast metrics, lag diagnostics,<br/>threshold metrics, uncertainty coverage, and figure source tables.
    deactivate EV
"""


def methodology_flowchart_mermaid_source() -> str:
    """Return Mermaid source for the simple end-to-end methodology flowchart."""

    return """%%{init: {"theme": "base", "htmlLabels": true, "securityLevel": "loose", "themeVariables": {"fontFamily": "Inter, Arial, Helvetica, sans-serif", "fontSize": "18px", "primaryTextColor": "#0F172A", "lineColor": "#334155", "mainBkg": "#FFFFFF", "clusterBkg": "#F8FAFC", "clusterBorder": "#CBD5E1", "edgeLabelBackground": "#FFFFFF"}, "flowchart": {"curve": "basis", "htmlLabels": true, "nodeSpacing": 34, "rankSpacing": 58, "padding": 16, "useMaxWidth": true}}}%%
flowchart LR
    A["<b>1. Data sources</b><br/>Station workbooks<br/>Pucón and La Poza<br/><br/>Satellite products<br/><span>validated separately</span>"]:::input
    B["<b>2. Provenance and QA</b><br/>File hashes and station IDs<br/>date repair and units<br/>duplicate / spike flags"]:::qc
    C["<b>3. Daily Chl-a target</b><br/>One daily series per station<br/>observed / interpolated / imputed flags<br/>no hidden preprocessing"]:::target
    D["<b>4. Forecast setup</b><br/>Calendar features<br/>1024-day Chl-a context<br/>horizons 1-30 days"]:::model
    E["<b>5. Foundation forecasts</b><br/>TimesFM and Chronos<br/>point forecasts<br/>q10 / q50 / q90 intervals<br/><span>current run: univariate Chl-a input</span>"]:::model
    F["<b>6. Evaluation</b><br/>Horizon errors<br/>observed-only checks<br/>lag diagnostics<br/>threshold and uncertainty metrics"]:::eval
    G["<b>7. Reproducible outputs</b><br/>Figures and source tables<br/>reviewer response matrix<br/>manuscript text with supported claims"]:::output

    H["<b>Satellite-inversion validation</b><br/>index formulas<br/>matchup table<br/>train/test split<br/>retrieval uncertainty"]:::satellite

    A --> B --> C --> D --> E --> F --> G
    A -.-> H
    H -. "required before direct satellite-feature claims" .-> C

    classDef satellite fill:#FFF7ED,stroke:#EA580C,color:#7C2D12,stroke-width:1.8px,font-weight:650;
    classDef input fill:#EFF6FF,stroke:#2563EB,color:#0F172A,stroke-width:1.8px;
    classDef qc fill:#F0FDFA,stroke:#0F766E,color:#0F172A,stroke-width:1.8px;
    classDef target fill:#F5F3FF,stroke:#7C3AED,color:#0F172A,stroke-width:1.8px;
    classDef model fill:#ECFDF5,stroke:#16A34A,color:#0F172A,stroke-width:1.8px;
    classDef eval fill:#FEFCE8,stroke:#CA8A04,color:#0F172A,stroke-width:1.8px;
    classDef output fill:#FDF2F8,stroke:#DB2777,color:#0F172A,stroke-width:1.8px;
"""


def _render_mermaid(
    mermaid_path: Path,
    svg_path: Path,
    png_path: Path,
    css_path: Path,
    config: dict[str, Any],
    *,
    width: str = "1700",
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
            width,
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
            width,
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
