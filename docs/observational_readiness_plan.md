# Observational Mode Readiness Plan

Last updated: 2026-05-29

This page defines what remains before `lrdbench` observational mode is ready for real neural or
biomedical time-series studies. The current implementation is useful for smoke tests and simple
CSV-backed series, but it is not yet a complete observational workflow for segmented LFP/EEG-like
data.

The plan intentionally preserves the existing ground-truth and stress-test behaviour. Observational
work must continue to avoid truth-based claims: no `bias`, `mae`, `rmse`, `coverage`,
`coverage_error`, `coverage_collapse`, or `false_positive_lrd_rate` on empirical records.

## Current baseline

Implemented now:

- `mode: observational` is accepted by the manifest loader and runner.
- Observational records can be loaded from:
  - `source.type: inline_table`;
  - `source.type: csv_series_index` with one numeric value column per listed file.
- Records are materialised with `source_type=observational`, `truth=None`, source annotations, and
  provenance seeds.
- The runner resolves relative CSV paths against the manifest directory or supplied `base_dir`.
- Truth-free metrics are available, including validity, runtime, CI width, instability,
  preprocessing sensitivity, estimator disagreement, family disagreement, and variant sensitivity.
- Validation rejects synthetic `generator_grid` sources and contamination blocks in observational
  mode.
- There is a packaged smoke manifest: `configs/suites/smoke_observational.yaml`.
- Unit and integration tests cover minimal inline/CSV ingestion and the smoke observational run.

Important files:

- `src/lrdbench/observational_sources.py`
- `src/lrdbench/evaluator.py`
- `src/lrdbench/validation.py`
- `src/lrdbench/runner.py`
- `docs/tutorials/observational_data.md`
- `configs/suites/smoke_observational.yaml`
- `tests/unit/test_observational_sources.py`
- `tests/integration/test_phase4_observational.py`

## Readiness gaps

### Data model and ingestion gaps

Current CSV ingestion drops missing values and returns only `values`. It does not yet preserve:

- time columns or sample indices;
- sampling rate;
- segment duration;
- subject/session/channel/condition metadata;
- preprocessing provenance;
- file hashes for auditability;
- per-record quality-control summaries;
- explicit handling rules for non-finite values beyond `dropna()`.

For neural data this is not enough. The observational record needs enough metadata to stratify,
audit, reproduce, and interpret the run without depending on filenames alone.

### Validation gaps

Manifest validation currently checks that the observational source type and series list exist, but it
does not deeply validate each series entry. It should reject malformed records before a long run
starts.

Missing checks include:

- required `path` for `csv_series_index` entries;
- non-empty `record_id` values;
- duplicate `record_id` detection;
- missing or invalid `value_column`;
- optional `time_column` / `sampling_rate` consistency;
- reserved annotation names;
- minimum length thresholds appropriate for LRD estimators;
- observational metric bundles that omit essential failure/stability metrics.

### Neural metadata gaps

The neural-classical benchmark specification requires subject/session/channel/condition,
sampling-rate, filter, artefact, normalisation, segment-duration, overlap, and missing-data metadata.
The current loader can only attach generic annotations.

The library needs either a richer `csv_series_index` schema or a sidecar metadata table so a manifest
can express real study structure without duplicating every detail in file paths.

### Segmentation and preprocessing gaps

The current observational path assumes records are already segmented and analysis-ready.
`preprocessing_sensitivity` is a scale perturbation proxy only. For neural work, readiness requires a
clear policy around:

- whether segmentation is performed outside `lrdbench` or by a first-party helper;
- whether per-record detrending, demeaning, z-scoring, resampling, filtering, or artefact masking is
  represented as metadata only or as executable transformations;
- how to compare declared preprocessing variants without implying truth.

The first library-ready step should be metadata and auditability, not a large preprocessing engine.

### Reporting and interpretation gaps

Reports can export metrics, but observational reports should make claim boundaries harder to miss.
They should emphasise:

- no benchmark truth is present;
- leaderboards are stability/robustness summaries, not accuracy rankings;
- estimator families and target estimands should not be collapsed without labels;
- failures and missing uncertainty must be shown beside any aggregate metric;
- record strata should be visible for subject/session/channel/condition analyses.

### Example and fixture gaps

Only one tiny observational smoke manifest exists. Before using real neural data, add synthetic or
sanitised observational fixtures that exercise the workflow without including sensitive data.

Needed examples:

