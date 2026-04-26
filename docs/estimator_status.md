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
| `RS` | temporal | `hurst_scaling_proxy` | baseline | Self-similar scaling over selected block sizes. | Clean fGn/fBm-style synthetic checks and simple public smoke suites. | Short signals, nonstationary trends, and contamination can bias the slope; bootstrap intervals are approximate. |
| `DFA` | temporal | `hurst_scaling_proxy` | baseline | Power-law fluctuation scaling after polynomial detrending. | fGn/fBm-style signals with a defensible scale window. | Scale-window and detrending-order choices can dominate finite-sample results. |
| `DMA` | temporal | `hurst_scaling_proxy` | baseline | Moving-average fluctuation scaling over selected windows. | fGn/fBm-style signals where window range avoids edge effects. | Window choices, short records, and deterministic trends can distort estimates. |
| `GPH` | spectral | `long_memory_parameter` | baseline | Low-frequency log-periodogram regression for ARFIMA-style memory. | ARFIMA(0,d,0)-like synthetic regimes with moderate sample sizes. | Bandwidth sensitivity, short-memory leakage, and low-frequency contamination. |
| `Periodogram` | spectral | `long_memory_parameter` | approximate | Log-periodogram slope approximates long-memory parameter. | ARFIMA-style long-memory comparisons. | Bandwidth choices materially affect results; periodogram noise is high. |
| `WhittleMLE` | spectral | `long_memory_parameter` | approximate | Gaussian ARFIMA(0,d,0) spectral likelihood approximation. | Clean ARFIMA-style records near the fitted model family. | Model misspecification, numerical bounds, and short samples. |
| `ModifiedLocalWhittle` | spectral | `long_memory_parameter` | approximate | Local low-frequency Whittle objective captures fractional memory. | ARFIMA-style long-memory regimes with adequate low-frequency support. | Bandwidth sensitivity and finite-sample instability. |
| `Higuchi` | geometric | `hurst_scaling_proxy` | approximate | Graph dimension maps to a Hurst-style proxy. | Geometry-based comparator on sufficiently long records. | It is indirect LRD evidence and can fail under short or highly noisy signals. |
| `GHE` | geometric | `hurst_scaling_proxy` | approximate | Increment moments scale across selected lags. | Multiscale increment-variance comparisons. | Lag-grid sensitivity and short-sample instability. |
| `WaveletOLS` | wavelet | `hurst_scaling_proxy` | approximate | Wavelet detail variances scale linearly across selected levels. | fGn/fBm-style records with adequate wavelet levels. | Scale-band selection, boundary effects, and short signals. |
| `WaveletAbryVeitch` | wavelet | `hurst_scaling_proxy` | experimental | Abry-Veitch-style wavelet log-scale regression approximation. | Exploratory wavelet comparison on long enough records. | Needs stronger validation; sensitive to wavelet family and usable levels. |
| `WaveletBardet` | wavelet | `hurst_scaling_proxy` | experimental | Weighted wavelet log-scale regression approximation. | Exploratory wavelet comparison on long enough records. | Weighting and level selection can drive results; short signals are invalid. |
| `WaveletJensen` | wavelet | `hurst_scaling_proxy` | experimental | Two-band wavelet slope extrapolation. | Exploratory comparison where fine and coarse bands are both populated. | Band definitions can be fragile; short or narrow-band records fail. |
| `WaveletWhittle` | wavelet | `hurst_scaling_proxy` | experimental | Wavelet-domain Whittle-type fit to detail variances. | Exploratory wavelet comparison on long enough records. | Numerical fit and level support remain experimental. |

## Interpretation Rules

Do not mix estimator targets casually. `hurst_scaling_proxy` and `long_memory_parameter` are related
in some model families but are not identical public-contract quantities.

Leaderboard results are summaries of declared component metrics. They are not universal estimator
rankings and should always be reported with the underlying metrics.

For publication-facing analysis, prefer reporting estimator families, target estimands, parameter
settings, and failure/missing-uncertainty rates alongside any accuracy or robustness summaries.
