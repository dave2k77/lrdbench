# Frequently Asked Questions

## Installation and dependencies

### `lrdbench run` fails with `ModuleNotFoundError: No module named 'matplotlib'`

Install the reporting extras:

```bash
pip install "lrdbench[reports]"
```

If you use data-driven estimators (Random Forest, SVR, CNN, LSTM), also install:

```bash
pip install "lrdbench[ml,nn,reports]"
```

See [Installation](installation.md) for the full extras matrix.

## Manifest errors

### Manifest validation error: `unknown top-level manifest keys`

`lrdbench` validates manifests strictly. Only the keys listed in
[Benchmark protocol](benchmark_protocol.md) are allowed at the top level.
Common mistakes:

- Typos like `estimator` instead of `estimators`.
- Putting estimator-specific keys (e.g. `min_scale`) at the top level instead of under `params`.

Run `lrdbench validate my_manifest.yaml` to see the exact offending key.

### `estimator 'X' must declare target_estimand`

Every estimator entry in a manifest must include `target_estimand`. This is a
deliberate design choice: the framework refuses to guess what an estimator is
trying to measure. Example:

```yaml
estimators:
  - name: DFA
    family: temporal
    target_estimand: hurst_scaling_proxy
    params:
      min_scale: 4
      max_scale: 64
```

## Estimation failures

### My estimator returns all invalid / NaN results

Check the signal length against the estimator's minimum requirements. In the
result store, read `tables/failures.csv` to see per-estimator invalid counts.

Common causes:

- **Short series:** Many estimators need at least 64–128 samples. The aggregation
  estimators (`AbsoluteMoment`, `Variance`, `VarianceResidual`) and wavelet
  estimators are especially sensitive to short records.
- **Constant or zero-variance series:** RS and spectral estimators return
  invalid when the standard deviation is near zero.
- **All-NaN input:** Observational loaders drop NaNs; if the result is empty,
  every estimator will fail.

### Why do bootstrap confidence intervals look very wide?

The default block length is `max(4, n // 10)`. For long-memory series this is a
pragmatic compromise, but it may be too short for very persistent processes or
too long for short records. You can override it per estimator:

```yaml
estimators:
  - name: DFA
    params:
      n_bootstrap: 200
      bootstrap_block_len: 32
```

See [Benchmark protocol](benchmark_protocol.md) for more on uncertainty blocks.

## Reproducibility

### How do I know if my run reproduced correctly?

Use the output contract validator:

```bash
lrdbench validate-output reports/<run_id>
```

This checks that all required files and columns are present. For full
reproducibility, keep the manifest, the package version, and the global seed.
Every run writes `manifest/environment.json` inside the report directory with
exact versions.

### Can I re-use estimates from a previous run?

Yes. Enable the estimate cache in the manifest:

```yaml
execution:
  estimate_cache_dir: .lrdbench_cache
  cache_read: true
  cache_write: true
```

The cache key is a hash of the series values, estimator name, and parameter
schema, so identical inputs will skip re-computation.

## Customisation

### How do I add my own estimator without forking the repository?

Use the third-party plugin workflow. Set an environment variable pointing to
your Python module:

```bash
export LRD_BENCH_ESTIMATOR_PLUGIN=my_package.my_estimators
lrdbench run my_manifest.yaml
```

See [Third-party estimator workflow](third_party_estimators.md) for details.

### Can I benchmark on my own CSV data?

Yes. Use observational mode with a `csv_series_index` source:

```yaml
mode: observational
source:
  type: csv_series_index
  series:
    - file: data/sensor_1.csv
      column: amplitude
      record_id: sensor_1
```

See [Observational data tutorial](tutorials/observational_data.md) and
`examples/quickstart_observational.py`.
