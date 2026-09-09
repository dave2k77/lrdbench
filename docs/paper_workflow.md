# Paper workflow

The current paper is rebuilt from the audited confirmation experiment. Start with the
[confirmation guide](confirmation_benchmark.md) for source links, version identities,
rebuilding commands and remaining publication work.

## Tracked publication sources

- `benchmark_experiment/remediation/protocol-v1/` contains the frozen design and settings.
- `benchmark_experiment/remediation/confirmation_audit/` contains the auditor, complete
  summary exports, evidence hashes and findings.
- `benchmark_experiment/manuscript_v3/` contains prose sources, native equation XML,
  table/figure generation scripts, references and numerical/visual verification records.

Edit `manuscript.template.md`, then regenerate the resolved source and assets with
`prepare_assets.py`. Build the editable Word document with `build_docx.py`, reconcile it
with `verify_manuscript.py`, and render and inspect every page. Direct edits to generated
tables or numeric insertions will be overwritten and can break their evidence mapping.
Keep Monte Carlo intervals, estimator intervals, independent parents and bootstrap draws
distinct in both captions and prose.

The source package can rebuild the manuscript from tracked summaries. A full raw-results
audit additionally needs the preserved production archive; a fresh simulation needs the
validated producer and environment. These are three different reproduction tasks.

## Outputs outside Git

The delivered Word draft, compact delivery ZIP and QA renders are local build outputs.
The much larger raw bootstrap archive remains outside Git and awaits public deposition.
Do not identify the software DOI as an archive of these results. A source merge alone
does not publish the raw archive or update the delivered document's availability text.

## Historical local paper kit

The ignored `paper_support/`, `configs/suites/paper/`, `reports/` and `.lrdbench_cache/`
paths belong to the earlier workstation workflow. A clean clone does not need that kit
to rebuild the current manuscript. Old paper suites and their exports retain their
historical meaning; do not combine their rankings or counts with the confirmation run.

For a general library smoke run, use the tracked CLI workflow:

```bash
lrdbench run configs/suites/smoke_ground_truth.yaml
```

See [Current research next steps](current_research_next_steps.md) for author review,
journal preparation, archival deposition and future observational work.
