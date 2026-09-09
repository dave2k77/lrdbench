# Benchmarking classical memory and scaling estimators under model mismatch and contamination

Davian R. Chin

Department of Biomedical Engineering, University of Reading, UK

## Abstract

Estimates of temporal scaling can change with the signal representation, the fitted scale range and the procedure used to quantify uncertainty. We evaluated these dependencies using lrdbench, with implementation checks completed before an independently seeded confirmation experiment. The study compared 21 pipelines based on 12 algorithms on stationary fractional Gaussian noise, ARFIMA(0,d,0) and autoregressive signals. Clean accuracy used 66,000 independent records across 33 process–length cells. A paired contamination study applied 23 separate operators to 7,000 of those records, and a clean interval study evaluated 248,000 nominal 95% intervals on 15,500 records. All 4,767,000 clean and contaminated point fits were numerically valid. Nevertheless, performance depended strongly on the generating process. Equal-cell mean absolute errors for raw Higuchi estimates were 0.034 on fractional Gaussian noise and 0.226 on short-memory autoregressive signals. Mean removal eliminated sensitivity to a constant offset in the geometric estimators, while increasing clean fractional Gaussian noise error and leaving substantial step sensitivity. For fractional Gaussian noise with H = 0.85 and n = 512, centered circular-block percentile intervals covered the target in 17.60% of Higuchi and 6.95% of generalized Hurst estimates. Fitted fractional Gaussian noise basic intervals increased coverage to 92.20% and 92.95%, respectively, but both procedures had zero observed coverage on the two strongly persistent autoregressive cells at this length. These results support reporting accuracy, contamination response and interval calibration separately. They do not establish a universal estimator ranking, a calibrated test for long-range dependence or validity for neural recordings.

Keywords: long-range dependence; Hurst exponent; simulation benchmark; contamination; confidence interval coverage; reproducibility

## 1 Introduction

Temporal scaling is often summarized by a Hurst exponent or a related memory parameter. Fractional Brownian motion and its stationary increments provide a precise setting in which such parameters have a probabilistic interpretation [1]. Fractionally differenced processes provide another model with a controllable low-frequency dependence structure [2]. In applications, however, an estimated slope over a finite collection of scales need not identify the asymptotic dependence of the underlying process. Agreement with a scaling model must be distinguished from the ability to return a numerical estimate.

Empirical comparison of long-memory estimators has a substantial history [3]. A useful benchmark must state what each method receives, what parameter it is intended to recover, and which departures from its assumptions are examined. This is particularly relevant to biomedical time series. Analyses of neuronal oscillation amplitudes, for example, involve a different representation from an unfiltered scalar signal or its cumulative path [4]. A benchmark on synthetic increments can inform the design of such analyses, but cannot by itself validate an EEG biomarker or an inference about neuronal criticality.

Three questions motivate the present study. First, how accurately do specified implementations recover known targets on clean records from persistent, antipersistent and short-memory processes? Second, how much do estimates and estimation errors change when individual contamination operators are applied to the same underlying records? Third, do nominal confidence intervals achieve their stated coverage, and how do mean removal, interval construction and a fitted dependence model affect that coverage? These questions require different denominators and different interpretations. A method that has low error on clean fractional Gaussian noise may respond strongly to a level shift. A method that returns an interval for every record may still have poor coverage.

We address these questions with lrdbench, a research framework for reproducible comparison of memory and scaling estimators. Before the confirmation experiment, we checked the implemented statistics, input transformations, contamination operators and summary calculations. The resulting study uses a locally frozen protocol, fresh evaluation streams, stored parent–descendant identities, and an independent audit of the resulting summaries. Its contribution is a traceable finite-sample comparison of declared pipelines, including unfavorable outcomes, rather than a new estimator or a claim of universal superiority. The design and reporting follow the separation of aims, generating mechanisms, estimands, methods and performance measures advocated for simulation studies [5].

## 2 Methods

### 2.1 Scope and target parameters

The observational unit was one stationary scalar record of length n, interpreted as increments. There was no physical sampling frequency. All scales and lags therefore refer to samples. We used fractional Gaussian noise (fGn), stationary ARFIMA(0,d,0), and stationary Gaussian AR(1). The evaluation target was H for fGn, d + 0.5 for ARFIMA, and the asymptotic value 0.5 for every AR(1) process. The mapping between H and d is used for these specified models; it is not assumed to hold for arbitrary contaminated signals.

