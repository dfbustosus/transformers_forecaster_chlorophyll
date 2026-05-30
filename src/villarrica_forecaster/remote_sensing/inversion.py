from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.io import write_csv


def build_satellite_matchup_audit(config: dict[str, Any]) -> dict[str, Path]:
    """Write an explicit satellite-data audit artifact for Reviewer 3.

    The current repository does not expose Sentinel/Landsat matchup tables or spectral
    bands. This function creates a machine-readable limitation report instead of
    fabricating inversion metrics.
    """

    tables_dir = path_from_config(config, "tables")
    reports_dir = path_from_config(config, "reports")
    row = {
        "artifact": "satellite_matchup_validation",
        "status": "needs_author_input",
        "local_input_found": False,
        "required_input": (
            "A table containing station_id, date, in-situ Chl-a, satellite sensor, "
            "pixel/ROI reflectance bands, QA/cloud mask, matchup distance/window, "
            "and train/test split identifiers."
        ),
        "reason": (
            "The local raw_data directory contains buoy/station spreadsheet exports but no "
            "satellite reflectance products, spectral indices, matchup table, or inversion outputs."
        ),
        "claim_risk": (
            "Title/abstract and Section 2.3 claims about satellite plus ML integration must be "
            "reduced unless these inputs are provided and validated."
        ),
    }
    csv_path = write_csv(pd.DataFrame([row]), tables_dir / "satellite_matchup_validation.csv")
    report_path = reports_dir / "needs_author_input.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# Needs author input\n\n"
        "The reproducible local repository is missing evidence required for several manuscript claims.\n\n"
        "## Satellite inversion and matchup validation\n\n"
        f"- Status: `{row['status']}`\n"
        f"- Required input: {row['required_input']}\n"
        f"- Reason: {row['reason']}\n\n"
        "## Foundation-model forecast recreation\n\n"
        "Figures 4–7 in the current manuscript name TimesFM and Chronos variants. "
        "The current repository does not contain cached TimesFM/Chronos prediction tables or "
        "the optional heavyweight model runtime. In strict manuscript mode the pipeline now "
        "blocks Figures 4–7 and writes forecast_model_blockers.csv instead of substituting "
        "local baseline forecasts. Cached predictions or executable model dependencies are "
        "required for TimesFM/Chronos claims.\n\n"
        "## Historical monitoring record\n\n"
        "The manuscript claims long-term records from 1989–2024 and 385 sampling events. "
        "The files currently visible under raw_data mainly cover 2021–2025 buoy/station exports. "
        "The full historical in-situ table is needed before those claims can be verified.\n",
        encoding="utf-8",
    )
    return {"satellite_matchup_validation": csv_path, "needs_author_input": report_path}
