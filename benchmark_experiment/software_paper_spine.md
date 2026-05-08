# Software Paper Spine

This outline is aimed at a JOSS-style or SoftwareX-style paper describing `lrdbench` as reusable
research software.

## Working Title

`lrdbench`: A Reproducible Benchmark Framework for Long-Range Dependence Estimator Evaluation

## Core Claim

`lrdbench` provides a manifest-driven, reproducible, extensible framework for evaluating
long-range dependence estimators across canonical synthetic, contaminated synthetic, and
observational settings with transparent reporting, uncertainty handling, and failure analysis.

## Target Venues

- JOSS: concise software paper focused on need, functionality, reuse, and archival metadata.
- SoftwareX: longer software description with architecture, implementation detail, examples, and
  reuse scenarios.

## Abstract

Briefly cover:

- the problem: LRD estimator comparison is fragmented and hard to reproduce;
- the software: a Python framework for manifest-driven benchmark execution;
- the modes: ground truth, stress testing, and observational workflows;
- the contribution: standard contracts for estimators, metrics, outputs, provenance, and reports;
- the intended users: time-series researchers, method developers, and applied scientists.

## 1. Statement of Need

Explain:

- why LRD estimation matters in scientific time-series analysis;
- why estimator comparison is difficult;
- why classical estimators are sensitive to assumptions, sample size, contamination, and tuning;
- why reproducible benchmark infrastructure is needed separately from a single empirical study.

Key points:

- many estimators target related but non-identical quantities;
- observational data rarely provide benchmark truth;
- contamination and nonstationarity can create misleading apparent LRD;
- existing comparisons are often script-specific and hard to reproduce.

## 2. Software Overview

Describe the user-facing workflow:

1. write or select a YAML manifest;
2. validate the manifest;
3. run the benchmark;
4. inspect generated reports and raw result stores;
5. validate output contract;
6. reuse outputs for analysis, leaderboards, or supplementary material.

Mention CLI examples:

```bash
lrdbench list-suites
lrdbench validate public_small_canonical_ground_truth
lrdbench run public_small_canonical_ground_truth
lrdbench validate-output reports/public_small/<run_id>
```

## 3. Benchmark Modes

### Ground-Truth Mode

Synthetic records with declared model-relative truth. Supports accuracy, coverage, uncertainty,
validity, and runtime metrics.

### Stress-Test Mode

Synthetic clean records paired with contaminated records. Supports degradation, drift, robustness,
validity collapse, coverage collapse, and false-positive style analyses where appropriate.

### Observational Mode

User-provided or empirical time series without benchmark truth. Supports truth-free stability,
sensitivity, disagreement, validity, and runtime analyses.

## 4. Architecture

Describe the main components:

- manifest parser and validator;
- synthetic generators;
- contamination operators;
- estimator registry and estimator interface;
- benchmark runner;
- metric catalog;
- leaderboard module;
- reporter and result store;
- output contract validator.

Suggested figure:

```text
YAML manifest -> records -> estimators -> metrics -> leaderboards -> reports/result store
```

## 5. Extensibility

Explain how users add:

- custom estimators;
- estimator parameter variants;
- custom manifests;
- observational CSV inputs;
- report formats and figures where supported.

Reference the estimator contract:

- `BaseEstimator`;
- `EstimatorMetadata`;
- `EstimateResult`;
- `lrdbench.testing` utilities.

## 6. Reproducibility and Provenance

Cover:

- manifest-driven runs;
- seeded synthetic records;
- environment capture;
- output contract;
- raw CSV result store;
- artefact index;
- version and contract reporting;
- cache behavior and reproducibility caveats.

Important files:

- `manifest/environment.json`;
- `artefacts/artefact_index.csv`;
- `raw/records.csv`;
- `raw/estimates.csv`;
- `raw/metrics.csv`.

## 7. Reporting and Interpretation

Summarise available outputs:

- HTML reports;
- CSV summary tables;
- raw result store;
- LaTeX tables;
- figures;
- failure summaries;
- benchmark uncertainty tables;
- estimator disagreement tables;
- scale/window sensitivity tables.

Emphasise:

- leaderboards are configured summaries, not universal rankings;
- invalid estimates and missing uncertainty are preserved;
- observational mode does not support truth-based accuracy claims.

## 8. Quality Control

Describe tests and checks:

- unit tests for schema, metrics, generators, estimators, contaminations, reporting;
- integration tests for benchmark modes;
- statistical sanity checks for generators and estimators;
- output contract validation;
- MkDocs strict build;
- packaging checks.

Mention stable release state:

- current public package release: `1.0.2`;
- public output contract: `1.0.0`;
- no DOI attached yet unless archival release is added before submission.

## 9. Example Use Case

Use a compact example rather than a full benchmark paper:

- run `public_small_canonical_ground_truth`;
- show that outputs include accuracy, validity, and report artefacts;
- mention how a user would extend to stress testing or third-party estimator comparison.

For SoftwareX, include screenshots or a small output table. For JOSS, keep this brief.

## 10. Availability

Include:

- repository URL;
- package distribution URL if published;
- documentation URL;
- license;
- supported Python versions;
- citation file;
- archived release DOI if available before submission.

## 11. Limitations

State clearly:

- the framework is not a clinical or diagnostic tool;
- synthetic truth is model-relative;
- observational workflows are truth-free;
- current estimator implementations include baseline and approximate methods;
- benchmark conclusions depend on manifest design;
- result caches should only be used from trusted locations.

## 12. Future Work

Possible items:

- additional estimator families;
- more generator families;
- richer observational workflows;
- plugin mechanism for external estimators;
- archived benchmark result bundles;
- DOI-backed release artefacts;
- larger canonical benchmark campaigns.

## 13. Suggested Figures and Tables

Figures:

- architecture diagram;
- manifest-to-report workflow;
- extensibility workflow diagram;
- example HTML report screenshot;
- example stress-test degradation plot.

Tables:

- supported modes and admissible metric classes;
- bundled estimator families and target estimands;
- output artefacts and their purpose;
- reproducibility metadata captured per run.

## 14. Minimal JOSS Structure

For JOSS, compress to:

1. Summary;
2. Statement of Need;
3. Functionality;
4. Reproducibility and Extensibility;
5. Availability;
6. Acknowledgements;
7. References.

## 15. Minimal SoftwareX Structure

For SoftwareX, expand to:

1. Motivation and significance;
2. Software description;
3. Architecture;
4. Functionality;
5. Illustrative examples;
6. Impact;
7. Limitations and future work;
8. Availability and dependencies;
9. References.
