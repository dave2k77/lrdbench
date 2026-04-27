# Reproducibility Checklist

Use this checklist before sharing a benchmark result, supplementary archive, or manuscript table.

## Required run information

- Manifest file or manifest copy from the generated run directory.
- `run_id`.
- `lrdbench` version.
- Git commit when run from a repository checkout.
- Python version and platform from `manifest/environment.json`.
- Random seeds from the manifest.
- Benchmark mode and target estimand.

## Required outputs

- `tables/run_summary.csv`.
- `tables/per_stratum_metrics.csv`.
- `tables/leaderboard.csv` when a leaderboard is reported.
- `tables/estimator_metadata.csv`.
- `tables/failures.csv` and `tables/failure_map.csv`.
- `raw/records.csv`, `raw/estimates.csv`, and `raw/metrics.csv`.
- `artefacts/artefact_index.csv`.

## Checks to run

```bash
lrdbench validate path/to/manifest.yaml
lrdbench run path/to/manifest.yaml
lrdbench validate-output reports/<run_id>
```

For code changes, run the relevant test subset before reporting results:

```bash
pytest tests/integration/test_smoke_run.py tests/integration/test_custom_estimator_workflow.py
```

## Reporting guidance

State whether results are ground-truth, stress-test, or observational. Report leaderboard rules and
component weights whenever ranks are shown. For observational data, avoid accuracy language unless
external truth is available and declared in the benchmark design.
