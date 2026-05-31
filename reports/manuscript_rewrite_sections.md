# Manuscript rewrite sections and replacement text

Use this file as a practical editing guide for `Transformer Villarrica 200326.docx`. The numbering below follows the current manuscript structure. Text is written to be pasted and then adjusted stylistically by the authors. Claims marked **AUTHOR CONFIRM** need author verification before final submission.

## 0. Global edits before section-level rewriting

1. **Reduce satellite-integration claims unless satellite matchup data are added.** The current reproducible forecasts use univariate Chl-a context windows for TimesFM and Chronos. Do not state that satellite reflectance or spatial predictors are ingested by the forecasting architectures unless a satellite-feature experiment is added.
2. **Remove “near-perfect” language.** Replace with quantified errors from `outputs/tables/forecast_metrics_by_horizon.csv` and `outputs/tables/observed_only_forecast_metrics.csv`.
3. **Remove unsupported threshold-warning skill values.** The current manuscript table reporting high POD/F1 at 10 µg/L is not supported by the processed 2024 forecast target. Replace it with the generated threshold-warning tables and the limitation that no processed 2024 target exceedances occur.
4. **Replace old Figure 2.** Use `figures/figure_02_preprocessing_workflow.png` or `.svg` for the detailed preprocessing/forecast-input sequence diagram.
5. **Add a standalone methodology roadmap.** Use `figures/figure_methodology_end_to_end.png` or `.svg` to answer Reviewer 3.10 in simple terms.
6. **Insert uncertainty interval figure.** Use `figures/figure_08_uncertainty_intervals.png` or `.svg`. Because the current manuscript already has Figures 8–9 for threshold/cyanobacteria graphics, either renumber the current threshold figures or make the uncertainty figure Supplementary Figure S1.
7. **Condense Section 2.5.** Remove textbook derivations of Chronos, TSMixer, Naive Seasonal, TimesFM, exponential smoothing, and GRU. Keep citations, model role, input/output contract, and runtime configuration.

---

## 1. Title

### Current risk

The current title says “Using Satellite Observations and Machine Learning,” but the reproducible forecast models do not directly ingest satellite reflectance bands or satellite-derived spatial predictors.

### Safer replacement title

**Short-term forecasting of chlorophyll-a dynamics in Lake Villarrica using foundation time-series models and reproducible monitoring data**

### Alternative if authors provide satellite inversion evidence

**Satellite-supported chlorophyll-a estimation and short-term foundation-model forecasting in Lake Villarrica, northern Patagonia**

Use the second title only if Section 2.3 is expanded with validated satellite inversion equations and metrics.

---

## 2. Abstract replacement text

Replace the current abstract with the following calibrated version:

> This study evaluates short-term forecasting of chlorophyll-a (Chl-a) dynamics at two monitoring stations in Lake Villarrica, northern Patagonia, Chile, using reproducible station-level Chl-a time series and foundation time-series models. We audited local station workbooks for Pucón and La Poza, generated provenance-tracked daily Chl-a targets, and explicitly quantified the proportion of direct observations and reconstructed values. The forecasting experiments used univariate Chl-a context windows as inputs to TimesFM and Chronos Large and evaluated 1–30 day horizons under a rolling-origin design. Short-horizon skill was highest at the 1-day horizon: at La Poza, D1 MAE was 0.099 µg/L for TimesFM and 0.106 µg/L for Chronos Large; at Pucón, D1 MAE was 0.063 µg/L for TimesFM and 0.071 µg/L for Chronos Large. Forecast error increased with lead time, with D28 MAE ranging from 0.606 to 0.757 µg/L across stations and models. Lag diagnostics showed that most D7 forecast cases had maximum correlation at lag 0, although Pucón Chronos Large showed a non-zero best lag, indicating that peak timing remains uncertain for warning applications. We also evaluated q10/q50/q90 predictive intervals and observed/gap-stratified performance. The results support the use of foundation time-series models for short-term forecasting of reconstructed Chl-a products, while highlighting limitations due to imputation, missing exogenous drivers, and the absence of validated satellite-feature ingestion in the current forecast architecture.

