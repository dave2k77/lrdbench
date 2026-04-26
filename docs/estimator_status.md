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

| Estimator | Family | Target estimand | Status | Notes |
| --- | --- | --- | --- | --- |
| `RS` | temporal | `hurst_scaling_proxy` | baseline | Rescaled-range Hurst proxy with optional block-bootstrap intervals. Useful as a simple classical baseline. |
| `DFA` | temporal | `hurst_scaling_proxy` | baseline | Detrended fluctuation analysis scaling exponent. Sensitive to scale range and detrending order. |
| `DMA` | temporal | `hurst_scaling_proxy` | baseline | Detrended moving-average fluctuation scaling. Sensitive to window range. |
| `GPH` | spectral | `long_memory_parameter` | baseline | Geweke-Porter-Hudak-style low-frequency regression for ARFIMA-style memory parameter `d`. |
| `Periodogram` | spectral | `long_memory_parameter` | approximate | Log-periodogram regression variant. Bandwidth choices materially affect results. |
| `WhittleMLE` | spectral | `long_memory_parameter` | approximate | Gaussian Whittle fit to ARFIMA(0,d,0) spectral shape. Use within its model assumptions. |
| `ModifiedLocalWhittle` | spectral | `long_memory_parameter` | approximate | Local Whittle-style low-frequency estimator. Needs more validation across finite samples and regimes. |
| `Higuchi` | geometric | `hurst_scaling_proxy` | approximate | Graph-dimension-derived Hurst proxy. Useful as a geometry-based comparator, not direct LRD evidence. |
| `GHE` | geometric | `hurst_scaling_proxy` | approximate | Multiscale increment-variance Hurst proxy. Sensitive to lag grid and short-sample behavior. |
| `WaveletOLS` | wavelet | `hurst_scaling_proxy` | approximate | OLS log-scale regression on wavelet detail variances. Scale-band selection is important. |
| `WaveletAbryVeitch` | wavelet | `hurst_scaling_proxy` | experimental | Abry-Veitch-style log-scale regression approximation. Needs stronger validation before public claims. |
| `WaveletBardet` | wavelet | `hurst_scaling_proxy` | experimental | Weighted log-scale regression approximation. Current implementation is exploratory. |
| `WaveletJensen` | wavelet | `hurst_scaling_proxy` | experimental | Two-band wavelet slope extrapolation. Current implementation is exploratory. |
| `WaveletWhittle` | wavelet | `hurst_scaling_proxy` | experimental | Wavelet-domain Whittle-type fit to detail variances. Current implementation is exploratory. |

## Interpretation Rules

Do not mix estimator targets casually. `hurst_scaling_proxy` and `long_memory_parameter` are related
in some model families but are not identical public-contract quantities.

Leaderboard results are summaries of declared component metrics. They are not universal estimator
rankings and should always be reported with the underlying metrics.

For publication-facing analysis, prefer reporting estimator families, target estimands, parameter
settings, and failure/missing-uncertainty rates alongside any accuracy or robustness summaries.
