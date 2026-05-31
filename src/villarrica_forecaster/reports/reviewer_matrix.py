from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from villarrica_forecaster.config import path_from_config
from villarrica_forecaster.io import write_csv


def build_reviewer_response_matrix(config: dict[str, Any]) -> dict[str, Path]:
    reports_dir = path_from_config(config, "reports")
    rows = reviewer_rows()
    frame = pd.DataFrame(rows)
    csv_path = write_csv(frame, reports_dir / "reviewer_response_matrix.csv")
    md_path = reports_dir / "reviewer_response_matrix.md"
    md_path.write_text(_to_markdown(frame), encoding="utf-8")
    return {"reviewer_response_matrix_csv": csv_path, "reviewer_response_matrix_md": md_path}


def reviewer_rows() -> list[dict[str, Any]]:
    return [
        {
            "reviewer": "Reviewer 1",
            "comment_id": "R1.3",
            "issue": "Data description lacks sampling methods, temporal resolution, sample size, and observed versus imputed proportions.",
            "risk_level": "high",
            "code_owner_agent": "data-engineer; data-validation-auditor",
            "required_artifact": "Data inventory, data dictionary, station coverage, mixed-date repair audit, preprocessing footprint.",
            "output_path": "outputs/tables/data_inventory.csv; outputs/tables/station_date_coverage.csv; outputs/tables/mixed_date_encoding_audit.csv; outputs/tables/preprocessing_footprint.csv",
            "test_path": "tests/test_ingest.py; tests/test_preprocessing.py",
            "manuscript_section": "2.2, 2.4, Results data description",
            "proposed_response": "We added reproducible source-file inventory, station/date coverage, and a mixed Excel-serial date repair audit for local files; sampling/laboratory method claims remain author-confirmed unless raw metadata are supplied.",
            "status": "partial_generated_needs_author_input_for_methods_and_full_history",
            "needs_author_input": "Historical 1989–2024 records, 385-event table, sampling methods, and analytical-procedure metadata if they are not in raw_data.",
        },
        {
            "reviewer": "Reviewer 1",
            "comment_id": "R1.4",
            "issue": "Preprocessing influence from interpolation, gap filling, smoothing, and outlier handling is unclear.",
            "risk_level": "high",
            "code_owner_agent": "imputation-specialist",
            "required_artifact": "Preprocessing footprint, observed/imputed flags, and no-smoothing 2024 imputation validation figure.",
            "output_path": "data/processed/daily_chl_a.csv; outputs/tables/preprocessing_footprint.csv; data/processed/realistic_imputed_chl_a_2024.csv; outputs/tables/realistic_imputation_diagnostics.csv; figures/realistic_imputation_validation.png",
            "test_path": "tests/test_preprocessing.py",
            "manuscript_section": "2.4.1, 2.4.2, Results reviewer diagnostics",
            "proposed_response": "Each modeled daily value now carries observed, interpolated, imputed, outlier, duplicate-candidate, and smoothing flags; proportions are reported by station. A separate 2024 observed-preserving, no-smoothing imputation validation artifact is generated before any forecast rerun.",
            "status": "generated_from_local_data",
            "needs_author_input": "Confirm whether manuscript HPBR was based on satellite-derived daily observations or in-situ observations; confirm station provenance for cross-station duplicate-candidate dates.",
        },
        {
            "reviewer": "Reviewer 1",
            "comment_id": "R1.6",
            "issue": "Possible 7-day forecast temporal shift must be assessed explicitly.",
            "risk_level": "high",
            "code_owner_agent": "forecast-diagnostics-specialist",
            "required_artifact": "Lagged cross-correlation, peak-date error, event-onset error.",
            "output_path": "outputs/tables/lag_diagnostics_d7.csv; outputs/tables/lag_correlation_by_model_d7.csv",
            "test_path": "tests/test_diagnostics.py",
            "manuscript_section": "Results forecast diagnostics; Discussion",
            "proposed_response": "We computed ±14-day lagged correlations, peak-date error, and event-onset error for cached TimesFM and Chronos Large rolling-origin predictions; results must be reported by station/model because Pucón Chronos Large does not peak at lag 0.",
            "status": "generated_from_foundation_predictions",
            "needs_author_input": "None for local 2022–2025 forecast diagnostics; full historical claims still require the complete historical table.",
        },
        {
            "reviewer": "Reviewer 1",
            "comment_id": "R1.7",
            "issue": "Threshold exceedance analysis is descriptive rather than quantitative.",
            "risk_level": "high",
            "code_owner_agent": "forecast-diagnostics-specialist; limnology-domain-scientist",
            "required_artifact": "Confusion matrices, POD, TNR, precision, F1, false alarm and missed-event rates.",
            "output_path": "outputs/tables/threshold_warning_metrics.csv; outputs/tables/threshold_warning_metrics_all_targets.csv; outputs/tables/threshold_event_inventory.csv; outputs/tables/threshold_event_summary.csv",
            "test_path": "tests/test_diagnostics.py",
            "manuscript_section": "Results threshold warning; Discussion management relevance",
            "proposed_response": "We generated observed-target and all-target binary-warning metrics for cached TimesFM and Chronos Large predictions, including confusion-matrix counts and POD/TNR/precision/F1/false-alarm/miss-rate fields. The 2024 local subset has no 10 µg/L Chl-a exceedances, so detection skill is not estimable from this subset and should not be overstated.",
            "status": "generated_no_2024_exceedance_events_detection_skill_not_estimable",
            "needs_author_input": "Confirm final management threshold wording and provide historical exceedance/event records if the manuscript must quantify warning skill for bloom-threshold events.",
        },
        {
            "reviewer": "Reviewer 3",
            "comment_id": "R3.2",
            "issue": "Remote-sensing inversion algorithms and validation metrics are absent.",
            "risk_level": "critical",
            "code_owner_agent": "remote-sensing-specialist",
            "required_artifact": "Satellite matchup validation table and inversion formulas/model documentation.",
            "output_path": "outputs/tables/satellite_matchup_validation.csv; reports/needs_author_input.md",
            "test_path": "Not testable until satellite matchup input is provided.",
            "manuscript_section": "2.3 Satellite Data; Abstract/title claims",
            "proposed_response": "The current repository lacks satellite matchup inputs; we explicitly mark this as requiring author input and recommend claim reduction until validated.",
            "status": "needs_author_input",
            "needs_author_input": "Provide reflectance/index matchup table, inversion model forms, splits, and validation outputs.",
        },
        {
            "reviewer": "Reviewer 3",
            "comment_id": "R3.3",
            "issue": "Title/abstract may overstate satellite and ML integration if forecasts ingest only univariate Chl-a.",
            "risk_level": "critical",
            "code_owner_agent": "transformer-timeseries-engineer; manuscript-response-editor",
            "required_artifact": "Model input contract and satellite-feature integration evidence or claim-reduction wording.",
            "output_path": "reports/needs_author_input.md; outputs/tables/satellite_matchup_validation.csv",
            "test_path": "tests/test_forecasting.py for reproducible local input contracts.",
            "manuscript_section": "Title, Abstract, 2.4, 2.5",
            "proposed_response": "Unless satellite-derived predictors are supplied and ingested, revise wording to state that satellite products support Chl-a estimation/data construction, not direct multivariate forecasting architecture input.",
            "status": "claim_reduction_required_unless_inputs_provided",
            "needs_author_input": "Provide multivariate satellite-feature forecast experiment or approve title/abstract reduction.",
        },
        {
            "reviewer": "Reviewer 3",
            "comment_id": "R3.4",
            "issue": "Model theory section is too long and application analysis should be strengthened.",
            "risk_level": "medium",
            "code_owner_agent": "manuscript-response-editor; forecast-diagnostics-specialist",
            "required_artifact": "Diagnostics outputs and proposed manuscript condensation.",
            "output_path": "outputs/tables/lag_diagnostics_d7.csv; outputs/tables/threshold_warning_metrics.csv; outputs/tables/uncertainty_coverage.csv; outputs/tables/cross_site_validation.csv",
            "test_path": "tests/test_diagnostics.py; tests/test_forecasting.py",
            "manuscript_section": "2.5, Results, Discussion",
            "proposed_response": "Condense textbook equations and replace space with code-backed application diagnostics now generated for TimesFM and Chronos Large: horizon metrics, lag, warning metrics, uncertainty coverage, and observed/gap-stratified scoring.",
            "status": "foundation_diagnostics_generated_wording_pending",
            "needs_author_input": "Author approval for moving model derivations to supplement or deleting them.",
        },
        {
            "reviewer": "Reviewer 3",
            "comment_id": "R3.5",
            "issue": "Models may learn imputation logic rather than ecological dynamics.",
            "risk_level": "critical",
            "code_owner_agent": "imputation-specialist; transformer-timeseries-engineer",
            "required_artifact": "Observed/imputed flags, preprocessing footprint, observed-only scoring plan.",
            "output_path": "data/processed/daily_chl_a.csv; outputs/tables/preprocessing_footprint.csv; data/processed/realistic_imputed_chl_a_2024.csv; outputs/tables/realistic_imputation_diagnostics.csv; outputs/tables/observed_only_forecast_metrics.csv; outputs/tables/gap_stratified_forecast_metrics.csv",
            "test_path": "tests/test_preprocessing.py; tests/test_forecasting.py",
            "manuscript_section": "2.4.1, Model evaluation, Discussion limitations",
            "proposed_response": "We expose imputation flags and generated observed-only plus gap-stratified scoring tables for cached TimesFM and Chronos Large predictions; observed-only results are a sensitivity check because the local 2024 observed-target sample is small.",
            "status": "generated_from_foundation_predictions",
            "needs_author_input": "Confirm whether manuscript HPBR/imputation description should be revised to match the code-derived masks.",
        },
        {
            "reviewer": "Reviewer 3",
            "comment_id": "R3.7",
            "issue": "Uncertainty sources and predictive intervals are not evaluated.",
            "risk_level": "high",
            "code_owner_agent": "forecast-diagnostics-specialist; limnology-domain-scientist",
            "required_artifact": "Interval coverage table, q10/q50/q90 visualization, and uncertainty-source limitation text.",
            "output_path": "outputs/tables/uncertainty_coverage.csv; outputs/tables/forecast_predictions_with_intervals.csv; figures/figure_08_uncertainty_intervals.png; figures/figure_08_uncertainty_intervals.svg",
            "test_path": "tests/test_diagnostics.py",
            "manuscript_section": "Results uncertainty; Discussion limitations",
            "proposed_response": "The pipeline evaluates cached TimesFM/Chronos q10/q50/q90 interval coverage, visualizes D7 predictive intervals, and no longer fabricates uncertainty bounds in strict manuscript mode; coverage should be described as empirical and not fully calibrated.",
            "status": "generated_from_foundation_quantiles",
            "needs_author_input": "Chronos Large was run with 16 samples on MPS for tractability; disclose this runtime setting if reporting Chronos quantile coverage.",
        },
        {
            "reviewer": "Reviewer 3",
            "comment_id": "R3.8",
            "issue": "Cross-site validation is missing.",
            "risk_level": "high",
            "code_owner_agent": "forecast-ml-engineer; transformer-timeseries-engineer",
            "required_artifact": "Pucón→La Poza and La Poza→Pucón metrics.",
            "output_path": "outputs/tables/cross_site_validation.csv",
            "test_path": "tests/test_forecasting.py",
            "manuscript_section": "Model evaluation; Results generalization",
            "proposed_response": "A reproducible local transfer baseline is generated only as a lower-bound diagnostic. It is not evidence that TimesFM/Chronos generalize across stations, so the manuscript must either add foundation-model transfer predictions or state this as a limitation.",
            "status": "local_baseline_only_foundation_transfer_not_supported",
            "needs_author_input": "Approve limitation wording or provide time/authorization to run transferred-context TimesFM/Chronos forecasts for Pucón→La Poza and La Poza→Pucón.",
        },
        {
            "reviewer": "Reviewer 3",
            "comment_id": "R3.9",
            "issue": "Figure 2 is unreadable.",
            "risk_level": "medium",
            "code_owner_agent": "visualization-engineer",
            "required_artifact": "Professional Mermaid sequence-diagram preprocessing workflow with rendered manuscript exports.",
            "output_path": "figures/figure_02_preprocessing_workflow.mmd; figures/figure_02_preprocessing_workflow.svg; figures/figure_02_preprocessing_workflow.png",
            "test_path": "Mermaid render via npm run render:figure02 or scripts/recreate_figures.py",
            "manuscript_section": "Figure 2",
            "proposed_response": "We rebuilt Figure 2 as a version-controlled Mermaid sequence diagram and rendered it to readable vector/raster manuscript exports.",
            "status": "generated",
            "needs_author_input": "None unless journal has specific figure dimensions.",
        },
        {
            "reviewer": "Reviewer 3",
            "comment_id": "R3.10",
            "issue": "A complete methodology flowchart is missing.",
            "risk_level": "medium",
            "code_owner_agent": "visualization-engineer",
            "required_artifact": "Standalone end-to-end methodology flowchart rendered from Node/Mermaid source.",
            "output_path": "figures/figure_methodology_end_to_end.mmd; figures/figure_methodology_end_to_end.svg; figures/figure_methodology_end_to_end.png",
            "test_path": "Mermaid render via npm run render:methodology or scripts/recreate_figures.py",
            "manuscript_section": "Methods overview figure; Section 2 roadmap",
            "proposed_response": "We added a standalone, high-legibility methodology flowchart showing the complete workflow from data acquisition through provenance and QA, daily Chl-a target construction, forecast setup, TimesFM/Chronos forecasting, evaluation diagnostics, and reproducible manuscript outputs. A dashed satellite-inversion validation branch clarifies that direct satellite-feature claims require matchup/inversion evidence.",
            "status": "generated_as_standalone_methodology_flowchart_satellite_details_need_input",
            "needs_author_input": "Provide satellite acquisition/inversion details if the flowchart should depict validated satellite feature ingestion rather than validated satellite-product auditing.",
        },
    ]


def _to_markdown(frame: pd.DataFrame) -> str:
    columns = [
        "reviewer",
        "comment_id",
        "risk_level",
        "required_artifact",
        "output_path",
        "status",
        "needs_author_input",
    ]
    lines = ["# Reviewer response evidence matrix", ""]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in frame.iterrows():
        values = [str(row[column]).replace("|", "\\|") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")
    return "\n".join(lines)
