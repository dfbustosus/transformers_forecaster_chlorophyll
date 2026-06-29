# Response draft: trajectory figure congestion and 1:1 scatter diagnostics

## Reviewer comment

Figures 6 and 7 present the core forecasting results, but in their current format they are visually congested. The reviewer suggested either annotating each subpanel with key accuracy metrics or adding 1:1 predicted-versus-observed scatter plots to evaluate bias and extreme-concentration behavior.

## Action taken

1. Figure 6 and Figure 7 captions were updated to report exact MAE and RMSE values for TimesFM and Chronos Large at D1, D7, D14, and D28.
2. Supplementary Figure S1 was added for La Poza as a 1:1 predicted-versus-target scatter diagnostic.
3. Supplementary Figure S2 was added for Pucón as a 1:1 predicted-versus-target scatter diagnostic.
4. Each scatter panel reports n, MAE, RMSE, and bias, and points distinguish direct observations from reconstructed targets.

## Generated artifacts

- `figures/figure_s1_predicted_vs_target_la_poza.png`
- `figures/figure_s1_predicted_vs_target_la_poza.svg`
- `outputs/tables/figure_s1_source.csv`
- `figures/figure_s2_predicted_vs_target_pucon.png`
- `figures/figure_s2_predicted_vs_target_pucon.svg`
- `outputs/tables/figure_s2_source.csv`
- Updated Figure 6 source: `outputs/tables/figure_06_source.csv`
- Updated Figure 7 source: `outputs/tables/figure_07_source.csv`

## Source-table synchronization check

- `outputs/tables/figure_s1_source.csv`: 200/200 rows matched the corresponding La Poza subset of `outputs/tables/forecast_predictions_long.csv` for horizons D1, D7, D14, and D28; max absolute differences for `y_pred`, `y_true`, `y_true_observed`, `q10`, `q50`, and `q90` were all 0.0.
- `outputs/tables/figure_s2_source.csv`: 200/200 rows matched the corresponding Pucón subset of `outputs/tables/forecast_predictions_long.csv` for horizons D1, D7, D14, and D28; max absolute differences for `y_pred`, `y_true`, `y_true_observed`, `q10`, `q50`, and `q90` were all 0.0.
- Each supplementary source table contains 25 origins per model and horizon for TimesFM and Chronos Large.
- Each supplementary source table contains 56 direct-observation prediction rows and 144 reconstructed/imputed prediction rows, matching the rolling-origin horizon subset used in the trajectory figures.

## Response text

We thank the reviewer for this suggestion. We revised the presentation of the trajectory results in two ways. First, the captions of Figures 6 and 7 now report the exact MAE and RMSE values for TimesFM and Chronos Large at the 1-, 7-, 14-, and 28-day horizons, so the reader can interpret each trajectory panel quantitatively without adding additional visual clutter to the plots. Second, we added 1:1 predicted-versus-target scatter plots as Supplementary Figures S1 and S2. These supplementary figures show the correspondence between predictions and target Chl-a values for each model and horizon, include the 1:1 reference line, report n, MAE, RMSE, and bias within each panel, and distinguish direct observed targets from reconstructed targets. This provides a clearer assessment of bias, amplitude damping, and high-concentration behavior while preserving the readability of the main trajectory figures.

## Updated captions

**Figure 6.** TimesFM and Chronos Large Chl-a forecasts at La Poza for 1-, 7-, 14-, and 28-day horizons. The blue line is the accepted daily Chl-a target; red and green markers/lines are model predictions at rolling forecast origins. Horizon metrics: TimesFM (D1: MAE=0.099, RMSE=0.173 µg/L; D7: MAE=0.300, RMSE=0.406 µg/L; D14: MAE=0.428, RMSE=0.661 µg/L; D28: MAE=0.702, RMSE=1.059 µg/L); Chronos Large (D1: MAE=0.106, RMSE=0.216 µg/L; D7: MAE=0.275, RMSE=0.399 µg/L; D14: MAE=0.471, RMSE=0.742 µg/L; D28: MAE=0.757, RMSE=1.183 µg/L). Supplementary Figure S1 provides the corresponding 1:1 predicted-versus-target scatter diagnostics. Source data: `outputs/tables/figure_06_source.csv`.

**Figure 7.** TimesFM and Chronos Large Chl-a forecasts at Pucón for 1-, 7-, 14-, and 28-day horizons. The blue line is the accepted daily Chl-a target; red and green markers/lines are model predictions at rolling forecast origins. Horizon metrics: TimesFM (D1: MAE=0.063, RMSE=0.088 µg/L; D7: MAE=0.241, RMSE=0.335 µg/L; D14: MAE=0.396, RMSE=0.576 µg/L; D28: MAE=0.606, RMSE=0.886 µg/L); Chronos Large (D1: MAE=0.071, RMSE=0.115 µg/L; D7: MAE=0.275, RMSE=0.398 µg/L; D14: MAE=0.456, RMSE=0.722 µg/L; D28: MAE=0.679, RMSE=1.073 µg/L). Supplementary Figure S2 provides the corresponding 1:1 predicted-versus-target scatter diagnostics. Source data: `outputs/tables/figure_07_source.csv`.

**Supplementary Figure S1.** Predicted-versus-target Chl-a scatter diagnostics for La Poza. Panels compare TimesFM and Chronos Large predictions against the accepted target at D1, D7, D14, and D28. The dashed line is the 1:1 line; panel annotations report n, MAE, RMSE, and bias. Blue points are direct observed targets and gray points are reconstructed targets. Source data: `outputs/tables/figure_s1_source.csv`.

**Supplementary Figure S2.** Predicted-versus-target Chl-a scatter diagnostics for Pucón. Panels compare TimesFM and Chronos Large predictions against the accepted target at D1, D7, D14, and D28. The dashed line is the 1:1 line; panel annotations report n, MAE, RMSE, and bias. Blue points are direct observed targets and gray points are reconstructed targets. Source data: `outputs/tables/figure_s2_source.csv`.