**Evidence paths:** `outputs/tables/forecast_metrics_by_horizon.csv`, `outputs/tables/lag_diagnostics_d7.csv`, `outputs/tables/uncertainty_coverage.csv`, `outputs/tables/preprocessing_footprint.csv`.

---

## 3. Highlights replacement text

Replace current highlights with:

- TimesFM and Chronos Large produced the strongest short-horizon forecasts from univariate Chl-a context windows, with D1 MAE between 0.063 and 0.106 µg/L across the two stations.
- Forecast skill degraded with horizon: D7 forecasts retained the broad seasonal envelope, while D14–D28 forecasts showed increasing amplitude damping and timing uncertainty.
- The final daily target is reconstruction-aware rather than fully observed; direct observations account for 45.9% of La Poza and 55.6% of Pucón daily records in the local reproducible dataset.
- Reviewer-oriented diagnostics now include observed-only scoring, gap-stratified metrics, D7 lag analysis, threshold-warning verification tables, q10/q50/q90 uncertainty coverage, and a cross-site transfer limitation analysis.

---

## 4. Section 2.2 — In-situ and monitoring data

### Replacement text

> Water-quality observations were compiled for two nearshore monitoring stations in Lake Villarrica: Pucón and La Poza. The reproducible local dataset used in this revision consists of 13 station workbook exports located under `raw_data/`: 10 files assigned to La Poza and 3 files assigned to Pucón. Each file was inventoried with its raw path, SHA-256 hash, file type, station label, sheet/table name, raw row count, variable names, units, date range, and date-parsing status. The local audited files cover 2022-08-22 to 2025-05-09 for La Poza and 2021-07-28 to 2025-05-09 for Pucón. For mean Chl-a, the local source tables contain 623 rows over 480 unique dates at La Poza and 827 rows over 788 unique dates at Pucón.
>
> The measured variables include Chl-a (µg/L), phycocyanin (µg/L), water temperature (°C), turbidity (NTU), dissolved oxygen (ppm or % saturation, depending on source file), dissolved organic matter (QSU), and pH where available. Source files used mixed spreadsheet formats, including HTML-XLS exports and XLSX workbooks. One Pucón source contained mixed slash-date and Excel-serial date encodings; these rows were repaired only where the repair restored chronological order, and the raw date value and parsing method were retained for provenance.
>
> **AUTHOR CONFIRM:** Historical DGA field-campaign information from 1989–2024, including the reported 385 discrete limnological sampling events, sampling depth, bottle type, preservation, filtration, extraction, and laboratory protocol, should be retained only after the authors confirm the original documentation. If confirmed, this historical field-campaign dataset should be described separately from the local high-frequency station workbook exports used in the reproducible forecast pipeline.

**Evidence paths:** `outputs/tables/data_inventory.csv`, `outputs/tables/station_date_coverage.csv`, `outputs/tables/mixed_date_encoding_audit.csv`.

---

## 5. Section 2.3 — Satellite data and remote-sensing inversion

### Required decision

The current local repository does **not** contain satellite reflectance/index matchup data or inversion validation outputs. Use one of the two versions below.

### Version A — if satellite matchup/inversion data are supplied

> Sentinel-2 MSI and Landsat 8/9 OLI products were processed to surface reflectance and screened using cloud and water-quality masks. For each in-situ station/date matchup, satellite pixels were extracted within [AUTHOR FILL: buffer/window] and paired with in-situ Chl-a measured within [AUTHOR FILL: temporal window]. The following spectral indices were evaluated: [AUTHOR FILL: index formulas, e.g., NDCI, red-edge ratios, band ratios]. Empirical/semi-empirical inversion models were fitted using [AUTHOR FILL: model forms], with train/test splits defined by [AUTHOR FILL]. Validation metrics were [AUTHOR FILL: RMSE, MAE, bias, R², n]. Satellite-derived Chl-a was then used as [AUTHOR FILL: either target construction, covariate, or validation layer]. The foundation-model forecasts reported in Section 3 used [AUTHOR FILL: univariate Chl-a target only / multivariate satellite features], as specified in Section 2.5.