The fGn grid contained H = 0.25, 0.50, 0.75 and 0.85. These values represent antipersistence, white noise and two levels of persistence. ARFIMA used d = −0.25, 0 and 0.25. The white-noise cases in the fGn and ARFIMA grids are separate simulation cells of the same distribution, rather than two substantively different null mechanisms. AR(1) used φ = −0.5, 0.5, 0.8 and 0.95. Even the strongly persistent AR(1) cases are short-memory processes: their finite-scale behavior must not be interpreted as a change in the declared asymptotic target.

For contaminated records, the target remained that of the clean parent. The contamination experiment consequently measures recovery of a latent clean parameter. It does not assume that a record containing a step, trend or outliers has its own well-defined H equal to that parameter. No human or animal recordings, amplitude envelopes, multichannel signals or empirical EEG validation were included.

### 2.2 Design and replication

Clean accuracy crossed all 11 process settings with n = 512, 1024 and 2048, giving 33 cells with 2,000 independent records per cell. All 21 pipelines were applied to all 66,000 records. The contamination study used n = 512 and 1024 and seven process settings: all four fGn values, ARFIMA d = 0.25, and AR(1) φ = 0.8 and 0.95. It selected the first 500 declared repetition indices in each of these 14 cells from the clean pool. Each of the resulting 7,000 parents generated 23 separately contaminated descendants (Table 1).

The interval study used clean records only. Its core comprised the same seven process settings at n = 512, with 2,000 records per cell. A prespecified length sensitivity analysis used 500 records per cell at n = 1024 for fGn H = 0.50 and 0.85 and AR(1) φ = 0.95. These 15,500 records were also subsets of the clean pool. Thus the three studies share parents; their record counts must not be added and interpreted as distinct independent observations. Repetitions were fixed before confirmation and were not extended or stopped in response to results.

The protocol, estimator settings and seed rules were frozen locally before the confirmation run. This was not external preregistration. Development and rehearsal streams were separate from the confirmation namespace. Deterministic seeds combined the namespace, global seed 20260915, process–length cell, repetition and stream using SHA-256. Contamination and resampling had separate streams linked to the parent identity. The summary-resampling seed was 20260916. Appendix A records the source and result identities needed to distinguish this experiment from earlier development runs.

### 2.3 Generation of clean records

We generated finite Gaussian records by exact covariance factorization for fGn and ARFIMA. For unit-variance fGn, the lag-k covariance was

EQUATION: γ(k) = ½ ( |k + 1|^(2H) − 2|k|^(2H) + |k − 1|^(2H) ).

For ARFIMA(0,d,0) with unit innovation variance, the stationary covariance was obtained from γ(0) = Γ(1 − 2d)/Γ(1 − d)² and γ(k) = γ(k − 1)(k − 1 + d)/(k − d), with the white-noise case handled explicitly. A Cholesky factor of the n × n covariance matrix transformed an independent standard Gaussian vector for each record. No diagonal jitter was added. The final experiment did not use an approximate spectral synthesis or a truncated fractional filter.

For AR(1), we sampled x₀ from N(0,1), then used xₜ = φxₜ₋₁ + √(1 − φ²)zₜ with independent standard Gaussian innovations. This initializes the process in its stationary distribution and preserves unit marginal variance without a burn-in period. These constructions specify the finite-record distributions actually tested; they do not resolve how well any model describes biological data.

### 2.4 Estimation pipelines and signal representations

The roster contained 19 configurations of 12 base algorithms, plus two explicit mean-centered geometric variants, for 21 pipelines. We grouped related implementations for interpretation without treating configurations as independent algorithmic discoveries. Table S1 gives the complete settings and the mapping from manuscript names to repository identifiers. All point-estimation bootstraps were disabled; uncertainty was evaluated in the separate interval study.

The temporal methods comprised rescaled range (R/S), absolute moments of block means, variance of block means, detrended residual variance, detrended fluctuation analysis (DFA), and detrended moving average (DMA). R/S fitted the scaling of the mean rescaled range over forward, disjoint blocks without the Anis–Lloyd correction. Absolute moment and variance used the slopes of block-mean summaries, mapped to H by 1 + slope and 1 + slope/2, respectively. Residual variance operated on the demeaned cumulative profile and used linear detrending within disjoint blocks, with H = slope/2. It is related to DFA and is not presented as an independent source of evidence merely because it has a different label.

DFA fitted root mean square fluctuations after linear detrending of forward, disjoint profile segments [6]. DMA used a backward moving average of the demeaned cumulative profile and all valid residual positions [7]. Both used short, balanced and long scale bounds of [8,96], [12,160] and [16,256], with successive integer scales obtained by multiplying by 1.25 and rounding. These bounds were fixed in samples at each record length. They are configuration labels, not claims that the resulting scales have an optimal or common physical interpretation.

