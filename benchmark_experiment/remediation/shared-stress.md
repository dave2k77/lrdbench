# Verified shared-parent stress development screen

## Design specified before execution

This seventh package connects verified contamination descendants to the joint
parent-summary helper. It is a development experiment for framework integrity
and point-estimator behaviour, not the final benchmark or an interval calibration
study. The public package and its CSV contract are unchanged.

The fixed [configuration](shared-stress.json) imports the 448 existing n=512
records from the mean-comparison development pool: 64 independent parents in
each of fGn H=0.25, 0.5, 0.75, 0.85; ARFIMA(0,0.25,0); and stationary AR(1)
phi=0.8, 0.95. The source run's identity is pinned in the configuration. No clean
signal is regenerated and no contamination is chained onto another contamination.
These already studied parents cannot become independent confirmation data.

Every descendant retains the **latent clean recovery target**: H for fGn, d+0.5
for ARFIMA, and the asymptotic short-memory reference 0.5 for AR(1). We do not
assert that a trend, a step, or another contaminated record has that H. Estimators
receive the signal without benchmark truth. They receive no physical sampling
rate; all scales in this screen are in samples.

The roster contains the 19 audited classical configurations and two additional
pipelines that sample-center the increments before Higuchi or GHE. Every other
parameter matches the corresponding raw pipeline. All within-record bootstrap
intervals are explicitly disabled. n=512 avoids the known n=256 ineligibility
of the conservative db4 wavelet band. GHE retains the classical roster's 18 lag
scales and its default maximum lag of integrated-path length divided by eight
(64 here), with q=1. This differs from the previous interval screen's GHE lag
settings; cross-screen point changes must not be attributed solely to stress.

Let s=std(x,ddof=0), epsilon=1e-12, and t be n equally spaced points from -1
to 1. The seven separately applied conditions are:

| Condition | Exact construction |
|---|---|
| Constant offset | Add s+epsilon to the whole record. This is a translation control. |
| Midpoint step | Add s from zero-based sample floor(n/2) onward; the first half is unchanged. |
| Additive outliers | Select max(1,round(0.01n)) distinct indices (5 at n=512); add independent random signs times 8(s+epsilon). Values are not replaced. |
| Linear trend | u=t-mean(t); add 0.5(s+epsilon)u/(std(u)+epsilon). |
| Linear plus quadratic | u=t+t²-mean(t+t²); add 0.5(s+epsilon)u/(std(u)+epsilon). This is not a pure quadratic. |
| t3 noise, realized-SD scaling | Draw z from Student-t with df=3; add 0.5(s+epsilon)z/(std(z)+epsilon). |
| t5 noise, realized-SD scaling | Same construction with df=5. |

The last two definitions describe the existing operator exactly. Its noise is
not centered, and its denominator is the realized sample SD rather than a
population-variance normalization. That shared denominator couples the scaled
noise samples; the resulting perturbations must not be described as independent
Student-t innovations. All amplitudes are also relative to the realized clean
record SD. This screen does not establish robustness to infinite-variance noise,
oscillations, varying step positions, multiple severities, or combined artifacts.

The intended workload is 448 clean records plus 3,136 descendants, each fitted
by 21 pipelines: **75,264 point fits**. The independent sample size remains 448,
with 64 parents in each fixed process cell. Descendants and methods are repeated
measurements on their parent, not extra independent observations.

## Integrity and recovery

[materialize_shared_stress.py](materialize_shared_stress.py) verifies every
upstream input ID, signal hash, and seed using the upstream design. Child IDs
and random streams depend on the clean ID/hash, operator name/version/parameters,
and contamination seed namespace. Display labels, condition order, estimator
settings and summary settings do not enter those child identities. Each cell is
stored in a compressed array bundle with complete transformation provenance.

Independent equation replay checks every stored child, including on resume.
The Student-t replay calls NumPy's direct sampler, separately from the production
operator's SciPy sampler. Hash checks alone are insufficient: changing a stored
value and updating its hash still fails equation replay. Both parent preservation
and the clean-to-child provenance chain are checked. Scientific provenance omits
wall-clock creation times; execution time is recorded with the fits.

[run_shared_stress.py](run_shared_stress.py) checkpoints the entire set of fits
for one parent as a transaction. A process interruption can require recomputing
an unfinished parent but cannot count a partially saved parent as complete.
Checkpoints have content hashes; resume refuses changes to the design, source
code, estimator roster, environment or upstream input files. Every estimator
failure remains an explicit result row. A fit receives its own read-only copy;
centering cannot change stored raw inputs.

## Planned summaries

