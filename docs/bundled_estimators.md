# Bundled Estimators

The default estimator registry exposes classical temporal, spectral, geometric, wavelet, and
data-driven methods. Discover the installed names with:

```bash
lrdbench list-estimators
```

Estimator entries in manifests use the registry name:

```yaml
estimators:
  - name: Variance
    family: temporal
    target_estimand: hurst_scaling_proxy
    params:
      min_scale: 2
      max_scale: 256
      scale_ratio: 1.5
      n_bootstrap: 200
```

## Temporal Hurst-Proxy Estimators

These estimators target `hurst_scaling_proxy`.

| Name | Method | Main parameters |
| --- | --- | --- |
| `RS` | Rescaled-range log-log slope over subseries lengths. | `min_scale`, `max_scale`, `scale_ratio`, `use_anis_lloyd_correction`, bootstrap parameters |
| `DFA` | Detrended fluctuation analysis on the cumulative profile. | `min_scale`, `max_scale`, `detrend_order`, bootstrap parameters |
| `DMA` | Detrended moving-average fluctuation scaling. | `min_scale`, `max_scale`, bootstrap parameters |
| `AbsoluteMoment` | Log-log slope of aggregation level versus absolute first moment of block-aggregated series. | `min_scale`, `max_scale`, `scale_ratio`, bootstrap parameters |
| `Variance` | Log-log slope of sample variance versus block size for block-aggregated series. | `min_scale`, `max_scale`, `scale_ratio`, bootstrap parameters |
| `VarianceResidual` | Log-log slope of aggregation level versus average within-block residual variance after local detrending. | `min_scale`, `max_scale`, `scale_ratio`, `detrend_order`, bootstrap parameters |

The aggregation estimators map their fitted slopes onto a bounded Hurst-style proxy:

- `AbsoluteMoment`: `H = slope + 1`
- `Variance`: `H = slope / 2 + 1`
- `VarianceResidual`: `H = slope / 2`

All three are approximate finite-sample methods. Interpret them with the same caution as other
scale-window estimators: the block-size range, scale spacing, detrending order, contamination, and
record length can materially change results.

## Other Classical Estimators

Spectral estimators target `long_memory_parameter`:

- `GPH`
- `Periodogram`
- `WhittleMLE`
- `ModifiedLocalWhittle`

Geometric estimators target `hurst_scaling_proxy`:

- `Higuchi`
- `GHE`

Wavelet estimators target `hurst_scaling_proxy`:

- `WaveletOLS`
- `WaveletAbryVeitch`
- `WaveletBardet`
- `WaveletJensen`
- `WaveletWhittle`

## Data-Driven Estimators

The experimental supervised baselines target `hurst_scaling_proxy`:

- `MLRandomForest`
- `MLSVR`
- `MLCNN`
- `MLLSTM`

These require a manifest-declared `ml_training` block unless a model artefact path is supplied.
See [Data-driven estimators](data_driven_estimators.md).

## Interpretation Notes

Do not mix `hurst_scaling_proxy` and `long_memory_parameter` results in a single accuracy ranking
unless the benchmark protocol explicitly justifies the comparison. For publication-facing analysis,
report estimator name, family, target estimand, parameters, validity rate, and uncertainty support
alongside accuracy or robustness metrics.

For maturity and failure-risk labels, see [Estimator status](estimator_status.md).