The spectral methods used the positive Fourier frequencies j/n without tapering. Geweke–Porter-Hudak (GPH) regression used m = 32 or 64 frequencies [8]. With xⱼ = log[4 sin²(πj/n)], H was 0.5 minus the ordinary least-squares slope of log periodogram on xⱼ. The method retained in the repository as WhittleMLE fitted an ARFIMA spectral shape on the first 64 frequencies. We call it band-limited ARFIMA-shape Whittle; it is not exact time-domain Gaussian maximum likelihood. The repository identifier ModifiedLocalWhittle computed the ordinary Gaussian local Whittle criterion on 64 frequencies [9], without an additional modification. Both optimization ranges were d ∈ [−0.49,0.49].

Wavelet estimation regressed log₂ sample detail variances on octave and used H = (slope + 1)/2 for the increment convention. The three settings used db2 over a broad or reduced band and db4 over a conservative band, with symmetric boundary extension. Regression was unweighted. The use of wavelet variance scaling is related to established wavelet analyses of long-range dependence [10], but the implemented unweighted procedure is not claimed to reproduce every correction or weighting scheme in that literature.

Higuchi and the generalized Hurst exponent (GHE) were applied to a cumulative path with an initial zero prepended. Higuchi used maximum lag 32, the graph-length normalization of the implemented Higuchi statistic, and H = 2 − D [11]. GHE used order q = 1 and the slope of log mean absolute path increments over 18 geometrically spaced candidate lags, reduced to distinct integers between 1 and floor((n + 1)/8) [12]. The raw variants integrated the original increments. The centered variants first subtracted their arithmetic sample mean. This forces the final cumulative displacement to zero and can change finite-record scaling even when the population mean is zero. The H = 2 − D relation is interpreted through the self-affine model used for calibration, not as a general identity for all observed paths.

Regression outputs were not clipped to [0,1]. Bounds internal to optimization were retained and distinguished from post hoc clipping. Nonfinite or insufficient inputs were rejected according to the audited method contracts. The benchmark compares these exact settings; it does not supply equal tuning budgets or match the temporal, Fourier and wavelet bands to a single effective range.

### 2.5 Contamination operators

Every operator was applied directly to its original clean parent. Let s denote the population-form sample standard deviation of that record (divisor n) and ε = 10⁻¹². A constant offset added s + ε to every sample. A step added a × s from index floor(np) onward, for a ∈ {0.5,1,2} and p ∈ {0.25,0.5,0.75}. These are different operations: subtracting a sample mean removes a constant offset but leaves a discontinuity from a step.

Outliers were additive impulses at max(1, round(qn)) uniformly chosen distinct indices, where q ∈ {0.005,0.01,0.05}. Each had an independent random sign and amplitude 8(s + ε). Polynomial contamination used an equally spaced coordinate t in [−1,1], with basis t for order one and t + t² for order two. The basis was centered, divided by its standard deviation plus ε, and multiplied by a(s + ε), for a ∈ {0.25,0.5,1}. Thus the order-two condition contains both linear and quadratic terms. It is not a pure quadratic basis.

The remaining four conditions added Student-t draws with ν ∈ {3,5} and strengths a ∈ {0.5,1}. Each noise vector z was scaled as a(s + ε)z/(sd(z) + ε), without subtracting its realized mean. This normalization fixes the realized relative scale and induces dependence among normalized entries; the added vector should not be described as independent, population-standardized Student-t innovations. Both degrees of freedom have finite population variance. There were 1 offset, 9 steps, 3 outlier, 6 polynomial and 4 noise conditions, with no combinations. Trends can cause scale-dependent effects in DFA [13]; the present operators evaluate particular amplitudes and placements rather than universal trend robustness.

### 2.6 Confidence interval procedures

The clean interval study evaluated GPH with m = 32, Higuchi and GHE. Circular block resampling used block length floor(n/16), or 32 and 64 at the two tested lengths. Random circular start indices defined blocks that were concatenated and truncated to n. A single pool of 1,999 block records per parent was shared across statistics and across the raw and centered treatments. In the centered treatment, each original or resampled record had its own arithmetic mean removed before evaluation. Block-bootstrap validity under long-range dependence depends on the statistic and assumptions; results for a sample mean do not establish validity for all scaling estimators [14]. We therefore measured coverage directly.

For a statistic T with bootstrap quantiles qᴮₐ, percentile and basic intervals were

EQUATION: I_percentile = [qᴮ₀.₀₂₅, qᴮ₀.₉₇₅],    I_basic = [2T(x) − qᴮ₀.₉₇₅, 2T(x) − qᴮ₀.₀₂₅].

