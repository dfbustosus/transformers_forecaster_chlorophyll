# Compact reviewer responses (code-backed)

- **R1.3 (data description):** Added reproducible inventory and station/date coverage with file hashes, date ranges, units, and quality summaries. Response: `outputs/tables/data_inventory.csv`, `outputs/tables/station_date_coverage.csv`, `outputs/tables/preprocessing_footprint.csv`; local modeled daily series is 941 days (La Poza, 45.9% observed; 527 imputed) and 1331 days (Pucón, 55.6% observed; 685 imputed). Limitation: historical 1989–2024 metadata still required from authors.

- **R1.4 (preprocessing footprint):** Added flags for interpolation, imputation, outlier removal, smoothing and provenance in the daily target; plus observed-preserving 2024 reconstruction validation. Response: `outputs/tables/preprocessing_footprint.csv`, `outputs/tables/realistic_imputation_diagnostics.csv`, `figures/realistic_imputation_validation.png`/`.svg`.

- **R1.6 (7-day temporal shift):** Added lag diagnostics for D7 and updated captions/figures. Response: `outputs/tables/lag_diagnostics_d7.csv`, `outputs/tables/lag_correlation_by_model_d7.csv`; best lag is 0 for three station/model pairs, while Pucón Chronos has best lag -14.

- **R1.7 (threshold analysis):** Replaced narrative-only section with confusion-matrix warning metrics and event summary tables. Response: `outputs/tables/threshold_warning_metrics.csv`, `outputs/tables/threshold_warning_metrics_all_targets.csv`, `outputs/tables/threshold_event_summary.csv`; 2024 subset has no 10 µg/L exceedances, so POD/F1/precision cannot be estimated there.

- **R3.2/R3.3 (satellite inversion and claim scope):** Audited and marked as local-input limitation: local forecasts use univariate Chl-a only; no local validated satellite-to-Chl-a inversion inputs are reproducible. Response: `outputs/tables/satellite_matchup_validation.csv`, `reports/needs_author_input.md`, manifest files in `data/processed/*metadata*`.

- **R3.4 (condense theory / add diagnostics):** Condensed methodology text and added application diagnostics. Evidence includes `outputs/tables/forecast_metrics_by_horizon.csv`, `outputs/tables/observed_only_forecast_metrics.csv`, `outputs/tables/gap_stratified_forecast_metrics.csv`, `outputs/tables/uncertainty_coverage.csv`, `outputs/tables/lag_diagnostics_d7.csv`, `outputs/tables/cross_site_validation.csv`.

- **R3.5 (imputation learning risk):** Added observed-target holdout, gap-classified metrics, and imputation-aware flags in forecast rows. Evidence: `outputs/tables/observed_only_forecast_metrics.csv`, `outputs/tables/gap_stratified_forecast_metrics.csv`, `outputs/tables/preprocessing_footprint.csv`.

- **R3.7 (uncertainty):** Added q10/q50/q90 forecast intervals and empirical interval coverage; added a discussion-ready uncertainty section scaffold. Evidence: `outputs/tables/forecast_predictions_with_intervals.csv`, `outputs/tables/uncertainty_coverage.csv`, `figures/figure_08_uncertainty_intervals.png`/`.svg`.

- **R3.8 (cross-site validation):** Added reproducible day-of-year climatology transfer baseline (lower bound), and clearly labeled non-foundation-scope. Evidence: `outputs/tables/cross_site_validation.csv`.

- **R3.9/R3.10 (figures):** Rebuilt Figure 2 for legibility and added full methodology flowchart. Evidence: `figures/figure_02_preprocessing_workflow.*`, `figures/figure_methodology_end_to_end.*`.

- **Reviewer follow-up (Figure 6/7 readability):** Added supplementary 1:1 scatter diagnostics (S1, S2) and moved dense point-level comparison there. Evidence: `figures/figure_s1_predicted_vs_target_la_poza.*`, `figures/figure_s2_predicted_vs_target_pucon.*`, `outputs/tables/figure_s1_source.csv`, `outputs/tables/figure_s2_source.csv`.
