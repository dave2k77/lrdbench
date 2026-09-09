# Design Specification

This page is the tracked clean-clone design authority for `lrdbench`. It replaces the earlier
local-only PDF dependency for public development. If an older local PDF exists, treat it as
historical design context unless this page explicitly says otherwise.

Reviewed against the implementation on 9 September 2026. This is the design of current `main`;
released package behavior and the frozen paper experiment have separate version identities.
See [architecture](architecture.md) for module ownership and the
[confirmation guide](confirmation_benchmark.md) for the research execution contract.

## Scope

`lrdbench` is a manifest-driven research benchmark framework for long-range dependence (LRD)
estimation. Its public contract is the package, YAML manifests, result-store schema, reports,
documentation, and tests tracked in this repository.

The framework supports three benchmark modes:

- `ground_truth`: synthetic records with declared model-relative truth.
- `stress_test`: synthetic records plus controlled contaminations.
- `observational`: user-provided or empirical records without benchmark truth.

The framework does not claim to detect genuine LRD in arbitrary observational data. Results are
valid only relative to the declared source, estimand, metrics, and aggregation rules.

## Design Principles

1. **Explicit estimands**: every estimator declares the quantity it targets.
2. **Mode-aware metrics**: truth-based metrics are not admissible where truth is absent.
3. **Failure transparency**: invalid estimates, crashes, missing uncertainty, and warnings are
   retained as benchmark outputs.
4. **Provenance preservation**: records, estimates, metrics, leaderboards, reports, and exported
   artefacts remain traceable to manifests and software metadata.
5. **Reproducibility first**: a run should be reproducible from a manifest, package version or
   commit, seed policy, estimator configuration, and input data.

## Core Objects

The central schema objects live in `lrdbench.schema`.

- `BenchmarkManifest`: parsed YAML contract for mode, source, estimators, metrics, leaderboards,
  reporting, execution, preprocessing, uncertainty, optional data-driven training, and seeds.
- `SeriesRecord`: materialised time series plus truth, annotations, contamination/preprocessing
  history, and provenance.
- `TruthSpec`: primary or companion model-relative estimand and validity domain.
- `ProvenanceRecord` and `TransformationRecord`: source identity, seeds and transformation history.
- `EstimatorSpec`: manifest-level estimator enrollment metadata and parameter schema.
- `EstimateResult`: estimator output with point estimate, optional uncertainty, validity,
  diagnostics, runtime, and failure reason.
- `MetricSpec` and `MetricValue`: metric contract and computed per-record, aggregate, or
  uncertainty-scoped value.
- `LeaderboardSpec` and `LeaderboardRow`: explicit composite ranking configuration and output.
- `ReportSpec`, `ReportBundle`, and `ArtefactRecord`: report request, generated outputs, and
  artefact metadata.

These dataclasses form the Python API schema, rendered from source in the
[API reference](reference/api.md). The [output contract](output_contract.md) separately defines
the persisted CSV projection; it does not serialize every dataclass field. The frozen research
archive has its own protocol and audit schema.

## Benchmark Loop

The orchestration path is:

1. load and validate the YAML manifest;
2. materialise records from generator grids or observational sources;
3. apply optional preprocessing as independent branches from each source record;
4. prepare optional data-driven estimators, training models when configured;
5. run each enrolled estimator on each retained record, using configured execution/cache settings;
6. evaluate mode-admissible metrics and compute configured leaderboards;
7. stage raw records, estimates, metrics and leaderboard rows in the result store;
8. build reports, collect model and plugin metadata, and finalise the raw CSV store.

`BenchmarkRunner` is the public library execution entry point. The CLI exposes:

```bash
lrdbench validate <manifest>
lrdbench run <manifest>
```

`validate` parses and validates the manifest without generating records or fitting estimators.
`run` performs the full benchmark loop.

## Manifest Contract

A manifest must declare:

- `manifest_id`, `name`, and `mode`;
- `source`;
- one or more `estimators`;
- one or more `metrics`.

Optional blocks:

- `contamination`: required for `stress_test`, rejected for `ground_truth` and `observational` in
  the public runner.
- `preprocessing`: correction operators applied independently to source records, with optional
  retention of raw records via `include_raw` (default true).
- `leaderboards`: composite rankings with weights summing to 1.
- `report`: requested formats, figures, table exports, and export root.
- `execution`: parallelism and optional estimate-cache behavior.
- `uncertainty`: benchmark-level bootstrap intervals and paired estimator differences.
- `ml_training`: run-local supervised training protocol for built-in data-driven estimators.
- `seeds`: reproducibility policy.
- `validation`: parser behavior such as unknown-key rejection.

Unknown top-level keys are rejected by default.
The parser also retains a `segmentation` mapping, but the current runner does not execute a
segmentation stage. Its presence does not request windowing. The JSON manifest schema is an
editor aid; `lrdbench validate` applies the implementation's structural and semantic rules.

`ml_training` is additive and is required for built-in data-driven estimators unless an estimator
entry provides an explicit `params.model_path`. The initial built-in data-driven target is
`hurst_scaling_proxy`; trained model artefacts are written under the run report directory and are
listed in `raw/artefacts.csv`. The reporter index is created before the runner appends these model
artefacts; it is not a complete inventory of the raw store.

## Mode Rules

Ground-truth mode permits truth-based accuracy and uncertainty metrics because each generated
record carries a `TruthSpec`.

Stress-test mode compares clean and contaminated synthetic records. It permits truth-based metrics
where truth remains model-relative, and degradation metrics such as estimate drift and relative
degradation ratio.

Contaminated and corrected records retain the declared latent clean-process target. A fitted
scaling slope on a transformed finite record is not automatically a new process truth. Companion
truths support other declared estimands; classification metrics require `lrd_class` truth.
Legacy null point-threshold exceedance diagnostics are not calibrated-test false-positive rates.

Observational mode has no benchmark truth. It permits stability, sensitivity, validity, runtime,
and truth-free disagreement metrics. Accuracy, coverage, and false-positive claims are not
admissible in this mode.

## Estimator Contract

An estimator implements `BaseEstimator.fit(record) -> EstimateResult` and must:

- use the enrolled `EstimatorSpec`;
- return a finite point estimate or a structured invalid result;
- report runtime when available;
- preserve failure reasons instead of raising through normal benchmark execution;
- declare whether it supports confidence intervals and diagnostics.

Parameter variants are declared in the manifest and materialised as names like
`DFA::short_scales`. The base registry estimator remains `DFA`.

## Metric Contract

Metrics are declared in `lrdbench.metrics_catalog`. Each metric specifies:

- whether truth is required;
- metric kind (scalar or classification);
- admissible benchmark modes;
- aggregation rule;
- optimisation direction;
- nominal levels when relevant.

Coverage-like metrics expand by nominal level. Aggregate rows include stratum metadata, including
balanced-global summaries where applicable.

## Reporting Contract

Reports are audit-oriented by design. A run may emit:

- raw CSV result-store tables;
- summary CSV tables;
- HTML report;
- LaTeX tables;
- figures requested by `report.figure_set`;
- environment and artefact-index metadata.

Report artefacts should not be interpreted without the manifest and metric definitions that
produced them.

## Release Stability

The latest published GitHub release checked on 9 September 2026 is `1.2.1`. The current `main`
includes unreleased benchmark repairs; see [migration notes](migration.md). The output-contract
version is independent of the package version and is included directly from its tracked source
in the [output specification](output_contract.md).

Manifest fields, metric names, output columns, and report artefacts documented here and in the
output contract are stable public surfaces. Breaking changes require an explicit compatibility
plan, migration notes, changelog entries, and release notes.