We additionally fitted a stationary Gaussian fGn model with unknown constant mean, variance and H to each original interval-study record. For a candidate correlation matrix R(H), the generalized least-squares mean was μ̂(H) = (1′R⁻¹x)/(1′R⁻¹1), and the variance estimate was Q(H)/n, where Q(H) = (x − μ̂1)′R⁻¹(x − μ̂1). The profiled objective was n log[Q(H)/n] + log det R(H). We searched 11 initial grid values, followed by bounded local optimization around the best grid location, over H ∈ [0.01,0.99]. Fits within 0.001 of either bound were retained and flagged. The fitted model generated a second pool of 1,999 records per parent, with the fitted mean added before each statistic's sample centering.

The fitted-model basic interval was centered using the model parameter that generated the bootstrap records:

EQUATION: I_fGn = [T_c(x) + Ĥ_ML − qᴮ₀.₉₇₅, T_c(x) + Ĥ_ML − qᴮ₀.₀₂₅].

Here T_c is the centered statistic and the quantiles are from its fitted-fGn bootstrap distribution. The original model was fitted once per parent, rather than refitted within each draw, because the evaluated statistics were GPH, Higuchi and GHE rather than the likelihood estimator. This is a plug-in fitted-model bootstrap, and its coverage under ARFIMA or AR(1) is a deliberate model-mismatch evaluation.

Each statistic had four circular-block candidates (two mean treatments by two interval constructions) and one centered fitted-fGn basic candidate. GPH also had a raw normal approximation with half-width z₀.₉₇₅√[π²/(6Sxx)], where Sxx = Σ(xⱼ − x̄)² for its fixed 32-frequency regressor. This gave 16 candidates per record. An interval required a finite original statistic and all requested finite bootstrap statistics. Unavailable intervals counted as coverage misses; bootstrap draws were not compacted to a finite subset. Endpoints were not clipped. Model failure would leave the block and normal procedures separately evaluable.

### 2.7 Performance measures and Monte Carlo uncertainty

Clean error summaries used records complete across all 21 pipelines within a cell. Primary measures were bias and mean absolute error (MAE), with root mean square error, numerical validity, estimates outside [0,1], runtime and the diagnostic frequency of estimates at least 0.6 retained as secondary outputs. The threshold diagnostic was not calibrated as a hypothesis test and is not reported as a false-positive rate. In the stress study, completeness was defined jointly across all methods and the clean reference plus 23 descendants. This preserves the same paired support for every declared comparison.

For parent r with target Hᵣ, clean estimate Tᵣ and contaminated estimate Tᵣᶜ, the two primary stress measures were

EQUATION: ΔMAE = meanᵣ[|Tᵣᶜ − Hᵣ| − |Tᵣ − Hᵣ|],    D_A = meanᵣ|Tᵣᶜ − Tᵣ|.

Here D_A denotes mean absolute estimate drift. Signed estimate drift was retained separately. A negative MAE change can occur when contamination moves a biased estimator towards the target; it does not imply that the record is cleaner. The secondary MAE ratio divided aggregate contaminated MAE by aggregate clean MAE, using a denominator floor of 10⁻¹². It was recomputed within every resample and was never calculated as the mean of per-record ratios.

We summarized fGn, ARFIMA and AR(1) separately, using fixed equal weights for their constituent process–length cells. Clean domain summaries therefore average 12, 9 and 12 cells; stress summaries average 8, 2 and 4 cells, respectively. Each contamination condition remains separate. We did not construct a pooled stress score or a global ranking. Core interval summaries were separated from the length sensitivity analysis.

The independent resampling unit was the clean parent within a fixed cell. Summary uncertainty used 1,999 parent resamples, carrying all paired methods and descendants together and maintaining fixed domain weights. These resamples quantify Monte Carlo uncertainty in the benchmark summaries. They are distinct from the 1,999 within-record bootstrap draws that construct each confidence interval, and neither count replaces the number of independent records. For continuous cell means, Monte Carlo standard errors (MCSEs) used the observed standard deviation divided by √R; RMSE uncertainty used the delta method from MSE. Cell proportions used Wilson 95% intervals [15], including zero and all events. At coverage 0.95, the planned MCSE is approximately 0.49 percentage points for R = 2,000 and 0.97 for R = 500; it is larger near coverage 0.5.

We report unconditional coverage over all attempted intervals, conditional coverage among available intervals, availability and mean width. Paired width comparisons use common availability. Cell median widths are descriptive, and no domain median width is defined. The five prespecified contrast groups concerned geometric mean removal on clean accuracy, geometric mean removal under stress, interval centering, basic versus percentile construction, and fitted-fGn versus circular-block centered basic intervals. All summary intervals are pointwise and descriptive. We make no multiplicity-adjusted winner claims and do not infer significance from overlap or nonoverlap of separate intervals.

