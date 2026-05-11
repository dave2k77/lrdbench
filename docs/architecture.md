# Architecture

This page describes the internal structure of `lrdbench` for contributors and advanced users. If you only want to run benchmarks, the [Quickstart](tutorials/quickstart.md) is the better starting point.

## The benchmark loop

Every benchmark run follows the same orchestration path:

```text
Manifest (YAML)
    │
    ▼
Record materialisation  ←  generators  |  observational sources
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
Result store  ←  CSV files under reports/<run_id>/
    │
    ▼
Reports  ←  HTML / CSV / LaTeX / figures
```

`BenchmarkRunner.run()` in `runner.py` is the single entry point that wires these stages together. Each stage is implemented by a dedicated module so that individual pieces can be tested and replaced in isolation.

## Key modules

| Module | Responsibility |
|--------|--------------|
| `cli.main` | Argparse front-end (`run`, `validate`, `list-*`, `validate-output`). |
| `manifest` | Load and parse YAML manifests into `BenchmarkManifest` dataclasses. |
| `runner` | `BenchmarkRunner` — orchestrates the full loop and collects `plugin_provenance`. |
| `execution` | `collect_fit_jobs` + `run_fit_jobs` — manages the `(record × estimator)` grid, optional thread pools, and on-disk estimate caches. |
| `evaluator` | `GroundTruthEvaluator`, `StressTestEvaluator` (shares GT), `ObservationalEvaluator` — compute metrics from records and estimates. |
| `leaderboard` | `WeightedRankLeaderboardBuilder` — composes metric columns into ranked rows. |
| `reporter` | `SimpleHtmlCsvReporter` — renders HTML, CSV, LaTeX, and matplotlib figures. |
| `result_store` | `CsvResultStore` — persists raw records, estimates, metrics, leaderboards, and artefacts as CSV/JSON. |
| `registries` | `EstimatorRegistry`, `GeneratorRegistry`, `ContaminationRegistry` — look-up tables for pluggable components. |
| `plugin_loader` | Safe, failure-transparent loading of third-party estimator plugins via environment variables. |
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

Contaminated records extend this history via `contamination_history`, preserving the clean parent id, operator name, parameters, and severity label.

Every run writes `manifest/environment.json` containing Python version, platform, package versions, seed policy, and execution settings. This makes a report self-describing: given the manifest, the package version, and the data sources, the run should be bitwise reproducible.

## Output contract

The framework enforces a machine-readable output contract (`configs/contracts/public_output_contract.json`). `lrdbench validate-output <run_root>` checks that:
- all required files exist,
- all required CSV columns are present,
- the contract version matches the expected schema.

Any change that adds, removes, or renames output columns must update this contract and the contract version.
