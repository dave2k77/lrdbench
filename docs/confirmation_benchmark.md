# Audited confirmation benchmark

Status reviewed on 9 September 2026 against merge commit
[`40d10f5`](https://github.com/dave2k77/lrdbench/commit/40d10f56e9a3c4099f11ecc1d7e9b388a8b84993).

The classical-estimator confirmation experiment, independent results audit and manuscript
rebuild are complete. This page is the entry point for that experiment. The older
`neural_classical_workstation` campaign, observational fixtures and EEG pilot are separate
records; they are not the evidence source for the rebuilt manuscript.

## Scope and results

The experiment evaluates stationary scalar increments from fGn, ARFIMA(0,d,0) and AR(1).
It separates clean accuracy, recovery of the latent clean target after contamination, and
clean confidence-interval coverage. It does not validate neural recordings, a calibrated
LRD test or a universal estimator ranking.

| Audited quantity | Count |
| --- | ---: |
| Independent clean parents | 66,000 |
| Clean process–length cells | 33 |
| Point-estimation pipelines | 21 |
| Separately applied contamination conditions | 23 |
| Contaminated descendants | 161,000 |
| Clean and contaminated point fits | 4,767,000 |
| Parents in the clean interval study | 15,500 |
| Available interval rows | 248,000 |
| Finite bootstrap-statistic attempts | 278,860,500 |
| Canonical cell/domain summary rows | 118,917 |

The stress and interval studies reuse subsets of the clean parents. Their counts must not
be added to the independent-parent total. The planned-contrast and convenience exports
overlap the six complete summary tables; they are not additional simulations.

Mean removal eliminates constant-offset sensitivity in the geometric estimators but does
not remove internal-step sensitivity. Fitted-fGn intervals improve coverage in persistent
fGn examples while failing on strongly persistent AR(1) controls. Availability of every
interval therefore does not establish calibration. Read the
[findings and claim ledger](https://github.com/dave2k77/lrdbench/blob/main/benchmark_experiment/remediation/confirmation-results.md)
for numerical comparisons and their uncertainty.

## Evidence and provenance

| Purpose | Authoritative source |
| --- | --- |
| Frozen design, settings and accounting | [Protocol and design lock](https://github.com/dave2k77/lrdbench/tree/main/benchmark_experiment/remediation/protocol-v1) |
| Producer revision | [`9c02d04`](https://github.com/dave2k77/lrdbench/commit/9c02d04) |
| Results audit revision | [`b3d0648`](https://github.com/dave2k77/lrdbench/commit/b3d0648) |
| Full summary exports and audit evidence | [Audit results](https://github.com/dave2k77/lrdbench/tree/main/benchmark_experiment/remediation/confirmation_audit/results) |
| Manuscript source revision | [`a2f4ee2`](https://github.com/dave2k77/lrdbench/commit/a2f4ee2) |
| Prose, equations, figures, tables and verification | [Manuscript package](https://github.com/dave2k77/lrdbench/tree/main/benchmark_experiment/manuscript_v3) |

Run identity:
`43d0a7f75c8afab6d32ab6fd1f2ff8db49cca59e36971e2b74404173f4cbfcf2`.
Canonical summary SHA-256:
`95b8e938fb98a674c7ba2e92b7d59ed0f909ffd6ae2e8585c90a0f23f7c01504`.
The audit's `audit_evidence.json` supplies the workload counts;
`export_provenance.json` supplies the export hashes. Manuscript insertions and plotted
values are mapped to those exports in `manuscript_v3/tables/evidence_map.csv`.

## Rebuild the manuscript

The publication sources and complete summary exports are tracked in Git. Building the
manuscript does not require rerunning the simulation or obtaining the full raw archive.
From a repository checkout, use separate interpreters with the required packages:

```text
SCIENCE_PYTHON benchmark_experiment/manuscript_v3/prepare_assets.py
DOCUMENT_PYTHON benchmark_experiment/manuscript_v3/build_docx.py --output rebuilt-manuscript/lrdbench-manuscript-v3.docx
DOCUMENT_PYTHON benchmark_experiment/manuscript_v3/verify_manuscript.py --docx rebuilt-manuscript/lrdbench-manuscript-v3.docx
```

Replace the interpreter placeholders with executable paths. The science environment needs
NumPy, pandas and Matplotlib; use the recorded scientific environment for reproduction.
The document environment needs python-docx, lxml and pypdf. Native equation XML is included;
Microsoft Office is only needed by the optional equation-regeneration utility.
See the [package README](https://github.com/dave2k77/lrdbench/blob/main/benchmark_experiment/manuscript_v3/README.md)
for the original build environment and rendering procedure. Check every rendered page
after changing prose, tables, figures or layout. The resolved `manuscript.md` still contains
placement commands and is a typesetting source, not a standalone reading edition.

## Reproduce the experiment or audit

The production runner deliberately requires its validated Python 3.14.5 environment,
dependency pins and exact source hashes. A current checkout is not interchangeable with
the frozen producer: later changes even to recorded test sources change its runtime identity.
Use the preserved runtime or the specified producer revision and its matching release
evidence. Do not loosen that guard to reproduce the paper.

General library CI uses Python 3.12. Its small rehearsal tests use a scoped test runtime;
separate cases exercise the production environment guard. A passing CI rehearsal does
not authorize a new production run or replace validation of the frozen runtime.

The full audit requires the preserved raw production directory as well as the frozen
runtime. Follow the [audit reproduction instructions](https://github.com/dave2k77/lrdbench/blob/main/benchmark_experiment/remediation/confirmation_audit/reproduce.md)
and use a fresh output directory to retain earlier evidence.

## Release and publication status

These sources were merged into `main` in [PR #3](https://github.com/dave2k77/lrdbench/pull/3).
The latest published GitHub release checked on 9 September 2026 is `v1.2.1`; the repairs
are unreleased development changes. Installing that release does not install this work.
Use a Git checkout and record its revision when evaluating the corrected implementations.

The full raw bootstrap archive has not been deposited publicly. The software concept DOI
does not identify this confirmation archive. Author review and declarations, journal
formatting, archive deposition and final availability wording remain publication work.
The delivered draft dated 8 September predates the GitHub merge; its availability wording
must be refreshed during the next editorial revision.

For subsequent work, see [Current research next steps](current_research_next_steps.md).