### 2.8 Verification and result integrity

Before confirmation, implementation checks examined covariance generation, estimator equations and transformations, scale indexing, offset and step semantics, invalid-input handling, pairing and metric definitions. The production experiment then stored input hashes, seeds, estimates, interval draws, endpoint records, settings and accounting. Its independent audit checked all 2,079 data chunks, parent–descendant identities, and replayed every contaminated record. It reconstructed all 248,000 endpoint pairs from stored bootstrap statistics and matched all 118,917 canonical summary rows.

For summary resampling, the audit inspected all stored cell draws, independently reconstructed a fixed subset of cell draw positions, and reconstructed all domain aggregation entries. It did not independently refit every point statistic or regenerate every clean Gaussian parent. The scope of the audit therefore supports the integrity of the recorded analysis and is complemented by the earlier implementation checks; it is not a second independent simulation of the entire experiment. All figures and tables below are generated from the audited exports without rerunning fits or altering the frozen producer.

## 3 Results

### 3.1 Completion and numerical availability

The clean study produced 1,386,000 point fits and the contamination study 3,381,000, totaling 4,767,000. All were numerically valid, with no missing or unattempted fits. The interval study produced all 248,000 requested intervals. Its two physical resampling pools contained 61,969,000 records and yielded 278,860,500 requested statistic evaluations, all finite. Fitting the original interval records added 93,000 statistic evaluations and 15,500 fGn model fits. These counts describe computational work; the number of independent clean parents remained 66,000.

Because all outputs were available, complete-case and all-attempt supports coincided, and conditional and unconditional interval coverage were identical. This did not imply correct calibration. Several interval procedures had very low coverage, and boundary fits were common under strongly persistent AR(1) model mismatch.

### 3.2 Clean accuracy depends on the generating process and settings

Table 2 reports MAE for every pipeline in each domain with Monte Carlo intervals; Figure 1 retains all process–length cells. Raw Higuchi had fGn domain MAE 0.0342 [0.0338, 0.0345], with short-scale DFA at 0.0352 [0.0348, 0.0355] and raw GHE at 0.0411 [0.0407, 0.0415]. On ARFIMA, the corresponding values were 0.0374 [0.0370, 0.0378], 0.0458 [0.0454, 0.0463] and 0.0410 [0.0406, 0.0415]. These are averages over the declared grids, rather than estimates of performance under a population distribution of possible biomedical signals.

The AR(1) profiles were different. Long-window DMA had domain MAE 0.1132 [0.1124, 0.1141], whereas short-scale DFA had 0.3876 [0.3870, 0.3882] and raw Higuchi 0.2265 [0.2260, 0.2269]. Changing the DFA bounds from short to long reduced its AR(1) domain MAE to 0.2646 [0.2638, 0.2654], while increasing its fGn MAE to 0.0488 [0.0482, 0.0492]. Likewise, using 64 rather than 32 frequencies reduced GPH's fGn domain MAE from 0.107 to 0.072, but increased its AR(1) domain MAE from 0.212 to 0.258. These configuration-dependent trade-offs argue against treating a single scale choice as a property of the algorithm in general.

The corrected geometric implementations responded to the fGn target rather than exhibiting a fixed apparent exponent. At n = 512, raw Higuchi and raw GHE had mean estimates of 0.247 and 0.247 at H = 0.25, and 0.835 and 0.832 at H = 0.85. Earlier implementation behavior is therefore not evidence for an intrinsic ceiling of Higuchi or a universal GHE anchor. The present estimates still have finite-sample error, and the relation between geometric scaling and a memory parameter remains model-dependent.

The bias summaries help interpret the AR(1) errors. Short-scale DFA had domain bias +0.3235 [+0.3228, +0.3241], compared with +0.1752 [+0.1748, +0.1757] for raw Higuchi and +0.1436 [+0.1430, +0.1441] for raw GHE. For AR(1) φ = 0.95 at n = 512, 99.90 [99.64, 99.97]% of short-scale DFA estimates were outside [0,1]. These outputs were retained as finite scaling estimates; numerical validity did not imply that they were admissible H values for a stationary fGn model. Complete bias and RMSE profiles accompany the MAE results in the machine-readable supplement.

Centering changed clean-data accuracy. The prespecified centered-minus-raw fGn MAE contrasts were +0.0047 [+0.0044, +0.0050] for Higuchi and +0.0089 [+0.0085, +0.0093] for GHE. The analogous AR(1) contrasts were -0.0026 [-0.0027, -0.0024] and -0.0055 [-0.0057, -0.0052], indicating small error reductions on that grid. These paired comparisons use the same parent records and hold the algorithm's lag settings fixed.

