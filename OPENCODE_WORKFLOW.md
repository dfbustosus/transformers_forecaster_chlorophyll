# OpenCode Workflow for the Villarrica Paper Revision

This project now has a specialized OpenCode setup for recreating the manuscript figures and answering reviewer comments with reproducible code.

## Start

From the repository root:

```bash
opencode .
```

OpenCode will use `paper-tl` as the default agent. If OpenCode was already running before these files were created, quit and restart it so the new config, agents, and skills are loaded.

## Main Commands

Use these configured OpenCode commands:

- `/paper-plan`: build the reviewer-resolution implementation plan.
- `/resolve-reviewers`: implement the code analyses needed for all reviewer comments.
- `/recreate-figures`: recreate all manuscript figures and the new methodology flowchart.
- `/qa-paper-release`: run final QA before resubmission.
- `/validate-setup`: audit this OpenCode setup itself.
- `/setup-python-quality`: prepare Poetry, pyproject, tests, linting, and reproducibility tooling when implementation begins.

You can also invoke agents directly with `@agent-name`.

## Primary Agent

- `paper-tl`: technical lead and orchestrator. It maps reviewer comments to artifacts, delegates specialist work, integrates outputs, and blocks unsupported manuscript claims.

## Specialist Agents

- `repo-architect`: repository architecture, package boundaries, configs, tests, outputs.
- `data-engineer`: raw Excel ingestion, station normalization, canonical tables, manifests.
- `data-validation-auditor`: schemas, missingness, observed/imputed proportions, leakage checks.
- `imputation-specialist`: HPBR/climatology, interpolation, smoothing, sensitivity tests.
- `remote-sensing-specialist`: satellite indices, inversion algorithms, matchup validation, integration audit.
- `limnology-domain-scientist`: HAB domain checks, ecological plausibility, thresholds, uncertainty framing.
- `forecast-ml-engineer`: forecasting models, rolling-origin metrics, baselines, cross-site validation.
- `transformer-timeseries-engineer`: TimesFM, Chronos, TSMixer, GRU, quantiles, foundation-model evaluation.
- `ai-reproducibility-engineer`: model versions, seeds, cached predictions, optional dependencies, hardware/runtime controls.
- `forecast-diagnostics-specialist`: D7 lag, thresholds, uncertainty coverage, warning metrics.
- `visualization-engineer`: figure recreation, Figure 2 redesign, end-to-end flowchart, visual QA.
- `scientific-python-engineer`: tests, package quality, deterministic scientific Python.
- `python-backend-engineer`: CLI/backend pipeline interfaces and robust run commands.
- `poetry-tooling-engineer`: Poetry, pyproject, dependency groups, ruff, pytest, type checking, pre-commit.
- `qa-reviewer`: independent no-edit QA review.
- `manuscript-response-editor`: response-to-reviewer text and manuscript insertion wording.

## Project Skills

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

## Expected Output Tree

The configured agents are instructed to build toward:

```text
src/villarrica_forecaster/
scripts/
configs/
data/processed/
outputs/tables/
figures/
reports/
tests/
```

## Recommended First Prompt

```text
Run /paper-plan. Use reviewer_comments.txt and the manuscript to create the reviewer-response implementation matrix. Then inspect raw_data and identify which reviewer claims can be answered from local data versus which need author input.
```
