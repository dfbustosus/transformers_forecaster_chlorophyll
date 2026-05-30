from __future__ import annotations

import argparse
from pathlib import Path

from villarrica_forecaster.config import ensure_output_directories, load_config
from villarrica_forecaster.data.ingest import build_ingestion_outputs
from villarrica_forecaster.diagnostics.lag import build_lag_outputs
from villarrica_forecaster.diagnostics.thresholds import build_threshold_outputs
from villarrica_forecaster.diagnostics.uncertainty import build_uncertainty_outputs
from villarrica_forecaster.figures.recreate_all import recreate_all_figures
from villarrica_forecaster.forecasting.cross_site import build_cross_site_outputs
from villarrica_forecaster.forecasting.evaluation import build_forecast_outputs
from villarrica_forecaster.preprocessing.daily import build_daily_chlorophyll
from villarrica_forecaster.remote_sensing.inversion import build_satellite_matchup_audit
from villarrica_forecaster.reports.reviewer_matrix import build_reviewer_response_matrix


def run_pipeline(config_path: str | Path = "configs/project.toml") -> dict[str, Path]:
    """Run the full local reproducibility pipeline."""

    config = load_config(config_path)
    ensure_output_directories(config)
    outputs: dict[str, Path] = {}
    outputs.update(build_ingestion_outputs(config))
    outputs.update(build_daily_chlorophyll(config))
    outputs.update(build_forecast_outputs(config))
    outputs.update(build_lag_outputs(config))
    outputs.update(build_threshold_outputs(config))
    outputs.update(build_uncertainty_outputs(config))
    outputs.update(build_cross_site_outputs(config))
    outputs.update(build_satellite_matchup_audit(config))
    outputs.update(build_reviewer_response_matrix(config))
    outputs.update(recreate_all_figures(config_path))
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Villarrica reviewer-resolution pipeline.")
    parser.add_argument(
        "--config", default="configs/project.toml", help="Path to project TOML config."
    )
    args = parser.parse_args(argv)
    outputs = run_pipeline(args.config)
    print(f"Generated {len(outputs)} output artifacts.")
    for name, path in sorted(outputs.items()):
        print(f"- {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
