# Development Handoff

Last updated: 2026-04-25

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

Local paper kit restored again on 2026-04-25 from the historical scaffold in commits `7e2453f` and
`f147529`:

- `paper_support/run_paper_suites.py`;
- `configs/suites/paper/canonical_ground_truth.yaml`;
- `configs/suites/paper/stress_contamination.yaml`;
- `configs/suites/paper/null_false_positive.yaml`;
- `configs/suites/paper/sensitivity_disagreement.yaml`;
- `tests/integration/test_paper_workflow.py`.

Verification on 2026-04-25:

- `python -m ruff check paper_support tests/integration/test_paper_workflow.py` — passed.
- `python -m pytest tests/integration/test_paper_workflow.py` — passed: 2 tests.
- Full local paper command used `PYTHONPATH=src` because the package was not installed in this
  shell:

  ```bash
  PYTHONPATH=src python -m paper_support.run_paper_suites \
    configs/suites/paper/canonical_ground_truth.yaml \
    configs/suites/paper/stress_contamination.yaml \
    configs/suites/paper/null_false_positive.yaml \
    configs/suites/paper/sensitivity_disagreement.yaml
  ```

Local paper suite runs on 2026-04-25:

- `canonical_ground_truth.yaml`
  - Run ID: `65a814d3-f659-456e-a569-85a0699228c7`
  - HTML report:
    `reports/paper/65a814d3-f659-456e-a569-85a0699228c7/html/report.html`
  - Staged artefacts: 7 files.
  - Key table counts: `per_stratum_metrics.csv` 1726 rows,
    `benchmark_uncertainty.csv` 961 rows, `estimator_disagreement.csv` 2542 rows,
    `failures.csv` 649 rows.
- `stress_contamination.yaml`
  - Run ID: `013396d5-2a31-444d-a5cf-d13112b78231`
  - HTML report:
    `reports/paper/013396d5-2a31-444d-a5cf-d13112b78231/html/report.html`
  - Staged artefacts: 8 files.
  - Key table counts: `per_stratum_metrics.csv` 9516 rows, `stress_metrics.csv` 10801 rows,
    `benchmark_uncertainty.csv` 4376 rows, `estimator_disagreement.csv` 10576 rows,
    `failures.csv` 2561 rows.
- `null_false_positive.yaml`
  - Run ID: `5600a62a-cb4d-42a8-a308-17351eb8cf6b`
  - HTML report:
    `reports/paper/5600a62a-cb4d-42a8-a308-17351eb8cf6b/html/report.html`
  - Staged artefacts: 8 files.
  - Key table counts: `per_stratum_metrics.csv` 236 rows,
    `benchmark_uncertainty.csv` 49 rows, `estimator_disagreement.csv` 631 rows,
    `failures.csv` 77 rows.
  - Observed `false_positive_lrd_rate` aggregate range: 0.0 to 0.1.
- `sensitivity_disagreement.yaml`
  - Run ID: `d5e94487-44e4-425e-a274-73fd15e6053c`
  - HTML report:
    `reports/paper/d5e94487-44e4-425e-a274-73fd15e6053c/html/report.html`
  - Staged artefacts: 8 files.
  - Key table counts: `per_stratum_metrics.csv` 1118 rows,
    `benchmark_uncertainty.csv` 574 rows, `estimator_disagreement.csv` 2201 rows,
    `scale_window_sensitivity.csv` 367 rows, `failures.csv` 577 rows.

Run index: `paper_support/artefacts/run_index.csv`. The local estimate cache now contains complete
fit caches for these runs under `.lrdbench_cache/paper_*`, which should make repeated local paper
runs substantially faster.

Planning note from inspecting the 2026-04-25 outputs: the current paper leaderboards should not be
treated as final paper rankings. Some truth-free aggregate metrics produce synthetic estimator names
such as `__all_estimators__`, and variant sensitivity metrics are grouped by base estimator while
accuracy rows are emitted per variant. Use the exported disagreement/sensitivity tables and figures
for interpretation until leaderboard semantics are tightened or the paper manifests remove those
metrics from leaderboard components.

Follow-up on 2026-04-25:

