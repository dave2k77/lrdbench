# Parameter Glossary

This page explains the most common parameters you will see in manifest `estimators` blocks.

## Target estimands

Every estimator declares a `target_estimand`. Truth-based metrics are only computed for an estimator
against a record that carries a matching truth (`raw/truths.csv`).

| Estimand | Kind | Model range | Meaning |
|----------|------|-------|---------|
| `hurst_scaling_proxy` | regression | `(0, 1)` | Hurst-like scaling exponent `H`. |
| `long_memory_parameter` | regression | `(-0.5, 0.5)` | Fractional-integration parameter; $d=H-1/2$ only under compatible stationary finite-variance scaling assumptions. |
| `spectral_exponent_beta` | regression | `~(-1, 1)` | Low-frequency spectral slope $\beta$, where $S(f) \propto f^{-\beta}$; $\beta=2H-1$ for fGn. Other models can have different ranges. |
| `timescale_tau` | regression | `> 0` | Autocorrelation-decay time constant `τ₀` in samples. Undefined (`None`) for power-law LRD. |
| `lrd_class` | classification | `[0, 1]` | Experimental decision score, not necessarily a calibrated probability; `lrd_class` truth is `0` or `1`. |

## Temporal estimators {#temporal-estimators-rs-dfa-dma-absolutemoment-variance-varianceresidual}

