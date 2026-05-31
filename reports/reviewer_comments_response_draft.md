# Draft point-by-point responses to reviewers

This draft is written only from reproducible repository outputs and the current manuscript text in `Transformer Villarrica 200326.pdf`. Quantitative claims below cite generated evidence paths. Items marked **AUTHOR INPUT REQUIRED** should not be asserted until the authors confirm or provide the missing source material.

## Reviewer 1

### Comment 3

**Reviewer comment.** The description of the data is not detailed enough. Key information is needed on sampling methods, analytical procedures, temporal resolution, sample size, and the proportion of observed versus imputed values. Without these details, it is difficult to assess the reliability and reproducibility of the analysis.

**Action taken.** We added a reproducible data-inventory and provenance audit for all local station workbooks. The inventory records the raw file path, SHA-256 hash, file type, station, sheet/table, raw row count, date range, variables, units, date-encoding status, and repair decisions. We also added station-level coverage summaries and observed-versus-reconstructed proportions for the daily modeling target.

**Evidence generated.**

- `outputs/tables/data_inventory.csv`
- `outputs/tables/station_date_coverage.csv`
- `outputs/tables/preprocessing_footprint.csv`
- `outputs/tables/mixed_date_encoding_audit.csv`
- `reports/data_qa_blockers.csv`

**Key reproducible numbers.** The local raw-data folder contains 13 station workbooks: 10 for La Poza and 3 for Pucón. The audited local file date ranges are 2022-08-22 to 2025-05-09 for La Poza and 2021-07-28 to 2025-05-09 for Pucón (`outputs/tables/data_inventory.csv`). For mean chlorophyll-a, the local reproducible source contains 623 rows / 480 unique dates for La Poza and 827 rows / 788 unique dates for Pucón (`outputs/tables/station_date_coverage.csv`). In the modeled daily series, La Poza contains 941 daily records, of which 432 are direct observations and 527 are imputed/reconstructed; Pucón contains 1331 daily records, of which 740 are direct observations and 685 are imputed/reconstructed (`outputs/tables/preprocessing_footprint.csv`).

**Manuscript change.** Revise Sections 2.2 and 2.4.1. Add a data-inventory table either in the main text or Supplementary Material. Do not retain unsupported statements such as “90% direct observations” unless a satellite-derived daily product with that density is provided and validated.

**Response text.** We agree with the reviewer. We revised the data-description section to separate author-confirmed field/laboratory sampling information from the reproducible local station-workbook inventory used in the forecast analysis. We added a source-file inventory with file hashes, date ranges, variables, units, raw row counts, station labels, and date-parsing provenance, and we report observed-versus-reconstructed proportions for each station. In the local reproducible dataset, the daily modeling series contains 941 days for La Poza and 1331 days for Pucón; direct observations account for 45.9% and 55.6% of these daily records, respectively, while reconstructed/imputed values account for 56.0% and 51.5%, respectively. These values are now explicitly reported, and the manuscript no longer asks readers to infer the reliability of the time series from the forecasts alone.

**Residual limitation.** **AUTHOR INPUT REQUIRED:** The repository does not contain the full historical 1989–2024 DGA sample table, laboratory certificates, or satellite matchup products. The authors must confirm the sampling method, analytical procedure, and historical sample count before those claims are retained in the final manuscript.

---

### Comment 4

**Reviewer comment.** The effect of preprocessing should be addressed more carefully. Since the time series were reconstructed using interpolation, gap filling, smoothing, and other steps, the authors should clarify how much of the final series is based on actual observations and how much may be influenced by preprocessing.

**Action taken.** We added explicit preprocessing masks and footprint tables. Each daily value now carries flags for direct observations, imputation, interpolation, outlier handling, smoothing, source count, and imputation method. We also generated a 2024 observed-preserving, no-smoothing reconstruction diagnostic.

**Evidence generated.**

