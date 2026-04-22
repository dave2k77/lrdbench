# Development Handoff

Last updated: 2026-04-22

## Current State

The repository is on `main`.

Recent commits (library / reporting; paper asset paths are **local-only**—see below):

- `9da6dea` - Paper workflow local-only; update CHANGELOG and handoff
- `8a5edb4` - Add paper support paths to `.gitignore`
- `f40cea1` - Update development handoff
- `f147529` - Harden paper workflow cache handling
- `7e2453f` - Add paper benchmark workflow scaffolding
- `9868d48` - Add advanced benchmark diagnostics and reporting

**Tracked in Git:** library source, `configs/suites/` smoke and shared benchmarks, `docs/`
(including this file), `CHANGELOG.md`, tests under `tests/` except the optional paper integration
test listed under “Local-only paths”.

Clean-clone docs now include `docs/paper_workflow.md`, which explains the local-only paper kit
without tracking draft paper artefacts.

**This file (`development_handoff.md`) and `CHANGELOG.md` are meant to stay synced with the remote**
so you can continue planning and execution notes on any machine after `git pull`.

## Local-only paths (not synced to the remote)

The following are listed in `.gitignore` and remain on your workstation only—copy or recreate them
when you set up a new environment for publication runs:

- `paper_support/` — entire directory (runner package, optional `artefacts/` staging).
- `configs/suites/paper/` — paper-oriented YAML manifests.
- `tests/integration/test_paper_workflow.py` — optional smoke test for the local runner.
- `reports/` — all benchmark HTML/CSV/LaTeX outputs (including `reports/paper/<run_id>/`).
- `.lrdbench_cache/` — estimate cache and matplotlib config dir used by local paper runs.

Other common ignores: `.codex`, `.venv/`, etc., per `.gitignore`.

## Completed recently (core library)

- Publication plotting is a core reporting capability:
  - `matplotlib` and `seaborn` are core dependencies;
  - requested figures are not silently skipped when plotting imports fail;
  - disagreement and sensitivity heatmaps use `seaborn`.
- Estimator disagreement metrics:
  - `cross_estimator_dispersion`;
  - `pairwise_estimator_disagreement`;
  - `family_level_disagreement`;
  - `estimator_disagreement.csv`.
- Estimator parameter variants for scale/window sensitivity:
  - manifest `variants`;
  - `parameter_variant_sensitivity`;
  - `max_variant_drift`;
  - `scale_window_sensitivity.csv`.
- Benchmark-level uncertainty:
  - aggregate bootstrap CIs;
  - paired bootstrap estimator differences;
  - raw result-store uncertainty scope;
  - `benchmark_uncertainty.csv`.
- Report completeness exports:
  - `estimator_metadata.csv`;
  - `failures.csv`;
  - `environment.json`;
  - `artefact_index.csv`;
  - raw `artefacts.csv`.
- Richer HTML and publication-oriented LaTeX tables for disagreement, sensitivity, benchmark
  uncertainty, and failures.
- Opt-in report figures:
  - `degradation_curve`;
  - `disagreement_heatmap`;
  - `sensitivity_heatmap`;
  - `benchmark_uncertainty_intervals`;
  - `false_positive_lrd`.

## Local paper workflow (reproduce on each machine)

When you maintain `paper_support/` and `configs/suites/paper/` locally, a typical layout is:

- Manifests (examples): `canonical_ground_truth.yaml`, `stress_contamination.yaml`,
  `null_false_positive.yaml`, `sensitivity_disagreement.yaml` under `configs/suites/paper/`.
- Runner: `python -m paper_support.run_paper_suites <manifest> [...]` from the repo root.
- Writes: normal reports under `reports/paper/<run_id>/`; copies LaTeX and figures to
  `paper_support/artefacts/`; appends `paper_support/artefacts/run_index.csv`.
- Cache/config: repo-root-relative estimate caches under `.lrdbench_cache/...`; set
  `MPLCONFIGDIR` to `.lrdbench_cache/matplotlib` in the runner to avoid unwritable home-config
  warnings.

Example command (paths exist only after you create or copy the local kit):

```bash
python -m paper_support.run_paper_suites configs/suites/paper/null_false_positive.yaml
```

Example outcomes from a prior local run (IDs will differ on your machine):

- HTML report: `reports/paper/<run_id>/html/report.html`
- Run index: `paper_support/artefacts/run_index.csv`
- Typical staged count: several LaTeX tables plus figures (disagreement heatmap, benchmark
  uncertainty intervals, false-positive LRD plot when requested).

## Verification (CI vs local)

On the remote / CI, the following are representative:

```bash
python -m ruff check .
python -m pytest
```

Optional **local** check after (re)creating `paper_support` and the paper integration test:

```bash
python -m pytest tests/integration/test_paper_workflow.py
```

Full `pytest` pass counts move with the test suite; run `pytest` after each pull for the current
number.

Local verification on 2026-04-22 after installing `.[all]`:

