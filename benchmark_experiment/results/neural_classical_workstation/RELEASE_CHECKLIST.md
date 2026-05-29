# Release Checklist

Use this checklist when publishing the workstation benchmark results.

## Commit To Git

- Benchmark specification:
  `benchmark_experiment/neural_classical_estimator_benchmark_spec.md`
- Workstation analysis:
  `benchmark_experiment/neural_classical_workstation_analysis.md`
- Public result index:
  `benchmark_experiment/README.md`
- Compact result tables:
  `benchmark_experiment/results/neural_classical_workstation/`
- Exact manifests:
  `configs/suites/neural_classical_workstation_ground_truth.yaml`
  `configs/suites/neural_classical_workstation_stress.yaml`
- Export helper:
  `scripts/export_public_benchmark_results.py`

## Do Not Commit To Git

- `reports/neural_classical_workstation/*/raw/`
- Large report tables such as `metrics.csv`, `estimator_disagreement.csv`,
  `benchmark_uncertainty.csv`, `per_stratum_metrics.csv`, `stress_metrics.csv`,
  `failure_map.csv`, and `failures.csv`
- Local caches under `configs/suites/.lrdbench_cache/`
- Local virtual environments

## Suggested Release Assets

Attach these to a GitHub Release or upload them to Zenodo/OSF/Figshare:

- `neural_classical_workstation_public_summaries.zip`
- `neural_classical_workstation_ground_truth_report.zip`
- `neural_classical_workstation_stress_report_core.zip`
- `neural_classical_workstation_stress_raw_metrics.zip`

If any archive is too large, split it by report subdirectory or table family.

## Pre-Release Verification

- Re-run `scripts/export_public_benchmark_results.py`.
- Confirm all public CSVs are small enough for git.
- Confirm `checksums.sha256.csv` changed only when the summaries changed.
- Validate the output contracts for both report directories.
- Record the release tag and DOI, if using Zenodo, in
  `benchmark_experiment/README.md`.
- Add a citation note to the project README once the DOI is available.

## Suggested Tag

`benchmark-neural-classical-workstation-2026-05`