- `data/processed/daily_chl_a.csv`
- `data/processed/realistic_imputed_chl_a_2024.csv`
- `outputs/tables/preprocessing_footprint.csv`
- `outputs/tables/preprocessing_footprint_by_month.csv`
- `outputs/tables/realistic_imputation_diagnostics.csv`
- `figures/realistic_imputation_validation.png`
- `figures/realistic_imputation_validation.svg`

**Key reproducible numbers.** For the full local daily target, direct observations are 45.9% for La Poza and 55.6% for Pucón; reconstructed/imputed values are 56.0% and 51.5%, respectively. Linear/spline interpolation contributes only 0.3% at La Poza and 1.6% at Pucón, and the final accepted target has no smoothing (`smoothed_count = 0`). In the 2024 forecast target specifically, direct observations are 102/366 days at La Poza and 106/366 days at Pucón; the remainder is reconstructed using the documented gap-aware method (`outputs/tables/realistic_imputation_diagnostics.csv`).

**Manuscript change.** Rewrite Sections 2.4.1 and 2.4.2. Remove claims that preprocessing has only a “minimal artifact footprint” unless supported by the new footprint table. Remove or revise the Savitzky–Golay statement because the final target used for the refreshed forecasts is not smoothed.

**Response text.** We agree and revised the preprocessing description substantially. The revised manuscript now reports the exact observed, interpolated, imputed, outlier-handled, and smoothed proportions for each station and includes the corresponding source tables. The final forecasting target preserves direct 2024 observations exactly, uses shape-preserving interpolation only for short bracketed gaps, applies a historical day-of-year/harmonic/analog-residual reconstruction for longer gaps, and uses no smoothing in the accepted target. We also added observed-only and gap-stratified scoring tables so that forecast skill on directly observed dates can be compared against skill on reconstructed dates.

**Residual limitation.** Because the 2024 forecast target remains reconstruction-dominated, the manuscript should describe the forecasting task as forecasting a reconstructed daily Chl-a product, not as a fully observed daily in-situ series.

---

### Comment 6

**Reviewer comment.** The evaluation of the 7-day forecast is not fully convincing. Although the reported errors are acceptable, the figures suggest a possible temporal shift between predicted and observed chlorophyll-a dynamics. For bloom warning applications, this issue is important and should be assessed explicitly.

**Action taken.** We added lag diagnostics for the 7-day forecasts: lagged correlations over ±14 days, lag-0 correlation, whether the best correlation occurs at lag 0, peak-date error, and event-onset timing fields.

**Evidence generated.**

- `outputs/tables/lag_diagnostics_d7.csv`
- `outputs/tables/lag_correlation_by_model_d7.csv`
- `figures/figure_06_forecasts_la_poza.png`
- `figures/figure_07_forecasts_pucon.png`

**Key reproducible numbers.** At D7, best correlation occurs at lag 0 for La Poza Chronos Large (r = 0.784), La Poza TimesFM (r = 0.774), and Pucón TimesFM (r = 0.860). Pucón Chronos Large is the exception: its best D7 correlation occurs at lag -14 days (best r = 0.790; lag-0 r = 0.743). Peak-date error is 14 days in all four station/model D7 cases (`outputs/tables/lag_diagnostics_d7.csv`).

**Manuscript change.** Revise Section 3.3 and Discussion. Replace broad statements such as “no systematic directional bias” or “mathematically disproves a systematic phase lag” with model- and station-specific wording.

**Response text.** We agree that the apparent temporal shift is important for bloom-warning use. We therefore added a lag-diagnostic analysis for the 7-day forecasts. Three of the four station/model combinations reached their maximum correlation at lag 0, indicating no systematic shift in those cases. However, Pucón Chronos Large reached its best correlation at a negative lag, and all D7 cases showed a 14-day peak-date error. We now report these diagnostics explicitly and describe the D7 forecasts as capturing the seasonal envelope and broad timing but not reliably resolving peak timing at day-level precision.

