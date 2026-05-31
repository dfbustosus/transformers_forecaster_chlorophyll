from __future__ import annotations

import pandas as pd

from villarrica_forecaster.preprocessing.realistic_imputation import (
    build_realistic_imputed_reference_2024,
    realistic_imputation_diagnostics,
)


def test_realistic_imputation_preserves_observed_values_exactly() -> None:
    canonical = pd.DataFrame(
        [
            _obs("pucon", "Pucón", "2023-03-01", 1.8),
            _obs("pucon", "Pucón", "2023-10-01", 2.6),
            _obs("pucon", "Pucón", "2024-02-10", 3.0),
            _obs("pucon", "Pucón", "2024-04-10", 1.0),
            _obs("pucon", "Pucón", "2024-12-10", 2.5),
        ]
    )

    imputed = build_realistic_imputed_reference_2024(canonical, _config())
    observed_rows = imputed[imputed["is_observed"]]

    assert len(imputed) == 366
    assert imputed["chl_a_imputed"].notna().all()
    assert observed_rows["chl_a_imputed"].tolist() == observed_rows["chl_a_observed"].tolist()
    assert not imputed["imputation_method"].str.contains("smooth", case=False).any()


def test_realistic_imputation_caps_only_imputed_extremes() -> None:
    canonical = pd.DataFrame(
        [
            _obs("pucon", "Pucón", "2023-06-01", 50.0),
            _obs("pucon", "Pucón", "2024-02-10", 2.0),
            _obs("pucon", "Pucón", "2024-02-11", 2.1),
            _obs("pucon", "Pucón", "2024-02-12", 2.2),
            _obs("pucon", "Pucón", "2024-10-10", 3.0),
        ]
    )

    imputed = build_realistic_imputed_reference_2024(canonical, _config())
    missing_rows = imputed[imputed["is_imputed"]]
    cap = float(imputed["imputation_cap"].iloc[0])

    assert missing_rows["chl_a_imputed"].max() <= cap
    assert cap >= 3.0


def test_realistic_imputation_diagnostics_report_variability_ratio() -> None:
    canonical = pd.DataFrame(
        [_obs("pucon", "Pucón", f"2024-01-{day:02d}", 1.0 + (day % 3)) for day in range(1, 12)]
        + [_obs("pucon", "Pucón", "2023-06-01", 2.0)]
    )
    imputed = build_realistic_imputed_reference_2024(canonical, _config())
    diagnostics = realistic_imputation_diagnostics(imputed)

    assert "diff_std_ratio_imputed_to_observed" in diagnostics.columns
    assert diagnostics.loc[0, "imputed_day_count"] > 0


def test_realistic_imputation_blends_long_gap_edges_to_observed_values() -> None:
    canonical = pd.DataFrame(
        [_obs("pucon", "Pucón", f"2023-01-{day:02d}", 5.0) for day in range(1, 15)]
        + [_obs("pucon", "Pucón", "2024-01-10", 1.0)]
    )
    config = _config()
    config["preprocessing"]["realistic_imputation_start"] = "2024-01-01"
    config["preprocessing"]["realistic_imputation_end"] = "2024-01-31"

    imputed = build_realistic_imputed_reference_2024(canonical, config)
    day_after = imputed[imputed["date"].eq("2024-01-11")].iloc[0]

    assert day_after["chl_a_imputed"] < 1.5
    assert day_after["imputation_method"] == "historical_seasonal_harmonic_analog_residual"


def _obs(station_id: str, station_name: str, date: str, value: float) -> dict[str, object]:
    return {
        "station_id": station_id,
        "station_name": station_name,
        "date": date,
        "variable": "chlorophyll_a",
        "statistic": "mean",
        "value": value,
        "quality_flag": "ok",
        "is_model_eligible": True,
        "source_file": "fixture.csv",
        "source_row": 1,
    }


def _config() -> dict[str, object]:
    return {
        "preprocessing": {
            "chlorophyll_variable": "chlorophyll_a",
            "statistic": "mean",
            "realistic_imputation_start": "2024-01-01",
            "realistic_imputation_end": "2024-12-31",
            "realistic_imputation_doy_bandwidth_days": 24,
            "realistic_imputation_short_gap_days": 10,
            "realistic_imputation_harmonics": 2,
            "realistic_imputation_analog_residual_weight": 0.28,
            "realistic_imputation_cap_quantile": 0.97,
            "realistic_imputation_cap_multiplier": 1.12,
            "realistic_imputation_boundary_blend_days": 21,
        }
    }
