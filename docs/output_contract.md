# Output Contract

The public benchmark output contract is tracked in
`configs/contracts/public_output_contract.json`. The same contract is exposed from
`lrdbench.output_contract.PUBLIC_OUTPUT_CONTRACT` for tests and downstream tooling.

The current contract version is `0.3.0-beta`.

## Run Root

Each run writes artefacts under:

```text
<report.export_root>/<run_id>/
```

For the public-small suites this is usually `reports/public_small/<run_id>/`. For public-medium
suites it is usually `reports/public_medium/<run_id>/`.

## Required Files

Every reported run should include these summary artefacts:

- `tables/run_summary.csv`
- `tables/per_stratum_metrics.csv`
- `tables/leaderboard.csv`
- `tables/estimator_metadata.csv`
- `tables/failures.csv`
- `tables/failure_map.csv`
- `tables/uncertainty_calibration.csv`
- `tables/benchmark_uncertainty.csv`
- `tables/estimator_disagreement.csv`
- `tables/scale_window_sensitivity.csv`
- `html/report.html`
- `manifest/environment.json`
- `artefacts/artefact_index.csv`

Every raw result store should include:

- `raw/records.csv`
- `raw/estimates.csv`
- `raw/metrics.csv`
- `raw/artefacts.csv`

`raw/leaderboards.csv` is present when leaderboard rows are generated. `tables/stress_metrics.csv`
is present for stress-test reports. Figures and LaTeX tables are present only when requested and
available for the run.

## Required Columns

The machine-readable JSON contract lists required columns for each stable CSV. Downstream checks
should treat these as a minimum set: extra `metric__*` and `stratum__*` columns are expected in
leaderboard, failure-map, and failure-summary tables when manifests or strata change.

Core examples:

| File | Required columns |
| --- | --- |
| `tables/run_summary.csv` | `run_id`, `manifest_id`, `benchmark_name`, `mode` |
| `tables/per_stratum_metrics.csv` | `estimator_name`, `metric_name`, `value`, `stratum_json`, `metadata_json` |
| `tables/leaderboard.csv` | `estimator_name`, `rank`, `score` |
| `raw/metrics.csv` | `scope`, `record_id`, `estimator_name`, `metric_name`, `value`, `stratum_json`, `metadata_json` |
| `artefacts/artefact_index.csv` | `artefact_id`, `run_id`, `artefact_type`, `format`, `path`, `hash`, `created_at`, `depends_on_json` |

Use the JSON contract as the authority when building automated output checks.

## Validation Command

After generating a report, validate the run directory against the public output contract:

```bash
lrdbench validate-output reports/public_small/<run_id>
```

The command checks required files and required CSV columns. It returns exit code `0` for a valid
output directory and exit code `2` with one `error=...` line per contract violation when validation
fails.

## Artefact Index

`artefacts/artefact_index.csv` records every exported report artefact known to the reporter. Its
rows include:

- a stable `artefact_id` within the run;
- the `run_id`;
- an `artefact_type`, such as `metric_export`, `leaderboard_export`, `figure`,
  `environment_snapshot`, `html_report`, or `artefact_index`;
- the file `format`;
- the artefact `path`;
- optional `hash`, `created_at`, and `depends_on_json` metadata.

The raw result store mirrors this information in `raw/artefacts.csv`.