**Residual limitation.** Event-onset timing at the 10 µg/L threshold could not be estimated from the processed 2024 forecast target because there were no processed-target exceedances of that threshold.

---

### Comment 7

**Reviewer comment.** The analysis of threshold exceedance is too descriptive in its current form. If the authors wish to highlight the management relevance of the study, this section should include more quantitative analysis rather than only visual or narrative description.

**Action taken.** We generated quantitative threshold-warning tables with confusion-matrix counts, sensitivity/POD, specificity/TNR, precision, F1, false-alarm ratio, missed-event rate, and overall accuracy for both observed-only targets and all processed targets.

**Evidence generated.**

- `outputs/tables/threshold_warning_metrics.csv`
- `outputs/tables/threshold_warning_metrics_all_targets.csv`
- `outputs/tables/threshold_event_inventory.csv`
- `outputs/tables/threshold_event_summary.csv`

**Key reproducible numbers.** In the processed 2024 forecasting target, neither station exceeded 10 µg/L (`processed_model_exceedance_count = 0` for La Poza and Pucón in `outputs/tables/threshold_event_summary.csv`). Therefore, sensitivity/POD, precision, F1, false-alarm ratio, and missed-event rate are not estimable for true bloom-event detection from the processed 2024 forecast target. The observed-only threshold table contains small sample sizes only (`n = 6–8` per station/model/horizon at D1/D7), with zero observed 10 µg/L events in the evaluated target dates.

**Manuscript change.** Replace the current threshold table in Section 3.5. The current manuscript table reports high POD/F1 values that are not supported by the current local 2024 target. Use the generated threshold tables and explicitly state that 10 µg/L event-detection skill cannot be estimated from the available processed forecast target.

**Response text.** We agree and replaced the descriptive threshold discussion with quantitative binary-warning verification tables. The revised tables report confusion-matrix counts and warning metrics. Importantly, the new analysis also shows a limitation: in the processed 2024 forecast target used for the refreshed TimesFM/Chronos evaluation, there are no 10 µg/L exceedance events. As a result, detection-oriented metrics such as POD, precision, F1, false-alarm ratio, and missed-event rate cannot be estimated from this subset. We therefore removed unsupported claims of high threshold-warning sensitivity and reframed the management analysis as a reproducible verification framework that requires historical exceedance events or author-confirmed bloom records to quantify operational detection skill.

**Residual limitation.** **AUTHOR INPUT REQUIRED:** If the authors want to retain operational threshold-detection claims, the full historical exceedance/event dataset and confirmed treatment of high Chl-a observations flagged for QC review are required.

---

## Reviewer 3

### Comment 2

**Reviewer comment.** In Section 2.3, the manuscript mentions establishing empirical and semi-empirical relationships between satellite spectral indices and in-situ data for modeling. However, it fails to explain what these relationships actually are or how they were validated. Furthermore, it remains completely unclear how the subsequent machine learning models actually utilize these “empirical relationships.” The authors need to explicitly present their remote sensing inversion algorithms, provide validation metrics for the satellite-derived estimates, and clearly explain how this satellite data is integrated into the final forecasting pipeline.

**Action taken.** We audited the repository for satellite matchup inputs and inversion outputs. No local satellite reflectance products, spectral-index matchup table, inversion coefficients, train/test split identifiers, or validation metrics were found. We therefore generated a satellite-matchup audit table and marked this as a claim-reduction / author-input item.

**Evidence generated.**

- `outputs/tables/satellite_matchup_validation.csv`
- `reports/reviewer_response_matrix.csv`

**Manuscript change.** Rewrite Section 2.3. Either add the missing inversion formulas, matchup design, and validation metrics, or reduce the claim so the satellite role is described only as contextual or as a prior pigment-estimation data source, not as a validated local input to the current forecast architectures.

