# lrdbench documentation

Welcome to the **lrdbench** documentation: a reproducible benchmark framework for long-range dependence estimators on synthetic (ground truth and stress-test) and observational series.

## Hosted site

This book is built with [MkDocs](https://www.mkdocs.org/) and the [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) theme. The canonical hosted copy is intended to live on **[Read the Docs](https://readthedocs.org/)** (see [Read the Docs setup](readthedocs.md)).

## Design authority

The frozen architecture, object contracts, and phased roadmap are in **`lrdbench-design-specifications.pdf`** when that local design file is available; a short traceability note is in **`SPECIFICATION.md`**.

## Repository layout (quick)

- **Runnable suites**: `configs/suites/` (YAML + small data).
- **Python package**: `src/lrdbench/`.
- **Target tree sketch** (aspirational package split): `lrdbench_repo_schema.txt` at the repo root.

## Where to go next

- [Installation](installation.md) — editable install, extras, local `mkdocs serve`.
- [Benchmark protocol](benchmark_protocol.md) — manifest modes, execution block, outputs.
- [Estimator contract](estimator_contract.md) — `BaseEstimator` and `EstimateResult`.
- [Architecture](architecture.md) — how the orchestration pieces fit together.
- [Python API](reference/api.md) — selected autodoc pages.
- [Public release roadmap](public_release_roadmap.md) — phased alpha/beta/v1.0 plan.
