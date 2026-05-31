# OpenCode Configuration Validation Report

Date: 2026-05-30

## Result

Status: PASS

The project-local OpenCode setup resolves correctly with OpenCode's native debug tools and contains the intended scientific, engineering, QA, and manuscript-response coverage for the Villarrica chlorophyll forecasting paper.

## Native OpenCode Validation

Commands run:

```bash
jq empty opencode.json
opencode debug config
opencode debug agent paper-tl
opencode debug skill
```

Validated facts:

- `opencode.json` is valid JSON.
- `opencode debug config` resolves without config errors.
- `default_agent` resolves to `paper-tl`.
- OpenCode resolves 17 custom project agents plus built-in `build` and `plan`.
- OpenCode resolves 14 project skills.
- OpenCode resolves 6 project commands.
- All command target agents exist.

## Agents

Primary orchestrator:

- `paper-tl`

Specialist agents:

- `repo-architect`
- `data-engineer`
- `data-validation-auditor`
- `imputation-specialist`
- `remote-sensing-specialist`
- `limnology-domain-scientist`
- `forecast-ml-engineer`
- `transformer-timeseries-engineer`
- `ai-reproducibility-engineer`
- `forecast-diagnostics-specialist`
- `visualization-engineer`
- `scientific-python-engineer`
- `python-backend-engineer`
- `poetry-tooling-engineer`
- `qa-reviewer`
- `manuscript-response-editor`

The count is intentional. It is not minimal, but it matches the paper's reviewer risk surface: data provenance, imputation, remote sensing, lake bloom science, transformer forecasting, ML reproducibility, diagnostics, visualization, Python architecture, Poetry/tooling, QA, and manuscript response.

## Agent Communication

Communication is centralized through `paper-tl`.

Validated routing:

- Global `task` permission is denied by default.
- `paper-tl` explicitly allows task delegation to each specialist agent.
- Specialist subagents resolve with `task: false`, so they cannot freely spawn other subagents.
- `qa-reviewer` resolves with `apply_patch: false`, so it is a no-edit audit agent.

This is the correct pattern for this project because reviewer-resolution work needs a technical lead to integrate evidence and prevent inconsistent analyses across agents.

## Commands

Configured commands:

- `/paper-plan` -> `paper-tl`
- `/resolve-reviewers` -> `paper-tl`
- `/recreate-figures` -> `paper-tl`
- `/qa-paper-release` -> `qa-reviewer`
- `/validate-setup` -> `qa-reviewer`
- `/setup-python-quality` -> `poetry-tooling-engineer`

## Project Skills

Project-local skills:

- `paper-reproduction-workflow`
- `data-provenance-audit`
- `imputation-sensitivity`
- `remote-sensing-inversion`
- `lake-bloom-science`
- `forecast-evaluation`
- `transformer-timeseries-forecasting`
- `ml-reproducibility-audit`
- `threshold-warning-metrics`
- `lag-diagnostics`
- `figure-recreation-qa`
- `scientific-python-quality`
- `poetry-quality-tooling`
- `manuscript-revision-evidence`

Each skill has valid frontmatter, a name matching its folder, and a nonempty description.

## Scientific Coverage Against Reviewer Risks

Reviewer concern coverage:

- Data details, sampling frequency, sample size: `data-engineer`, `data-validation-auditor`, `data-provenance-audit`
- Observed versus imputed proportions: `data-validation-auditor`, `imputation-specialist`, `imputation-sensitivity`
- Preprocessing footprint and leakage: `imputation-specialist`, `transformer-timeseries-engineer`, `imputation-sensitivity`
- Satellite inversion algorithms and validation: `remote-sensing-specialist`, `remote-sensing-inversion`
- Claims about satellite integration: `remote-sensing-specialist`, `transformer-timeseries-engineer`, `manuscript-response-editor`
- TimesFM, Chronos, TSMixer, GRU, baselines: `transformer-timeseries-engineer`, `forecast-ml-engineer`, `transformer-timeseries-forecasting`
- AI model reproducibility and cached predictions: `ai-reproducibility-engineer`, `ml-reproducibility-audit`
- 7-day temporal shift: `forecast-diagnostics-specialist`, `lag-diagnostics`
- Threshold warning metrics: `forecast-diagnostics-specialist`, `limnology-domain-scientist`, `threshold-warning-metrics`
- Predictive uncertainty: `forecast-diagnostics-specialist`, `forecast-evaluation`
- Cross-site validation: `forecast-ml-engineer`, `transformer-timeseries-engineer`
- Figure 2 and end-to-end workflow figure: `visualization-engineer`, `figure-recreation-qa`
- Ecological uncertainty and management interpretation: `limnology-domain-scientist`, `lake-bloom-science`
- Poetry, pyproject, tests, linting, type checks: `poetry-tooling-engineer`, `scientific-python-engineer`, `poetry-quality-tooling`

## Local Tooling Check

Observed local environment:

- Poetry is installed: `Poetry (version 2.3.2)`.
- `python3` is installed.
- `pytest` is installed.
- `mypy` is installed.
- `pyproject.toml` and `poetry.lock` now exist in the repository root.
- Current validation commands pass: `poetry check`, `poetry run pytest`, `poetry run ruff check .`, and `poetry run ruff format --check .`.

Correct implication:

- The OpenCode setup now routes scientific Python/package maintenance to the configured tooling agents, while the repository itself has an executable Poetry package for reviewer-resolution outputs.
- Foundation-model forecast figures are now regenerated from `data/processed/foundation_model_predictions.csv`, which contains TimesFM and Chronos Large rolling-origin predictions for horizons 1–30.

## Residual Notes

- This report validates the OpenCode setup and routing. Scientific evidence status is tracked separately in `reports/reviewer_response_matrix.csv`, `reports/forecast_model_blockers.csv`, and `reports/needs_author_input.md`.
- Remaining blockers are missing satellite matchup inputs, missing full historical records, and foundation-model cross-site transfer validation.
