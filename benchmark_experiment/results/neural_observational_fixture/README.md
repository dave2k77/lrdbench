# Neural Observational Fixture Results

This directory contains compact, tracked CSV summaries from the first clean observational-mode rehearsal run for the neural-classical benchmark workflow.

The full row-level report is intentionally not tracked because `reports/` is ignored. Re-run the manifest to regenerate it locally.

## Run

| Run | Mode | Run ID | Manifest |
| --- | --- | --- | --- |
| Neural observational fixture | `observational` | `8e08181f-7f9c-40a8-be83-e8c1c0c5424c` | `neural_observational_fixture_v1` |

Manifest:

`configs/suites/neural_observational_fixture.yaml`

Local full report from this workstation run:

`reports/neural_observational_fixture/8e08181f-7f9c-40a8-be83-e8c1c0c5424c/`

## Scope and claim boundary

This is a non-sensitive, deterministic, neural-like CSV fixture with two subjects, two channels, two conditions, 2048 samples per segment, and no benchmark truth. It is useful for verifying the observational workflow, report shape, QC exports, metadata strata, estimator disagreement, and scale/window sensitivity.

It must not be interpreted as evidence that the fixture contains true LRD, nor as an accuracy ranking. Observational outputs support truth-free claims about validity, runtime, uncertainty width, stability, disagreement, sensitivity, missingness, and failure concentration.

## Compact tables

- `run_index.csv` - run metadata and local report path.
- `observational_qc_summary.csv` - per-record source hashes, sampling rates, retained counts, missingness, duration, and value summaries.
- `observational_leaderboard.csv` - stability/robustness summary, not an accuracy ranking.
- `observational_metric_summary.csv` - estimator-level truth-free metric summaries.
- `observational_condition_summary.csv` - metric summaries by `rest`/`task` condition.
- `estimator_disagreement_summary.csv` - cross-estimator and family disagreement summaries.
- `scale_window_sensitivity_summary.csv` - variant sensitivity and max drift summaries.
- `checksums.sha256.csv` - SHA-256 checksums for the compact CSVs.

## Reproduce

From the repository root on this Windows workstation:

```bash
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate configs/suites/neural_observational_fixture.yaml
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main run configs/suites/neural_observational_fixture.yaml --dry-run --no-plugins
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main run configs/suites/neural_observational_fixture.yaml --no-plugins
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate-output reports/neural_observational_fixture/<run_id>
```