### Version B — if no satellite matchup/inversion data are supplied

> Satellite observations provide regional monitoring context and motivate the broader pigment-estimation framework, but the reproducible forecasting experiments reported here do not directly ingest satellite reflectance bands, spectral indices, or spatial predictors. In the current pipeline, TimesFM and Chronos Large use univariate daily Chl-a context windows as inputs. Because the local revision package does not contain a satellite matchup table, inversion coefficients, or validation metrics, we do not present new satellite inversion claims in this manuscript. Future work should integrate validated satellite-derived Chl-a or spatial predictors once matchup uncertainty, cloud screening, and point-pixel mismatch are quantified.

**Evidence path:** `outputs/tables/satellite_matchup_validation.csv`.

---

## 6. Section 2.4.1 — Temporal alignment and reconstruction

### Replacement text

> Daily Chl-a targets were constructed from irregular station observations using a provenance-preserving preprocessing pipeline. For each station, source observations were first aggregated to daily means while retaining source-file paths, source rows, source counts, and quality flags. The resulting daily modeling series contains 941 days for La Poza and 1331 days for Pucón. Direct observations account for 432 days at La Poza (45.9%) and 740 days at Pucón (55.6%). Reconstructed/imputed values account for 527 days at La Poza (56.0%) and 685 days at Pucón (51.5%).
>
> For the 2024 forecast evaluation target, direct observations were preserved exactly. Short bracketed gaps were filled using shape-preserving PCHIP interpolation only when valid neighboring observations existed. Longer gaps were reconstructed using a historical day-of-year baseline combined with harmonic seasonal fitting and analog residual structure. The final target records the imputation method for each value and retains flags for direct observations, missing-before-imputation, interpolated values, imputed values, outlier handling, smoothing, and source observation count. The final accepted target used for the refreshed foundation-model forecasts was not smoothed.
>
> Because the 2024 forecast target remains reconstruction-dominated (102/366 direct observed days at La Poza and 106/366 at Pucón), all model results are interpreted as forecasts of a reconstructed daily Chl-a product rather than a fully observed daily in-situ series.

**Evidence paths:** `outputs/tables/preprocessing_footprint.csv`, `outputs/tables/realistic_imputation_diagnostics.csv`, `data/processed/daily_chl_a.csv`, `data/processed/realistic_imputed_chl_a_2024.csv`.

---

## 7. Section 2.4.2 — Outlier handling and smoothing

### Replacement text

> Potentially anomalous Chl-a values were flagged for review rather than automatically interpreted as either artifacts or true blooms. The pipeline records IQR-based outlier flags, abrupt-transition flags, high-Chl-a review flags, and whether a value was replaced in the modeling target. The generated QA table identified 18 La Poza and 94 Pucón direct observations requiring review before they can be treated as confirmed blooms or confirmed artifacts. These flags are retained in the forecast target and in prediction tables. The final accepted 2024 target used for model evaluation did not apply Savitzky–Golay smoothing (`smoothed_count = 0`), so the reported forecast results are not based on an SG-smoothed target.

**Evidence paths:** `outputs/tables/chlorophyll_spike_review.csv`, `reports/data_qa_blockers.csv`, `outputs/tables/preprocessing_footprint.csv`.

---

## 8. Section 2.5 — Model architecture and input/output design

### Replacement text

> We evaluated two pretrained foundation time-series models, TimesFM and Chronos Large, as zero-shot forecasters for daily Chl-a. Both models were applied to univariate Chl-a context windows; satellite reflectance bands or spatial predictors were not directly ingested by the forecast architectures in the reproducible experiments reported here. Forecasts were generated for horizons 1–30 days using a context length of up to 1024 daily values. TimesFM used the `google/timesfm-2.0-500m-pytorch` checkpoint, and Chronos Large used `amazon/chronos-t5-large`. The models returned point forecasts and q10/q50/q90 quantile forecasts where available. Runtime metadata, package versions, random seed, platform, and input-data hashes were stored with each model run to ensure reproducibility.
>
> We intentionally focus this section on model selection, input/output contracts, and runtime configuration rather than reproducing standard architectural derivations. Detailed theoretical descriptions of Chronos, TimesFM, GRU, TSMixer, and classical baselines are available in the cited model papers.

