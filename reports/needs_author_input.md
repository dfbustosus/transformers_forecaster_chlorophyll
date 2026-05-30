# Needs author input

The reproducible local repository is missing evidence required for several manuscript claims.

## Satellite inversion and matchup validation

- Status: `needs_author_input`
- Required input: A table containing station_id, date, in-situ Chl-a, satellite sensor, pixel/ROI reflectance bands, QA/cloud mask, matchup distance/window, and train/test split identifiers.
- Reason: The local raw_data directory contains buoy/station spreadsheet exports but no satellite reflectance products, spectral indices, matchup table, or inversion outputs.

## Foundation-model forecast recreation

Figures 4–7 in the current manuscript name TimesFM and Chronos variants. The current repository does not contain cached TimesFM/Chronos prediction tables or the optional heavyweight model runtime. In strict manuscript mode the pipeline now blocks Figures 4–7 and writes forecast_model_blockers.csv instead of substituting local baseline forecasts. Cached predictions or executable model dependencies are required for TimesFM/Chronos claims.

## Historical monitoring record

The manuscript claims long-term records from 1989–2024 and 385 sampling events. The files currently visible under raw_data mainly cover 2021–2025 buoy/station exports. The full historical in-situ table is needed before those claims can be verified.