**Response text.** We agree with the reviewer. We audited the reproducible data package and found that the local repository did not contain the satellite reflectance/index matchup table or inversion coefficients required to independently reproduce the claimed satellite-to-Chl-a empirical relationships. We therefore revised the manuscript to avoid unsupported methodological claims. In the current reproducible forecast experiment, TimesFM and Chronos ingest the daily Chl-a target series and do not ingest satellite reflectance bands or spatial predictors directly. If the satellite inversion is retained, the revised manuscript must include the specific index formulas/model equations, matchup window, cloud/QA rules, train/test split, validation metrics, and uncertainty of the satellite-derived Chl-a estimates.

**Residual limitation.** **AUTHOR INPUT REQUIRED:** Provide the satellite matchup table and inversion validation outputs, or approve claim reduction in the title, abstract, Section 2.3, and Discussion.

---

### Comment 3

**Reviewer comment.** Similar to the previous question, the manuscript's title and abstract heavily emphasize the integration of “Satellite Observations and Machine Learning.” However, a detailed review of the methodology (Sections 2.4 and 2.5) reveals that the core foundation models (TimesFM, Chronos, etc.) only utilize univariate time-series data of Chlorophyll-a. There is no evidence showing how satellite-derived spatial predictors are actually ingested into these forecasting architectures. The study overstates its methodological integration, and the title is scientifically misleading.

**Action taken.** We clarified the model input contract and revised the response matrix to require claim reduction unless satellite-feature forecasts are provided. The forecast cache and Figure 4–8 outputs are generated from univariate Chl-a context windows, not from multivariate satellite predictors.

**Evidence generated.**

- `data/processed/forecast_evaluation_manifest.json`
- `outputs/tables/forecast_predictions_long.csv`
- `outputs/tables/satellite_matchup_validation.csv`
- `data/processed/foundation_20260531T200051Z_metadata.json`
- `data/processed/foundation_20260531T200120Z_metadata.json`

**Manuscript change.** Revise the title, abstract, highlights, Sections 2.3–2.5, Discussion, and Conclusion. Do not call the forecasting architectures “satellite-driven” unless satellite predictors are explicitly ingested.

**Response text.** We agree and have reduced the methodological claim. The revised text now distinguishes between satellite/monitoring data used to support pigment data construction and the forecasting architectures themselves. In the reproducible experiments reported here, the foundation models receive a univariate Chl-a context window and return 1–30 day point and quantile forecasts. They do not directly ingest satellite reflectance bands, spectral indices, or spatial predictors. We therefore revised the title and abstract to avoid implying direct satellite-feature ingestion by TimesFM or Chronos.

**Residual limitation.** A true satellite-feature integration experiment would require a validated matchup table and a multivariate forecast design, which are not present in the current local data package.

---

### Comment 4

**Reviewer comment.** In Section 2.5, the manuscript devotes a significant amount of space—spanning several pages with standard mathematical equations—to describing the theoretical backgrounds of publicly available models. Since the study applies these off-the-shelf models without proposing any novel algorithmic or architectural improvements, this textbook-level description is unnecessary and severely dilutes the paper's actual scientific contribution. I recommend drastically condensing Section 2.5. The authors should simply introduce the selected models, provide the appropriate academic citations, and focus exclusively on the specific configurations, hyperparameters, and input/output designs utilized in this study. Any lengthy architectural derivations should be completely removed or moved to the Supplementary Material. Furthermore, given the absence of methodological innovations to the models themselves, the overall scientific contribution of the current manuscript may be insufficient for the standards of this journal. To strengthen the paper's value, I suggest adding an in-depth application analysis of the forecasting results.

**Action taken.** We propose replacing the long model-theory section with a concise input/output and configuration section. We also added application-oriented analyses: observed-only metrics, gap-stratified metrics, lag diagnostics, threshold-warning verification tables, uncertainty interval coverage, and a cross-site baseline limitation table.

**Evidence generated.**