**Evidence paths:** `data/processed/foundation_20260531T200051Z_metadata.json`, `data/processed/foundation_20260531T200120Z_metadata.json`, `data/processed/forecast_evaluation_manifest.json`.

---

## 9. Section 2.6 — Model evaluation

### Replacement text

> Forecasts were evaluated with a rolling-origin design over the 2024 target window. To keep foundation-model inference reproducible and computationally tractable, forecast origins were spaced every 14 days, and each origin generated horizons 1–30 days. Metrics were computed by station, model, and horizon using MAPE, MSE, RMSE, bias, median absolute error, and MAE. In addition to standard horizon metrics, we computed observed-only metrics, gap-stratified metrics, D7 lag diagnostics, threshold-warning confusion matrices, q10/q90 interval coverage, and a preliminary cross-site transfer baseline. Observed-only metrics were treated as sensitivity checks because the number of direct observed targets in the 2024 rolling-origin grid is small.

**Evidence paths:** `outputs/tables/foundation_forecast_origin_plan.csv`, `outputs/tables/forecast_metrics_by_horizon.csv`, `outputs/tables/observed_only_forecast_metrics.csv`, `outputs/tables/gap_stratified_forecast_metrics.csv`.

---

## 10. Results Section 3.2 — Forecast metrics

### Replacement text

> TimesFM and Chronos Large showed the strongest skill at the 1-day horizon and progressively degraded with lead time at both stations (Figures 4 and 5). At La Poza, D1 MAE was 0.099 µg/L for TimesFM and 0.106 µg/L for Chronos Large; D7 MAE increased to 0.300 and 0.275 µg/L, respectively. By D28, MAE increased to 0.702 µg/L for TimesFM and 0.757 µg/L for Chronos Large. At Pucón, D1 MAE was 0.063 µg/L for TimesFM and 0.071 µg/L for Chronos Large; D7 MAE was 0.241 and 0.275 µg/L, respectively; and D28 MAE reached 0.606 and 0.679 µg/L. These results indicate useful short-horizon performance but clear horizon-dependent degradation.

**Evidence path:** `outputs/tables/forecast_metrics_by_horizon.csv`.

### Updated captions

**Figure 4.** Forecast performance metrics for TimesFM and Chronos Large at La Poza. Metrics are computed by rolling-origin forecast horizon (1–30 days) from validated foundation-model predictions. Panels show MAPE, MSE, RMSE, bias, median absolute error, and MAE. Source data: `outputs/tables/figure_04_source.csv`.

**Figure 5.** Forecast performance metrics for TimesFM and Chronos Large at Pucón. Metrics are computed by rolling-origin forecast horizon (1–30 days) from validated foundation-model predictions. Panels show MAPE, MSE, RMSE, bias, median absolute error, and MAE. Source data: `outputs/tables/figure_05_source.csv`.

---

## 11. Results Section 3.3 — Forecast trajectories and lag diagnostics

### Replacement text

> Forecast trajectories confirm that short-horizon predictions follow the broad Chl-a seasonal pattern, but they also show increasing amplitude damping and timing uncertainty with lead time (Figures 6 and 7). D7 lag diagnostics showed that the best correlation occurred at lag 0 for La Poza Chronos Large (r = 0.784), La Poza TimesFM (r = 0.774), and Pucón TimesFM (r = 0.860). Pucón Chronos Large was the exception, with the best D7 correlation at lag -14 days (best r = 0.790; lag-0 r = 0.743). Peak-date error was 14 days in all four D7 station/model combinations. These diagnostics indicate that D7 forecasts can capture the broad seasonal envelope but should not be interpreted as precise peak-timing forecasts.

**Evidence paths:** `outputs/tables/lag_diagnostics_d7.csv`, `outputs/tables/lag_correlation_by_model_d7.csv`.

### Updated captions

