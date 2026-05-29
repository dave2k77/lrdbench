# Neural Classical Workstation Results

These are compact public summaries from the completed workstation benchmark.
They are intended to be tracked in git and reviewed directly on GitHub.

The full report directories are not included here because the row-level stress
outputs contain very large CSV files. Publish those separately as release or
archive assets.

## Runs

| Label | Run ID | Mode |
| --- | --- | --- |
| Ground truth | `2800af31-ae35-4d12-af1d-dd5f4ed17223` | `ground_truth` |
| Stress | `5357f529-6c14-40e8-b3ad-027cd06539a8` | `stress_test` |

## Files

- `run_index.csv`: run IDs, manifest IDs, and local report paths.
- `estimator_leaderboard_comparison.csv`: ground-truth versus stress MAE,
  validity, runtime, rank, and stress drift.
- `uncertainty_coverage_summary.csv`: mean coverage and confidence-interval
  width before and after stress.
- `stress_operator_summary.csv`: aggregate drift, degradation, and coverage
  collapse by contamination operator.
- `stress_estimator_failure_modes.csv`: estimator-by-stressor drift and
  coverage collapse means.
- `false_positive_summary.csv`: false-positive LRD rates at `H=0.5` in the
  clean ground-truth run.
- `scale_window_sensitivity_summary.csv`: average scale/window variant
  sensitivity for DFA, DMA, and WaveletOLS variants.
- `checksums.sha256.csv`: SHA-256 checksums for the public summary CSV files.

## Interpretation

The tracked summaries preserve the key scientific result: classical estimators
can appear operationally valid while producing biased, unstable, saturated, or
miscalibrated inferences under neural-like contamination. The most important
stress failure mode is polynomial trend, followed by outliers and heavy-tailed
noise. Level shifts are comparatively benign for the estimators and metrics used
in this run.

The full interpretation is in
`../../neural_classical_workstation_analysis.md`.