The primary descriptive endpoint is the change in aggregate absolute error,
B-A, supplemented by the ratio B/A, against the same latent clean target.
fGn, ARFIMA and AR(1) domains are kept separate, with equal fixed cell weights
within each domain. Every condition is reported separately; no operator-pooled
score or winning-method ranking is defined.

The [paired-summary helper](paired-summary.md) retains common complete parents
across all 21 declared pipelines and seven conditions within each cell. Missing
pairs and excluded parents remain in the accounting. It jointly resamples each
retained parent's full vector within its cell, holds cell weights fixed and
recomputes B-A and B/A in each draw. The predeclared summary seed is 20260914,
with 999 draws, percentile 95% intervals and a 1e-12 clean-MAE denominator floor.
Those intervals quantify uncertainty in benchmark performance across parents;
they are not within-record confidence intervals for H, nor simultaneous intervals
for the many descriptive comparisons.

Per-cell tables additionally show bias, MAE, RMSE, bias Monte Carlo standard
error, validity, out-of-(0,1) values, and signed/absolute estimate drift. These
per-cell summaries retain each method's own available support, labelled separately
from the joint summary's common support. Drift is descriptive here; pooled drift
uncertainty, coverage changes and severity-response curves remain future work.

## Reproduction

Use the established locked environment and the preserved complete local
mean-comparison bundle. Dry-run verifies the source pool and prints the workload:

```console
python benchmark_experiment/remediation/run_shared_stress.py --source ../mean-candidate-verification --dry-run
python benchmark_experiment/remediation/run_shared_stress.py --source ../mean-candidate-verification --output ../shared-stress-verified-v2 --max-new-parents 2
python benchmark_experiment/remediation/run_shared_stress.py --source ../mean-candidate-verification --output ../shared-stress-verified-v2 --summarize
```

Save the first two checkpoint checksums before the full run to verify recovery.
Calling the final command again performs input/equation verification, skips
completed parent fits and deterministically rebuilds the summaries. The full
array bundles, checkpoint database, raw fits and joint summary draws belong in
the local evidence bundle; compact indexes, summaries and source hashes belong
in the repository. The completed results and verification are recorded below.


## Completed development results

All 448 intended parents and 3,136 independently applied descendants completed
their 21 point fits: **75,264 valid point results**, no invalid fits, and no
within-record interval fits. All 64 parents per cell remain in common support;
none were dropped from the paired summaries. The export has 882 performance
summary rows, 1,029 parent-accounting rows and 881,118 joint summary-draw rows.
The larger draw-row count reflects methods, conditions and two metrics; it does
not increase the independent sample size. Timed estimator calls took 97.94 seconds
on this host, excluding materialization, checkpoint writes, export, plotting and
independent verification; this is not a production wall-time forecast.

Under the declared equal weights across the four fGn cells, the mean-removed
geometric pipelines have exact constant-offset invariance to numerical precision,
but substantial sensitivity to internal steps and trends. Selected entries below
illustrate the prespecified centering contrast and the narrow-band GPH comparator;
the complete roster and all seven conditions remain in the linked exports.

| Pipeline | Clean MAE | Offset: ΔMAE | Step: ΔMAE | Linear trend: ΔMAE | Outliers: ΔMAE |
|---|---:|---:|---:|---:|---:|
| Higuchi | 0.0436 | 0.3354 | 0.2520 | 0.2159 | 0.0441 |
| Higuchi / centered | 0.0528 | 0.0000 | 0.2345 | 0.2038 | 0.0461 |
| GHE | 0.0463 | 0.3342 | 0.2533 | 0.2136 | 0.0443 |
| GHE / centered | 0.0580 | 0.0000 | 0.2312 | 0.1994 | 0.0461 |
| GPH / narrow_band | 0.1052 | 0.0000 | 0.2164 | 0.3417 | 0.0351 |

For the midpoint step, the centered Higuchi inflation is 0.2345 H units
(percentile 95% summary interval [0.2280, 0.2414]); centered GHE inflation is
0.2312 ([0.2245, 0.2383]). The largest cell-mean absolute constant-offset drift
for the two centered pipelines is 8.33e-17 H units. Translation invariance does
not establish robustness to a change occurring within the record. Narrow-band
GPH is also invariant to the offset, while the linear trend increases its
aggregate MAE by 0.3417 H units ([0.3274, 0.3562]). These descriptive intervals
are not adjusted for the many reported comparisons.

Centering also changes clean accuracy. At fGn H=0.85, n=512, Higuchi's bias/MAE
change from -0.0128/0.0514 to -0.0757/0.0779; GHE changes from -0.0157/0.0568 to
-0.0860/0.0879. The stress improvements must therefore be read alongside each
pipeline's clean error, not used to recommend centering universally.