- `outputs/tables/forecast_metrics_by_horizon.csv`
- `outputs/tables/observed_only_forecast_metrics.csv`
- `outputs/tables/gap_stratified_forecast_metrics.csv`
- `outputs/tables/lag_diagnostics_d7.csv`
- `outputs/tables/threshold_warning_metrics.csv`
- `outputs/tables/uncertainty_coverage.csv`
- `outputs/tables/cross_site_validation.csv`
- `figures/figure_08_uncertainty_intervals.png`

**Manuscript change.** Condense Section 2.5 to one short subsection on selected models and configuration. Move any textbook equations to Supplementary Material or delete them. Expand Results/Discussion with the application analyses above.

**Response text.** We agree and have substantially rebalanced the manuscript. Section 2.5 was condensed to describe the selected models, citations, input context length, forecast horizons, quantile outputs, runtime configuration, and evaluation protocol, rather than reproducing standard model derivations. The space saved is used to present application-relevant diagnostics: horizon-dependent forecast degradation, observed-only and gap-stratified performance, 7-day lag diagnostics, threshold-warning verification, uncertainty coverage, and site-transfer limitations.

**Residual limitation.** The revised manuscript should not claim algorithmic novelty. Its contribution should be framed as a reproducible application and diagnostic evaluation of foundation time-series models for Lake Villarrica Chl-a forecasting.

---

### Comment 5

**Reviewer comment.** In Section 2.4.1, the authors state they used “day-of-year climatological imputation” to convert irregular in-situ sampling into a continuous daily frequency. Given that in-situ sampling of lakes is typically infrequent, applying a 1-day horizon forecast on heavily imputed daily data raises a methodological concern. It is highly likely the model is merely predicting the climatological mean used for the imputation itself, rather than actual ecological dynamics. This challenges the reported “near-perfect” agreement. The authors must clarify the exact original sampling frequency and robustly prove the models are not just learning the imputation logic.

**Action taken.** We quantified observed versus reconstructed proportions, added observed-only scoring, added gap-stratified scoring, preserved imputation flags in all forecast rows, and removed overclaims of “near-perfect” agreement.

**Evidence generated.**

- `outputs/tables/preprocessing_footprint.csv`
- `outputs/tables/realistic_imputation_diagnostics.csv`
- `outputs/tables/observed_only_forecast_metrics.csv`
- `outputs/tables/gap_stratified_forecast_metrics.csv`
- `data/processed/forecast_evaluation_manifest.json`
- `figures/realistic_imputation_validation.png`

**Key reproducible numbers.** In the 2024 forecast target, direct observations are 102/366 days at La Poza and 106/366 days at Pucón; 264 and 260 days, respectively, are reconstructed (`outputs/tables/realistic_imputation_diagnostics.csv`). Observed-only D1 MAE is 0.103 µg/L for La Poza TimesFM, 0.178 µg/L for La Poza Chronos Large, 0.063 µg/L for Pucón TimesFM, and 0.123 µg/L for Pucón Chronos Large (`outputs/tables/observed_only_forecast_metrics.csv`). Observed-only sample sizes are small (`n = 6–8` depending on station/model/horizon), so these are sensitivity checks rather than definitive proof.

**Manuscript change.** Rewrite Sections 2.4.1, 2.6, 3.2, 3.3, and Discussion. Replace “near-perfect” with quantified error values and explicitly state the limitation from reconstruction-dominated daily targets.

**Response text.** We agree and now explicitly quantify the original observation density and the preprocessing footprint. We added observed-only and gap-stratified evaluations so that forecast performance on directly observed target dates can be separated from performance on reconstructed dates. The results show that short-horizon errors remain low on directly observed dates, but the observed-only sample in the 2024 evaluation window is small. We therefore no longer claim “near-perfect” ecological prediction. Instead, we describe the forecasts as skillful for the reconstructed daily Chl-a product and interpret observed-only results as a sensitivity check against imputation-driven performance.

