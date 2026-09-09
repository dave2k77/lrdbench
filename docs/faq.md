# Frequently Asked Questions

## Installation and dependencies

### `lrdbench run` fails with `ModuleNotFoundError: No module named 'matplotlib'`

Matplotlib is a core dependency. Reinstall the package in the interpreter used by the CLI:

```bash
python -m pip install --upgrade lrdbench
```

If you use data-driven estimators (Random Forest, SVR, CNN, LSTM), also install:

```bash
pip install "lrdbench[ml,nn,reports]"
```

See [Installation](installation.md) for the full extras matrix.

## Manifest errors

### Manifest validation error: `unknown top-level manifest keys`

`lrdbench` validates manifests strictly. Only the keys listed in
[Design specification](design_specification.md) are allowed at the top level.
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
- **Non-finite input:** CSV loading uses `missing_policy: drop` by default and
  rejects records with no finite samples left. `missing_policy: error` rejects any missing
  or non-finite value. Inline arrays follow a separate loading path.

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

Start with structural validation:

```bash
lrdbench validate-output reports/<run_id>
```

This checks required files and minimum headers, not reproduced values. Preserve the inputs,
source revision, dependency environment, seed policy and estimator/plugin settings. Compare
scientific outputs from repeated runs separately from UUIDs, timestamps and runtimes.
See [Reproducibility](reproducibility.md) and [validation limits](output_contract.md).

### Can I re-use estimates from a previous run?

Yes. Enable the estimate cache in the manifest:

```yaml
execution:
  estimate_cache_dir: .lrdbench_cache
  cache_read: true
  cache_write: true
```

Cache reuse also depends on record identity/seed, target, parameters, estimator versions and
the shared cache revision. See [execution settings](benchmark_protocol.md#execution-phase-5).
Use caches only from trusted locations.

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

Yes. Use this fragment within a complete observational manifest with IDs, estimators and
truth-free metrics:

```yaml
mode: observational
source:
  type: csv_series_index
  series:
    - path: data/sensor_1.csv
      value_column: amplitude
      record_id: sensor_1
```

See [Observational data tutorial](tutorials/observational_data.md) and
`examples/quickstart_observational.py`.
