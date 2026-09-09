# Architecture

This page describes the internal structure of `lrdbench` for contributors and advanced users. If you only want to run benchmarks, the [Quickstart](tutorials/quickstart.md) is the better starting point.

## The benchmark loop

Public manifest-driven runs follow this orchestration path. The paper's frozen confirmation
engine has a separate execution and archive contract, described below.

```text
Manifest (YAML)
    │
    ▼
Record materialisation  ←  generators  |  observational sources
    │
    ▼
Optional preprocessing  ←  independent raw-to-corrected branches
    │
    ▼
Optional ML training  ←  ml_training block (data-driven estimators only)
    │
    ▼
Estimation  ←  estimator registry (+ optional third-party plugins)
    │
    ▼
Evaluation  ←  mode-specific evaluator (ground_truth / stress_test / observational)
    │
    ▼
Leaderboards  ←  weighted-rank builder
    │
    ▼
Result store staging  ←  record arrays, metadata and buffered CSV rows
    │
    ▼
Reports  ←  HTML / CSV / LaTeX / figures
    │
    ▼
Result store finalisation  ←  raw CSVs, report/model artefacts, plugin provenance
```

`BenchmarkRunner.run()` in `runner.py` wires these public stages together and expects a
validated `BenchmarkManifest`. The manifest loaders parse and validate YAML or mappings
before calling it. Each stage is implemented by a dedicated module.

If a manifest declares `preprocessing.operators`, the runner materializes additional corrected records after source materialization and before estimation. These records keep the original truth target, add `preprocessing_*` stratum fields, and preserve `raw_record_id` / `pair_group_id` annotations for raw-vs-corrected comparisons.

In stress mode, each contamination acts on the clean parent independently. Each preprocessing
operator then acts independently on its source record; operators are not a sequential pipeline.
`preprocessing.include_raw` controls whether the original records remain in the fitting grid.
Preprocessing precedes optional model preparation. `preview()` also materialises and preprocesses
records, but does not train models, fit estimators or write reports.

## Key modules

| Module | Responsibility |
|--------|--------------|
| `cli.main` | Argparse front-end (`run`, `validate`, `list-*`, `validate-output`). |
| `manifest` | Load and parse YAML manifests into `BenchmarkManifest` dataclasses. |
| `validation` | Validate manifest structure, metric admissibility and truth compatibility. |
| `runner` | `BenchmarkRunner` — orchestrates the full loop and collects `plugin_provenance`. |
| `execution` | `collect_fit_jobs` + `run_fit_jobs` — manages the `(record × estimator)` grid, optional thread pools, and on-disk estimate caches. |
| `evaluator` | `GroundTruthEvaluator` handles both synthetic modes; `ObservationalEvaluator` handles truth-free records. |
| `paired_metrics` | Clean/contaminated and raw/corrected comparisons with record pairing. |
| `preprocessing`, `ml_training` | Correction operators and optional run-local model preparation. |
| `leaderboard` | `WeightedRankLeaderboardBuilder` — composes metric columns into ranked rows. |
| `reporter` | `SimpleHtmlCsvReporter` — renders HTML, CSV, LaTeX, and matplotlib figures. |
| `result_store` | `CsvResultStore` — persists signal arrays as `.npy`, selected fields as CSV, and run metadata as JSON/YAML. |
| `output_contract` | Required file/header checks and the public export schema. |
| `registries` | Estimator, generator, contamination and preprocessing look-up tables. |
| `plugin_loader` | Discovery and ordinary import-failure reporting for trusted third-party estimator plugins. |
| `schema` | Immutable dataclasses (`SeriesRecord`, `EstimateResult`, `MetricSpec`, …) that form the public data contract. |
| `interfaces` | Abstract base classes (`BaseEstimator`, `BaseGenerator`, `BaseContamination`, …) that define extension points. |

## Extension points

### Adding a generator

1. Subclass `BaseGenerator` and implement `family`, `version`, and `generate()`.
2. Register it in `defaults.build_default_generator_registry()`.
3. Reference the family name in a manifest `source.generator_grid` block.

### Adding a contamination operator

1. Subclass `BaseContamination` and implement `name`, `family`, `version`, and `apply()`.
2. Register it in `defaults.build_default_contamination_registry()`.
3. Reference the operator name in a manifest `contamination.operators` block.

### Adding a preprocessing or correction operator

1. Subclass `BasePreprocessing` and implement `name`, `family`, `kind`, `version`, and `apply()`.
2. Register it in `defaults.build_default_preprocessing_registry()`.
3. Reference the operator name in a manifest `preprocessing.operators` block.

### Adding an estimator

1. Subclass `BaseEstimator` and implement `spec` and `fit()`.
2. Register it in `defaults.build_default_estimator_registry()` **or** use the [third-party plugin workflow](third_party_estimators.md).
3. Declare it in a manifest `estimators` block with `name`, `family`, `target_estimand`, and optional `params`.

For a complete walkthrough, see [Adding estimators](adding_estimators.md).

## Provenance and reproducibility

Every synthetic record carries a `ProvenanceRecord` with:
- a stable `record_id` (SHA-1 hash of manifest id, family, parameters, and replicate index),
- the generator `seed` derived deterministically from the manifest's `global_seed`,
- timestamps and software version metadata.

Contaminated records extend this history via `contamination_history`, preserving the clean parent id, operator name, parameters, and severity label. Preprocessed records extend `preprocessing_history` so empirical corrections and oracle corrections remain auditable.

Every run writes `manifest/environment.json` containing Python version, platform, package
versions, seed policy, and execution settings. Reproduction also requires matching inputs,
dependencies, estimator/plugin implementations and relevant numerical backend settings.
Run UUIDs, timestamps and measured runtimes vary; byte-identical report directories are not
promised. Public record IDs do not incorporate the global seed, so an ID alone does not
identify signal content across changed seeds. Estimate cache keys include values and record seed.

## Confirmation research workflow

The research implementation lives under `benchmark_experiment/remediation/` and reuses library
statistics while controlling its own frozen design, batching, resampling and storage:

```text
Frozen protocol → compiled design + runtime/source checks
    → run_confirmation.py / confirmation_batch.py
    → confirmation_intervals.py + confirmation_store.py
    → raw chunks and completion evidence
    → confirmation_analysis.py / summarize_confirmation.py + confirmation_audit/
    → audited exports → manuscript_v3 assets → manuscript verification
```

The [confirmation guide](confirmation_benchmark.md) links the protocol, execution specification,
archive audit and reproduction commands. This workflow uses its own run identity and paired
resampling rules. Its raw chunks and summary tables are not `CsvResultStore` exports and must
not be checked or interpreted using only the public CSV contract. Preserve the original producer
revision and runtime lock; changes to current library code do not retroactively change the study.

## Output contract

The public machine-readable contract is rendered directly in the [output specification](output_contract.md).
`lrdbench validate-output <run_root>` checks that:
- all required files exist,
- all required CSV columns are present,
- optional CSVs that exist contain their declared minimum columns.

It does not check a stored contract version, conditional-file eligibility, row values, hashes or
scientific completeness. The Python dataclasses are richer than the CSV projection: for example,
raw estimate CSVs do not retain full diagnostics or bootstrap draws. See the output specification
for these boundaries and the research audit for stronger study-specific checks.

Review schema, implementation, migration notes and contract version together when changing a
stable output requirement. Data-dependent columns already permitted by the contract do not
require a version change for each run. The [contributor checklist](contributor_checklist.md)
maps architecture and workflow changes to documentation and verification responsibilities.