### 3.3 Offset invariance does not imply robustness to other contamination

An offset of one parent standard deviation increased fGn domain MAE by 0.341 [0.340, 0.342] for raw Higuchi and 0.339 [0.338, 0.341] for raw GHE. The corresponding changes after mean removal were indistinguishable from zero at numerical precision. This follows the transformation: a constant in the increments becomes a linear component in the raw cumulative path, while sample centering removes that constant exactly.

The midpoint step of amplitude two standard deviations remained harmful. Its fGn MAE increases were 0.314 [0.313, 0.315] and 0.314 [0.313, 0.315] for raw Higuchi and GHE, and 0.330 [0.329, 0.332] and 0.320 [0.319, 0.321] for the centered variants. The centered absolute estimate drifts were 0.404 and 0.412. These drift values differ from the MAE increases because movement of an estimate and movement of its absolute error are different quantities. Centering removed the offset vulnerability without providing general protection against a discontinuity.

Other operators produced distinct profiles (Table 3 and Figures S1–S3). For short-scale DFA on fGn, the MAE increase was 0.057 under the order-two trend at strength one and 0.194 [0.192, 0.196] under the midpoint step of amplitude two. Polynomial contamination was therefore not universally the most damaging tested condition. With outliers at 5% of positions, fGn MAE increases were 0.120 for short-scale DFA, 0.105 for raw Higuchi, 0.094 for raw GHE and 0.054 for GPH with 32 frequencies. Under Student-t noise with three degrees of freedom at strength one, the corresponding increases were 0.068, 0.055, 0.053 and 0.033.

These examples are descriptive illustrations of the complete condition profiles, not an additional selection rule for estimators. Relative performance changed with the process family, operator and configuration. In particular, small or negative error inflation on an AR(1) cell can reflect movement towards its asymptotic target from an initially biased finite-scale estimate. Absolute drift and the paired clean error remain necessary to interpret that result.

### 3.4 Interval coverage and width depend on the complete procedure

The strongest fGn core cell illustrates the distinction between statistic accuracy and interval calibration (Table 4). At H = 0.85 and n = 512, raw circular-block percentile intervals covered the target in 63.80 [61.67, 65.88]% of Higuchi estimates and 60.65 [58.49, 62.77]% of GHE estimates. Centering reduced percentile coverage to 17.60 [15.99, 19.33]% and 6.95 [5.92, 8.15]%. Changing the centered construction from percentile to basic increased coverage to 80.25 [78.45, 81.94]% and 75.60 [73.67, 77.43]%, still below the nominal 95% level.

The fitted-fGn centered basic procedure achieved coverage of 92.20 [90.94, 93.30]% for Higuchi and 92.95 [91.74, 93.99]% for GHE. Relative to circular-block centered basic intervals, the paired increases were 11.95 [10.55, 13.45] and 17.35 [15.70, 19.00] percentage points. Mean widths increased from 0.194 to 0.223 for Higuchi and from 0.207 to 0.242 for GHE. Thus the coverage gains accompanied wider intervals, and residual undercoverage remained in this cell.

GPH with 32 frequencies behaved differently. Its circular-block percentile coverage in the same cell was 95.50%, whereas basic coverage was 69.65%, despite identical mean widths of 0.517. The fitted-fGn basic and normal procedures achieved 95.00% and 94.75%, with widths 0.534 and 0.529, respectively. Equality of raw and centered GPH results is consistent with mean removal leaving the nonzero-frequency regression unchanged. These comparisons show why the resampling law, the statistic transformation and the interval construction must all be named when reporting coverage.

### 3.5 Model mismatch and the length sensitivity analysis

The fitted-fGn approach did not transfer reliably to strongly persistent AR(1). At n = 512, both geometric fitted-model intervals had zero observed coverage in each of the φ = 0.8 and 0.95 cells. A zero count out of 2,000 has a Wilson upper 95% bound of approximately 0.19%, rather than proving a population probability of exactly zero. The fGn model fit reached its boundary tolerance in 1,971 of 2,000 records at φ = 0.8 and all 2,000 records at φ = 0.95. These intervals were computable but targeted a poor fitted approximation to the asymptotic AR(1) memory parameter.

GPH was also affected by mismatch. Its fitted-fGn coverage at n = 512 was 61.10% at φ = 0.8 and 0.45% at φ = 0.95; normal coverage was 58.95% and 0.45%. By comparison, normal coverage across the four core fGn cells ranged from 94.35% to 95.00%. This evidence supports a distinction between calibration within the investigated fGn settings and robustness to short-memory alternatives with long apparent persistence.

