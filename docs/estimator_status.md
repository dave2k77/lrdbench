# Estimator Status

This table describes the implementation status of estimators available through the default
registry. Status is not a ranking. It tells users how cautiously to interpret results.

The [confirmation study](confirmation_benchmark.md) now reports point accuracy for its
21 pipelines and interval coverage for selected GPH, Higuchi and GHE procedures. These
model- and configuration-specific results do not upgrade any method to reference-grade
or establish calibration of every package-default interval.

Status meanings:

- **baseline**: suitable as a simple comparison method in public examples and smoke benchmarks.
- **approximate**: useful for research benchmarking, but implemented as a pragmatic approximation
  rather than a reference implementation.
- **experimental**: available for exploratory comparison; needs stronger validation before it
  should anchor public claims.
- **reference-grade**: validated enough to serve as an implementation reference. No estimator has
  this status yet.

| Estimator | Family | Target estimand | Status | Assumptions | Expected regime | Known failure risks |
| --- | --- | --- | --- | --- | --- | --- |
| `RS` | temporal | `hurst_scaling_proxy` | baseline | Rescaled-range scaling of stationary increments over selected block sizes. | Clean fGn-style checks with declared block support. | Upward finite-sample bias near H = 0.5 remains. The optional Anis-Lloyd expectation normalization is not a general unbiased correction. Raw slopes are retained; bootstrap calibration is pending. |
| `DFA` | temporal | `hurst_scaling_proxy` | baseline | Power-law residual RMS of a detrended cumulative profile. | Stationary increments with a defensible scale window. | It integrates the input; its slope on an fBm path is not the fGn H target. Out-of-range slopes, scale-window effects and detrending sensitivity remain visible. |
| `DMA` | temporal | `hurst_scaling_proxy` | baseline | Backward moving-average residual RMS of a cumulative profile. | Stationary increments with adequate window support. | Window choices, short records and deterministic trends can distort estimates. Raw slopes are retained. |
| `AbsoluteMoment` | temporal | `hurst_scaling_proxy` | approximate | Absolute first moment of block-aggregated series follows power-law scaling. | Aggregated-variance/moment comparisons on stationary fGn-style records. | Scale-window choices, short records, and centring choices can materially affect the slope. |
| `Variance` | temporal | `hurst_scaling_proxy` | approximate | Variance of block-aggregated series follows power-law scaling. | Classical aggregated variance checks for stationary long-memory-like records. | Bias under trends, level shifts, and poor block-size support. |
| `VarianceResidual` | temporal | `hurst_scaling_proxy` | approximate | Average variance of within-block residuals follows power-law scaling after local detrending. | Residual-variance scaling comparisons on records with enough block support. | Detrending order and scale window can dominate finite-sample estimates. |
| `GPH` | spectral | `long_memory_parameter` | baseline | Low-frequency log-periodogram regression for ARFIMA-style memory. | ARFIMA(0,d,0)-like synthetic regimes with moderate sample sizes. | Bandwidth sensitivity, short-memory leakage, and low-frequency contamination. Optional cosine taper (`params.taper: cosine`) can reduce periodogram bias from spectral leakage. |
| `Periodogram` | spectral | `long_memory_parameter` | approximate | Log-periodogram slope approximates long-memory parameter. | ARFIMA-style long-memory comparisons. | Bandwidth choices materially affect results; periodogram noise is high. Optional cosine taper (`params.taper: cosine`) can reduce spectral leakage. |
| `WhittleMLE` | spectral | `long_memory_parameter` | approximate | ARFIMA(0,d,0) Whittle objective over a selected low-frequency band. | Records near the declared spectral model. | It is not exact time-domain Gaussian MLE or exact fGn likelihood. Model misspecification, bandwidth and bounds matter; optimizer boundary hits are reported. |
| `ModifiedLocalWhittle` | spectral | `long_memory_parameter` | approximate | Ordinary Gaussian local Whittle objective under a legacy registry name. | Stationary low-frequency power-law regimes with adequate bandwidth support. | No nonstationary modification is implemented. Bandwidth sensitivity, finite-sample instability and optimizer bounds require validation. |
| `Higuchi` | geometric | `hurst_scaling_proxy` | approximate | H = 2 - D for a suitable self-affine path graph; declare path versus increments explicitly. | Path roughness comparisons on sufficiently long records. | Normalization corrected; estimates are unclipped. Short-memory processes can show apparent persistence over the chosen lags. The confirmation study measures substantial block-percentile undercoverage and fitted-fGn failure on strong AR(1) controls. |
| `GHE` | geometric | `hurst_scaling_proxy` | approximate | Absolute q-th moments of path differences scale as lag raised to qH(q). | Selected-lag moment regression; default q = 2, with q = 1 available explicitly. | Forced H = 0.5 fallback removed; nonzero `flat_slope_tol` rejected. Declare input representation. Lag range, trends, moment existence and bootstrap calibration require attention. |
| `WaveletOLS` | wavelet | `hurst_scaling_proxy` | approximate | Log detail variances scale linearly across levels under the fGn convention. | Stationary increments with at least three retained levels. | Scale-band selection, symmetric-extension boundaries and short signals. Raw slopes are retained; the conservative db4 pilot band is unavailable at n = 256. |
| `WaveletAbryVeitch` | wavelet | `hurst_scaling_proxy` | experimental | Abry-Veitch-style wavelet log-scale regression approximation. | Exploratory wavelet comparison on long enough records. | Needs stronger validation; sensitive to wavelet family and usable levels. |
| `WaveletBardet` | wavelet | `hurst_scaling_proxy` | experimental | Weighted wavelet log-scale regression approximation. | Exploratory wavelet comparison on long enough records. | Weighting and level selection can drive results; short signals are invalid. |
| `WaveletJensen` | wavelet | `hurst_scaling_proxy` | experimental | Two-band wavelet slope extrapolation. | Exploratory comparison where fine and coarse bands are both populated. | Band definitions can be fragile; short or narrow-band records fail. |
| `WaveletWhittle` | wavelet | `hurst_scaling_proxy` | experimental | Wavelet-domain Whittle-type fit to detail variances. | Exploratory wavelet comparison on long enough records. | Numerical fit and level support remain experimental. |
| `MLRandomForest` | data-driven | `hurst_scaling_proxy` | experimental | Supervised synthetic training distribution declared in `ml_training`. | Contaminated synthetic Hurst-proxy comparisons where train/eval provenance is explicit. | Distribution shift, training-grid leakage, and optional dependency availability. |
| `MLSVR` | data-driven | `hurst_scaling_proxy` | experimental | Supervised synthetic training distribution declared in `ml_training`. | Feature-based nonlinear baseline against classical estimators. | Feature design and hyperparameters can dominate results; no estimator-level CI. |
| `MLCNN` | data-driven | `hurst_scaling_proxy` | experimental | Supervised synthetic training distribution declared in `ml_training`; requires `lrdbench[nn]`. | Sequence baseline for exploratory neural comparisons. | Small training grids can overfit; distribution shift and stochastic training affect results. |
| `MLLSTM` | data-driven | `hurst_scaling_proxy` | experimental | Supervised synthetic training distribution declared in `ml_training`; requires `lrdbench[nn]`. | Sequential neural baseline for exploratory comparisons. | Slow training, overfitting, and weak extrapolation outside the manifest training grid. |
| `PeriodogramBeta` | spectral | `spectral_exponent_beta` | approximate | Low-frequency log-periodogram slope, reported as `β = 2d` under the fractional-noise model. | Spectral-exponent comparisons alongside compatible Hurst estimators. | GPH slope conversion corrected; old results halved d. Bandwidth trades variance against short-memory contamination and approximation bias; wider is not universally better. |
| `ACFDecay` | timescale | `timescale_tau` | approximate | Log-linear fit of the leading exponential band of the autocorrelation. | Single-timescale (AR(1)/OU) recovery; a diagnostic contrast under true LRD. | Deliberately misspecified for power-law LRD (window-dependent `τ`); reciprocal-of-slope skew inflates the mean. |
| `ThresholdHurstDiscriminator` | discrimination | `lrd_class` | baseline | Logistic squash of a point Hurst estimate. | Naive LRD-vs-short-memory decision floor. | No power against apparent LRD (multi-timescale) — near-chance on that adversary by design. |
| `LowFreqSpectralDiscriminator` | discrimination | `lrd_class` | experimental | Local-Whittle memory parameter at a shrinking low-frequency band. | Distinguishing true LRD from short-memory nulls. | Low-frequency estimate is noisy; bandwidth choice (`m_power`) affects separation. |
| `ScaleCrossoverDiscriminator` | discrimination | `lrd_class` | experimental | Large-scale DFA slope (scale-invariance of the exponent). | Detecting the crossover that short-memory processes show at large scales. | Weaker/noisier signal than the spectral and likelihood discriminators. |
| `ICModelSelectDiscriminator` | discrimination | `lrd_class` | experimental | Whittle-BIC comparison of ARFIMA(0,d,0) vs AR(1)/AR(2). | Principled LRD-vs-short-memory model selection. | Depends on the AR-order set and the fitted spectral models; BIC scale (`scale`) sets score calibration. |

## Interpretation Rules

Do not mix estimator targets casually. `hurst_scaling_proxy` and `long_memory_parameter` are related
in some model families but are not identical public-contract quantities.

Leaderboard results are summaries of declared component metrics. They are not universal estimator
rankings and should always be reported with the underlying metrics.

For publication-facing analysis, prefer reporting estimator families, target estimands, parameter
settings, and failure/missing-uncertainty rates alongside any accuracy or robustness summaries.

Data-driven estimators are run-local supervised baselines. Interpret them relative to the
manifest-declared `ml_training` distribution, not as distribution-free LRD estimators.