**Figure 6.** TimesFM and Chronos Large Chl-a forecasts at La Poza for 1-, 7-, 14-, and 28-day horizons. The blue line is the accepted daily Chl-a target; red and green markers/lines are model predictions at rolling forecast origins. Source data: `outputs/tables/figure_06_source.csv`.

**Figure 7.** TimesFM and Chronos Large Chl-a forecasts at Pucón for 1-, 7-, 14-, and 28-day horizons. The blue line is the accepted daily Chl-a target; red and green markers/lines are model predictions at rolling forecast origins. Source data: `outputs/tables/figure_07_source.csv`.

---

## 12. Results Section 3.5 — Threshold-warning analysis

### Replacement text

> We evaluated the 10 µg/L Chl-a threshold using binary-warning confusion matrices. For each station, model, and horizon, predictions and targets were classified as exceedance or non-exceedance, and true positives, false positives, true negatives, false negatives, sensitivity/POD, specificity/TNR, precision, F1, false-alarm ratio, missed-event rate, and overall accuracy were tabulated. In the processed 2024 forecast target, however, neither station exceeded the 10 µg/L threshold. Therefore, event-detection metrics such as POD, precision, F1, false-alarm ratio, and missed-event rate are not estimable from the current processed 2024 forecast subset. The threshold analysis is retained as a reproducible verification framework, but operational bloom-detection skill must be evaluated with confirmed historical exceedance events or a forecast target that includes verified threshold crossings.

**Evidence paths:** `outputs/tables/threshold_warning_metrics.csv`, `outputs/tables/threshold_warning_metrics_all_targets.csv`, `outputs/tables/threshold_event_summary.csv`.

### Delete/replace current table

Delete the current manuscript table claiming D1 POD of 96.2% and D7 POD of 84.6%. Those values are not supported by the current processed 2024 forecast target.

---

## 13. New Results subsection — Predictive uncertainty

### Replacement text

> We evaluated probabilistic forecast output using the cached q10 and q90 intervals from TimesFM and Chronos Large. At D7, empirical 10–90% interval coverage was 0.72 for La Poza TimesFM, 0.72 for La Poza Chronos Large, 0.88 for Pucón TimesFM, and 0.64 for Pucón Chronos Large, compared with the nominal 0.80 target. These results show that predictive intervals provide useful uncertainty information but are not uniformly calibrated across stations and models. Undercoverage for Pucón Chronos Large indicates that model-specific uncertainty should be interpreted cautiously for warning applications.

**Evidence paths:** `outputs/tables/uncertainty_coverage.csv`, `figures/figure_08_uncertainty_intervals.png`, `outputs/tables/figure_08_source.csv`.

### New figure caption

**Methodology roadmap figure.** End-to-end workflow for Lake Villarrica Chl-a forecasting. The flowchart shows data sources, provenance and QA, daily Chl-a target construction, forecast setup, TimesFM/Chronos execution, evaluation diagnostics, and reproducible manuscript outputs. The dashed satellite-inversion branch indicates that direct satellite-feature claims require validated matchup and inversion evidence. Source: `figures/figure_methodology_end_to_end.mmd`.

**Figure 8 or Supplementary Figure S1.** Predictive uncertainty intervals for D7 Chl-a forecasts. The blue line is the accepted daily Chl-a target, colored lines show q50 forecasts, and shaded envelopes show q10–q90 intervals for TimesFM and Chronos Large at Pucón and La Poza. Panel titles report empirical interval coverage and sample size. Source data: `outputs/tables/figure_08_source.csv`.

---

## 14. Discussion — Uncertainty sources and forecast reliability

### Replacement text