At n = 1024 and fGn H = 0.85, centered circular-block percentile coverage remained low: 31.00% for Higuchi and 9.60% for GHE. Fitted-fGn basic coverage was 94.80% and 95.00%, and GPH normal coverage was 96.00%. For AR(1) φ = 0.95 at this length, both geometric fitted-model procedures again had zero coverage in 500 records, with a Wilson upper bound of approximately 0.76%, and all fitted models were boundary-flagged. Figure 2 presents all 160 candidate–cell combinations and distinguishes the larger core replication from the smaller sensitivity study. The latter is a restricted sensitivity check, not evidence for monotonic improvement with record length across the full design.

## 4 Discussion

### 4.1 What this benchmark establishes

This experiment demonstrates that three properties often conflated in estimator comparisons can diverge: clean error against a declared target, sensitivity to contamination, and interval coverage. Numerical completion was excellent throughout the run, yet some interval procedures covered the target in only a small fraction of records. Several pipelines had low MAE on the fGn grid and appreciably larger error on AR(1), where finite-scale persistence differs from the asymptotic target. The evidence therefore favors reporting process-specific profiles with explicit settings rather than treating successful computation or a pooled rank as validation.

The geometric results also illustrate why validation must precede interpretation. Correct normalization and input representation restored a response to the fGn target that was absent in earlier development behavior. That correction does not establish a new theorem about Higuchi or GHE, nor does it invalidate earlier applications of correctly implemented methods. It changes the evidence available from this particular research tool. Claims about an algorithm's inherent behavior should rest on its declared mathematical procedure and reproducible implementation, not on an unverified label.

### 4.2 Mean treatment and scale selection are part of the estimator

Subtracting the sample mean may look like a harmless preprocessing choice, but for integrated-path statistics it changes the path's endpoint constraint. In this study it removed constant-offset sensitivity while worsening clean fGn MAE and materially altering circular-block percentile coverage. The same preprocessing did not remove step effects. These findings support specifying both the transformation and the statistic when describing a method, and evaluating their combination under the relevant perturbations.

Scale selection produced additional trade-offs. Longer DFA scales improved recovery of the asymptotic AR(1) target on this grid, while the short configuration had lower fGn error. GPH bandwidth changes also moved fGn and AR(1) errors in different directions. This is compatible with the distinction between fitting a finite-scale relationship and estimating an asymptotic parameter. Because the settings were not optimized for each generating family or matched across methods, the results compare usable declared pipelines rather than the best attainable performance of each algorithm.

### 4.3 Dependence assumptions matter for uncertainty

The fitted-fGn bootstrap improved geometric coverage in the persistent fGn example but did not achieve uniform nominal coverage, and its performance deteriorated sharply on AR(1). Boundary flags supplied a useful diagnostic of mismatch without repairing that mismatch. Removing such intervals from the coverage denominator would have made availability and coverage difficult to interpret; retaining them exposed the failure. The observed improvement under a compatible model must therefore be reported together with width, residual undercoverage and behavior on alternative processes.

The comparison between percentile and basic intervals is equally instructive. The two constructions use the same bootstrap distribution and have the same width for a given record, but locate their endpoints differently. Their markedly different coverage shows that obtaining many finite resamples is insufficient to justify an interval. Nor does increasing bootstrap count create more independent benchmark evidence: uncertainty in an observed coverage rate is controlled by the number of parent records, while within-record resampling approximates the chosen bootstrap distribution.

### 4.4 Relevance and limits for biomedical applications

The current evidence can guide implementation checks and selection of sensitivity analyses before studying EEG, MEG or other physiological recordings. It suggests examining stationary short-memory alternatives, additive shifts, impulses and trends; declaring the scale range; and validating a chosen interval procedure on models compatible with the intended representation. It does not establish accuracy for real recordings, where the target is unknown and preprocessing, oscillations, artifacts and nonstationarity interact. In particular, a raw increment benchmark cannot be transferred directly to the long-range temporal correlations of oscillation amplitude envelopes discussed in the neural literature [4].

An estimated H above 0.5 or above the stored diagnostic threshold of 0.6 is not, by itself, a calibrated rejection of short memory. The AR(1) results show why a separate discrimination study would need explicit null families, a prespecified test and independent threshold calibration. Neither such a test nor a mechanistic interpretation in terms of criticality was evaluated here. An observational extension would also require a sampling and preprocessing protocol, independent subject-level replication, and an analysis of how estimated scaling changes with those choices.

### 4.5 Limitations

The process and parameter grid is finite, with modest record lengths and Gaussian clean inputs. ARFIMA had no autoregressive or moving-average terms beyond fractional differencing. There were no oscillatory components, missing data, combined contamination operators, stochastic volatility, infinite-variance noise or multifractal targets. The Student-t conditions used realized standard-deviation normalization, and the polynomial conditions used specified centered bases; extrapolation to other formulations would require a new experiment.

