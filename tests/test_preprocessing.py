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
