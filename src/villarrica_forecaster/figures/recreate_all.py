from __future__ import annotations

import argparse
from pathlib import Path

from villarrica_forecaster.config import load_config
from villarrica_forecaster.figures.forecast_figures import build_forecast_figures
from villarrica_forecaster.figures.preprocessing_qa import build_preprocessing_qa_figures
from villarrica_forecaster.figures.workflows import build_workflow_figures


def recreate_all_figures(config_path: str | Path = "configs/project.toml") -> dict[str, Path]:
    config = load_config(config_path)
    outputs: dict[str, Path] = {}
    outputs.update(build_workflow_figures(config))
    outputs.update(build_preprocessing_qa_figures(config))
    outputs.update(build_forecast_figures(config))
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recreate manuscript and reviewer figures.")
    parser.add_argument(
        "--config", default="configs/project.toml", help="Path to project TOML config."
    )
    args = parser.parse_args(argv)
    recreate_all_figures(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