The interval study was restricted to three statistics, clean inputs, one block-length rule and one fitted dependence model. It does not establish interval behavior under contamination, for DFA or DMA, or for other bootstrap schemes. The fixed optimization bounds and arithmetic centering choices are part of the evaluated procedures. The length sensitivity analysis covered only three cells with fewer independent records, and equal-cell domain averages are design summaries rather than prevalence-weighted estimates for a biomedical population.

Finally, implementation verification and summary auditing reduce several forms of error without eliminating all possible defects. The final audit used stored statistic streams and did not refit every point estimate. Monte Carlo intervals are pointwise and do not support simultaneous selection of the best among all displayed methods and conditions. The source and local result identities make these limits inspectable; a public archival deposit of the complete confirmation bundle remains a separate dissemination step.

## 5 Conclusion

Across the declared synthetic increment models, estimator performance depended on the generating process, scale settings and mean treatment. Mean removal eliminated constant-offset sensitivity in geometric pipelines but did not provide general contamination robustness. Interval coverage required its own evaluation: fitted-fGn basic intervals improved persistent-fGn coverage while failing under strongly persistent AR(1) mismatch. A useful benchmark should therefore report clean error, paired contamination effects, interval availability, coverage and width as separate quantities with explicit targets and Monte Carlo uncertainty. The present results support those comparisons for the audited lrdbench pipelines and the tested design; they do not establish a universal estimator winner or clinical validity.

## Code and data availability

The lrdbench repository is available at https://github.com/dave2k77/lrdbench. This manuscript uses the locally frozen producer revision 9c02d04 and the independently audited confirmation run identified in Appendix A. The manuscript source, generated tables, vector figures, evidence mapping and rebuild scripts are included in the accompanying local manuscript package. The full raw confirmation archive and these new revisions have not yet been publicly deposited or released; the repository URL should not be interpreted as a permanent public archive of this exact experiment. No participant data were analyzed.

## References

REFERENCES

PAGEBREAK

## Tables

TABLE: design

PAGEBREAK

TABLE: clean

PAGEBREAK

TABLE: stress

PAGEBREAK

TABLE: coverage

LANDSCAPE

FIGURE: clean

PAGEBREAK

FIGURE: coverage

PORTRAIT

## Appendix A Reproducibility and supplementary material

The source experiment is lrdbench-classical-confirmation-v1. The producer revision is 9c02d04 and the audit package revision is b3d0648. The scientific design SHA-256 is b5b9399d284e3fae8135050aeac5c8bc0a02ab36b4f0a6d15041f55a497681bb. The confirmation run identity is 43d0a7f75c8afab6d32ab6fd1f2ff8db49cca59e36971e2b74404173f4cbfcf2. The canonical summary SHA-256 is 95b8e938fb98a674c7ba2e92b7d59ed0f909ffd6ae2e8585c90a0f23f7c01504. These identify local artifacts; none is presented as an archival DOI.

The confirmation run completed all point and interval work on 7 September 2026. A subsequent summary-only recovery addressed a filesystem name-clash event without recomputing fits. The independent results audit passed that day. The audit's checks and limitations are documented with the producer bundle and in Section 2.8. The manuscript rebuild reads only verified summary exports. Its evidence map records the exact source rows used for numeric narrative insertions, tables and plots, and checks the export hashes before generation.

Table S1 lists every evaluated pipeline and the exact settings needed to interpret its label. The machine-readable supplements retain all 118,917 canonical rows, including bias, RMSE, runtime, availability, out-of-range estimates, threshold diagnostics, all stress metrics, interval widths and paired contrasts. These secondary outputs remain available without being converted into an undeclared ranking. Figures S1–S3 display MAE change for every stress condition and pipeline, separately for each domain; the corresponding full-precision tables also include Monte Carlo intervals and absolute and signed drift.

The finite grids of temporal and wavelet scales differ across algorithms. R/S and block-aggregation methods use rounded 1.5-fold spacing; DFA and DMA use rounded 1.25-fold spacing. The fixed upper bounds of several methods do not grow with n, whereas Fourier frequencies at fixed m shrink with increasing n. Symmetric wavelet extension includes boundary coefficients in the retained variances. These details are important when assessing whether a finding might reflect the chosen scales rather than a general property of an estimator.

PAGEBREAK

TABLE: methods

LANDSCAPE

FIGURE: stress_fGn

PAGEBREAK

FIGURE: stress_ARFIMA

PAGEBREAK

FIGURE: stress_AR1