- a multi-record observational manifest;
- a metadata sidecar example;
- a variant-heavy classical-estimator observational suite;
- a no-truth neural-like fixture with subject/session/channel/condition strata;
- a docs walkthrough that reads the resulting CSV outputs.

## Prioritized backlog

### P0: Release-blocking for real observational neural use

#### P0.1 Add a richer observational source schema

Objective: allow each observational record to carry time, sampling, and study metadata.

Likely files:

- `src/lrdbench/observational_sources.py`
- `src/lrdbench/validation.py`
- `docs/tutorials/observational_data.md`
- `tests/unit/test_observational_sources.py`
- `tests/integration/test_phase4_observational.py`

Work outline:

1. Extend `csv_series_index` entries with optional keys:
   - `time_column`
   - `sampling_rate`
   - `metadata`
   - `metadata_path` or `metadata_row_id` if using a sidecar table
   - `missing_policy`, initially limited to `drop`, `error`, or `interpolate_linear` if implemented
2. Populate `SeriesRecord.time_axis`, `SeriesRecord.sampling_rate`, and `annotations` from those
   fields.
3. Preserve existing simple manifests as valid.
4. Record source file SHA-256 in provenance or annotations for each CSV file.
5. Add tests for time-axis loading, sampling-rate loading, metadata attachment, file hashing, and
   backwards compatibility.

Acceptance criteria:

- Existing `configs/suites/smoke_observational.yaml` still validates and runs.
- A new multi-record fixture can carry subject/session/channel/condition metadata.
- Duplicate or malformed metadata is rejected before fitting starts.
- `records.csv` contains enough fields or annotation exports to join outputs back to study metadata.

#### P0.2 Deep-validate observational series entries

Objective: catch bad manifests before long estimator runs.

Likely files:

- `src/lrdbench/validation.py`
- `tests/integration/test_phase4_observational.py`
- `tests/unit/test_observational_sources.py`

Work outline:

1. Validate every `source.series` entry for source-specific required keys.
2. Reject duplicate `record_id` values.
3. Reject blank paths, blank value columns, invalid sampling rates, and non-mapping metadata.
4. Optionally check local file existence during `lrdbench validate` when a manifest path is known;
   otherwise keep file checks in the loader and improve error messages.
5. Add negative tests for each failure mode.

Acceptance criteria:

- Bad observational manifests fail with actionable `ManifestValidationError` messages.
- The loader no longer depends on raw `KeyError` or pandas `ValueError` for common user mistakes.

#### P0.3 Add observational QC summaries

Objective: expose enough signal-quality context to interpret truth-free metrics.

Likely files:

- `src/lrdbench/observational_sources.py`
- `src/lrdbench/result_store.py`
- `src/lrdbench/reporter.py`
- `tests/unit/test_observational_sources.py`
- `tests/integration/test_phase4_observational.py`

Work outline:

1. Compute per-record QC annotations during loading:
   - original row count;
   - retained sample count;
   - missing/non-finite count;
   - mean, standard deviation, min, max;
   - duration when sampling rate or time axis is available.
2. Export QC metadata in records or a dedicated observational QC CSV.
3. Add report text that warns if metrics are based on heavily filtered or very short records.

Acceptance criteria:

- Observational outputs include retained sample counts and missingness rates.
- Reports show or link QC summaries near observational metric tables.
- Tests prove QC summaries remain deterministic for fixtures.

#### P0.4 Provide a neural observational manifest template

Objective: make the first real neural run a manifest-filling exercise rather than a design exercise.

Likely files:

- `configs/suites/neural_observational_template.yaml`
- `docs/tutorials/observational_data.md`
- `docs/current_research_next_steps.md`

Work outline:

1. Add a commented template with classical estimators only.
2. Include truth-free metrics only:
   - `validity_rate`
   - `runtime`
   - `ci_width`
   - `instability`
   - `preprocessing_sensitivity`
   - `cross_estimator_dispersion`
   - `pairwise_estimator_disagreement`
   - `family_level_disagreement`
   - `parameter_variant_sensitivity`
   - `max_variant_drift`
3. Include estimator variants for scale-window and bandwidth sensitivity.
4. Include benchmark-level uncertainty for aggregate truth-free metrics.
5. Use conservative leaderboards labelled as robustness/stability summaries.

Acceptance criteria:

- The template validates after placeholder paths are replaced with fixture paths.
- It does not contain any truth-based metrics.
- Docs explain that spectral long-memory estimators and Hurst-scaling estimators must be grouped or
  labelled separately.

### P1: Strongly recommended before committee/manuscript use

#### P1.1 Add a non-sensitive multi-record observational fixture

Objective: test real workflow structure without shipping sensitive neural data.

Likely files:

- `configs/suites/data/observational_multirecord/`
- `configs/suites/observational_multirecord_fixture.yaml`
- `tests/integration/test_phase4_observational.py`

Acceptance criteria:

- The fixture has at least four records across at least two strata.
- The run exercises metadata, time/sampling fields, multiple estimators, and disagreement metrics.
- The fixture is small enough for CI.

#### P1.2 Improve observational report language

Objective: make incorrect interpretation less likely.

Likely files:

- `src/lrdbench/reporter.py`
- `docs/tutorials/reading_outputs.md`
- `tests/integration/test_phase4_observational.py`

Acceptance criteria:

- HTML reports for observational runs include a no-truth banner.
- Leaderboard captions say “stability/robustness summary,” not “accuracy ranking.”
- Reports surface failure counts and missing CI counts beside aggregate metrics.

#### P1.3 Add observational output-contract checks

Objective: ensure observational outputs remain reproducible and auditable.

Likely files:

- `src/lrdbench/cli/main.py`
- `src/lrdbench/output_contract.py` or equivalent validation module
- `tests/integration/`

Acceptance criteria:

- `validate-output` verifies observational records have no truth fields.
- It checks required observational metadata/QC fields once P0.1 and P0.3 exist.
- It rejects truth-based metrics in observational result stores.

#### P1.4 Add analysis helpers for observational CSV outputs

Objective: reduce manual post-processing for committee figures.

Likely files:

- `benchmark_experiment/`
- `examples/`
- `docs/research_notebooks.md`

Acceptance criteria:

- A documented script/notebook builds truth-free summary tables by estimator, family, and stratum.
- The helper keeps `hurst_scaling_proxy` and `long_memory_parameter` outputs separated or explicitly
  labelled.
- Figures are generated from archived CSV outputs, not copied values.

### P2: Optional polish after the first neural workflow is stable

#### P2.1 First-party segmentation helpers

Only add this if repeated real studies need it. The safer near-term policy is to require segments to
be prepared outside `lrdbench` and documented in metadata.

#### P2.2 Rich preprocessing variant engine

Only add executable preprocessing variants after metadata, QC, and report guardrails are stable.
Initial readiness can use precomputed segment variants and metadata labels.

#### P2.3 Plugin/source adapters

Optional future adapters for NWB, EDF, BIDS, or lab-specific stores should be plugin-style. Do not
make them required for the core library.

## Recommended execution order

1. Implement P0.2 deep validation first. It is low-risk and improves user errors immediately.
2. Implement P0.1 metadata/time/sampling ingestion next, with backwards-compatible tests.
3. Implement P0.3 QC summaries so observational outputs carry interpretation context.
4. Add P1.1 multi-record fixture to exercise the richer path end-to-end.
5. Add P0.4 neural observational template after the schema is real, not before.
6. Improve reports and output validation with P1.2 and P1.3.
7. Add analysis helpers once output shape is stable.

## Verification gate

Use the dedicated project environment on this Windows host:

```bash
PYTHONPATH=src .venv/Scripts/python.exe -m ruff check src tests
PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests/unit/test_observational_sources.py tests/integration/test_phase4_observational.py -q --tb=short -o addopts=
PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q --tb=short -o addopts=
PYTHONPATH=src .venv/Scripts/python.exe -m mkdocs build --strict --quiet
```

For any new observational manifest, also run:

```bash
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate <manifest.yaml>
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main run <manifest.yaml> --dry-run --no-plugins
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main run <manifest.yaml> --no-plugins
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate-output <report_root>/<run_id>
```

## Claim boundaries

Observational mode can support claims like:

- an estimator was valid or invalid on declared empirical records;
- estimates were stable or unstable under declared variants;
- estimator families agreed or disagreed under declared preprocessing and segmentation;
- missing uncertainty or failures concentrated in specific strata.

Observational mode cannot support claims like:

- the empirical records contain true LRD;
- one estimator is most accurate on empirical records without benchmark truth;
- estimator confidence intervals have empirical coverage on records with no truth;
- high Hurst-like values alone establish physiology rather than model-dependent summaries.
