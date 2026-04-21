# Development Handoff

Last updated: 2026-04-21

## Current State

The repository is on `main` and has been pushed to `origin/main`.

Recent commits:

- `db8239d` - Add failure maps and false-positive LRD metric
- `b2d0840` - Add MRW and fOU generators

The only local untracked file at handoff was `.codex`, which was pre-existing and intentionally left alone.

## Completed Today

- Read and internalized `lrdbench-design-specifications.pdf`.
- Fixed bootstrap percentile CI construction.
- Updated reporter aggregate export so `per_stratum_metrics.csv` includes per-stratum rows plus balanced-global summaries.
- Added MRW and fOU synthetic generators.
- Added contamination severity metadata:
  - `contamination_operator`
  - `contamination_family`
  - `contamination_severity`
- Added `failure_map.csv` report export.
- Added `false_positive_lrd_rate` metric with manifest-configurable:
  - `threshold`
  - `null_max`
- Added estimator disagreement metrics:
  - `cross_estimator_dispersion`
  - `pairwise_estimator_disagreement`
  - `family_level_disagreement`
- Added `estimator_disagreement.csv` report export.
- Added estimator parameter variants for scale/window sensitivity.
- Added scale/window sensitivity metrics:
  - `parameter_variant_sensitivity`
  - `max_variant_drift`
- Added `scale_window_sensitivity.csv` report export.
- Added benchmark-level uncertainty:
  - aggregate bootstrap CIs;
  - paired bootstrap estimator differences;
  - `benchmark_uncertainty.csv`;
  - raw result-store uncertainty scope.
- Added report completeness exports:
  - `estimator_metadata.csv`;
  - `failures.csv`;
  - `environment.json`;
  - `artefact_index.csv`;
  - raw `artefacts.csv`.
- Added richer HTML sections and publication-oriented LaTeX tables for disagreement, sensitivity, benchmark uncertainty, and failures.
- Added opt-in report figures:
  - `disagreement_heatmap`;
  - `sensitivity_heatmap`;
  - `benchmark_uncertainty_intervals`;
  - `false_positive_lrd`.
  These now use core `matplotlib`/`seaborn` dependencies rather than silently skipping when plotting
  is unavailable.
- Added regression and integration tests for the above.
- Ran exploratory contamination-stability benchmarks under `/tmp`.

## Verification At Handoff

The following passed before the latest push:

```bash
python -m ruff check .
python -m pytest
```

Full suite result after the false-positive metric work:

```text
43 passed
```

## Research Direction

The project has two linked roles:

1. Provide a comprehensive, reproducible LRD benchmarking framework.
2. Support a benchmark paper showing that classical second-order LRD estimators are unstable outside their intended stationary finite-variance regimes and cannot reliably separate genuine LRD from nonstationarity, heavy tails, intermittency, and related mechanisms.

This benchmark paper is intended to precede a theory paper arguing that the failure is structural rather than estimator-specific.

## Next Recommended Feature Slice

Proceed in this order:

1. Paper-scale benchmark manifests:
   - canonical ground-truth suite;
   - stress-test contamination suite;
   - null/false-positive suite;
   - disagreement and scale/window sensitivity suites.
2. Paper support workflow:
   - script or make target to run suites;
   - collect run IDs;
   - copy publication tables and figures.

Estimator disagreement, scale/window sensitivity, benchmark-level uncertainty, report-completeness exports, richer HTML/LaTeX report outputs, and first-pass figure support are now implemented. The most natural next step is paper-scale benchmark manifests and a repeatable paper-support workflow.
