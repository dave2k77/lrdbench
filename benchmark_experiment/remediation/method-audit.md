# Estimator equations, metric definitions and diagnostic pilot

7 September 2026. Second local repair package, following foundation commit
`5189d85`. The equation defects are repaired and the additive metric contract is
implemented. Scientific validation of the complete roster and uncertainty methods
remains open. These diagnostic results do not replace the paper's benchmark.

## Mathematical findings and changes

**GPH: an additional factor-of-two defect (R17).** For the fractional-noise spectral
factor `S(w) proportional to (4 sin²(w/2))^(-d)`, a regression on
`log(4 sin²(w/2))` has slope `-d`. The previous code multiplied the slope by `-1/2`,
halving the estimated memory parameter before mapping to H. It now uses `d = -slope`.
An exact inverse-Fourier construction with the specified spectrum checks positive,
negative and out-of-model-range d at several bandwidths. The public H, d and beta
conversions are checked separately. The correction affects GPH, Periodogram,
PeriodogramBeta and ThresholdHurstDiscriminator when its base is GPH. Regression
estimates are no longer clipped to the stationary model range.
See the derivation in [Reducing the Bias of the Smoothed Log Periodogram Regression, equations 4–5](https://www.mdpi.com/2225-1146/8/4/40)
and the [original GPH article record](https://doi.org/10.1111/j.1467-9892.1983.tb00371.x).
The original publisher's full text was unavailable in this review; its record alone
is not the evidence for the equation check.

**Higuchi: missing length normalization (R04).** The implementation omitted the final
division by lag k in `L_m(k)`. Restoring it gives graph dimension D = 1 for a straight
line and approximately 1.5 across independent Brownian paths. The old implementation
returned clipped H = 0.9999 on the Brownian probes. Both D and H = 2 - D are now
unclipped, with diagnostics for values outside the nominal H range. This mapping
requires a suitable self-affine path interpretation; graph roughness alone does not
establish LRD. [Higuchi (1988), printed page 278](https://www.ism.ac.jp/~higuchi/index_e/papers/PhysicaD-1988.pdf)
was read and visually checked for the normalization.

**GHE: implement the declared moments (R04).** The calculation now fits
`mean(abs(X[t+lag] - X[t])**q)` against lag on logarithmic axes and divides the slope
by q. It supports explicit q = 1 and q = 2, defaulting to 2. The lag-independent
normalization affects only the intercept and is omitted. There is no automatic
detrending; this is the selected-lag moment regression, not a reproduction of every
preprocessing choice in the source. The variance-based calculation, forced H = 0.5
fallback and clipping were removed. Nonzero `flat_slope_tol` is rejected.
[Di Matteo, Aste and Dacorogna (2003), equations 1–2](https://arxiv.org/abs/cond-mat/0302434)
specify the moment scaling. Tests cover lines, Brownian paths, raw white-noise
levels, constant inputs and invalid moment orders.

**Input representation is explicit.** Higuchi and GHE accept `path` or `increments`.
For fGn records, declare `input_representation: increments`: the adapter prepends
zero to the cumulative sum, without demeaning. Already integrated paths use `path`.
Omission retains the direct-path interpretation and emits a warning; truth labels
never choose preprocessing. Their candidate circular bootstrap now resamples
increments and reconstructs paths, with an identity-resampling check. This corrects
the resampling object; it does not establish valid uncertainty under LRD.

**WaveletOLS convention check (R03).** Constructed Haar detail coefficients with
variance proportional to `2^(j(2H-1))` recover known H at 0.2, 0.5 and 0.8, validating
the current coarse-to-fine level indexing and H conversion. The ordering agrees
with the [official PyWavelets decomposition contract](https://pywavelets.readthedocs.io/en/latest/ref/dwt-discrete-wavelet-transform.html).
No further WaveletOLS equation change was made. Boundary effects, all configured
wavelets/bands and the other wavelet estimators remain to be audited.

## Diagnostic experiment and results

The reproducible script is [run_method_audit.py](run_method_audit.py). It creates
fGn independently of the framework generator using the exact increment covariance
matrix and Cholesky factorization. There are 32 independent records per condition,
512 samples per record, H = 0.25, 0.5 and 0.75, plus an AR(1) null with coefficient
0.8 and a 4096-sample burn-in. Seven fixed configurations give 896 point fits. This
is a development pilot, not a power calculation or a final choice of parameters.

The old and repaired calculations use identical inputs. Higuchi receives the same
integrated path on both sides, isolating the length normalization from the separate
input-adapter change. Mean estimates across the 32 records are:

| True H | GPH before | GPH after | Higuchi before | Higuchi after |
| --- | ---: | ---: | ---: | ---: |
| 0.25 | 0.3768 | 0.2536 | 0.9999 | 0.2545 |
| 0.50 | 0.4931 | 0.4862 | 0.9999 | 0.4847 |
| 0.75 | 0.6355 | 0.7709 | 0.9999 | 0.7433 |

The equation tests establish the correction; improved agreement in this small
sample is supporting evidence. It does not establish uniform superiority or remove
finite-sample bias and variance. The [point summary](pilot/point_summary.csv) includes
MAE, bias, valid counts and Monte Carlo standard errors for all seven configurations.

For three configurations at H = 0.5 and 0.75, each record receives 64 within-record
resamples, block length 32: 192 interval-producing fits and 12,288 bootstrap attempts.
All these points and intervals were available. Coverage is conditional on that
availability. Wilson 95% intervals below express Monte Carlo uncertainty in coverage,
not uncertainty in the mean estimated H:

| H | Configuration | Covered / available | Coverage | Wilson interval |
| --- | --- | ---: | ---: | --- |
| 0.50 | GPH, m = 32 | 32 / 32 | 100.0% | 89.3–100.0% |
| 0.50 | Higuchi, k max = 32 | 30 / 32 | 93.8% | 79.9–98.3% |
| 0.50 | GHE, q = 1, max lag = 32 | 30 / 32 | 93.8% | 79.9–98.3% |
| 0.75 | GPH, m = 32 | 32 / 32 | 100.0% | 89.3–100.0% |
| 0.75 | Higuchi, k max = 32 | 27 / 32 | 84.4% | 68.2–93.1% |
| 0.75 | GHE, q = 1, max lag = 32 | 26 / 32 | 81.3% | 64.7–91.1% |

The two geometric configurations show undercoverage at persistent H in this pilot.
GPH's 32/32 result is too imprecise to certify calibration; interval width and a much
broader parameter grid must be assessed. Sixty-four bootstrap draws are also too few
for stable tail quantiles in a confirmatory study. See the [coverage export](pilot/coverage_pilot.csv).

The AR(1) control has short memory and asymptotic H = 0.5. At the selected finite
scales, 26/32 GPH estimates and 32/32 estimates from each other configuration exceed
H = 0.6. These are counts for this null and these settings, not general false-positive
rates for the methods. They demonstrate why a point cutoff cannot be interpreted
as a nominal 5% LRD test and why null populations and scale sensitivity are essential.

## Metrics and reporting

The [version 2 metric contract](metric_contract.md) defines all implemented names.
Independent examples distinguish signed/absolute drift, error inflation, mean of
individual ratios versus ratio of paired MAEs, lost versus recovered coverage,
zero denominators and missing pairs. Target-based comparisons require the estimator's
own truth. Aggregates expose included/missing counts and available stratum counts.
Legacy names retain their earlier meanings. New names appear in stress exports;
ratio components remain in raw metadata and computed ratios in aggregate tables.

The current scalar summary bootstrap cannot estimate ratio uncertainty correctly;
such requests fail explicitly. Signed drift is descriptive and cannot be minimized
as a leaderboard component. Publication-specific plots and cluster-aware summary
resampling remain outstanding. Existing overview plots retain their labelled legacy
metrics and pool severity levels, so they are not ready-made paper figures.

## Reproduction, verification and remaining gates

Run from the repository with its test/report dependencies installed:

```console
python benchmark_experiment/remediation/run_method_audit.py --output reports/method-verification
python benchmark_experiment/remediation/run_foundation_smoke.py --output reports/method-foundation-verification
pytest -q tests/unit tests/integration/test_phase3_stress.py
```

Use a writable pytest `--basetemp` on this host. Full local row-level pilot outputs,
the checked before/after figure and source/package provenance are in the workspace's
`method-verification` directory, beside the repository. Compact pilot outputs and the
original execution provenance are retained in [pilot](pilot/provenance.json). The
recorded hashes identify the execution snapshot before subsequent documentation,
formatting, missing-pair accounting and reporter edits; the estimator calculations
were unchanged.

Verification results are recorded in [verification.json](pilot/verification.json).
The complete unit suite passed 253 tests with eight optional-dependency skips.
All seven targeted stress integration tests passed after two new fixture corrections.
A final 67-test check covers paired metrics, reports, foundation regressions and
stress integration, including completely absent stressed fits. Ruff and the strict
documentation build pass. Three small workflows each repeated exactly and passed
the output contract. All 20 frozen historical files still match their hashes.
The complete scientific/statistical suite and complete method roster are not
certified by this package. The existing Python 3.14 environment has four pre-existing
type-check errors, and the default Python 3.11 type-check target cannot parse its
NumPy stubs. A supported locked environment remains a prerequisite for final runs.

Next: finish analytical and generator checks for every retained method; calibrate
candidate uncertainty procedures across H, record length, bandwidth/scale and
short-memory nulls; select independent repetitions by required precision; freeze
shared clean parents and a fresh confirmatory seed set; then run the research grid
and regenerate the paper from canonical exports. Keep all historical results and
the supplied PDFs unchanged.
