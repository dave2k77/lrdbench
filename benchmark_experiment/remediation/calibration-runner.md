# Calibration execution and cost profile

This package turns the [prospective calibration design](calibration-design.md)
into a resumable development runner. It establishes execution and accounting,
not scientific acceptance of any confidence interval. The earlier Higuchi/GHE
undercoverage finding remains unresolved.

## Implemented design

[calibration-screen.json](calibration-screen.json) declares 36 cells: lengths
512, 1024 and 2048 crossed with five fGn H values, three stationary ARFIMA d values,
and four short-memory AR(1) coefficients. The full development screen has 256
independent records per cell, 19 point configurations, and three circular-block
interval candidates at three block lengths. Its exact workload is:

| Quantity | Full development screen | Cost profile |
| --- | ---: | ---: |
| Independent records per cell | 256 | 2 |
| Independent input records | 9,216 | 72 |
| Point fits | 175,104 | 1,368 |
| Interval fits | 82,944 | 648 |
| Within-record draws per interval fit | 399 | 399 |
| Total within-record draws | 33,094,656 | 258,552 |

The interval block rules are `floor(n/32)`, `floor(n/16)` and `floor(n/8)`.
They reproduce lengths 16, 32 and 64 at n=512 and scale with n without consulting
the unknown H. The current GPH bandwidth m=32 and geometric maximum lag/scale=32
remain fixed candidate settings, explicitly saved in every fit. GHE uses q=1;
both geometric candidates receive increments through the audited path adapter.
The 19 point configurations come from the eligibility roster with bootstrap
disabled and the explicit geometric conventions. This does not freeze a final
scale-selection rule or expand the scientific domain of those configurations.

## Input and checkpoint guarantees

- A record's random stream depends only on the seed namespace, global seed,
  process parameters, length, repetition and stream purpose. Method names,
  estimator settings, iteration order and total repetitions do not enter input
  identity. Input generation and within-record resampling use distinct streams;
  estimator-specific resampling offsets remain part of the underlying methods.
- fGn and ARFIMA use their stationary covariance matrices with Cholesky sampling
  and zero added diagonal jitter. ARFIMA has innovation SD=1. fGn has marginal
  SD=1. AR(1) starts in its stationary distribution with marginal SD=1 and uses
  the exact recursion, without burn-in or a truncated memory filter.
- Each clean record is stored with its input hash and seeds. Arrays are read-only
  when loaded; each estimator receives its own protected copy. The pool is ready
  to supply clean parents to a future stress runner. Stress transformations and
  paired summary resampling are not implemented in this package.
- Each fit, including a failed fit, is committed to a local SQLite checkpoint.
  An operating-system lock prevents concurrent writers to the same directory and
  releases if the process dies. A completed run resumes without refitting.
- Resuming requires the same expanded configuration, source hashes, interpreter,
  package versions, numerical build information and recorded thread settings.
  Input and result hashes are verified. A mismatch stops the run rather than
  combining different implementations or silently replacing earlier results.
- Raw output exports are streamed one process/length cell at a time. The run keeps
  full parameters, estimator version, warnings, failure reasons, point and interval
  values, diagnostics, elapsed fit time, input hash and target interpretation.

These are dedicated research exports (`run.json`, `estimates.jsonl`, `summary.csv`,
`input_index.csv`, `timing.csv`, `progress.json`), outside the package's public
`CsvResultStore` contract. Historical output bundles and public CSV columns are
unchanged. The SQLite file is the checkpoint authority; derived exports can be
rebuilt by rerunning the same command after interruption. Use one local writer;
cross-machine concurrent editing or synchronisation of an active database is not
a supported execution mode.

## Statistical accounting

Every stratum retains attempted fits, invalid points and missing intervals.
Conditional coverage uses available, finite, ordered, explicitly labelled 95%
intervals attached to valid finite points. Its denominator and Wilson interval
are exported alongside interval availability and covered/attempted counts. Missing
intervals therefore cannot disappear behind a favourable conditional rate.
Bootstrap attempted/retained/invalid/failed counts are separate; a failed fit with
no counters is recorded as missing bootstrap accounting, not zero attempted work.

The AR(1) H=0.5 target describes asymptotic short memory. Error against that target
is a finite-scale estimator diagnostic, not proof that every finite-scale slope
should be exactly 0.5. The H>=0.6 point count is labelled an exceedance diagnostic,
not a calibrated hypothesis test. Out-of-range finite point estimates remain in
bias, MAE and RMSE calculations.

The two-record cost profile cannot estimate coverage reliably. Its raw outputs
are retained for traceability; they must not be used to select interval settings
or claim that previous undercoverage has improved.

## Measured cost and recovery

The completed profile contains all 2,016 requested fits. All 1,368 point fits are
valid; all 648 interval fits produce intervals. All 258,552 within-record draws
are accounted for and retained. These are execution checks, not calibration claims.
Every method uses the same 72 input records, and all input hashes were verified.
The first 100 fit payloads are unchanged after stopping and resuming. A subsequent
resume performs zero new fits. All 20 historical baseline files still match their
frozen hashes.