**Residual limitation.** **AUTHOR INPUT REQUIRED:** The authors can strengthen this response by adding a clear narrative on the original in-situ/buoy sampling frequency and by confirming whether the high-frequency buoy observations are independent physical measurements or derived products.

---

### Comment 7

**Reviewer comment.** The Discussion section overall lacks sufficient depth and would benefit from a more explicit and structured analysis of the sources of uncertainty within the proposed forecasting framework. Currently, the manuscript attributes medium- to long-term forecast degradation almost exclusively to “intrinsic ecological unpredictability”. It fails to clearly distinguish between uncertainties arising from: (1) satellite retrieval limitations, (2) spatiotemporal mismatches between point-based in-situ samples and satellite pixels, or (3) structural artifacts introduced by the daily data imputation process. Furthermore, while Section 2.4.4 explicitly mentions generating probabilistic forecasts (mapping to the 10th, 50th, and 90th percentiles), any discussion or visualization of these predictive uncertainty bounds is entirely absent from the results and discussion. The authors must expand this section to critically examine these distinct error sources and their relative impacts on model reliability.

**Action taken.** We added interval coverage metrics and a new q10/q50/q90 uncertainty figure. We also propose a structured Discussion subsection separating satellite retrieval uncertainty, point-pixel mismatch, imputation/reconstruction uncertainty, model/horizon uncertainty, and ecological-driver uncertainty.

**Evidence generated.**

- `outputs/tables/forecast_predictions_with_intervals.csv`
- `outputs/tables/uncertainty_coverage.csv`
- `outputs/tables/figure_08_source.csv`
- `figures/figure_08_uncertainty_intervals.png`
- `figures/figure_08_uncertainty_intervals.svg`

**Key reproducible numbers.** D7 empirical 10–90% interval coverage is 0.72 for La Poza TimesFM, 0.72 for La Poza Chronos Large, 0.88 for Pucón TimesFM, and 0.64 for Pucón Chronos Large (`outputs/tables/uncertainty_coverage.csv`).

**Manuscript change.** Insert the uncertainty figure after the forecast trajectory figures or as a supplementary figure. Add a Discussion subsection titled “Uncertainty sources and forecast reliability”. Avoid attributing all longer-horizon degradation to intrinsic ecological unpredictability.

**Response text.** We agree. The revised manuscript now separates uncertainty sources into satellite retrieval limitations, spatial mismatch between point measurements and satellite pixels, daily reconstruction artifacts, model/horizon uncertainty, and unresolved ecological-driver uncertainty. We also added a new predictive-interval figure showing q10, q50, and q90 forecasts and report empirical 10–90% interval coverage. These results show that uncertainty intervals are informative but not perfectly calibrated, especially for Pucón Chronos Large at D7. The Discussion now interprets medium-range degradation as a combination of model horizon effects, reconstructed-target uncertainty, and missing exogenous drivers rather than only intrinsic ecological unpredictability.

**Residual limitation.** Satellite retrieval and point-pixel mismatch uncertainty cannot be quantified until satellite matchup data are supplied.

---

### Comment 8

**Reviewer comment.** The models are trained and evaluated independently on the Pucon and Poza stations. While the results are promising at a 1-day horizon, there is no cross-site validation presented. To prove the generalizability of these foundation models in lake ecosystems, the authors should test whether a model trained on Pucon data can accurately predict dynamics at La Poza, or validate the framework on other Patagonian lakes.

**Action taken.** We generated a transparent cross-site transfer baseline using transferred day-of-year climatology. We do not present this as foundation-model cross-site validation. It is a lower-bound diagnostic and a limitation marker.

**Evidence generated.**

- `outputs/tables/cross_site_validation.csv`

**Key reproducible numbers.** The local transfer baseline gives Pucón→La Poza D1 MAPE = 75.9% and RMSE = 0.919 µg/L, and La Poza→Pucón D1 MAPE = 25.6% and RMSE = 1.896 µg/L (`outputs/tables/cross_site_validation.csv`). The table is explicitly marked `local_baseline_transfer_not_foundation_model`.