- Tracked library fix: `WeightedRankLeaderboardBuilder` now ranks only estimator names declared in
  the manifest. Synthetic aggregate diagnostic names such as `__all_estimators__` remain in metric
  exports, but cannot appear as leaderboard rows.
- Added a unit regression test for this behavior:
  `tests/unit/test_leaderboard.py`.
- Local paper manifest adjustment: removed group-level disagreement/sensitivity metrics from
  leaderboard component lists while leaving those metrics in reports and exported tables.
- Added local-only paper smoke manifests under `configs/suites/paper/smoke_*.yaml`.
- Added `--smoke` to `python -m paper_support.run_paper_suites`, selecting the smoke manifest set.
- Verification:
  - `python -m ruff check .` — passed.
  - `python -m pytest` — passed: 60 tests, 80% total coverage.
  - Local paper smoke command:

    ```bash
    PYTHONPATH=src python -m paper_support.run_paper_suites --smoke \
      --export-root reports/paper_smoke \
      --artefact-root paper_support/artefacts_smoke \
      --index-path paper_support/artefacts_smoke/run_index.csv
    ```

Smoke paper runs on 2026-04-25:

- `smoke_canonical_ground_truth.yaml`
  - Run ID: `071d5d24-2433-407d-90e2-e19b2b34f689`
  - HTML report:
    `reports/paper_smoke/071d5d24-2433-407d-90e2-e19b2b34f689/html/report.html`
  - Staged artefacts: 7 files.
- `smoke_stress_contamination.yaml`
  - Run ID: `d28f1de0-ab83-407e-a865-6c9dc087ce6c`
  - HTML report:
    `reports/paper_smoke/d28f1de0-ab83-407e-a865-6c9dc087ce6c/html/report.html`
  - Staged artefacts: 8 files.
- `smoke_null_false_positive.yaml`
  - Run ID: `17f564ab-060d-4501-bbcb-08aeb1fd246e`
  - HTML report:
    `reports/paper_smoke/17f564ab-060d-4501-bbcb-08aeb1fd246e/html/report.html`
  - Staged artefacts: 8 files.
- `smoke_sensitivity_disagreement.yaml`
  - Run ID: `63970c6b-792f-4546-a815-da880658eafd`
  - HTML report:
    `reports/paper_smoke/63970c6b-792f-4546-a815-da880658eafd/html/report.html`
  - Staged artefacts: 8 files.

Refreshed full paper reports after the leaderboard fix:

- `canonical_ground_truth.yaml`
  - Run ID: `cad42a6a-79bb-450a-87c0-d084171cbf31`
  - HTML report:
    `reports/paper/cad42a6a-79bb-450a-87c0-d084171cbf31/html/report.html`
  - Leaderboard rows checked: 6; no synthetic estimator rows.
- `sensitivity_disagreement.yaml`
  - Run ID: `1ad150af-055f-4300-8f96-c0f8f68af393`
  - HTML report:
    `reports/paper/1ad150af-055f-4300-8f96-c0f8f68af393/html/report.html`
  - Leaderboard rows checked: 9; no synthetic estimator rows.

Grid-tuning pass on 2026-04-25:

- Current output summary before tuning:
  - stress degradation was strongest for `polynomial_trend`, moderate for `outliers`, weaker for
    `heavy_tail_noise`, and effectively invariant for `level_shift`;
  - null false-positive aggregate rows ranged from 0.0 to 0.05 in the then-current full run;
  - sensitivity run had 24 invalid estimates, all from `WaveletOLS::balanced_band` at `n=512`
    (`insufficient_signal_for_wavelet_ols`).
- Full local paper manifest changes:
  - canonical replicates increased from 3 to 5;
  - stress replicates increased from 3 to 5;
  - stress `level_shift` reduced to one negative-control level: `shift: [0.75]`;
  - stress `polynomial_trend` strengths expanded to `[0.25, 0.75, 1.25]`;
  - stress `outliers` rates expanded to `[0.01, 0.05, 0.1]`;
  - stress `heavy_tail_noise` scales expanded to `[0.25, 0.75, 1.25]`;
  - null false-positive replicates increased from 10 to 30;
  - sensitivity/disagreement replicates increased from 3 to 5;
  - sensitivity `WaveletOLS::balanced_band` changed from `j_drop_low: 2`,
    `j_drop_high: 2` to `j_drop_low: 1`, `j_drop_high: 1`.
