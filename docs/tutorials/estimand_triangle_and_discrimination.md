# Estimand triangle and LRD discrimination

The Hurst parameter $H$, spectral exponent $\beta$ and decay timescale $\tau$ describe
related but different properties. This tutorial compares their declared model-relative targets,
then introduces experimental LRD classifiers. These suites are separate from the
[audited confirmation study](../confirmation_benchmark.md).

## H, spectral slope and timescale

For stationary fractional Gaussian noise (fGn), the low-frequency convention is

$$
\begin{aligned}
S(f) &\propto f^{-\beta}, \\
\beta &= 2H - 1, \qquad H = \frac{\beta + 1}{2}.
\end{aligned}
$$

This conversion is model-dependent. It does not apply unchanged to an integrated fBm path:
fBm is nonstationary and its generalized spectral scaling has exponent $2H+1$.
See [Caccia et al., *Analyzing exact fractal time series*](https://pmc.ncbi.nlm.nih.gov/articles/PMC3205082/).
A finite exponential decay time is not determined by the fGn spectral exponent.

For the implemented OU-style recurrence with $H=0.5$, the coefficient and stationary ACF obey

$$
\begin{aligned}
a &= e^{-\theta\,\Delta t}, \\
\rho(k) &= a^k = e^{-k/\tau}, \\
\tau &= \frac{1}{\theta\,\Delta t}.
\end{aligned}
$$

Here $k$ and $\tau$ are in samples. With correlated fGn innovations ($H\ne0.5$), the same
mean-reversion parameter is stored, but it is not an exact single-exponential ACF timescale.
The fractional OU distinction is also described by
[Cheridito, Kawaguchi and Maejima](https://people.math.ethz.ch/~patrickc/foup.pdf).
A companion truth records a declared target; it does not establish that every estimator is
correctly specified for that target.

```bash
lrdbench run configs/suites/smoke_neural_timescale.yaml --dry-run
lrdbench run configs/suites/smoke_neural_timescale.yaml
```

- `fGn` declares H and spectral-slope truths, and leaves `timescale_tau` unavailable.
  At H = 0.5 it is white noise; a positive decay time is not assigned there either.
- `fOU` declares the driving H and mean-reversion timescale in samples; it does not
  currently declare a spectral-exponent companion truth.

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

## Point-threshold exceedance on short-memory controls

The `multi_timescale` generator is a finite superposition of AR(1) components: genuinely
short-memory (truth `H = 0.5`) but engineered to look power-law over finite samples. It is a
controlled null for the LRD illusion, with severity graded by `tau_max`.

```bash
lrdbench run configs/suites/smoke_lrd_discrimination.yaml
```

The legacy `false_positive_lrd_rate` metric (clearer alias: `persistence_exceedance_rate`)
counts valid null estimates at or above a point cutoff, H ≥ 0.6 by default. It is not the
Type I error of a calibrated hypothesis test. Inspect the measured rate and validity for each
family; neither clean-null rejection nor multi-timescale failure is guaranteed by the suite.
Full size: `neural_lrd_discrimination_ground_truth`.

## Per-series classification

A **discriminator** emits a score in `[0, 1]` for the decision estimand `lrd_class`, scored by the
classification metric family — `roc_auc` (primary), `balanced_accuracy`, `true_positive_rate`,
`false_positive_rate` — against binary `lrd_class` companion truths. Metrics are routed by estimand *kind*, so
error metrics such as `bias`/`mae` never apply to a decision estimand.

```bash
lrdbench run configs/suites/smoke_lrd_model_selection.yaml
```

Four experimental discriminators are bundled. Their scores are not calibrated probabilities
or tests with guaranteed Type I error:

| Discriminator | Idea |
| --- | --- |
| `ThresholdHurstDiscriminator` | logistic squash of a point Hurst estimate (baseline) |
| `LowFreqSpectralDiscriminator` | local-Whittle memory score over a selected low-frequency band |
| `ScaleCrossoverDiscriminator` | large-scale DFA score; apparent persistence depends on scale support and record length |
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
