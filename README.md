# Villarrica chlorophyll forecasting revision pipeline

This repository now contains a reproducible Python pipeline for rebuilding the Lake Villarrica chlorophyll manuscript figures and generating reviewer-response evidence.

The pipeline is intentionally evidence-first: if a manuscript claim cannot be reproduced from local files, the generated reports mark it as `needs_author_input` rather than inventing values.

## Quick start

Recommended Python: **3.11**.

```bash
poetry install --with dev
poetry run villarrica-run-all --config configs/project.toml
poetry run pytest
poetry run ruff check .
```

Forecast figures are strict by default: `configs/project.toml` sets
`allow_local_baseline_fallback = false`. Figures 4–7 are blocked unless
`data/processed/foundation_model_predictions.csv` contains validated rolling-origin
TimesFM and Chronos Large forecasts for horizons 1–30. To generate that cache when
the optional model runtime/checkpoints are available, run:

```bash
poetry run villarrica-run-foundation --config configs/project.toml
poetry run villarrica-run-all --config configs/project.toml
```

Without installing the package, the scripts can be run directly if the dependencies are available:

```bash
python3.11 scripts/run_pipeline.py --config configs/project.toml
python3.11 scripts/recreate_figures.py --config configs/project.toml
```

## Main outputs

- `data/processed/canonical_observations.csv`
- `data/processed/daily_chl_a.csv`
- `outputs/tables/data_inventory.csv`
- `outputs/tables/preprocessing_footprint.csv`
- `outputs/tables/forecast_metrics_by_horizon.csv`
- `outputs/tables/forecast_predictions_long.csv`
- `outputs/tables/lag_diagnostics_d7.csv`
- `outputs/tables/threshold_warning_metrics.csv`
- `outputs/tables/uncertainty_coverage.csv`
- `outputs/tables/cross_site_validation.csv`
- `outputs/tables/satellite_matchup_validation.csv`
- `figures/figure_02_preprocessing_workflow.mmd` plus rendered `.svg`/`.png` Mermaid exports
- `outputs/tables/figure_04_status.csv` / `figure_05_status.csv` / `figure_06_status.csv` / `figure_07_status.csv` when foundation predictions are missing
- `figures/figure_04_forecast_metrics_la_poza.*`, `figure_05_forecast_metrics_pucon.*`, `figure_06_forecasts_la_poza.*`, and `figure_07_forecasts_pucon.*` only after validated TimesFM/Chronos predictions are available
- `figures/figure_methodology_end_to_end.*`
- `reports/reviewer_response_matrix.csv`
- `reports/forecast_model_blockers.csv`

## Important scientific note

The current local repository contains buoy/station files under `raw_data/`, but it does not yet visibly contain satellite matchup tables, satellite imagery products, cached TimesFM/Chronos predictions, or the full historical 1989–2024 in-situ dataset claimed in the manuscript. The code therefore produces reproducible local-data evidence and explicit author-input requests for missing items. It does not substitute local baselines for manuscript TimesFM/Chronos forecast figures.