- Validation:
  - `python -m pytest tests/integration/test_paper_workflow.py` — passed: 3 tests.
  - All `configs/suites/paper/*.yaml` manifests loaded successfully with `PYTHONPATH=src`.
  - Paper smoke preflight passed with:

    ```bash
    PYTHONPATH=src python -m paper_support.run_paper_suites --smoke \
      --export-root reports/paper_smoke \
      --artefact-root paper_support/artefacts_smoke \
      --index-path paper_support/artefacts_smoke/run_index.csv
    ```

Latest smoke paper runs after grid tuning:

- `smoke_canonical_ground_truth.yaml`
  - Run ID: `ba3d36b8-1dc6-48fc-88a7-70bc39fb325b`
  - HTML report:
    `reports/paper_smoke/ba3d36b8-1dc6-48fc-88a7-70bc39fb325b/html/report.html`
- `smoke_stress_contamination.yaml`
  - Run ID: `32e65c9b-4851-4230-8dc2-e1c1cfd60c9b`
  - HTML report:
    `reports/paper_smoke/32e65c9b-4851-4230-8dc2-e1c1cfd60c9b/html/report.html`
- `smoke_null_false_positive.yaml`
  - Run ID: `420d3440-5bc3-4bac-814f-34713ef00152`
  - HTML report:
    `reports/paper_smoke/420d3440-5bc3-4bac-814f-34713ef00152/html/report.html`
- `smoke_sensitivity_disagreement.yaml`
  - Run ID: `0f09e394-09c1-4cc0-af59-c25ce8d3ec29`
  - HTML report:
    `reports/paper_smoke/0f09e394-09c1-4cc0-af59-c25ce8d3ec29/html/report.html`

Next paper-campaign command, when ready for a longer local run:

```bash
PYTHONPATH=src python -m paper_support.run_paper_suites \
  configs/suites/paper/canonical_ground_truth.yaml \
  configs/suites/paper/stress_contamination.yaml \
  configs/suites/paper/null_false_positive.yaml \
  configs/suites/paper/sensitivity_disagreement.yaml
```

Tuned full paper campaign completed on 2026-04-25 with the command above.

Final tuned paper runs:

- `canonical_ground_truth.yaml`
  - Run ID: `53f3f969-4f42-4233-82df-e0137ceeb69b`
  - HTML report:
    `reports/paper/53f3f969-4f42-4233-82df-e0137ceeb69b/html/report.html`
  - Staged artefacts: 7 files.
  - Key table counts: `per_stratum_metrics.csv` 1726 rows,
    `benchmark_uncertainty.csv` 961 rows, `estimator_disagreement.csv` 3886 rows,
    `failures.csv` 649 rows.
  - Estimates: 960 total, 0 invalid.
  - Leaderboard rows checked: 6; no synthetic estimator rows.
- `stress_contamination.yaml`
  - Run ID: `c4f56a44-1d66-4808-8705-28c2b20383f9`
  - HTML report:
    `reports/paper/c4f56a44-1d66-4808-8705-28c2b20383f9/html/report.html`
  - Staged artefacts: 8 files.
  - Key table counts: `per_stratum_metrics.csv` 11916 rows, `stress_metrics.csv` 22801 rows,
    `benchmark_uncertainty.csv` 5496 rows, `estimator_disagreement.csv` 20416 rows,
    `failures.csv` 3201 rows.
  - Estimates: 6000 total, 0 invalid.
  - Leaderboard rows checked: 5; no synthetic estimator rows.
  - Stress pattern: `level_shift` remains a useful negative control (`estimate_drift` 0.0,
    degradation ratio 1.0). Degradation increases clearly with stronger polynomial trends,
    outlier rates/amplitudes, and heavy-tail noise scales. Highest mean degradation ratios in this
    run were polynomial trend strength 1.25 (`order=2`: 7.8751, `order=1`: 7.3011), followed by
    high-rate/high-amplitude outliers and scale 1.25 heavy-tail noise.
