# Needs author input

The reproducible local repository is missing evidence required for several manuscript claims.

## Satellite inversion and matchup validation

- Status: `needs_author_input`
- Required input: A table containing station_id, date, in-situ Chl-a, satellite sensor, pixel/ROI reflectance bands, QA/cloud mask, matchup distance/window, and train/test split identifiers.
- Reason: The local raw_data directory contains buoy/station spreadsheet exports but no satellite reflectance products, spectral indices, matchup table, or inversion outputs.

## Foundation-model forecast recreation

Figures 4–7 are now regenerated from cached TimesFM and Chronos Large rolling-origin predictions produced from the local processed Chl-a series. The cache is stored at data/processed/foundation_model_predictions.csv. Chronos Large was executed on MPS with 16 samples for tractable local inference; this setting should be disclosed for uncertainty-interval interpretation.

## Historical monitoring record

The manuscript claims long-term records from 1989–2024 and 385 sampling events. The files currently visible under raw_data mainly cover 2021–2025 buoy/station exports. The full historical in-situ table is needed before those claims can be verified.
