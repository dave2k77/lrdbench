# Reading Outputs

Every reported run writes artefacts under:

```text
<report.export_root>/<run_id>/
```

The CLI and example scripts print the result store path after each run.

## First files to inspect

Start with:

- `html/report.html` for a human-readable overview;
- `tables/run_summary.csv` for run metadata;
- `tables/per_stratum_metrics.csv` for aggregate metrics by estimator and stratum;
- `tables/leaderboard.csv` for configured rankings;
- `tables/estimator_metadata.csv` for declared estimator metadata;
- `tables/failures.csv` and `tables/failure_map.csv` for invalid outputs and failure patterns.

Raw row-level records are stored under `raw/`. These files are better suited for downstream
analysis, replication checks, and custom plotting.

## Validate the contract

```bash
lrdbench validate-output reports/<run_id>
```

The validator checks the public output contract: required files, required CSV columns, environment
metadata, report files, and artefact index entries.

## Match files to interpretation

Use truth-aware files only in modes where truth exists. For example, `bias`, `mae`, `rmse`, and
empirical interval coverage are meaningful in ground-truth mode. Observational mode should be read
through stability, validity, preprocessing sensitivity, interval width, and failure summaries.

## Preserve provenance

For publication or sharing, keep the manifest copy, result store, environment snapshot, software
version, and generated tables together. The HTML report is useful for review, but the CSV and JSON
artefacts are the reproducible analysis surface.
