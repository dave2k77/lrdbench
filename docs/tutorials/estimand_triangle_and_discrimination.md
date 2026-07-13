# Estimand triangle and LRD discrimination

Beyond the Hurst exponent, `lrdbench` can benchmark two companion views of temporal-correlation
structure — the spectral exponent `β` and the autocorrelation timescale `τ` — and can score whether
an estimator distinguishes *genuine* long-range dependence (LRD) from a short-memory process that
merely *mimics* it. This tutorial walks through both.

## 1. The H / β / τ triangle

The literature relates the Hurst exponent, the `1/f^β` spectral slope, and the autocorrelation decay
time as three views of the same structure (`β = 2H − 1`, `H = (β + 1)/2`). A single realisation can
now carry ground truth for all three via companion truths, so Hurst, spectral-exponent, and
timescale estimators run side by side and are each scored against the truth for their own estimand.

```bash
lrdbench run configs/suites/smoke_neural_timescale.yaml --dry-run
lrdbench run configs/suites/smoke_neural_timescale.yaml
```

- `fGn` declares `(H, β = 2H − 1, τ = None)` — a power-law ACF has no finite exponential timescale.
- `fOU` declares `(H, τ = 1/(θ·dt))` — the mean-reversion timescale in samples.

Estimators: `DFA` (`hurst_scaling_proxy`), `PeriodogramBeta` (`spectral_exponent_beta`), `ACFDecay`
(`timescale_tau`). Every declared truth is written to `raw/truths.csv` (primary + companions), so the
cross-estimand relationships are reproducible from disk:

```text
record_id  target_estimand         target_value  is_primary  notes
<fgn>      hurst_scaling_proxy      0.7           True
<fgn>      spectral_exponent_beta   0.4           False       beta = 2H - 1 for fGn
<fgn>      timescale_tau                          False       no finite timescale (power-law ACF)
<fou>      hurst_scaling_proxy      0.5           True
<fou>      timescale_tau            10.0          False       tau = 1/(theta*dt) samples
```

The full-size counterpart is `neural_timescale_triangle_ground_truth`.

## 2. True-vs-apparent LRD (false-positive rate)

The `multi_timescale` generator is a finite superposition of AR(1) components: genuinely
short-memory (truth `H = 0.5`) but engineered to look power-law over finite samples. It is a
controlled null for the LRD illusion, with severity graded by `tau_max`.

```bash
lrdbench run configs/suites/smoke_lrd_discrimination.yaml
```

The `false_positive_lrd_rate` metric counts how often each Hurst estimator calls `H ≥ 0.6` on these
`H = 0.5` nulls. Clean `fGn` nulls are correctly rejected; the multi-timescale nulls fool most
estimators — the point of the suite. Full size: `neural_lrd_discrimination_ground_truth`.

## 3. Per-series model selection

A **discriminator** emits a score in `[0, 1]` for the decision estimand `lrd_class`, scored by the
classification metric family — `roc_auc` (primary), `balanced_accuracy`, `true_positive_rate`,
`false_positive_rate` — against binary `is_lrd` labels. Metrics are routed by estimand *kind*, so
error metrics such as `bias`/`mae` never apply to a decision estimand.

```bash
lrdbench run configs/suites/smoke_lrd_model_selection.yaml
```

Four discriminators are bundled, from a naive baseline to principled tests:

| Discriminator | Idea |
| --- | --- |
| `ThresholdHurstDiscriminator` | logistic squash of a point Hurst estimate (baseline) |
| `LowFreqSpectralDiscriminator` | low-frequency memory parameter (survives as `f→0` only for true LRD) |
| `ScaleCrossoverDiscriminator` | large-scale DFA slope (short memory crosses over to `0.5`) |
| `ICModelSelectDiscriminator` | Whittle-BIC of ARFIMA(0,d,0) vs AR(1)/AR(2) |

Classification metrics are written as aggregate rows in `raw/metrics.csv` (with `scope = aggregate`,
`stratum.level = balanced_global`); the `discrimination_power` leaderboard ranks discriminators by
ROC-AUC. Full size: `neural_lrd_model_selection_ground_truth`.

## Reading the results

- Per-estimand truths: `raw/truths.csv`.
- Per-series estimates/scores: `raw/estimates.csv`.
- Metrics (per-series and aggregate, including the classification metrics): `raw/metrics.csv`.
- Leaderboards: `tables/leaderboard.csv`.

See the [parameter glossary](../parameter_glossary.md) for the estimands and estimator parameters,
and [bundled estimators](../bundled_estimators.md) for the full method list.
