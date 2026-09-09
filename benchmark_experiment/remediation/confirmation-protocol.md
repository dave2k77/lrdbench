# Classical benchmark: frozen scientific protocol v1

The eighth work package fixes the scientific design for the replacement synthetic
benchmark. The [machine-readable protocol](confirmation-protocol-v1.json) expands
into [33 process/length cells](protocol-v1/cells.csv),
[63 method/length settings](protocol-v1/method_settings.csv) and
[23 contamination conditions](protocol-v1/conditions.csv). Its
[scientific design lock](protocol-v1/scientific_design_lock.json) has SHA-256
`b5b9399d284e3fae8135050aeac5c8bc0a02ab36b4f0a6d15041f55a497681bb`.

**No confirmation signals have been generated.** A separate rehearsal verifies
the calculations, numerical precision, runtime and storage. The scientific
design is frozen; release of the checkpointed confirmation executor, its final
source/environment lock and a final capacity check remain required before launch.
The development runners continue to reject a confirmation stage.

This is a local prospective protocol, not a claim of external preregistration.
An amendment needs a new protocol version and a recorded reason before viewing
new confirmation results. Methods may perform poorly without preventing study
completion. The study evaluates their performance; it is not required to find a
universally calibrated interval or a winning estimator.

## Questions and claim boundaries

The study asks how classical configurations estimate a declared clean memory
target, how specified contaminations change that recovery error, and how a
limited set of interval constructions behaves on clean model and mismatch data.
It analyses scalar stationary increments with scales in samples. No physical
sampling rate, EEG envelope or clinical target is implied.

Clean targets are fGn H, ARFIMA(0,d,0) d+0.5, and the AR(1) asymptotic
short-memory reference 0.5. Under contamination, the same number is a **latent
clean recovery target**, not an asserted H of the contaminated process. fGn
H=0.25 is an antipersistent control; white noise at fGn H=0.5 and ARFIMA d=0
provides a generator comparison, not two independent kinds of null evidence.

The final paper must remove unsupported claims of empirical EEG validation,
calibrated 5% LRD testing, universal interval calibration, and coverage robustness
under contamination. H>=0.6 remains an explicitly named point-exceedance
diagnostic. A calibrated discrimination study or real EEG study would be a
separate declared extension. Oscillatory, combined-artifact and infinite-variance
noise robustness are also outside this protocol.

## Fixed populations and counts

| Component | Cells and repetitions | Relationship to main parents |
|---|---|---|
| Clean accuracy | n=512, 1024, 2048; fGn H=0.25, 0.5, 0.75, 0.85; ARFIMA d=-0.25, 0, 0.25; AR(1) phi=-0.5, 0.5, 0.8, 0.95. 33 cells, 2,000 records each. | 66,000 independent clean parents. |
| Point stress | n=512, 1024; all four fGn H values; ARFIMA d=0.25; AR(1) phi=0.8, 0.95. 14 cells, 500 parents each. | First 500 repetition indices in those main cells: 7,000 existing parents. |
| Core intervals | n=512; all four fGn H values; ARFIMA d=0.25; AR(1) phi=0.8, 0.95. Seven cells, 2,000 records each. | 14,000 existing main parents. |
| Interval length sensitivity | n=1024; fGn H=0.5, 0.85; AR(1) phi=0.95. Three cells, 500 records each. | Another 1,500 existing main parents. |

These deterministic subset selections depend on repetition index, never on an
estimate or its accuracy. Descendants, interval subsets, methods and bootstrap
draws do not increase the independent sample size beyond 66,000.

There are 19 classical configurations representing 12 base algorithms, plus
sample-centered Higuchi and GHE pipelines: 21 point pipelines in total.
The expanded workload is:

| Work item | Planned count |
|---|---:|
| Clean point fits | 1,386,000 |
| Contaminated descendants | 161,000 |
| Stressed point fits | 3,381,000 |
| Total point fits | 4,767,000 |
| Interval-study model fits | 15,500 |
| Interval-study point-statistic evaluations | 93,000 |
| Interval comparison rows | 248,000 |
| Physical within-record bootstrap records | 61,969,000 |
| Bootstrap statistic evaluations | 278,860,500 |

The 93,000 point-statistic evaluations inside the interval kernel are separately
accounted for; they are not silently included in the 4,767,000 public-estimator
point fits. Summary resampling uses 1,999 joint parent draws per declared domain.

## Estimator, generator and contamination definitions

The audited classical point settings are retained. Geometric estimators integrate
increments with an initial zero; the additional centered pipelines first remove
each record's arithmetic mean. GHE uses q=1, 18 geometric lag scales and maximum
lag floor((n+1)/8); Higuchi uses k_max=32. The interval kernel now uses these
same settings. Earlier GHE interval development used 16 scales and h_max=32;
those results are not relabelled as results for the new frozen settings.

The compiler makes public defaults explicit where possible, including the RS
scale limit n/2 and disabled Anis-Lloyd correction, aggregation scale ratios,
GHE lag limits, retained wavelet levels and actual spectral frequency endpoints.
All 21 resolved point pipelines reproduce their pre-expansion point estimates
in tests at all three lengths. The conservative db4 band remains eligible at
these lengths. Public package source and default intervals are unchanged.

Temporal scale/window settings, spectral m=32 or 64 and wavelet drop rules are
fixed as declared. Their relative frequency bands and retained levels can change
with n. This is not a comparison at matched physical or relative-frequency scales.
No parameter is tuned using the true target of a confirmation record.

Clean fGn and ARFIMA use their audited exact covariance and Cholesky sampling,
without diagonal jitter. AR(1) uses exact stationary initialization and recursion.
fGn and AR(1) have marginal SD 1; ARFIMA uses innovation SD 1. Every descendant
is applied separately to its clean parent and inherits its provenance and target.

| Operator | Frozen grid | Conditions |
|---|---|---:|
| Constant offset control | +1 clean sample SD, retaining the legacy epsilon convention | 1 |
| Internal step | Shifts 0.5, 1, 2 clean sample SDs; positions 0.25, 0.5, 0.75 | 9 |
| Additive outliers | Rates 0.005, 0.01, 0.05; signed amplitude 8 clean sample SDs | 3 |
| Polynomial trend | Orders 1, 2; strengths 0.25, 0.5, 1 | 6 |
| Student-t-shaped noise | df=3, 5; scales 0.5, 1 | 4 |

The exact equations and operator versions are preserved in the expanded
condition table and [seventh-package audit](shared-stress.md). Order 2 means
t+t² after centering, not a pure quadratic. Noise is divided by its realized
sample SD plus 1e-12, without subtracting its mean; it is not independent
population-standardized t innovation noise. The shared normalization couples
the scaled noise samples. All 23 expanded conditions passed independent equation
replay on the rehearsal's 644 descendants, including the new positions/severities.

## Interval study and precision

The interval study is limited to clean GPH narrow-band, Higuchi and GHE points.
It retains five bootstrap constructions per method: circular-block percentile
and basic intervals on raw increments, the same two constructions after sample
centering, and an unknown-constant-mean fitted-fGn basic interval on the centered
statistic. GPH additionally has its untapered normal approximation. Thus each
record produces 16 interval comparisons.

The block length is floor(n/16). A shared pool contains 1,999 circular-block
records and another contains 1,999 fitted-fGn records. Methods share their pool;
raw and centered block statistics use the same draws. Sample means are removed
separately from each bootstrap record. The fGn model profiles H, variance and
the GLS mean by ordinary maximum likelihood, not REML. Its basic interval centers
the bootstrap statistic at the fitted model H, rather than at the benchmark truth.
Optimization boundary hits remain reported results. No endpoint or point estimate
is clipped to (0,1).

