# Villarrica chlorophyll forecasting revision pipeline

Reproducible Python and Mermaid/Node pipeline for the Lake Villarrica chlorophyll-a manuscript revision. The repository builds local data provenance tables, daily Chl-a targets, forecast diagnostics, reviewer-response evidence, and manuscript figures from version-controlled code and local data.

## Scope

- Raw station workbooks are read from `raw_data/` and are not modified.
- Reusable code lives in `src/villarrica_forecaster/`.
- Entry points are in `scripts/` and exposed as Poetry console scripts.
- Derived tables are written to `data/processed/` and `outputs/tables/`.
- Figures are written to `figures/` with source tables and metadata where applicable.
- Reviewer-response and manuscript-editing material is written to `reports/`.

The current reproducible forecast models use univariate daily Chl-a context windows. TimesFM and Chronos do not directly ingest satellite reflectance bands or spectral indices in the current pipeline. Satellite inversion/matchup validation is tracked separately in `outputs/tables/satellite_matchup_validation.csv`.

## Requirements

- Python `>=3.11,<3.13`
- Poetry
- Node.js and npm for Mermaid figure rendering
- Optional ML runtime for regenerating foundation-model predictions:
  - `timesfm`
  - `chronos-forecasting`
  - `torch`

## Install

Core pipeline and tests:

```bash
poetry install --with dev
```

Foundation-model inference:

```bash
poetry install --with dev,ml
```

Mermaid rendering:

```bash
npm install
```

## Main commands

Run the local reproducibility pipeline:

```bash
poetry run villarrica-run-all --config configs/project.toml
```

Recreate figures only:

```bash
poetry run villarrica-recreate-figures --config configs/project.toml
```

Regenerate actual TimesFM and Chronos Large rolling-origin predictions:

```bash
poetry run villarrica-run-foundation --config configs/project.toml --models "TimesFM,Chronos Large"
poetry run villarrica-run-all --config configs/project.toml
```

Render Mermaid workflow figures through Node/Mermaid:

```bash
npm run render:figure02
npm run render:methodology
```

Direct script equivalents:

```bash
python3.11 scripts/run_pipeline.py --config configs/project.toml
python3.11 scripts/recreate_figures.py --config configs/project.toml
python3.11 scripts/run_foundation_forecasts.py --config configs/project.toml --models "TimesFM,Chronos Large"
```

## Validation

```bash
poetry run pytest
poetry run ruff check .
poetry run ruff format --check .
poetry check
```

Optional render validation:

```bash
npm run render:figure02
npm run render:methodology
```

## Key outputs

### Data provenance and preprocessing

- `outputs/tables/data_inventory.csv`
- `outputs/tables/station_date_coverage.csv`
- `data/processed/canonical_observations.csv`
- `data/processed/daily_chl_a.csv`
- `outputs/tables/preprocessing_footprint.csv`
- `outputs/tables/preprocessing_footprint_by_month.csv`
- `outputs/tables/chlorophyll_spike_review.csv`
- `reports/data_qa_blockers.csv`

### Imputation and target reconstruction

- `data/processed/realistic_imputed_chl_a_2024.csv`
- `data/processed/realistic_imputation_manifest.json`
- `outputs/tables/realistic_imputation_diagnostics.csv`
- `figures/realistic_imputation_validation.png`
- `figures/realistic_imputation_validation.svg`

### Foundation forecasts and diagnostics

- `data/processed/foundation_model_predictions.csv`
- `data/processed/foundation_20260531T200051Z_metadata.json`
- `data/processed/foundation_20260531T200120Z_metadata.json`
- `data/processed/forecast_evaluation_manifest.json`
- `outputs/tables/foundation_forecast_origin_plan.csv`
- `outputs/tables/forecast_predictions_long.csv`
- `outputs/tables/forecast_predictions_with_intervals.csv`
- `outputs/tables/forecast_metrics_by_horizon.csv`
- `outputs/tables/observed_only_forecast_metrics.csv`
- `outputs/tables/gap_stratified_forecast_metrics.csv`
- `outputs/tables/lag_diagnostics_d7.csv`
- `outputs/tables/lag_correlation_by_model_d7.csv`
- `outputs/tables/threshold_warning_metrics.csv`
- `outputs/tables/threshold_warning_metrics_all_targets.csv`
- `outputs/tables/threshold_event_inventory.csv`
- `outputs/tables/threshold_event_summary.csv`
- `outputs/tables/uncertainty_coverage.csv`
- `outputs/tables/cross_site_validation.csv`
- `reports/forecast_model_blockers.csv`

### Remote-sensing audit

- `outputs/tables/satellite_matchup_validation.csv`

This table records whether local satellite matchup/inversion inputs are available. If no validated matchup table is present, the manuscript must not claim direct satellite-feature ingestion by TimesFM or Chronos.

### Figures

- `figures/figure_02_preprocessing_workflow.mmd`
- `figures/figure_02_preprocessing_workflow.svg`
- `figures/figure_02_preprocessing_workflow.png`
- `figures/figure_methodology_end_to_end.mmd`
- `figures/figure_methodology_end_to_end.svg`
- `figures/figure_methodology_end_to_end.png`
- `figures/figure_04_forecast_metrics_la_poza.png`
- `figures/figure_04_forecast_metrics_la_poza.svg`
- `figures/figure_05_forecast_metrics_pucon.png`
- `figures/figure_05_forecast_metrics_pucon.svg`
- `figures/figure_06_forecasts_la_poza.png`
- `figures/figure_06_forecasts_la_poza.svg`
- `figures/figure_07_forecasts_pucon.png`
- `figures/figure_07_forecasts_pucon.svg`
- `figures/figure_08_uncertainty_intervals.png`
- `figures/figure_08_uncertainty_intervals.svg`

Figure source tables are written under `outputs/tables/figure_*_source.csv`.

### Reviewer and manuscript material

- `reports/reviewer_response_matrix.csv`
- `reports/reviewer_response_matrix.md`
- `reports/reviewer_comments_response_draft.md`
- `reports/manuscript_rewrite_sections.md`

## Forecast cache rules

`configs/project.toml` sets `allow_local_baseline_fallback = false`. Forecast figures are generated only from validated TimesFM/Chronos predictions. If `data/processed/foundation_model_predictions.csv` is missing, stale, incomplete, or inconsistent with the current daily target, figure generation is blocked and `reports/forecast_model_blockers.csv` records the reason.

Each foundation run writes metadata with model identifier, package versions, random seed, platform, input-data hash, and output hash. Current retained metadata files correspond to the validated TimesFM and Chronos Large cache:

- `data/processed/foundation_20260531T200051Z_metadata.json`
- `data/processed/foundation_20260531T200120Z_metadata.json`

## Data limitations tracked by code

- The local forecast package contains station workbook exports, not the full historical 1989–2024 DGA source table.
- The local package does not contain satellite reflectance products, spectral-index matchup tables, inversion coefficients, or satellite retrieval validation metrics.
- The daily Chl-a target is reconstruction-aware; observed and imputed values are flagged in processed outputs.
- Threshold-warning detection skill at 10 µg/L is not estimated when the processed forecast target contains no threshold exceedance events.
- Cross-site generalization is not claimed from the current foundation-model runs; `outputs/tables/cross_site_validation.csv` is a local baseline diagnostic, not a transferred-context TimesFM/Chronos validation.

## Configuration

Primary configuration file:

- `configs/project.toml`

Mermaid figure styles:

- `configs/figure_02_mermaid.css`
- `configs/methodology_flowchart_mermaid.css`

Do not overwrite or edit files under `raw_data/` as part of pipeline execution.