> Forecast uncertainty in this framework arises from several distinct sources. First, if satellite-derived pigment products are used in future versions of the pipeline, retrieval uncertainty must be quantified through station-date matchup validation, including atmospheric correction, cloud masking, optical complexity, and sensor-specific band limitations. Second, point-pixel mismatch can occur when nearshore in-situ or buoy measurements represent local water conditions that are not spatially equivalent to the satellite pixel or extraction window. Third, the daily Chl-a target used here is partly reconstructed; direct observations account for 45.9% of La Poza and 55.6% of Pucón daily records in the local reproducible dataset, so imputation and gap-reconstruction uncertainty directly affect model evaluation. Fourth, forecast uncertainty increases with horizon as models rely increasingly on learned seasonal structure rather than recent observations. Finally, unresolved ecological drivers, including wind, stratification, tributary inputs, nutrient pulses, and meteorological forcing, likely contribute to bloom timing and amplitude errors.
>
> The q10/q50/q90 interval analysis confirms that uncertainty is model- and station-dependent. D7 empirical coverage ranged from 0.64 to 0.88 across station/model combinations, indicating that intervals are informative but not fully calibrated. Consequently, medium-range degradation should not be attributed exclusively to intrinsic ecological unpredictability. It reflects a combination of missing exogenous drivers, reconstruction uncertainty, model horizon effects, and, where satellite data are used, retrieval and matchup uncertainty.

**Evidence paths:** `outputs/tables/preprocessing_footprint.csv`, `outputs/tables/uncertainty_coverage.csv`, `outputs/tables/lag_diagnostics_d7.csv`, `outputs/tables/satellite_matchup_validation.csv`.

---

## 15. Discussion — Cross-site validation limitation

### Replacement text

> The present foundation-model results should be interpreted as station-specific rolling-origin forecasts rather than proof of cross-site or cross-lake generalization. A preliminary transferred day-of-year climatology baseline showed substantial transfer error, particularly for Pucón→La Poza (MAPE = 75.9%) and La Poza→Pucón (MAPE = 25.6%). Because this diagnostic is not a transferred-context TimesFM/Chronos experiment, it is reported as a limitation. Demonstrating generalizability will require explicit transferred-context foundation-model tests and, ideally, validation on independent Patagonian lakes.

**Evidence path:** `outputs/tables/cross_site_validation.csv`.

---

## 16. Conclusion replacement text

> This study provides a reproducible evaluation of foundation time-series models for short-term Chl-a forecasting at two Lake Villarrica monitoring stations. TimesFM and Chronos Large showed strong short-horizon skill, with lowest errors at D1 and systematic degradation toward D14–D28 horizons. The revised analysis also shows that forecast interpretation must be reconstruction-aware: the daily target is not fully observed, and imputed/reconstructed values make up a substantial portion of the modeled daily series. Additional diagnostics demonstrate that D7 forecasts generally capture broad seasonal dynamics but do not guarantee exact peak timing; q10–q90 intervals are informative but not uniformly calibrated; and threshold-warning skill at 10 µg/L cannot be estimated from the processed 2024 target because no verified processed-target exceedances occur. Therefore, the main contribution is a transparent, code-backed forecasting and diagnostic workflow rather than a claim of direct satellite-feature integration or universal cross-site generalization. Future work should integrate validated satellite inversion products, meteorological and hydrodynamic drivers, confirmed bloom-event records, and independent lakes to strengthen operational early-warning capacity.

---

## 17. Reference list additions / checks

Check that the following are cited where relevant:

- TimesFM: Das et al. (2024).
- Chronos: Ansari et al. (2024).
- Forecasting/error metrics: Hyndman and Athanasopoulos (2018) or equivalent.
- WHO thresholds: WHO / Chorus and Welker (2021), but ensure units are correct and do not claim threshold-warning skill where no events exist.
- Remote-sensing inversion references only if actual inversion formulas and validation are included.

---

## 18. Items requiring author decision before final manuscript edit

1. Confirm whether the historical 1989–2024 / 385-event field-campaign dataset is available and whether its sampling/laboratory methods can be documented.
2. Decide whether to provide satellite matchup/inversion data or reduce satellite-methodology claims.
3. Confirm whether high Chl-a values flagged in `outputs/tables/chlorophyll_spike_review.csv` are true bloom observations or artifacts.
4. Decide whether to run a true transferred-context TimesFM/Chronos cross-site evaluation or state cross-site generalization as a limitation.
5. Decide whether the uncertainty interval figure should be a main figure or supplementary figure to avoid conflicting with current Figure 8/9 numbering.
