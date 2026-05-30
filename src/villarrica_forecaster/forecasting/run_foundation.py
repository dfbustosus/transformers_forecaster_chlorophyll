from __future__ import annotations

import argparse

from villarrica_forecaster.config import load_config
from villarrica_forecaster.forecasting.foundation import run_foundation_forecasts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run actual TimesFM/Chronos rolling-origin forecasts and cache one row per "
            "station/origin/model/horizon. This command may download large checkpoints."
        )
    )
    parser.add_argument("--config", default="configs/project.toml", help="Path to TOML config.")
    parser.add_argument(
        "--models",
        default="",
        help="Optional comma-separated model labels, e.g. 'TimesFM,Chronos Large'.",
    )
    args = parser.parse_args(argv)
    config = load_config(args.config)
    selected = {item.strip() for item in args.models.split(",") if item.strip()} or None
    outputs = run_foundation_forecasts(config, model_labels=selected)
    for key, value in outputs.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
