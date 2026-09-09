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
| `VarianceResidual` | Half the log-log slope of average sample variance of detrended cumulative-profile residuals versus block size. Closely related to DFA; uses a different scale grid and residual divisor. | `min_scale`, `max_scale`, `scale_ratio`, `detrend_order`, bootstrap parameters |

The aggregation estimators map their fitted slopes onto an unclipped Hurst-style proxy:

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

The legacy `ModifiedLocalWhittle` name implements ordinary Gaussian local Whittle;
`WhittleMLE` fits a band-limited ARFIMA spectral shape rather than exact fGn likelihood.
See the [parameter glossary](parameter_glossary.md) for bandwidths and optimizer bounds.

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

## Spectral-Exponent and Timescale Estimators

These target the two companion estimands of the temporal-correlation triangle (see the
[parameter glossary](parameter_glossary.md) and `raw/truths.csv`). A single realisation can carry
ground truth for `hurst_scaling_proxy`, `spectral_exponent_beta`, and `timescale_tau` at once (e.g.
the `fOU` generator), so a suite may run Hurst, spectral-exponent, and timescale estimators side by
side; each is scored only against the truth for its own estimand.

| Name | Family | Target estimand | Method |
| --- | --- | --- | --- |
| `PeriodogramBeta` | `spectral` | `spectral_exponent_beta` | Low-frequency log-periodogram slope, reported as `β = 2d = 2H − 1` (`S(f) ~ f^(-β)`). |
| `ACFDecay` | `timescale` | `timescale_tau` | Log-linear fit of the autocorrelation over its leading exponential band; reports the decay constant `τ₀` in samples. Correctly specified for AR(1)/OU-type single-timescale dynamics and deliberately misspecified (window-dependent) under true long-range dependence. |

## LRD Discriminators

These target the decision estimand `lrd_class`: each emits a score in `[0, 1]` (higher = stronger
evidence of true long-range dependence) rather than a scalar, and is scored by the classification
metrics (`roc_auc`, `balanced_accuracy`, `true_positive_rate`, `false_positive_rate`) against binary
`is_lrd` labels. These experimental methods compare declared LRD models with short-memory
controls, including `multi_timescale` signals that mimic scaling. Their scores are not
automatically calibrated probabilities or hypothesis tests; they are outside the
[confirmation paper's scope](confirmation_benchmark.md).

| Name | Method |
| --- | --- |
| `ThresholdHurstDiscriminator` | Naive baseline: a Hurst estimate (`base` = `dfa`/`gph`/`rs`) squashed through a logistic centred at `h0`. |
| `LowFreqSpectralDiscriminator` | Local-Whittle memory parameter at a shrinking low-frequency band (true LRD keeps `d>0` as `f→0`; a bounded spectrum collapses to `d≈0`). |
| `ScaleCrossoverDiscriminator` | Large-scale DFA slope used as an experimental persistence score; finite-sample behavior depends on scale support and the underlying timescales. |
| `ICModelSelectDiscriminator` | Whittle-BIC model comparison of ARFIMA(0,d,0) against short-memory AR(1)/AR(2); favours LRD when the fractional model wins. |

## Interpretation Notes

Do not mix `hurst_scaling_proxy` and `long_memory_parameter` results in a single accuracy ranking
unless the benchmark protocol explicitly justifies the comparison. For publication-facing analysis,
report estimator name, family, target estimand, parameters, validity rate, and uncertainty support
alongside accuracy or robustness metrics.

For maturity and failure-risk labels, see [Estimator status](estimator_status.md).
