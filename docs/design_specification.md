# Design Specification

This page is the tracked clean-clone design authority for `lrdbench`. It replaces the earlier
local-only PDF dependency for public development. If an older local PDF exists, treat it as
historical design context unless this page explicitly says otherwise.

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
  reporting, execution, uncertainty, and seeds.
- `SeriesRecord`: materialised time series plus truth, annotations, contamination/preprocessing
  history, and provenance.
- `EstimatorSpec`: manifest-level estimator enrollment metadata and parameter schema.
- `EstimateResult`: estimator output with point estimate, optional uncertainty, validity,
  diagnostics, runtime, and failure reason.
- `MetricSpec` and `MetricValue`: metric contract and computed per-record, aggregate, or
  uncertainty-scoped value.
- `LeaderboardSpec` and `LeaderboardRow`: explicit composite ranking configuration and output.
- `ReportSpec`, `ReportBundle`, and `ArtefactRecord`: report request, generated outputs, and
  artefact metadata.

These objects are intentionally simple dataclasses. Their fields form the current public schema
surface until a release-candidate schema freeze says otherwise.

## Benchmark Loop

The orchestration path is:

1. load and validate the YAML manifest;
2. materialise records from generator grids or observational sources;
3. run each enrolled estimator on each record;
4. evaluate mode-admissible metrics;
5. compute configured leaderboards;
6. persist a CSV result store;
7. build requested HTML, CSV, LaTeX, and figure artefacts.

`BenchmarkRunner` is the execution entry point. The CLI exposes:

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
  this release.
- `leaderboards`: composite rankings with weights summing to 1.
- `report`: requested formats, figures, table exports, and export root.
- `execution`: parallelism and optional estimate-cache behavior.
- `uncertainty`: benchmark-level bootstrap intervals and paired estimator differences.
- `seeds`: reproducibility policy.
- `validation`: parser behavior such as unknown-key rejection.

Unknown top-level keys are rejected by default.

## Mode Rules

Ground-truth mode permits truth-based accuracy and uncertainty metrics because each generated
record carries a `TruthSpec`.

Stress-test mode compares clean and contaminated synthetic records. It permits truth-based metrics
where truth remains model-relative, and degradation metrics such as estimate drift and relative
degradation ratio.

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

The project is currently alpha-stage. Manifest fields, metric names, output columns, and report
artefacts are documented public surfaces, but they are not frozen for v1.0 yet. Breaking changes
must be reflected in the changelog and release notes.