- `python -m ruff check .` — passed.
- `python -m pytest` — passed: 56 tests, 80% total coverage in a clean clone; 57 tests, 80%
  total coverage when the local-only `tests/integration/test_paper_workflow.py` is present.
- `mkdocs build --strict` — passed after adding the tracked paper workflow docs page and nav entry.
- `python -m pytest tests/integration/test_paper_workflow.py` — passed after recreating the
  local-only paper runner scaffold on this machine.

Note: `SPECIFICATION.md` refers to `lrdbench-design-specifications.pdf` as the frozen design
authority when present locally. That PDF is not currently tracked in this clean repository.

Local paper kit recreated on this machine:

- `paper_support/run_paper_suites.py`;
- `configs/suites/paper/canonical_ground_truth.yaml`;
- `configs/suites/paper/stress_contamination.yaml`;
- `configs/suites/paper/null_false_positive.yaml`;
- `configs/suites/paper/sensitivity_disagreement.yaml`;
- `tests/integration/test_paper_workflow.py`.

These paths remain ignored by Git.

Canonical paper smoke run on 2026-04-22:

- Command: `python -m paper_support.run_paper_suites configs/suites/paper/canonical_ground_truth.yaml`
- Run ID: `2d321e2e-3cb2-4c41-a43b-a5caaa09fe5e`
- HTML report: `reports/paper/2d321e2e-3cb2-4c41-a43b-a5caaa09fe5e/html/report.html`
- Staged artefacts: 7 files under
  `paper_support/artefacts/2d321e2e-3cb2-4c41-a43b-a5caaa09fe5e/`.
- Key table counts: `per_stratum_metrics.csv` 151 rows,
  `benchmark_uncertainty.csv` 48 rows, `estimator_disagreement.csv` 76 rows,
  `failures.csv` 42 rows.

Additional local paper suite runs on 2026-04-22:

- `stress_contamination.yaml`
  - Run ID: `10cfa083-3278-4f1b-9862-f489580bcc09`
  - HTML report:
    `reports/paper/10cfa083-3278-4f1b-9862-f489580bcc09/html/report.html`
  - Staged artefacts: 8 files.
  - Key table counts: `per_stratum_metrics.csv` 296 rows, `stress_metrics.csv` 160 rows,
    `benchmark_uncertainty.csv` 96 rows, `estimator_disagreement.csv` 74 rows,
    `failure_map.csv` 48 rows, `failures.csv` 48 rows.
  - Local manifest correction made before the successful run: `outliers` uses
    `rate`/`amplitude`; `polynomial_trend` uses `order`/`strength`.
- `null_false_positive.yaml`
  - Run ID: `f811d6eb-5008-4f2c-b2b4-3d1f69b71fae`
  - HTML report:
    `reports/paper/f811d6eb-5008-4f2c-b2b4-3d1f69b71fae/html/report.html`
  - Staged artefacts: 7 files.
  - Key table counts: `per_stratum_metrics.csv` 42 rows,
    `estimator_disagreement.csv` 60 rows, `failures.csv` 14 rows.
  - `false_positive_lrd_rate` balanced-global rows were produced for `RS`, `DFA`, and `GPH`;
    all were 0.0 in this small smoke-sized null run.
- `sensitivity_disagreement.yaml`
  - Run ID: `f7b513aa-829c-43ec-a9e1-428a73c4e101`
  - HTML report:
    `reports/paper/f7b513aa-829c-43ec-a9e1-428a73c4e101/html/report.html`
  - Staged artefacts: 7 files.
  - Key table counts: `per_stratum_metrics.csv` 66 rows,
    `estimator_disagreement.csv` 56 rows, `scale_window_sensitivity.csv` 14 rows,
    `failures.csv` 26 rows.

## Research Direction

The project has two linked roles:

1. Provide a comprehensive, reproducible LRD benchmarking framework.
2. Support a benchmark paper showing that classical second-order LRD estimators are unstable outside
   their intended stationary finite-variance regimes and cannot reliably separate genuine LRD from
   nonstationarity, heavy tails, intermittency, and related mechanisms.

This benchmark paper is intended to precede a theory paper arguing that the failure is structural
rather than estimator-specific.

## Next recommended steps

1. On a machine where the **local** paper kit exists, run the canonical ground-truth manifest:

   ```bash
   python -m paper_support.run_paper_suites configs/suites/paper/canonical_ground_truth.yaml
   ```

2. Inspect the canonical report, figures, and `paper_support/artefacts/run_index.csv`.
3. Run `stress_contamination.yaml` and `sensitivity_disagreement.yaml` from the same local kit.
4. Compare tables and figures across runs; adjust manifest grids, estimators, or `report.figure_set`
   before longer benchmark campaigns.

When working **only** from a clean clone without the local paper kit, use `lrdbench run` with tracked
manifests under `configs/suites/` (e.g. smoke suites) and the same reporting options supported by
`docs/benchmark_protocol.md`.
