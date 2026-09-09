# Confirmation execution release

The ninth package completes the production executor, planned analyses and
runtime lock for the [frozen scientific protocol](confirmation-protocol.md).
The release is validated for the full fixed run. Its
[live job status](</C:/Users/davia/.codex/visualizations/2026/09/06/01a078d5-72f2-7d11-a191-191abff26904/confirmation-production-v1-job.json>)
records launch, interruption and completion separately from this immutable
development evidence. Rehearsal results are software validation, not confirmation
evidence or a reason to change the scientific design.

## What the executor now guarantees and records

[The executor](run_confirmation.py) consumes the compiled scientific lock and
compares the actual estimator settings, operator versions and workload with it.
Its release check binds the Python 3.14.5 environment, every pinned dependency
version, numerical-library build information, thread settings and exact source
bytes. The source ZIP preserves bytes that a Git checkout might normalize.
Changed sources/environment require a new validated release; they cannot silently
resume an existing run. This package changes research execution and exports only;
the public package source and public CSV contract are unchanged.

The complete design contains 2,079 chunks, each holding at most 32 clean parents.
Every chunk retains clean/contaminated signals, per-record provenance and seeds,
all point attempts, interval endpoints and model diagnostics, and nine aligned
within-record statistic streams. Gzip JSON Lines preserve nested diagnostics and
integer seeds without float conversion. NPZ arrays preserve the aligned floating
values, including NaNs. This final research archive format replaces the proposed
raw point CSV layout; canonical summaries remain CSV.

A chunk becomes committed only after all four payload files are flushed and
checksummed, followed by an atomic directory rename. On restart, a valid committed
chunk is checked and reused. An unfinished chunk is preserved in an abandoned
directory and recomputed. A corrupted committed chunk is rejected. An OS lock
prevents simultaneous writers. These are tested interruption/recovery semantics,
not a claim of immunity to arbitrary hardware or filesystem failure.

The runner applies each of the 23 conditions directly to its clean parent and
replays the operator equation. Production contamination uses the frozen
contamination namespace; interval pools use the reserved confirmation streams.
Every result carries its run identity and parent ID. Fixed stopping counts are
unchanged; an engineering interruption does not turn a partial run into a smaller
scientific study.

## Completed analyses

The [analysis implementation](confirmation_analysis.py) and
[exporter](summarize_confirmation.py) provide the declared cellwise error, drift,
validity, runtime and interval summaries, plus all five groups of planned
contrasts. They preserve these distinctions:

- Point-error and drift comparisons condition on parents complete across every
  declared method and condition in that cell. Exact excluded parent IDs, missing
  pairs, and failure reasons are retained. Accuracy uses the full clean sample;
  stress uses its declared parent subset, including the matching clean baseline.
- Coverage uses every attempted interval, with an unavailable interval counted
  as a miss. Conditional coverage, availability and widths are separate outputs.
  Zero/all-event cell proportions receive Wilson bounds; a zero plug-in standard
  error is not presented as zero uncertainty.
- Mean removal, interval centering, interval construction and fitted-fGn versus
  block-basic comparisons retain their declared pairing. Width differences use
  explicit common available support. All attempted parents are resampled jointly
  before conditioning on that support; resamples with no common available pair
  remain unavailable rather than disappearing.
- Each parent and all its methods/descendants travel together within a summary
  resample. Counts of sampled parents and a bounded matrix multiplication replace
  large gathered arrays, without changing the resampling distribution. Every
  requested summary draw stays aligned; incomplete draw vectors do not yield a
  silently filtered interval.
- Domain summaries use fixed equal cell weights separately for fGn, ARFIMA and
  AR(1). Interval core and length sensitivity remain separate. MAE ratios are
  rebuilt from weighted MAEs inside each resample; RMSE is rebuilt from weighted
  MSE. Empty cells are not dropped or reweighted. Width medians are cellwise
  descriptive statistics, not averages of cell medians passed off as pooled
  medians. No global score or winner claim is produced.

The exporter requires every declared chunk before scientific summaries are
available. It holds one cell at a time, then combines its saved draws by domain.
A completed summary manifest checksums all tables, support ledgers and draw
arrays; a no-op resume leaves them unchanged. Cell and domain summary rows are
outputs, not additional independent observations.

## Validation evidence