Applies to: RS, DFA, DMA, AbsoluteMoment, Variance, VarianceResidual.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_bootstrap` | int | 200 | Number of bootstrap replicates for confidence intervals. Set to 0 to skip bootstrap CIs. |
| `bootstrap_block_len` | int | `max(4, n//10)` | Block length in samples for the circular block bootstrap. |
| `ci_levels` | list[float] | `[0.95]` | Nominal coverage levels for symmetric percentile intervals. |
| `min_scale` | int | varies | Minimum block size or scale (in samples) for RS, DFA, DMA, and aggregation estimators. RS defaults to 8. |
| `max_scale` | int | varies | Maximum block size or scale (in samples). RS defaults to `n//2` so each fitted scale has at least two subseries. |
| `detrend_order` | int | 1 | Polynomial detrending order for DFA and VarianceResidual. |
| `scale_ratio` | float | 1.5 | Geometric spacing factor between consecutive aggregation scales. |
| `use_anis_lloyd_correction` | bool | `False` | *(RS only)* Divide each scale's average R/S value by the Anis-Lloyd white-noise expectation before fitting the slope. |

## Spectral estimators {#spectral-estimators-gph-periodogram-whittlemle-modifiedlocalwhittle}

Applies to: GPH, Periodogram, WhittleMLE, ModifiedLocalWhittle.

`ModifiedLocalWhittle` is the historical registry name for an ordinary Gaussian
local Whittle objective. It has no implemented nonstationary correction. Both it
and `WhittleMLE` optimize d within [-0.49, 0.49]; boundary hits are diagnostic
warnings. WhittleMLE fits an ARFIMA(0,d,0) spectral shape on the selected frequency
band, not an exact time-domain likelihood or the exact fGn spectrum.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_bootstrap` | int | 200 | Number of bootstrap replicates for CIs. |
| `bootstrap_block_len` | int | `max(4, n//10)` | Block length for the circular block bootstrap. |
| `ci_levels` | list[float] | `[0.95]` | Nominal coverage levels. |
| `m` | int | varies | Number of low-frequency Fourier frequencies used. GPH and Periodogram default to `n^0.5`; WhittleMLE defaults to `n//8`; ModifiedLocalWhittle defaults to `n^0.55`. |
| `taper` | str | `"none"` | GPH/Periodogram taper. `"none"` uses the raw periodogram; `"cosine"` uses a Hann window. WhittleMLE and ModifiedLocalWhittle do not consume this parameter. |

## Geometric estimators {#geometric-estimators-higuchi-ghe}

Applies to: Higuchi, GHE.

Both methods analyse a path. Declare `input_representation: increments` for fGn
records: the adapter constructs a path by prepending zero to their cumulative sum,
without demeaning the increments. Declare `path` for an already integrated path.
Omission defaults to `path` and records a warning. This choice is never inferred
from the record's truth. Path-based H proxies are not automatically LRD parameters.

Their candidate circular block bootstrap resamples increments and reconstructs the
path for each draw. It does not resample path levels. This procedure still requires
method-specific coverage calibration under long memory.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_representation` | str | `"path"` | `"path"` or `"increments"`; declare explicitly in research manifests. |
| `k_max` | int | `max(8, min(64, n//8))` | Maximum lag / block size for Higuchi curve-length calculation. |
| `n_scales` | int | 16 | Number of geometrically spaced lags for GHE. |
| `h_min` | int | 1 | Minimum lag for GHE. |
| `h_max` | int | `n//8` | Maximum GHE lag on the analysed path; must exceed `h_min` and remain below `n/2`. |
| `q` | float | 2.0 | Positive finite moment order for GHE: mean absolute lagged differences raised to `q`; report log-log slope divided by `q`. Use 1.0 for the first absolute moment. |
| `flat_slope_tol` | float | 0.0 | Deprecated; nonzero values are rejected. The former forced H = 0.5 fallback was removed. |

Higuchi and GHE report unclipped slopes, with out-of-range diagnostics. GPH,
Periodogram and PeriodogramBeta also retain unconstrained regression estimates.
The ranges in the estimand table describe model parameters, not enforced estimator
bounds. These changes intentionally alter results and require new output bundles.

RS, DFA, DMA, AbsoluteMoment, Variance, VarianceResidual and the WaveletOLS,
AbryVeitch and Bardet regressions also retain unconstrained estimates. Their
stationary-increment H interpretation requires appropriate inputs. In particular,
DFA integrates its input internally; its raw fluctuation slope on an fBm path is
not the same target as H on fGn increments. Out-of-range points and bootstrap draws
are counted, not silently capped or relabelled as successful memory recovery.

The RS `use_anis_lloyd_correction` option divides by the Gaussian white-noise
expectation before regression and adds 0.5. This is an implementation-specific
normalization using that expectation, not a general unbiased estimator.

## Wavelet estimators {#wavelet-estimators-waveletols-waveletabryveitch-waveletbardet-waveletjensen-waveletwhittle}

Applies to: WaveletOLS, WaveletAbryVeitch, WaveletBardet, WaveletJensen, WaveletWhittle.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_bootstrap` | int | 200 | Number of bootstrap replicates for CIs. |
| `bootstrap_block_len` | int | `max(4, n//10)` | Block length for the circular block bootstrap. |
| `ci_levels` | list[float] | `[0.95]` | Nominal coverage levels. |
| `wavelet` | str | `"db4"` | Wavelet family passed to `pywt.wavedec`. |
| `j_drop_high` | int | AbryVeitch: 2; OLS/Bardet/Whittle: 1 | Number of finest (highest-frequency) levels removed. |
| `j_drop_low` | int | AbryVeitch/Bardet: 2; OLS/Whittle: 1 | Number of coarsest (lowest-frequency) levels removed. |
| `fine_band`, `coarse_band` | pair[int, int] | `[2, 4]`, `[4, 6]` | Jensen level bands. |

Maximum DWT depth is computed from record length and the wavelet filter. `max_level` is not
a consumed estimator parameter. At least three retained detail levels are required by the
regression helpers; length alone does not guarantee a fit.

## Data-driven estimators {#data-driven-estimators-mlrandomforest-mlsvr-mlcnn-mllstm}

Applies to: MLRandomForest, MLSVR, MLCNN, MLLSTM.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_path` | str | `None` | Path to a pre-trained model artefact. If absent, the estimator trains from the manifest's `ml_training` block. |
| `max_lag` | int | 16 | *(MLRandomForest, MLSVR)* Number of autocorrelation lags included in the feature vector. Changing this from the value used during training will raise a `max_lag_mismatch` error instead of silently producing garbage. |
| `n_estimators` | int | 100 | *(MLRandomForest)* Number of trees in the random forest. |
| `max_depth` | int | `None` | *(MLRandomForest)* Maximum depth of each tree. `None` means fully grown. |
| `min_samples_leaf` | int | 1 | *(MLRandomForest)* Minimum samples per leaf. |
| `C` | float | 10.0 | *(MLSVR)* SVR regularization parameter. |
| `epsilon` | float | 0.03 | *(MLSVR)* SVR epsilon-tube margin. |
| `kernel` | str | `"rbf"` | *(MLSVR)* Kernel type. |
| `sequence_length` | int | 256 | *(MLCNN, MLLSTM)* Length every input series is resampled to before being fed to the network. Values smaller than 8 raise an error. |
| `conv1_channels` | int | 16 | *(MLCNN)* First convolution channel count. |
| `conv2_channels` | int | 32 | *(MLCNN)* Second convolution channel count. |
| `hidden_size` | int | 32 | *(MLLSTM)* LSTM hidden size per layer. |
| `num_layers` | int | 1 | *(MLLSTM)* Number of stacked LSTM layers. Values >1 trigger inter-layer dropout. |
| `dropout` | float | 0.2 | *(MLCNN, MLLSTM)* Dropout probability applied after conv/LSTM layers and in the MLP head. Set to `0.0` to disable (LSTM will still use 0.2 when `num_layers > 1` because the implementation uses a fallback at that setting). |
| `learning_rate` | float | 0.001 | *(MLCNN, MLLSTM)* Adam learning rate. |
| `weight_decay` | float | 1e-4 | *(MLCNN, MLLSTM)* Adam weight-decay (L2 regularization). |
| `batch_size` | int | 16 | *(MLCNN, MLLSTM)* Training mini-batch size. |
| `epochs` | int | 8 | *(MLCNN, MLLSTM)* Number of training epochs. |

## Spectral-exponent and timescale estimators {#spectral-exponent-and-timescale-estimators-periodogrambeta-acfdecay}

Applies to: PeriodogramBeta, ACFDecay.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `m` | int | `n^0.5` | *(PeriodogramBeta)* Number of low-frequency Fourier frequencies for the slope fit. |
| `taper` | str | `"none"` | *(PeriodogramBeta)* Spectral taper (`"none"` or `"cosine"`). |
| `max_lag` | int | automatic, capped at `n//4` | *(ACFDecay)* Automatic fitting stops before the first ACF value below `rho_floor`. An explicit cap instead retains positive ACF values above `1e-6` within that cap. |
| `rho_floor` | float | 0.1 | *(ACFDecay)* Threshold used to end the automatic leading ACF band; an explicit `max_lag` overrides this stopping rule. |
| `n_bootstrap`, `bootstrap_block_len`, `ci_levels` | | | Shared block-bootstrap CI parameters (see temporal estimators). |

## LRD discriminators {#lrd-discriminators-thresholdhurst-lowfreqspectral-scalecrossover-icmodelselect}

Applies to: ThresholdHurst / LowFreqSpectral / ScaleCrossover / ICModelSelect.

All target `lrd_class` and emit a `[0, 1]` score.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base` | str | `"dfa"` | *(ThresholdHurst)* Underlying Hurst estimator: `"dfa"`, `"gph"`, or `"rs"`. |
| `h0` | float | 0.55 | *(ThresholdHurst, ScaleCrossover)* Logistic decision centre on the Hurst / large-scale-slope axis. |
| `width` | float | 0.05 | Logistic scale. |
| `m_power` | float | 0.45 | *(LowFreqSpectral)* Low-frequency bandwidth as `m = n^m_power`. |
| `d0` | float | 0.075 | *(LowFreqSpectral)* Logistic centre on the memory-parameter axis. |
| `ar_orders` | list[int] | `[1, 2]` | *(ICModelSelect)* Short-memory AR orders compared against ARFIMA(0,d,0). |
| `scale` | float | 4.0 | *(ICModelSelect)* Logistic scale on the ΔBIC axis. |

## Execution block

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_workers` | int | 1 | Thread-pool size for parallel estimator fits. |
| `estimate_cache_dir` | str | `None` | Directory for on-disk estimate caches. |
| `cache_read` | bool | `True` | Allow reading from the estimate cache. |
| `cache_write` | bool | `True` | Allow writing to the estimate cache. |