The AR(1) controls illustrate why a reduction in error under contamination is
not sufficient to establish a useful estimator. With equal weights over phi=0.8
and 0.95, raw Higuchi's clean MAE against the 0.5 reference is 0.3440. The t(5)
perturbation reduces that error by 0.0187, yet the resulting MAE remains 0.3253.
The negative inflation describes this particular difference; it does not repair
the clean short-memory bias or establish reliable LRD discrimination.

See the [full paired summaries](stress-pilot/paired_summary.csv),
[cell accuracy](stress-pilot/cell_summary.csv),
[cell drift](stress-pilot/cell_drift.csv),
[parent accounting](stress-pilot/parent_accounting.csv),
and figures for [fGn](stress-pilot/stress_fGn.png),
[ARFIMA](stress-pilot/stress_ARFIMA.png) and [AR(1)](stress-pilot/stress_AR1.png).
All three figures use the same colour scale and show one metric only. Their
rounded display values do not replace the full precision CSVs or their intervals.

## Verification and execution record

The final checks comprise **435 passing tests and eight skips**: 23 new stress
tests, plus 412 unit/statistical and relevant stress/failure-map regression tests.
They cover independent operator equations, unchanged parents, zero-rate outliers,
condition-label/order independence, malformed designs, corruption with an updated
hash, seed/provenance integrity, explicit failure retention, latent-truth exclusion
from estimator input, and resumed versus uninterrupted scientific results.
The global Ruff check and formatting checks for changed Python files pass.
No new public package behaviour or CSV columns were introduced by this package.

An initial completed run exposed nullable 64-bit seeds being rounded in the CSV
index. Exact seeds remained intact in its array-bundle provenance. The writer now
converts integer seeds to decimal strings before DataFrame type inference; a
regression check includes 2^64-1 and missing clean-record seeds. The corrected
source was rerun into a new bundle, and every exported seed was compared with
its exact provenance integer. The earlier local `shared-stress-verification`
bundle is retained as superseded; `shared-stress-verified-v2` is canonical.
All 448 scientific parent-result hashes match between the two executions.
This repeated computation supplies no additional independent simulation records.

[verify_shared_stress.py](verify_shared_stress.py) independently replays every
summary draw using a separate index-vector calculation and different batching.
It recomputes point summaries, fixed-weight ratios, percentile endpoints,
bootstrap standard errors, support counts, and per-cell accuracy/drift. It
verifies every source/input hash and operator equation, exact CSV seeds, retained
first-two-parent checksums, and a final no-op resume with zero new fits. All 20
historical baseline file hashes remain unchanged. These are reproducibility and
calculation checks, not an empirical proof of summary-interval coverage.

The compact [verification record](stress-pilot/verification.json) includes hashes
of the full local raw-fit and summary-draw files. Its source ZIP preserves the
exact executed working-file bytes, including inherited CRLF line endings. This
avoids relying on Git's normalized source bytes to reproduce a recorded hash.
The complete local evidence bundle retains the arrays, database and raw rows;
those larger files are not all included in the compact repository archive.

After the run and regression tests, generate and inspect the figures, then audit:

```console
python benchmark_experiment/remediation/plot_shared_stress.py --output ../shared-stress-verified-v2
python benchmark_experiment/remediation/verify_shared_stress.py --source ../mean-candidate-verification --output ../shared-stress-verified-v2 --archive benchmark_experiment/remediation/stress-pilot
```

The verifier expects `first-two-checksums.csv`, `focused-tests.xml` and
`regression-tests.xml` in the output directory. The compact archive includes those
audit inputs. For a new reproduction, save its first two checksums and pass JUnit
output paths to pytest for the focused and regression suites.

## Next protocol decisions

The paired point-stress path is now operational. The next work package should
freeze a feasible confirmatory protocol: estimator and mean/scale rules, the
severity and step-position grid, a clearly scoped interval sub-study, primary
contrasts, and independent-record precision. Coverage gains/losses and pooled
drift uncertainty must either be implemented for that declared scope or explicitly
excluded from its claims. Correctly implemented procedures may remain comparators
even when they perform poorly. Fresh confirmation seeds, hypothesis-test
calibration and regenerated paper tables/figures remain pending; these development
records and their repeated executions must not be repurposed as confirmation.


Subsequent update: the [eighth package](confirmation-protocol.md) now freezes
those scientific choices and verifies a full-grid execution rehearsal. Its
23-condition grid adds the declared severities and step positions, while
within-record interval inference is explicitly scoped to clean inputs. The
production confirmation executor and fresh-data run are the next release step.
