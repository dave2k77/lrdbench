# Benchmark foundation repair — 7 September 2026

The first repair package is implemented on `fix/benchmark-foundations`, based on
`59a6b65069fca80b89447921ed20afaa5246e60f`. It addresses shared framework defects
before mathematical validation and a revised research run. It does not establish
that the estimators or their intervals are scientifically valid.

## Implemented

| Finding | Change | Evidence |
| --- | --- | --- |
| R01 — rankings | Average component ranks for exact ties; missing/nonfinite results receive N+1 in either direction; primary or named tie-break applied; unresolved ties share competition ranks. Declared metric directions are respected. | Renamed/reordered methods, missing values, both directions and composite tie tests. Component ranks exported in existing metadata. |
| R02 — offset versus step | Historical `level_shift` preserved; explicit `constant_offset` alias added; `step_change` adds a clean-SD-scaled jump at `floor(position*n)`, default midpoint. Zero outlier rate is now identity. | Exact onset/amplitude, negative/zero/positive shifts, invalid positions, unchanged input and provenance tests; end-to-end stress check. |
| R08 — bootstrap accounting | Attempted, retained, invalid and exception-failed draws recorded separately with failure categories. Replicate exceptions do not invalidate a successful point fit. `n_bootstrap=0` disables draws. New `ci_availability` reports interval availability by nominal level. | Injected invalid/exception draws; all three fitting paths (shared, RS, GPH); valid point with all resamples failing; availability denominator example. |
| R10 — figures | Drift and per-record error ratios use separate panels; estimator values remain separate. Global uncertainty plots separate metrics/levels, retain all methods and draw exact interval endpoints. | Hand-set values checked against plotted bars; 35-method retention check; interval excluding its point rendered without changing endpoints; smoke figures visually inspected. |
| R15 — global seed, newly found | Include the previously ignored global seed in generator, contamination and preprocessing seed derivation. Cache keys include record seed and shared fitting revision. | Seed-change and seed-repeat tests; repeated three-mode checks. |
| R16 — nominal interval level, newly found | Default endpoint fields represent 95% only; other intervals stay explicitly labelled. Evaluation requires valid finite points and finite ordered intervals at the requested level. | 80%-only intervals never score as 95%; invalid/nonfinite/reversed intervals rejected. |

The [issue register](issue_register.csv) contains 22 findings with separate
implementation status, evidence and remaining work. The [metric contract](metric_contract.md)
defines implemented metrics and unsupported ratio resampling. The
[eligibility table](estimator_eligibility.csv) contains the 19 expanded v2
configurations, their actual parameters and outstanding validation requirements.

## Verification

- The unchanged targeted baseline passed 22 tests.
- The complete unit-test run passed 206 tests and skipped eight optional dependency
  tests. One plotting fixture lacked the newly required uncertainty type/nominal
  metadata; after correcting the fixture, all nine reporter tests passed. Thus the
  unit checks have no outstanding failures after the focused rerun.
- Three small end-to-end runs, each repeated: ground truth 4 records / 12 fits;
  stress 20 records / 60 fits; observational fixture 1 record / 3 fits. There are
  600 within-record bootstrap attempts per combined pass, with eight per fit.
  Record values, points, intervals, diagnostics and scientific leaderboards match
  exactly on repetition. Every exported result bundle passes the output contract.
- Ruff checks passed; the strict documentation build passed.
- Type checking under the installed Python 3.14 environment reports four errors
  also reproduced from an untouched archive of the base commit. The project's
  default Python 3.11 mypy target cannot parse the installed NumPy 2.5 stubs.
  Neither check is reported as passing. Establish a supported, locked environment
  and address the baseline typing issues separately.
- A broader non-statistical test run was stopped during the expensive legacy
  neural-observational fixture. No complete integration/statistical suite pass is
  claimed; the three repeated small workflows above are the completed integration
  evidence for this package.
- All 20 frozen historical manifests/compact exports still match their SHA-256
  entries in [baseline.json](baseline.json). Original PDF files were not edited.

The local verification directory outside the repository contains generated YAML
manifests, full output bundles, figures and `verification.json`, including Python,
package versions and SHA-256 hashes of every framework source file. Reproduce it
from a checkout with the test/report dependencies installed:

```console
python benchmark_experiment/remediation/run_foundation_smoke.py --output reports/foundation-verification
pytest -q tests/unit/test_benchmark_foundations.py tests/unit/test_reporter.py
```

Use a dedicated writable pytest temporary directory where required by the host.
The smoke script generates new directories rather than replacing historical runs.
Its eight estimator draws and 32 benchmark-summary draws are software-test settings,
not recommendations for a research protocol. The observational input is a fixture.

## Migration and interpretation

1. Keep old bundles as historical evidence. Ranking changes can reorder methods even
   when point estimates are unchanged; do not mix repaired leaderboards with old
   tables or silently overwrite exported results.
2. Existing `level_shift` manifests still generate constant offsets. Change new
   research manifests to `step_change` for internal jumps, retaining `constant_offset`
   as a separately named control. The legacy offset retains its `std(x)+1e-12`
   scale for compatibility; the new step uses `std(x)` exactly.
3. New random streams differ even with old manifest files because the declared
   global seed now takes effect. Manifest IDs still affect generation; this repair
   does not yet create shared parents across independently named tracks.
4. Old estimate caches are intentionally invalidated. Cached estimates also depend
   on the record seed because within-record resampling uses it.
5. Exported CSV columns retain their existing public contract. New counters live in
   `diagnostics_json`, and ranking details in existing metadata. Include
   `ci_availability` alongside conditional coverage and interval width in new suites.
6. Point validity, interval availability and interval calibration are separate.
   Reporting failures honestly does not validate circular block bootstrap under LRD.
7. Revised plots still display the legacy metric calculations. In particular,
   `relative_degradation_ratio` remains the mean of per-record ratios, and the
   stress overview pools records across severities within each estimator/operator.
   Publication-specific stratum selection, captions and counts remain to be built.

## Next work package

The [second repair report](method-audit.md) records the completed additive metrics,
missing-pair accounting, GPH/Higuchi/GHE equation corrections and an independent
WaveletOLS scale-convention check. Its small diagnostic pilot exposes persistent-H
interval undercoverage and false persistence on a short-memory null. The verification
counts above describe the first package; the second report records subsequent checks.

The [third repair report](remaining-audit.md) completes the first equation-check
pass across the classical roster, records the generator audit and presents a
larger development pilot. Its coverage failures remain after changing block length.
The [next calibration design](calibration-design.md) separates tuning from fresh
confirmation, quantifies Monte Carlo precision and records the projected workload.

The [fourth package](calibration-runner.md) implements a resumable development
runner with immutable shared inputs, exact fit accounting and dependency pins with
distribution hashes. Its complete cost profile uses 72 inputs, 2,016 fits and
258,552 within-record draws; it projects about 13 hours for the full interval
screen. This profile measures cost and recovery, not coverage. The full scientific
screen and confirmation runs remain pending.

Continue validating every retained generator/estimator against mathematical references
and appropriate inputs, and calibrate uncertainty procedures. Then freeze shared
clean parents, null/alternative populations, scales, repetitions and paired or
clustered summary resampling. Run the revised benchmark only after these gates,
and regenerate every paper table, figure and claim from its canonical exports.

Correctly implemented methods may perform poorly. Scientific eligibility depends
on implementing the declared procedure, not on obtaining a favourable ranking.