- `null_false_positive.yaml`
  - Run ID: `9e55852c-d670-4e11-a1c5-8df238feb187`
  - HTML report:
    `reports/paper/9e55852c-d670-4e11-a1c5-8df238feb187/html/report.html`
  - Staged artefacts: 8 files.
  - Key table counts: `per_stratum_metrics.csv` 236 rows,
    `benchmark_uncertainty.csv` 49 rows, `estimator_disagreement.csv` 1751 rows,
    `failures.csv` 77 rows.
  - Estimates: 600 total, 0 invalid.
  - Leaderboard rows checked: 5; no synthetic estimator rows.
  - Balanced-global false-positive LRD rates: `RS` 0.0167, `DFA` 0.0333, `GPH` 0.0667,
    `Periodogram` 0.0167, `ModifiedLocalWhittle` 0.05.
- `sensitivity_disagreement.yaml`
  - Run ID: `f5aeb79c-c1d6-4219-92ab-e68d2e591783`
  - HTML report:
    `reports/paper/f5aeb79c-c1d6-4219-92ab-e68d2e591783/html/report.html`
  - Staged artefacts: 8 files.
  - Key table counts: `per_stratum_metrics.csv` 1184 rows,
    `benchmark_uncertainty.csv` 628 rows, `estimator_disagreement.csv` 3721 rows,
    `scale_window_sensitivity.csv` 559 rows, `failures.csv` 625 rows.
  - Estimates: 720 total, 0 invalid.
  - Leaderboard rows checked: 9; no synthetic estimator rows.
  - Balanced-global `parameter_variant_sensitivity`: `DFA` 0.0477, `DMA` 0.0640,
    `WaveletOLS` 0.0284.
  - Balanced-global `max_variant_drift`: `DFA` 0.1114, `DMA` 0.1518, `WaveletOLS` 0.0673.

The tuned full campaign writes the current `paper_support/artefacts/run_index.csv` and completes
the immediate publication-run preflight. Next recommended work is interpretive: inspect the latest
HTML reports and staged figures/tables, choose the subset of results to carry into the manuscript,
and decide whether the stress narrative should emphasize polynomial-trend nonstationarity first or
present heavy tails/outliers as separate robustness sections.

Manuscript-facing selection pass on 2026-04-25:

- Created local-only selection bundle under `paper_support/artefacts/selected/`.
- Selection note:
  - `paper_support/artefacts/selected/manuscript_selection.md`
- Candidate main figures:
  - `paper_support/artefacts/selected/fig1_stress_degradation_curve.png`
  - `paper_support/artefacts/selected/fig2_null_false_positive_lrd.png`
  - `paper_support/artefacts/selected/fig3_scale_window_sensitivity_heatmap.png`
- Candidate supplementary figure:
  - `paper_support/artefacts/selected/fig_supp_canonical_disagreement_heatmap.png`
- Main-text numeric anchors recorded in the selection note:
  - canonical balanced-global MAE;
  - stress balanced-global degradation ratio;
  - null balanced-global false-positive LRD rate;
  - scale/window sensitivity and max variant drift;
  - selected stress-severity degradation ratios.

Selection recommendation: use the stress degradation result as the first main results figure, then
use null false-positive and scale/window sensitivity as separate results panels/figures. Keep the
canonical disagreement heatmap and full audit-style LaTeX/CSV exports in supplement unless the paper
needs an early estimator-disagreement framing figure. The current `metrics_summary.tex` exports are
too broad for main text; derive compact manuscript tables from CSV exports or from
`manuscript_selection.md`.

Public research release roadmap documented on 2026-04-25:

- Tracked roadmap: `docs/public_release_roadmap.md`.
- MkDocs nav entry: Meta → Public release roadmap.
- Roadmap separates local manuscript infrastructure from public library readiness.
- Immediate next sprint targets Alpha 0.1:
  - tracked design specification;
  - public small/medium benchmark suites;
  - estimator status table;
  - uncertainty/leaderboard/failure semantics docs;
  - `lrdbench validate <manifest>`;
  - clean-clone public-small-suite verification.

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