Every requested statistic draw must be finite for its bootstrap interval to be
available. Invalid and failed draws remain aligned and counted; none disappear
before availability is assessed. Model failure leaves the block and normal
comparators available when their own calculations succeed.

The core uses R=2,000: at coverage 0.95, sqrt(p(1-p)/R)=0.004873, about **0.49
percentage points** of Monte Carlo SE. At p=0.5 the SE is 1.12 points. R=500 in
the length sensitivity gives 0.97 points at p=0.95 and 2.24 points at p=0.5.
These are planning values, not guaranteed interval widths. This separation of
independent repetitions from within-record bootstrap draws follows the simulation
precision calculation in [Morris, White and Crowther (2019), section 5.3](https://discovery.ucl.ac.uk/10066118/1/2019%20-%20Morris%20-%20simulation%20studies%20tutorial%20-%20stat%20med.pdf).

The [precision table](protocol-v1/precision.csv) includes approximate normal
half-widths for planning. Observed cell proportions will use 95% Wilson intervals,
including zero/all-event cells; the implementation is documented in
[SciPy's binomial proportion interval interface](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html).
For unbounded continuous errors, no uniform SE guarantee is claimed: report the
achieved per-cell Monte Carlo SE. Repetition counts are fixed; an unexpectedly
large error or wide interval does not trigger an outcome-dependent early stop,
extension or omission. There is no binary universal-calibration acceptance rule.

## Endpoints, pairing and interpretation

Clean MAE and bias are primary accuracy summaries; RMSE, validity, out-of-range
values, timing and the named exceedance diagnostic are secondary. Stress error
inflation B-A and absolute estimate drift are primary; signed drift, ratio B/A
and validity loss are secondary. B/A is a ratio of aggregate MAEs, recomputed
inside each parent resample, not an average of individual ratios.

For conditional point-error/drift comparisons, retain common complete parents
over the declared methods and conditions within each cell. Export every missing
pair and excluded parent. Keep fGn, ARFIMA and AR(1) domains separate, with fixed
equal cell weights inside each domain; report every contamination condition
separately. These conditional summaries do not make failures ignorable.

Interval **unconditional coverage** uses all attempted parents, counting an
unavailable interval as a miss. It is not subject to the common-complete error
filter. Also report availability, conditional coverage, mean/median width and
boundary hits. Paired coverage differences use those same attempted parents;
paired width comparisons require explicitly reported common available intervals.

The declared contrasts isolate geometric mean removal in clean error and stress
response; interval centering at a fixed block construction; basic versus
percentile at a fixed mean treatment; and fitted-fGn versus block basic with the
centered statistic. All methods, descendants and contrasted endpoints travel
together in within-cell parent resampling. The intervals are descriptive and
pointwise, with no significance claims, global winner or unadjusted multiple-test
claims. The complete cell results must remain available alongside aggregates.

## Rehearsal, numerical checks and feasibility

The rehearsal uses 66 separately seeded development parents, two per main cell.
It completed 1,386 clean and 13,524 stressed point fits, all valid, and verified
644 descendants. Twelve parents spanning fGn H=0.25/0.85 and AR(1) phi=0.95 at
n=512/1024 support the numerical interval check. Two resampling streams produced
647,784 statistic evaluations and 576 interval rows, all available. The model
hit a boundary on four distinct AR parents, with eight hits across the two
repeated model fits; this is retained mismatch evidence, not silently discarded.
The rehearsal is too small to establish coverage and is not used to estimate it.

For each bootstrap interval, the check compares 1,999 draws with their 3,999-draw
refinement, and with an independent 1,999-draw repeat. The numerical criteria were
specified before inspection: 90th-percentile endpoint change <=0.01 for refinement,
<=0.02 for repetition, and no change >0.05 H units. The observed values are
0.00590, 0.01582 and 0.02958, respectively. All criteria pass. The largest
refinement change alone is 0.01230. This supports the chosen draw budget for
this rehearsal; it is not a uniform quantile-error guarantee or coverage proof.

The first scalar rehearsal projected 22.0 compute hours, before allowances.
[Batched statistics](confirmation_batch.py) reduce repeated Python work while
preserving the equations. Tests include constant/invalid rows, extreme scales,
steps, trends, offsets and several batch sizes. Against all 647,784 actual scalar
rehearsal statistics, the maximum difference is **4.11e-15**; all 1,152 interval
endpoints also agree to numerical precision. No public estimator was replaced.

The new projected fit cost is 1.29 hours clean, 2.36 hours stressed, and 3.70 hours
for intervals: **7.35 hours total**, or **14.70 hours with a twofold planning
allowance**. This fits the provisional 24-hour local budget. It is a small-sample
cost projection, excluding full-scale I/O, final summaries and independent audit;
it is not a promised finishing time or a reason to truncate a run at 24 hours.

Lossless compressed CSV and binary-array round trips were verified for all 14,910
rehearsal point rows and 647,784 stored statistics. They project about **3.65 GiB**
for primary inputs/point/draw artifacts. A twofold allowance plus 10 GiB of free
disk reserve requires about 17.3 GiB; about 44.4 GiB was free at the check.
Runtime checks must include summaries, temporary files and any duplication.
Raw bootstrap signal arrays are generated in bounded batches and reconstructed
from stored seeds; retaining every one would be a very different storage budget.

Verification totals **465 passing tests and eight skips**, including 30 new
protocol/interval/batch tests and 435 regression checks. A no-op rehearsal resume
rewrote no checkpoints. All 20 historical baseline hashes remain unchanged.
The [verification record](protocol-v1/verification.json) contains exact source
snapshots, raw-file hashes and the scalar/batched comparison. Repeating the same
rehearsal after optimization adds no independent parents.

## Execution release and paper rebuilding

The new [compiler](compile_confirmation_protocol.py) expands and locks the
scientific design without generating confirmation inputs. It reserves 66,000
clean seeds and 132,000 interval stream seeds, checks collisions with the rehearsal
namespace, and refuses a changed or corrupted existing lock. Distinct pseudorandom
seeds are bookkeeping, not a mathematical proof of independence. Every downstream
join must include the source/run identity and parent ID; matching an unqualified
record name across different runs is insufficient.

Before launching, the next package must provide a confirmation executor that
consumes this lock, stores inputs and results in bounded chunks, checkpoints
atomically, and verifies a resumed representative run. It must implement the
declared paired drift/mean-removal contrasts and interval coverage denominators,
bind the exact source bytes and pinned environment, and recheck disk capacity.
The existing Python 3.14 Windows dependency lock remains the execution baseline;
no new dependency was installed for this package. Large working outputs should
use the available local directory outside OneDrive, with compact evidence copied
into the repository. This is execution engineering, not an opportunity to retune
the scientific grid against new outcomes.

Only after that release should the fresh run begin. Rebuild the paper's tables,
figures, counts and claims from the resulting canonical exports. The original
PDFs and historical result bundles remain untouched.

```console
python benchmark_experiment/remediation/compile_confirmation_protocol.py
python benchmark_experiment/remediation/profile_confirmation.py --dry-run
python benchmark_experiment/remediation/profile_confirmation.py --output ../confirmation-rehearsal-batched-v1
python benchmark_experiment/remediation/verify_confirmation_design.py --scalar ../confirmation-rehearsal-v1 --output ../confirmation-rehearsal-batched-v1 --archive benchmark_experiment/remediation/protocol-v1
```

The comparison verifier requires the preserved scalar rehearsal, its exact source
ZIP, and the focused/regression JUnit files. The compact repository archive is
not the full raw rehearsal bundle. Use its source hashes and snapshots when
reproducing the historical comparison; ordinary Git checkout normalization can
change inherited CRLF source bytes even when Python behaviour is unchanged.

Subsequent execution release: [package nine](confirmation-execution.md) now supplies and validates the executor, declared analyses, recovery and runtime lock described above. The scientific design hash is unchanged.
