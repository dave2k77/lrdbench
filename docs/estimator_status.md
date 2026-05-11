# Estimator Status

This table describes the implementation status of estimators available through the default
registry. Status is not a ranking. It tells users how cautiously to interpret results.

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
| `RS` | temporal | `hurst_scaling_proxy` | baseline | Self-similar scaling over selected block sizes. | Clean fGn/fBm-style synthetic checks and simple public smoke suites. | **Finite-sample bias:** the classical estimator systematically over-estimates `H` near `0.5` and for small `n`. An opt-in Anis-Lloyd correction is available via `params.use_anis_lloyd_correction`. Short signals, nonstationary trends, and contamination can also bias the slope; bootstrap intervals are approximate. |
| `DFA` | temporal | `hurst_scaling_proxy` | baseline | Power-law fluctuation scaling after polynomial detrending. | fGn/fBm-style signals with a defensible scale window. | Scale-window and detrending-order choices can dominate finite-sample results. |
| `DMA` | temporal | `hurst_scaling_proxy` | baseline | Moving-average fluctuation scaling over selected windows. | fGn/fBm-style signals where window range avoids edge effects. | Window choices, short records, and deterministic trends can distort estimates. |
| `AbsoluteMoment` | temporal | `hurst_scaling_proxy` | approximate | Absolute first moment of block-aggregated series follows power-law scaling. | Aggregated-variance/moment comparisons on stationary fGn-style records. | Scale-window choices, short records, and centring choices can materially affect the slope. |
| `Variance` | temporal | `hurst_scaling_proxy` | approximate | Variance of block-aggregated series follows power-law scaling. | Classical aggregated variance checks for stationary long-memory-like records. | Bias under trends, level shifts, and poor block-size support. |
| `VarianceResidual` | temporal | `hurst_scaling_proxy` | approximate | Average variance of within-block residuals follows power-law scaling after local detrending. | Residual-variance scaling comparisons on records with enough block support. | Detrending order and scale window can dominate finite-sample estimates. |
| `GPH` | spectral | `long_memory_parameter` | baseline | Low-frequency log-periodogram regression for ARFIMA-style memory. | ARFIMA(0,d,0)-like synthetic regimes with moderate sample sizes. | Bandwidth sensitivity, short-memory leakage, and low-frequency contamination. Optional cosine taper (`params.taper: cosine`) can reduce periodogram bias from spectral leakage. |
| `Periodogram` | spectral | `long_memory_parameter` | approximate | Log-periodogram slope approximates long-memory parameter. | ARFIMA-style long-memory comparisons. | Bandwidth choices materially affect results; periodogram noise is high. Optional cosine taper (`params.taper: cosine`) can reduce spectral leakage. |
| `WhittleMLE` | spectral | `long_memory_parameter` | approximate | Gaussian ARFIMA(0,d,0) spectral likelihood approximation. | Clean ARFIMA-style records near the fitted model family. | Model misspecification, numerical bounds, and short samples. |
| `ModifiedLocalWhittle` | spectral | `long_memory_parameter` | approximate | Local low-frequency Whittle objective captures fractional memory. | ARFIMA-style long-memory regimes with adequate low-frequency support. | Bandwidth sensitivity and finite-sample instability. |
| `Higuchi` | geometric | `hurst_scaling_proxy` | approximate | Graph dimension maps to a Hurst-style proxy. | Geometry-based comparator on sufficiently long records. | It is indirect LRD evidence and can fail under short or highly noisy signals. |
| `GHE` | geometric | `hurst_scaling_proxy` | approximate | Increment moments scale across selected lags. | Multiscale increment-variance comparisons. | **Arbitrary heuristic:** when the absolute log-log slope is below `flat_slope_tol` (default `0.08`), the estimate is clamped to `0.5`. This guard is empiric, not theoretically derived; set `flat_slope_tol: 0.0` to disable it. Also sensitive to lag-grid choices and short samples. |
| `WaveletOLS` | wavelet | `hurst_scaling_proxy` | approximate | Wavelet detail variances scale linearly across selected levels. | fGn/fBm-style records with adequate wavelet levels. | Scale-band selection, boundary effects, and short signals. |
| `WaveletAbryVeitch` | wavelet | `hurst_scaling_proxy` | experimental | Abry-Veitch-style wavelet log-scale regression approximation. | Exploratory wavelet comparison on long enough records. | Needs stronger validation; sensitive to wavelet family and usable levels. |
| `WaveletBardet` | wavelet | `hurst_scaling_proxy` | experimental | Weighted wavelet log-scale regression approximation. | Exploratory wavelet comparison on long enough records. | Weighting and level selection can drive results; short signals are invalid. |
| `WaveletJensen` | wavelet | `hurst_scaling_proxy` | experimental | Two-band wavelet slope extrapolation. | Exploratory comparison where fine and coarse bands are both populated. | Band definitions can be fragile; short or narrow-band records fail. |
| `WaveletWhittle` | wavelet | `hurst_scaling_proxy` | experimental | Wavelet-domain Whittle-type fit to detail variances. | Exploratory wavelet comparison on long enough records. | Numerical fit and level support remain experimental. |
| `MLRandomForest` | data-driven | `hurst_scaling_proxy` | experimental | Supervised synthetic training distribution declared in `ml_training`. | Contaminated synthetic Hurst-proxy comparisons where train/eval provenance is explicit. | Distribution shift, training-grid leakage, and optional dependency availability. |
| `MLSVR` | data-driven | `hurst_scaling_proxy` | experimental | Supervised synthetic training distribution declared in `ml_training`. | Feature-based nonlinear baseline against classical estimators. | Feature design and hyperparameters can dominate results; no estimator-level CI. |
| `MLCNN` | data-driven | `hurst_scaling_proxy` | experimental | Supervised synthetic training distribution declared in `ml_training`; requires `lrdbench[nn]`. | Sequence baseline for exploratory neural comparisons. | Small training grids can overfit; distribution shift and stochastic training affect results. |
| `MLLSTM` | data-driven | `hurst_scaling_proxy` | experimental | Supervised synthetic training distribution declared in `ml_training`; requires `lrdbench[nn]`. | Sequential neural baseline for exploratory comparisons. | Slow training, overfitting, and weak extrapolation outside the manifest training grid. |

## Interpretation Rules

Do not mix estimator targets casually. `hurst_scaling_proxy` and `long_memory_parameter` are related
in some model families but are not identical public-contract quantities.

Leaderboard results are summaries of declared component metrics. They are not universal estimator
rankings and should always be reported with the underlying metrics.

For publication-facing analysis, prefer reporting estimator families, target estimands, parameter
settings, and failure/missing-uncertainty rates alongside any accuracy or robustness summaries.

Data-driven estimators are run-local supervised baselines. Interpret them relative to the
manifest-declared `ml_training` distribution, not as distribution-free LRD estimators.
