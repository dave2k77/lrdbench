# Parameter Glossary

This page explains the most common parameters you will see in manifest `estimators` blocks.

## Temporal estimators (RS, DFA, DMA, AbsoluteMoment, Variance, VarianceResidual)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_bootstrap` | int | 200 | Number of bootstrap replicates for confidence intervals. Set to 0 to skip bootstrap CIs. |
| `bootstrap_block_len` | int | `max(4, n//10)` | Block length in samples for the circular block bootstrap. |
| `ci_levels` | list[float] | `[0.95]` | Nominal coverage levels for symmetric percentile intervals. |
| `min_scale` | int | varies | Minimum block size or scale (in samples) for DFA, DMA, and aggregation estimators. |
| `max_scale` | int | varies | Maximum block size or scale (in samples). |
| `detrend_order` | int | 1 | Polynomial detrending order for DFA and VarianceResidual. |
| `scale_ratio` | float | 1.5 | Geometric spacing factor between consecutive aggregation scales. |
| `use_anis_lloyd_correction` | bool | `False` | *(RS only)* Apply the Anis-Lloyd finite-sample bias correction. |

## Spectral estimators (GPH, Periodogram, WhittleMLE, ModifiedLocalWhittle)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_bootstrap` | int | 200 | Number of bootstrap replicates for CIs. |
| `bootstrap_block_len` | int | `max(4, n//10)` | Block length for the circular block bootstrap. |
| `ci_levels` | list[float] | `[0.95]` | Nominal coverage levels. |
| `m` | int | varies | Number of low-frequency Fourier frequencies used. GPH defaults to `n^0.5`; WhittleMLE defaults to `n//8`; ModifiedLocalWhittle defaults to `n^0.55`. |
| `taper` | str | `"none"` | Spectral taper. `"none"` uses the raw periodogram; `"cosine"` applies a cosine bell (Hann-type) window to reduce spectral leakage. |

## Geometric estimators (Higuchi, GHE)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `k_max` | int | `max(8, min(64, n//8))` | Maximum lag / block size for Higuchi curve-length calculation. |
| `n_scales` | int | 16 | Number of geometrically spaced lags for GHE. |
| `h_min` | int | 1 | Minimum lag for GHE. |
| `flat_slope_tol` | float | 0.08 | *(GHE only)* Threshold below which the log-log slope is treated as flat and the estimate is clamped to `0.5`. Set to `0.0` to disable. |

## Wavelet estimators (WaveletOLS, WaveletAbryVeitch, WaveletBardet, WaveletJensen, WaveletWhittle)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_bootstrap` | int | 200 | Number of bootstrap replicates for CIs. |
| `bootstrap_block_len` | int | `max(4, n//10)` | Block length for the circular block bootstrap. |
| `ci_levels` | list[float] | `[0.95]` | Nominal coverage levels. |
| `wavelet` | str | `"db4"` | Wavelet family passed to `pywt.wavedec`. |
| `max_level` | int | varies | Maximum decomposition level. Defaults to the largest usable level minus boundary scales. |

## Data-driven estimators (MLRandomForest, MLSVR, MLCNN, MLLSTM)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_path` | str | `None` | Path to a pre-trained model artefact. If absent, the estimator trains from the manifest's `ml_training` block. |

## Execution block

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_workers` | int | 1 | Thread-pool size for parallel estimator fits. |
| `estimate_cache_dir` | str | `None` | Directory for on-disk estimate caches. |
| `cache_read` | bool | `True` | Allow reading from the estimate cache. |
| `cache_write` | bool | `True` | Allow writing to the estimate cache. |