Projecting each process/length/method/block cell's mean time from two records to
256 records gives the following approximate single-process fit costs:

| Fit group | Projected hours |
| --- | ---: |
| All 19 point configurations | 0.18 (about 11 minutes) |
| GPH intervals, three block rules | 0.93 |
| GHE intervals, three block rules | 1.43 |
| Higuchi intervals, three block rules | 10.67 |
| All interval candidates | 13.02 |

Higuchi accounts for about 82% of the interval workload. These estimates exclude
checkpoint/export I/O, generation and future resource contention. Covariance
factor construction plus generation took 1.88 seconds for this small input pool;
generation is not extrapolated as if Cholesky were repeated for every record.
Brief local dependency installation occurred during profiling. Two timings per
setting do not provide a reliable timing uncertainty interval, and a parallel
speed-up has not been measured.

The [compact profile](calibration-profile/verification.json) links these counts,
timings and source/environment provenance. [Timing rows](calibration-profile/timing.csv)
retain every cell rather than only a pooled runtime. Full input arrays, raw fit
rows and the checkpoint database remain in the separate local verification folder.
Two-record coverage summaries are intentionally not promoted into the compact
research report.

## Rebuilt dependency environment

The [dependency lock](environment-py314-win64.lock) pins package versions and
distribution hashes for Windows x64 with Python 3.14.5. Its
[input pins](environment-py314-win64.in) include the runtime, test and documentation
packages from the profile environment plus the build backend and editable-install
requirements. Resolving and installing the lock succeeded offline from the local
cache. A separate environment was created from the lock, and this checkout was
installed without dependency resolution or build isolation. This revealed the
need to include `editables` as well as `hatchling`; both are now pinned.

Reproduce with uv (the verification used uv 0.11.28):

```console
uv venv .venv-calibration --python 3.14.5
uv pip sync --python .venv-calibration/Scripts/python.exe --require-hashes benchmark_experiment/remediation/environment-py314-win64.lock
uv pip install --python .venv-calibration/Scripts/python.exe --no-deps --no-build-isolation -e .
```

The interpreter version is recorded separately; Python itself and the operating
system are not installed by the package lock. Use `--offline` when the required
distributions are already cached. This is a verified local development environment,
not evidence of compatibility with every supported Python version or operating
system. Keep the source revision/hashes with the lock: dependencies alone cannot
identify the repaired estimator code. The final confirmation environment still
needs freezing after the interval procedures and any performance changes are chosen.

## Verification

- In the rebuilt environment, all unit tests, statistical tests and the targeted
  stress integration module passed: **345 passed, 8 optional-dependency skips**.
  This includes 26 new runner tests covering input/order/prefix independence,
  independent covariance checks, resume recovery, single-writer locking, corrupt
  inputs/checkpoints, changed sources/environment, failed jobs and interval
  denominators. No full integration-suite pass is claimed.
- Ground-truth (4 records / 12 fits), stress (20 / 60) and observational-fixture
  (1 / 3) workflows were each run twice in the rebuilt environment. Records,
  estimates, intervals, diagnostics and scientific leaderboards matched exactly;
  all exported bundles passed the public output contract. The observational
  fixture remains a software check, not empirical EEG validation.
- Ruff and formatting checks passed. Type checking passed for all 57 package
  source files with the Python 3.14 target. The strict documentation build passed.
  No new Python 3.11 environment was tested.
- All original profile package versions are preserved in the rebuilt environment;
  the only added packages are locked build dependencies. The profile's estimator
  and runner source hashes still match the final working files.

## Execution

Run from the repository with the documented environment. Preview counts first:

```console
python benchmark_experiment/remediation/run_calibration.py --dry-run
python benchmark_experiment/remediation/run_calibration.py --dry-run --profile-repetitions 2
```

Use a new output directory for the cost profile. This bounded stop demonstrates
checkpointing; repeating the second command completes the same run:

```console
python benchmark_experiment/remediation/run_calibration.py --output reports/calibration-cost --profile-repetitions 2 --max-new-fits 100
python benchmark_experiment/remediation/run_calibration.py --output reports/calibration-cost --profile-repetitions 2
```

Changing scientific settings, code or environment requires a new output directory.
Omit `--profile-repetitions` only when intentionally launching the full development
screen. The script rejects `stage=confirmation`: the confirmatory protocol,
acceptance tolerance, multiplicity rule and retained intervals are still pending.

## Remaining scientific work

The runner currently evaluates the circular-block candidates. Before committing
the larger interval workload, add independently justified method-specific or
model-conditional alternatives and test their implementations. Use an economical
development comparison to select a prospective rule, then evaluate fresh records
after the rule and acceptance criteria are fixed. A method can remain a point
comparator while its intervals remain unvalidated.

Shared-parent stress generation, paired/clustered summary resampling, confirmation
runs and manuscript regeneration remain separate gates. No full development or
confirmatory experiment has been launched by this cost profile.
