# Interpretation Semantics

This page defines how to read uncertainty, leaderboard, and failure outputs. It is part of the
stable public research contract.

This page describes the public manifest-driven evaluator. The separate
[confirmation research runner](confirmation_benchmark.md) uses fixed cell weights,
joint parent resampling and unconditional interval coverage. Do not apply the public
evaluator's missing-value aggregation rules to those research exports.

## Metric Scopes

Metric rows have one of three scopes:

- `per_series`: one metric value for a specific record-estimator pair.
- `aggregate`: a stratum summary or a balanced-global summary.
- `uncertainty`: a bootstrap interval for an aggregate metric or paired estimator difference.

The raw result store writes these rows to `raw/metrics.csv` with `scope`, `stratum_json`, and
`metadata_json`. Report tables provide narrower CSV views for common analysis tasks.

## Aggregation

Most metrics aggregate by arithmetic mean within each stratum. `rmse` is special: per-series rows
store squared error and aggregate rows report the square root of the mean squared error.

Coverage error is derived from aggregate coverage rows:

$$
\operatorname{coverage\_error} = \left|\widehat{C} - c\right|,
$$

where $\widehat{C}$ is empirical coverage and $c$ is the requested nominal level.

Balanced-global rows use `stratum_json` equal to `{"level": "balanced_global"}`. They are computed
as the mean of available stratum-level aggregate rows, so each represented stratum contributes
equally regardless of how many records it contains.

Missing metric values are skipped during aggregation. This makes `validity_rate`, `failures.csv`,
and raw estimate exports necessary companions to accuracy summaries.

## Estimator Uncertainty

Estimator uncertainty is produced by an estimator itself. Public raw estimate exports retain:

- `ci_low` and `ci_high`;
- `bootstrap_cis_json`;

Bootstrap counts and other diagnostics can be present in the returned `EstimateResult`, but
are not serialized in `raw/estimates.csv`; see [persistence boundaries](output_contract.md).

`ci_low`/`ci_high` represent the default 95% interval; other levels remain labelled in
`bootstrap_cis_json`. Metrics such as `coverage`, `ci_width`, and `coverage_error` evaluate these estimator-provided
intervals. If an interval is missing, the corresponding metric row has `value=null` and
`metadata_json` includes `missing_ci=true`.

Public coverage is conditional on valid points and available finite ordered intervals. Report
`ci_availability` and `validity_rate` alongside it. Estimator intervals are not automatically benchmark-level confidence intervals. They describe the
estimator's uncertainty output for one fitted record.

## Benchmark Uncertainty

Benchmark uncertainty is requested with the manifest `uncertainty` block. It estimates uncertainty
of benchmark summaries, not uncertainty of individual fitted estimates.

Supported outputs:

- `aggregate_bootstrap` with `aggregation=bootstrap_within_stratum`: bootstrap interval for a
  metric within one stratum using per-series metric rows.
- `aggregate_bootstrap` with `aggregation=bootstrap_over_strata`: bootstrap interval for a
  balanced-global summary using stratum aggregate rows.
- `paired_bootstrap_difference` with `aggregation=paired_bootstrap_within_stratum`: bootstrap
  interval for the mean paired difference between two estimators on records where both have a
  value for the same metric.

Benchmark uncertainty rows are exported to `tables/benchmark_uncertainty.csv` and to
`raw/metrics.csv` with `scope=uncertainty`.

The `value` column is the bootstrap target point estimate. Interval bounds live in `ci_low` and
`ci_high`, and the confidence level for the interval is recorded as `nominal`.

If the metric itself has a nominal level, for example 95% coverage, that metric nominal is stored
separately in metadata as `metric_nominal`.

## Leaderboards

Leaderboards are configured summaries, not universal rankings.

Current leaderboards use weighted ranks:

1. Select balanced-global aggregate rows only.
2. Exclude rows whose `estimator_name` is not declared in the manifest estimator specs.
3. For each component metric, rank finite values according to its optimisation direction;
   equal values receive average ranks.
4. Assign missing or nonfinite components rank N + 1, where N is the enrolled estimator count.
5. Compute the score as the weighted sum of component ranks.
6. Resolve score ties using `tie_break_rule`: the first component for `best_primary_metric`,
   the specified component metric, or no secondary metric for `none`.
7. Retain equal competition ranks for unresolved ties (for example, 1, 1, 3).
   Estimator names order their display only; they do not break scientific ties.

Lower scores rank better. Component weights must sum to 1. Metric optimisation directions come
from the metric catalog.

Synthetic diagnostic rows such as `__all_estimators__`, paired estimator-difference rows, and
base-estimator sensitivity rows that are not enrolled estimator names are intentionally excluded
from leaderboard ranking.

When reporting a leaderboard, also report the manifest, component metrics, weights, and raw
component values.

## Failures

Estimator failure is represented at multiple levels:

- raw estimates include `valid`, `failure_reason`, `warnings`, and any point/interval fields;
- `validity_rate` emits 1.0 for valid estimates and 0.0 for invalid estimates;
- truth-based accuracy metrics skip invalid estimates and incompatible estimand pairs;
- missing confidence intervals create missing uncertainty metric rows rather than fake interval
  scores;
- `tables/failures.csv` summarizes missing metric values, missing uncertainty, invalid estimate
  counts, and rates by estimator and stratum.

`tables/failure_map.csv` is a wide aggregate audit table. It is useful for identifying which
metrics are present or absent across estimator-stratum combinations, especially in stress tests.

Failure transparency is part of the benchmark result. A high-accuracy aggregate over a small valid
subset should not be interpreted without checking validity and failure exports.

## Mode-Specific Interpretation

Ground-truth mode supports accuracy and coverage claims relative to the declared synthetic truth.
Those claims remain model-relative.

Stress-test mode supports degradation and robustness claims relative to clean and contaminated
synthetic records. Stress results depend on contamination design and severity.

Observational mode supports stability and sensitivity claims only. It does not support truth-based
accuracy, coverage, or false-positive LRD claims.