**Manuscript change.** Add a limitation paragraph. Do not claim demonstrated foundation-model generalizability across stations unless a true transferred-context foundation-model experiment is run.

**Response text.** We agree. The revised manuscript now makes clear that the current TimesFM/Chronos experiments evaluate station-specific forecasting contexts and do not prove cross-site generalization. We added a reproducible cross-site baseline as a diagnostic, but because it is not a foundation-model transfer experiment, we frame it as a limitation rather than as evidence of generalizability. The manuscript now states that future work should evaluate transferred-context foundation forecasts and independent Patagonian lakes before generalizing beyond the two monitored Villarrica stations.

**Residual limitation.** A full reviewer-satisfying response would require running a true transferred-context foundation-model evaluation or adding external-lake validation data.

---

### Comment 9

**Reviewer comment.** Figure 2 is unreadable at 100% scale. The text is too small, and the excessive whitespace makes it visually unappealing. Please redraw the figure to improve its legibility.

**Action taken.** We rebuilt Figure 2 as a publication-facing Mermaid sequence diagram with larger labels, reduced visual clutter, consistent orientation, and vector/raster exports.

**Evidence generated.**

- `figures/figure_02_preprocessing_workflow.mmd`
- `figures/figure_02_preprocessing_workflow.svg`
- `figures/figure_02_preprocessing_workflow.png`
- `figures/figure_02_preprocessing_workflow.metadata.json`

**Manuscript change.** Replace the old Figure 2 and caption.

**Response text.** We agree and replaced Figure 2. The new version is generated from a version-controlled Mermaid source file and exported as both SVG and PNG. It uses larger text, grouped workflow lanes, reduced whitespace, and a cleaner left-to-right sequence that is legible at manuscript scale.

**Residual limitation.** None, except final journal-specific figure dimension requirements.

---

### Comment 10

**Reviewer comment.** While Figure 2 outlines the preprocessing steps, the manuscript lacks a clear, overarching technical flowchart detailing the entire methodology. Given the complex integration of various data sources and multiple foundation models, a comprehensive roadmap is highly necessary. The authors should include a high-quality flowchart illustrating the end-to-end workflow—from data acquisition and feature engineering to model training, evaluation, and forecasting—to significantly improve the manuscript's readability and structural clarity.

**Action taken.** We added a standalone Node/Mermaid methodology flowchart that shows the end-to-end roadmap in simple terms: data sources → provenance and QA → daily Chl-a target → forecast setup → TimesFM/Chronos forecasts → evaluation diagnostics → reproducible manuscript outputs. The satellite branch is shown as a validation/audit step before any direct satellite-feature claim.

**Evidence generated.**

- `figures/figure_methodology_end_to_end.mmd`
- `figures/figure_methodology_end_to_end.svg`
- `figures/figure_methodology_end_to_end.png`
- `figures/figure_methodology_end_to_end.metadata.json`

**Manuscript change.** Insert the new methodology flowchart as the Methods roadmap figure. Keep Figure 2 as the detailed preprocessing/forecast-input sequence diagram if desired, or use the new flowchart as the main response to Reviewer 3.10. Add a caption explaining that satellite inversion is a separately validated branch before direct satellite-feature ingestion can be claimed.

**Response text.** We agree. We added a standalone end-to-end technical roadmap rendered from version-controlled Mermaid source using Node. The figure summarizes the full workflow from data acquisition and provenance tracking through daily Chl-a target construction, forecast setup, foundation-model forecasting, diagnostic evaluation, and reproducible manuscript outputs. It also explicitly separates satellite-inversion validation from the current univariate Chl-a foundation-model input contract, improving methodological clarity without overstating satellite-feature ingestion.

**Residual limitation.** Satellite inversion can be added to the workflow only after validated satellite matchup and inversion artifacts are supplied.
