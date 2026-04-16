# Benchmark protocol

1. **Manifest** (YAML): declares `mode`, `source`, optional `contamination`, `estimators`, `metrics`, `leaderboards`, `report`, and `seeds`.
2. **Records**: synthetic grid (`generator_grid`), stress pairs (clean + contaminated), or observational series (`csv_series_index` / `inline_table`).
3. **Estimation**: each `(record, estimator_spec)` yields an `EstimateResult`.
4. **Evaluation**: mode-appropriate metrics (`MetricBundle`) and optional leaderboards.
5. **Outputs**: CSV result store under `reports/<run_id>/` plus HTML/CSV summaries from the reporter.

Example suite manifests: `configs/suites/smoke_*.yaml`.

## Execution (Phase 5)

Optional YAML block `execution`:

- `max_workers` (integer ≥ 1, default 1): when greater than 1, estimator `fit` calls run in parallel with a thread pool (order of results matches the serial `(record × estimator)` grid).
- `estimate_cache_dir` (string, optional): directory for pickle caches of `EstimateResult` keyed by record id, estimator name, parameter schema, and a hash of the series values. Resolve relative paths against the same working base as observational CSV paths (manifest directory when using `lrdbench run <file.yaml>`, else current working directory / `base_dir` for programmatic runs).
- `cache_read` / `cache_write` (booleans, default true): control cache lookup and population.

Only use estimate caches from trusted locations (pickle execution model).