The [independent audit](execution-v1/verification.json) records:

| Check | Verified result |
| --- | ---: |
| Representative rehearsal cells / clean parents | 33 / 66 |
| Descendants independently replayed | 644 |
| Point fits retained / valid | 14,910 / 14,910 |
| Clean points matching the previous verified rehearsal | 1,386 |
| Clean interval parents / interval rows | 20 / 320 |
| Physical bootstrap records / aligned statistics | 79,960 / 359,820 |
| Stored interval endpoints recomputed | 640 |
| Individual statistics checked against scalar equations | 540 |
| Point-summary rows / aligned draw entries independently recomputed | 97,184 / 194,270,816 |
| Interval-summary rows / aligned draw entries independently recomputed | 1,120 / 2,238,880 |
| Canonical summary groups / rows | 68 / 118,917 |
| Automated tests passed / skipped | 490 / 8 |
| Preserved historical file hashes | 20 |

The recovery rehearsal deliberately interrupted the first chunk immediately before
and after commitment. Partial and complete no-op resumes preserved committed file
bytes and modification times. Summary no-op recovery did likewise. Recomputing
the interrupted rehearsal chunk adds no independent parents.

[Additional boundary fixtures](execution-v1/boundary_verification.json) exercise
48 separately seeded development parents, not confirmation inputs. A full
32-parent chunk crosses repetition 500 at n=1024: it contains 20 stress/interval
parents and 12 clean-only parents, giving 460 descendants, 10,332 point fits and
320 interval rows. The final 16-parent chunk has 336 clean point fits and no
intervals. Both preserve the exact selected grid. Another 540 stored statistics
match scalar replay. The exact auxiliary fixture source is retained alongside
its report; it originally ran from the workspace's `tmp` directory.

The rehearsal's paired summaries were independently reconstructed through
literal parent gathers rather than the executor's count-matrix calculation.
The aligned-entry counts above include explicitly unavailable descriptive-median
draw positions. Unit checks also inject missing methods, unavailable intervals,
zero denominators, empty cells, corrupt archives and changed runtime identities.
No new coverage-based method selection or tuning was performed.

## Resources and operation

The [resource check](execution-v1/resource_check.json) projects about **3.78 GiB**
for primary archives plus **1.85 GiB** conservatively allowing uncompressed
summary arrays. A twofold allowance plus 10 GiB free reserve totals **21.26 GiB**.
The executor requires **30 GiB free at initial launch** and checks the 10 GiB
reserve during execution. About 40.9 GiB was free during this verification.
Abandoned chunks and unrelated applications remain part of actual disk usage.

A full-shape resource fixture with 500 artificial estimator rows, 24 conditions,
21 pipelines and 1,999 summary resamples completed in 6.49 seconds. Peak tracked
Python/NumPy allocation was about 221 MiB; this excludes some native-library
buffers and is not total process memory. Those artificial estimator values are
not simulated study signals or scientific results. The earlier 7.35-hour fit
projection and 14.70-hour planning allowance remain estimates, not finish-time
promises. The complete representative fit and summary rehearsal took about 64
and 70 seconds, respectively, excluding its deliberate repeated first chunk and
the independent audit.

Scientific design SHA-256:
`b5b9399d284e3fae8135050aeac5c8bc0a02ab36b4f0a6d15041f55a497681bb`

Validated runtime SHA-256:
`20f9a612326abec5fa26d16d3764919244c5346ea847f9240c4d6543c0beabc6`

The [release manifest](execution-v1/release.json) also covers the launcher and
auxiliary evidence. The launcher runs fits followed by canonical summaries,
records a local process ID/status, and preserves resumable results if interrupted.
It does not declare the paper validated when computation finishes. The next
scientific step is a full-run accounting and independent results audit, followed
by rebuilding the manuscript tables, figures and claims from canonical exports.
Original PDFs and historical evidence remain unchanged.

```console
python benchmark_experiment/remediation/execution-v1/launch_confirmation.py --output <local-output-outside-OneDrive> --dry-run
python benchmark_experiment/remediation/execution-v1/launch_confirmation.py --output <same-local-output>
```

Use the validated locked environment. Repeating the second command resumes after
an interruption. A live job keeps its exclusive lock; do not start duplicate jobs.
The compact repository evidence is not the full raw rehearsal/confirmation data.
