# Current research next steps

Last reviewed: 9 September 2026.

## Current state

The classical benchmark repairs, frozen confirmation run, independent audit and manuscript
rebuild are complete and merged into `main`. Use the
[audited confirmation guide](confirmation_benchmark.md) for the current evidence, exact
revisions, workload counts, reproduction instructions and release status.

The library also contains estimand-triangle, discrimination, machine-learning and
observational workflows. Those are separate from the confirmation paper. The older
`neural_classical_workstation` exports and eight-record neural-like fixture do not provide
the rebuilt manuscript's evidence. The OpenNeuro pilot remains a separate observational
workflow demonstration, with no known H target or accuracy/coverage ground truth.

## Next publication work

1. Complete author review of the rebuilt manuscript and its claim-reconciliation ledger.
2. Supply corresponding-author details, funding, competing interests and the target journal.
3. Prepare deposition of the preserved raw results, frozen runtime and checksums. Assign an
   archive identifier only after the deposit exists; the software DOI is not a result DOI.
4. Update the manuscript's availability statement to reflect the public GitHub sources and
   the eventual archive. The delivered 8 September draft predates the source merge.
5. Apply journal formatting and recheck all tables, figures, equations and rendered pages.

Do not rerun or retune the confirmation merely to recover historical rankings. Extensions
need a separately declared design, run identity and analysis, retaining the completed study.

## Library maintenance

- Keep parameter defaults, input transformations, metric denominators and migration notes
  aligned with code changes. Follow the [documentation maintenance checklist](contributor_checklist.md#documentation-maintenance).
- Preserve historical outputs and frozen runtime snapshots; document which revision produced
  each result. Current source is not a replacement for the validated producer checkout.
- Keep release versions distinct from unreleased `main`. Update citation and release guidance
  when a new package release or result archive is actually published.
- Validate public output-contract changes separately from the research export format.

For normal development, install the documented extras into a development environment and run:

```bash
python -m ruff check src tests
python -m pytest
python -m mkdocs build --strict
```

These commands use the chosen development interpreter. They do not reproduce the production
run, which requires the frozen environment described in the confirmation guide.

## Future observational work

Use the [observational readiness plan](observational_readiness_plan.md) for that separate
workstream. Require stable segment identifiers, sampling rate and preprocessing metadata,
quality-control records, and a truth-free interpretation plan. Report validity, runtime,
interval availability/width, estimator disagreement and sensitivity; do not present these
as evidence of estimator accuracy, calibrated coverage or neural LRD detection.
