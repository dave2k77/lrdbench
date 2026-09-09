# lrdbench documentation

`lrdbench` benchmarks long-range-dependence estimators on synthetic, contaminated and
observational time series. Begin with a small run, inspect failures and uncertainty, then
choose a design suited to the estimand you want to measure.

!!! note "Documentation version"
    These pages describe the source revision built by Read the Docs, with package version 2.0.0.
    Version 2.0 changes estimator behavior and includes the September benchmark repairs.
    See [migration notes](migration.md) before comparing results across revisions.

## Start here

| Your task | Reading path |
| --- | --- |
| Run a first benchmark | [Installation](installation.md) → [Quickstart](tutorials/quickstart.md) → [Read outputs](tutorials/reading_outputs.md) |
| Design a comparison | [Protocol](benchmark_protocol.md) → [Parameters](parameter_glossary.md) → [Interpretation](interpretation_semantics.md) |
| Use empirical data | [Observational tutorial](tutorials/observational_data.md) → [Limitations](known_limitations.md) |
| Reproduce the paper | [Audited confirmation](confirmation_benchmark.md) → [Manuscript workflow](paper_workflow.md) |
| Extend the framework | [Architecture](architecture.md) → [Estimator contract](estimator_contract.md) → [Python API](reference/api.md) |

## Find a reference

The **User guide** groups setup, methods and outputs. **Research** covers the frozen experiment
and publication work. **Development** covers implementation and contributions. **History** retains
older plans; those plans are excluded from search to keep current guidance easier to find.

Use the page table of contents for sections and the search box for estimator names, parameters
or metric names. Start with the [FAQ](faq.md) for common execution problems.

## Sources and contracts

The [design specification](design_specification.md) describes the public framework;
[architecture](architecture.md) maps its stages to modules. The [output specification](output_contract.md)
includes the tracked machine-readable contract. The paper's separate archive is documented in
its [confirmation guide](confirmation_benchmark.md).

Runnable manifests live in `configs/suites/` and implementation in `src/lrdbench/` in the
[repository](https://github.com/dave2k77/lrdbench). The old target-layout sketch is historical.
