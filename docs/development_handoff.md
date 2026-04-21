# Development Handoff

Last updated: 2026-04-21

## Current State

The repository is on `main`.

Recent commits:

- `f147529` - Harden paper workflow cache handling
- `7e2453f` - Add paper benchmark workflow scaffolding
- `9868d48` - Add advanced benchmark diagnostics and reporting
- `db8239d` - Add failure maps and false-positive LRD metric
- `b2d0840` - Add MRW and fOU generators

The only local untracked path at handoff is `.codex`, which was pre-existing and intentionally left
alone.

Generated benchmark outputs and caches are intentionally ignored:

- `reports/`
- `paper_support/artefacts/`
- `.lrdbench_cache/`

## Completed Today

- Promoted publication plotting to a core reporting capability:
  - `matplotlib` and `seaborn` are now core dependencies;
  - requested figures no longer silently skip when plotting imports fail;
  - disagreement and sensitivity heatmaps use `seaborn`.
- Added estimator disagreement metrics:
  - `cross_estimator_dispersion`;
  - `pairwise_estimator_disagreement`;
  - `family_level_disagreement`;
  - `estimator_disagreement.csv`.
- Added estimator parameter variants for scale/window sensitivity:
  - manifest `variants`;
  - `parameter_variant_sensitivity`;
  - `max_variant_drift`;
  - `scale_window_sensitivity.csv`.
- Added benchmark-level uncertainty:
  - aggregate bootstrap CIs;
  - paired bootstrap estimator differences;
  - raw result-store uncertainty scope;
  - `benchmark_uncertainty.csv`.
- Added report completeness exports:
  - `estimator_metadata.csv`;
  - `failures.csv`;
  - `environment.json`;
  - `artefact_index.csv`;
  - raw `artefacts.csv`.
- Added richer HTML sections and publication-oriented LaTeX tables for disagreement, sensitivity,
  benchmark uncertainty, and failures.
- Added opt-in report figures:
  - `degradation_curve`;
  - `disagreement_heatmap`;
  - `sensitivity_heatmap`;
  - `benchmark_uncertainty_intervals`;
  - `false_positive_lrd`.
- Added paper-oriented benchmark manifests:
  - `configs/suites/paper/canonical_ground_truth.yaml`;
  - `configs/suites/paper/stress_contamination.yaml`;
  - `configs/suites/paper/null_false_positive.yaml`;
  - `configs/suites/paper/sensitivity_disagreement.yaml`.
- Added the paper-support runner:
  - `python -m paper_support.run_paper_suites`;
  - writes normal reports under `reports/paper/<run_id>/`;
  - copies LaTeX tables and figures under `paper_support/artefacts/`;
  - writes `paper_support/artefacts/run_index.csv`.
- Hardened paper workflow cache/config behavior:
  - repo-root relative estimate caches under `.lrdbench_cache/...`;
  - `MPLCONFIGDIR` set to `.lrdbench_cache/matplotlib` to avoid unwritable home-config warnings.

## Paper Suite Run

Ran the null false-positive paper suite successfully:

```bash
python -m paper_support.run_paper_suites configs/suites/paper/null_false_positive.yaml
```

Latest run:

- run ID: `f9af4751-0514-4fee-b534-6b7cc12f94ff`
- HTML report:
  `reports/paper/f9af4751-0514-4fee-b534-6b7cc12f94ff/html/report.html`
- run index: `paper_support/artefacts/run_index.csv`
- copied artefacts: 8 files
  - 5 LaTeX tables;
  - 3 figures: disagreement heatmap, benchmark uncertainty intervals, false-positive LRD plot.

An earlier null-suite run also exists:

- run ID: `8726f2e8-b882-488b-9813-a2e0cc93db92`

The later run is preferred because it used the hardened cache/config behavior.

## Verification At Handoff

The following passed:

```bash
python -m ruff check .
python -m pytest tests/integration/test_paper_workflow.py
python -m pytest
```

Full suite result:

```text
58 passed
```

The null paper suite also completed successfully after the hardening patch, with no Matplotlib
configuration warning.

## Research Direction

The project has two linked roles:

1. Provide a comprehensive, reproducible LRD benchmarking framework.
2. Support a benchmark paper showing that classical second-order LRD estimators are unstable outside
   their intended stationary finite-variance regimes and cannot reliably separate genuine LRD from
   nonstationarity, heavy tails, intermittency, and related mechanisms.

This benchmark paper is intended to precede a theory paper arguing that the failure is structural
rather than estimator-specific.

## Next Recommended Step

Run the canonical ground-truth paper suite next:

```bash
python -m paper_support.run_paper_suites configs/suites/paper/canonical_ground_truth.yaml
```

Then proceed in this order:

1. Inspect the canonical report, generated figures, and `run_index.csv`.
2. Run `configs/suites/paper/stress_contamination.yaml`.
3. Run `configs/suites/paper/sensitivity_disagreement.yaml`.
4. Compare paper-suite tables and figures across runs to decide whether manifest grid sizes,
   estimator sets, or figure/table outputs need refinement before longer benchmark runs.
