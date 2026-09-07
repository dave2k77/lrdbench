# Next calibration experiment: design and decision gates

This is a prospective design for development and confirmation, not a claim that
any interval procedure is calibrated. The completed block-length pilot is described
in [remaining-audit.md](remaining-audit.md). Its data may guide development but must
not become confirmatory results after settings are selected.

Execution update: the [calibration runner and cost profile](calibration-runner.md)
now implement this development grid with shared inputs, per-fit checkpoints,
failure-transparent summaries and a Windows/Python dependency lock. A two-record
profile across all 36 cells projects about 13 hours of interval fitting in a single
process. The full development and confirmation screens have not been launched;
independently justified interval alternatives remain to be added before the larger
interval workload is committed.

## Scientific targets and inputs

- Primary synthetic target: the stationary-increment scaling/memory parameter.
  fGn uses H; stationary Gaussian ARFIMA(0,d,0) uses d with H = d + 0.5 only under
  that declared model. Use covariance-based sampling for ARFIMA confirmation.
- Fit geometric methods to integrated increments using the explicit adapter.
  Temporal profile methods receive increments. WaveletOLS uses the fGn detail
  variance convention. Record complete scale/frequency settings and input hashes.
- Use short-memory AR(1) controls separately from persistent fGn/ARFIMA. A
  short-memory finite-scale slope above 0.5 is not itself evidence of LRD.
- Retain a correctly implemented method even when it is biased. Interval
  eligibility is a separate decision from point-estimation eligibility.
- Keep empirical EEG inference outside these synthetic coverage calculations.
  Physical scales, preprocessing and the actual analysed signal must be specified
  before making neural LRTC claims.

## Development grid and precision

The next development grid should vary record length (512, 1024, 2048), fGn H
(0.2, 0.35, 0.5, 0.65, 0.8), exact ARFIMA d (-0.3, 0, 0.3), and AR(1) coefficient
(-0.5, 0.5, 0.8, 0.95). This gives 36 process/length cells. White noise is already
represented by fGn H = 0.5 and ARFIMA d = 0; these are generator cross-checks, not
independent types of null evidence. Do not use n = 256 for configurations with too
few usable wavelet levels; declare configuration eligibility by n before fitting.

Begin with 256 independent records per cell and 399 draws for the candidate
within-record procedures. Near coverage 0.95, 256 independent trials give a Monte
Carlo standard error about 1.36 percentage points; an approximate 95% half-width
is 2.67 points. That is a screening stage, not evidence for a one-point tolerance.
Record Wilson intervals and exact denominators. Compare widths, point bias,
interval availability and optimizer/range diagnostics alongside coverage.

For confirmation, 2,000 independent trials per retained cell give approximately
0.49 percentage-point standard error at coverage 0.95 (95% half-width about 0.96
points). At coverage 0.5 the half-width is about 2.19 points. These are binomial
planning calculations, not guaranteed interval widths. Confirm repetitions against
the declared tolerance and expected missingness before freezing the run. Increasing
bootstrap draws never replaces independent records. Use 1,999 draws initially for
retained resampling intervals and check tail-quantile stability independently.

## Candidate intervals and acceptance

The current circular block percentile interval is a candidate, not the default
scientific answer. Compare block lengths that scale with n and independently
justified method-specific or model-conditional alternatives. A parametric interval
must name the fitted model and be evaluated under model misspecification. Do not
transfer an fGn calibration claim to ARMA contamination or empirical EEG.

Before confirmation, fix one setting rule per retained configuration using only the
development stage. Do not choose block length using the unknown true H of a test
record. Do not select a different method for each cell based on its test error.
Declare any data-adaptive rule and repeat its entire fitting/selection operation
inside resampling. Keep tuning and confirmation seeds and records separate.

A practical prospective acceptance rule is simultaneous scrutiny of coverage,
availability and width across the declared model domain, with a specified tolerance
around nominal coverage. The tolerance and multiplicity rule still require a
scientific decision; they are not chosen from the pilot's favourable cells. Methods
whose intervals fail remain point-estimation comparators with uncertainty labelled
unvalidated. Global averaging must not hide undercoverage in a particular regime.

Keep LRD hypothesis testing separate. A lower endpoint of a central 95% interval
exceeding H = 0.5 corresponds to a 2.5% one-sided tail under exact calibration,
not a 5% one-sided test. A 5% test needs a declared one-sided rule and calibration
against its full null population. Point exceedance at H = 0.6 remains a diagnostic.

## Reproducibility and workload

Create and freeze a shared input pool keyed by process, length and repetition,
independent of method names, report settings and execution order. The present
development script already stores such records and hashes. New stress conditions
must derive from these immutable clean parents. Pair method and clean/stressed
comparisons on the same parents, preserving that pairing when resampling summaries.
Repeated windows, channels and subjects require their actual clustering hierarchy.
The current scalar summary bootstrap is insufficient for paired MAE ratios.

At 36 cells, 256 records and 19 configurations, the point screen contains 175,104
fits on 9,216 independent inputs. If three methods each retain three block settings,
the CI screen adds 82,944 fits and 33,094,656 bootstrap attempts at 399 draws.
These counts justify profiling and batching before launching the full screen.
Confirmation at 2,000 records/cell means 72,000 independent inputs and 1,368,000
point fits; its interval workload depends on the procedures retained. Do not start
that workload until methods, precision, environment and compute needs are frozen.

Store a reproducible dependency lock, interpreter, source revision, generator
parameters, actual scale bands, all failure counts, raw outputs and derived-table
hashes. Verify repeated small ground-truth/stress/observational workflows first.
The paper's figures and tables are regenerated only from the eventual frozen
confirmatory exports.
