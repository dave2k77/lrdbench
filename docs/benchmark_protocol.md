# Benchmark protocol

1. **Manifest** (YAML): declares `mode`, `source`, optional `contamination`, `estimators`, `metrics`, `leaderboards`, `report`, and `seeds`.
2. **Records**: synthetic grid (`generator_grid`), stress pairs (clean + contaminated), or observational series (`csv_series_index` / `inline_table`).
3. **Estimation**: each `(record, estimator_spec)` yields an `EstimateResult`.
4. **Evaluation**: mode-appropriate metrics (`MetricBundle`) and optional leaderboards.
5. **Outputs**: CSV result store under `reports/<run_id>/` plus HTML/CSV summaries from the reporter.

Example suite manifests: `configs/suites/smoke_*.yaml`.

## Report completeness

The CSV/HTML reporter emits audit-oriented tables in addition to metric summaries:

- `tables/estimator_metadata.csv`: enrolled estimators, families, target estimands, assumptions,
  parameters, and version metadata.
- `tables/failures.csv`: per-estimator/per-stratum missing metric values, missing uncertainty
  counts, invalid estimate counts, and invalid rates when `validity_rate` rows are available.
- `manifest/environment.json`: Python/platform/package metadata plus seed, execution, and
  uncertainty settings.
- `artefacts/artefact_index.csv`: one row per exported report artefact.

The raw result store also persists report artefact metadata to `raw/artefacts.csv`.

The HTML report renders compact sections for failure summaries, estimator disagreement,
scale/window sensitivity, benchmark uncertainty, uncertainty calibration, and audit artefact links.
When `latex` is requested, the reporter also writes publication-oriented tables for disagreement,
sensitivity, benchmark uncertainty, and failures under `latex/`.

Optional `report.figure_set` entries:

- `degradation_curve`: stress-test degradation bar plot by contamination operator.
- `disagreement_heatmap`: aggregate estimator-disagreement heatmap.
- `sensitivity_heatmap`: aggregate scale/window-sensitivity heatmap.
- `benchmark_uncertainty_intervals`: point estimates with bootstrap interval error bars.
- `false_positive_lrd`: balanced-global false-positive LRD rate bar plot.

Figure generation is part of the core reporting contract and uses the standard plotting stack
(`matplotlib` and `seaborn`). Requested figures are omitted only when the relevant data is absent;
if suitable data exists but plotting cannot be imported, the reporter raises a clear runtime error.

## Estimator disagreement

Truth-free disagreement metrics are admissible in all benchmark modes when multiple estimators are
declared:

- `cross_estimator_dispersion`: population standard deviation of valid point estimates within
  each record.
- `pairwise_estimator_disagreement`: absolute point-estimate difference for each estimator pair
  within each record.
- `family_level_disagreement`: mean absolute disagreement within estimator families and between
  estimator-family pairs.

These metrics preserve record-level estimator pairing and aggregate using the same stratum and
balanced-global rules as other metrics. The reporter exports them to
`tables/estimator_disagreement.csv`.

## Scale/window sensitivity

An estimator entry may declare parameter variants to evaluate sensitivity to plausible scale,
window, or tuning choices:

```yaml
estimators:
  - name: DFA
    family: time_domain
    target_estimand: hurst_scaling_proxy
    params:
      n_bootstrap: 0
    variants:
      - name: short_scales
        params:
          min_scale: 8
          max_scale: 32
      - name: long_scales
        params:
          min_scale: 16
          max_scale: 64
```

Variants are materialised as estimator names of the form `DFA::short_scales` while preserving the
base registry estimator `DFA` for execution. Truth-free sensitivity metrics are admissible in all
benchmark modes:

- `parameter_variant_sensitivity`: population standard deviation of valid variant point estimates
  for each base estimator within each record.
- `max_variant_drift`: maximum absolute point-estimate difference across valid variants for each
  base estimator within each record.

The reporter exports these rows to `tables/scale_window_sensitivity.csv`.

## Benchmark-level uncertainty

Optional YAML block `uncertainty`:

- `enabled` (boolean, default false when the block is absent): compute benchmark-level
  uncertainty rows.
- `n_bootstrap` (integer >= 1, default 200): bootstrap replicates.
- `ci_levels` (list of confidence levels, default `[0.95]`): percentile interval levels.
- `seed` (integer, optional): bootstrap RNG seed; defaults to `seeds.global_seed`.
- `metrics` (list of metric names, optional): restrict aggregate bootstrap intervals to selected
  metrics.
- `paired` (boolean, default false): also compute paired bootstrap intervals for estimator
  differences on records where both estimators have the same per-record metric.
- `paired_metrics` (list of metric names, optional): restrict paired differences separately.

Aggregate intervals bootstrap records within each stratum and bootstrap stratum summaries for
balanced-global rows. Paired intervals preserve record-level estimator pairing and report mean
differences as `EstimatorA__minus__EstimatorB`. The reporter exports rows to
`tables/benchmark_uncertainty.csv`, and the raw result store records them with
`scope=uncertainty`.

## Execution (Phase 5)

Optional YAML block `execution`:

- `max_workers` (integer ≥ 1, default 1): when greater than 1, estimator `fit` calls run in parallel with a thread pool (order of results matches the serial `(record × estimator)` grid).
- `estimate_cache_dir` (string, optional): directory for pickle caches of `EstimateResult` keyed by record id, estimator name, parameter schema, and a hash of the series values. Resolve relative paths against the same working base as observational CSV paths (manifest directory when using `lrdbench run <file.yaml>`, else current working directory / `base_dir` for programmatic runs).
- `cache_read` / `cache_write` (booleans, default true): control cache lookup and population.

Only use estimate caches from trusted locations (pickle execution model).
