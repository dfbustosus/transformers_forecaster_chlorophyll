from __future__ import annotations

import pandas as pd

from villarrica_forecaster.preprocessing.daily import (
    build_daily_chlorophyll_frame,
    southern_hemisphere_season,
)


def test_southern_hemisphere_season() -> None:
    assert southern_hemisphere_season(1) == "Summer"
    assert southern_hemisphere_season(4) == "Autumn"
    assert southern_hemisphere_season(7) == "Winter"
    assert southern_hemisphere_season(10) == "Spring"


def test_daily_chlorophyll_flags_missing_days() -> None:
    canonical = pd.DataFrame(
        [
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "date": "2024-01-01",
                "variable": "chlorophyll_a",
                "statistic": "mean",
                "value": 1.0,
                "quality_flag": "ok",
            },
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "date": "2024-01-03",
                "variable": "chlorophyll_a",
                "statistic": "mean",
                "value": 3.0,
                "quality_flag": "ok",
            },
        ]
    )
    config = {
        "preprocessing": {
            "chlorophyll_variable": "chlorophyll_a",
            "statistic": "mean",
            "interpolation_limit_days": 3,
            "iqr_multiplier": 1.5,
            "remove_iqr_outliers": False,
            "savgol_window_days": 5,
            "savgol_polyorder": 2,
            "use_smoothed_for_forecast": False,
        }
    }
    daily = build_daily_chlorophyll_frame(canonical, config)
    middle = daily[daily["date"].eq("2024-01-02")].iloc[0]
    assert not bool(middle["is_direct_observation"])
    assert bool(middle["is_interpolated"])
    assert middle["imputation_method"] == "linear_interpolation"
    assert middle["chl_a_filled"] == 2.0


def test_iqr_flag_does_not_remove_bloom_by_default() -> None:
    canonical = pd.DataFrame(
        [
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "date": f"2024-01-{day:02d}",
                "variable": "chlorophyll_a",
                "statistic": "mean",
                "value": value,
                "quality_flag": "ok",
            }
            for day, value in enumerate([1.0, 1.1, 1.0, 1.2, 25.0], start=1)
        ]
    )
    config = {
        "preprocessing": {
            "chlorophyll_variable": "chlorophyll_a",
            "statistic": "mean",
            "interpolation_limit_days": 3,
            "iqr_multiplier": 1.5,
            "remove_iqr_outliers": False,
            "savgol_window_days": 5,
            "savgol_polyorder": 2,
            "use_smoothed_for_forecast": False,
        }
    }
    daily = build_daily_chlorophyll_frame(canonical, config)
    bloom = daily[daily["date"].eq("2024-01-05")].iloc[0]
    assert bool(bloom["is_iqr_outlier"])
    assert not bool(bloom["is_outlier_removed"])
    assert bloom["chl_a_model"] == 25.0


def test_long_gaps_are_not_partially_interpolated() -> None:
    canonical = pd.DataFrame(
        [
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "date": "2024-01-01",
                "variable": "chlorophyll_a",
                "statistic": "mean",
                "value": 1.0,
                "quality_flag": "ok",
            },
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "date": "2024-01-10",
                "variable": "chlorophyll_a",
                "statistic": "mean",
                "value": 10.0,
                "quality_flag": "ok",
            },
        ]
    )
    config = _preprocessing_config(interpolation_limit_days=3)

    daily = build_daily_chlorophyll_frame(canonical, config)
    gap_day = daily[daily["date"].eq("2024-01-05")].iloc[0]

    assert int(gap_day["gap_length_days"]) == 8
    assert not bool(gap_day["is_interpolated"])
    assert gap_day["imputation_method"] == "historical_station_median_low_support"
    assert bool(gap_day["is_low_support_imputation"])


def test_smoothing_is_not_marked_when_diagnostic_disabled() -> None:
    canonical = pd.DataFrame(
        [
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "date": f"2024-01-{day:02d}",
                "variable": "chlorophyll_a",
                "statistic": "mean",
                "value": float(day),
                "quality_flag": "ok",
            }
            for day in range(1, 8)
        ]
    )
    config = _preprocessing_config(compute_smoothed_variant=False)

    daily = build_daily_chlorophyll_frame(canonical, config)

    assert not daily["is_smoothed"].any()
    assert not daily["has_smoothed_variant"].any()
    assert daily["chl_a_smoothed"].isna().all()
    assert daily["chl_a_model"].equals(daily["chl_a_filled"])


def test_cross_station_duplicate_candidate_is_flagged() -> None:
    canonical = pd.DataFrame(
        [
            {
                "station_id": station_id,
                "station_name": station_name,
                "date": "2024-01-01",
                "variable": "chlorophyll_a",
                "statistic": "mean",
                "value": 5.0,
                "quality_flag": "ok",
            }
            for station_id, station_name in [("pucon", "Pucón"), ("la_poza", "La Poza")]
        ]
    )
    config = _preprocessing_config()

    daily = build_daily_chlorophyll_frame(canonical, config)

    assert daily["is_cross_station_duplicate_candidate"].all()


def test_strict_quarantine_removes_bloom_range_from_model_input() -> None:
    canonical = pd.DataFrame(
        [
            {
                "station_id": "pucon",
                "station_name": "Pucón",
                "date": f"2024-01-{day:02d}",
                "variable": "chlorophyll_a",
                "statistic": "mean",
                "value": value,
                "quality_flag": "ok",
            }
            for day, value in enumerate([1.0, 1.1, 1.2, 55.0, 1.3], start=1)
        ]
    )
    config = _preprocessing_config(
        strict_outlier_quarantine=True,
        quarantine_bloom_range=True,
        quarantine_iqr_high_chl=True,
    )

    daily = build_daily_chlorophyll_frame(canonical, config)
    spike = daily[daily["date"].eq("2024-01-04")].iloc[0]

    assert bool(spike["is_qc_excluded_from_model"])
    assert "bloom_range_requires_confirmation" in spike["qc_exclusion_reason"]
    assert spike["chl_a_clean"] != 55.0
    assert spike["chl_a_model"] != 55.0


def _preprocessing_config(**overrides: object) -> dict:
    preprocessing = {
        "chlorophyll_variable": "chlorophyll_a",
        "statistic": "mean",
        "interpolation_limit_days": 3,
        "iqr_multiplier": 1.5,
        "remove_iqr_outliers": False,
        "savgol_window_days": 5,
        "savgol_polyorder": 2,
        "use_smoothed_for_forecast": False,
        "compute_smoothed_variant": False,
        "climatology_window_days": 15,
        "climatology_min_observations": 3,
        "monthly_min_observations": 3,
        "spike_review_delta_ug_l": 15.0,
        "high_chl_threshold_ug_l": 10.0,
        "bloom_range_threshold_ug_l": 30.0,
        "strict_outlier_quarantine": False,
        "quarantine_iqr_high_chl": False,
        "quarantine_bloom_range": False,
        "quarantine_cross_station_duplicates": False,
        "quarantine_abrupt_transitions": False,
    }
    preprocessing.update(overrides)
    return {"preprocessing": preprocessing}
