# lrdbench

**A reproducible benchmark framework for evaluating long-range dependence estimators on canonical, contaminated, and observational time series.**

**Documentation:** [lrdbench.readthedocs.io](https://lrdbench.readthedocs.io/) (built with MkDocs; configure your Read the Docs project slug if it differs).

`lrdbench` is a research-oriented benchmarking framework for studying the behaviour of long-range dependence (LRD) estimators across three distinct settings:

- **ground-truth mode** for canonical synthetic time series with declared target truth;
- **stress-test mode** for synthetic time series under controlled contamination;
- **observational mode** for biomedical or user-provided time series without benchmark truth.

The framework is designed to support:

- rigorous comparison of classical and new LRD estimators;
- uncertainty-aware benchmarking, including empirical interval coverage where applicable;
- robustness analysis under heavy tails, nonstationarity, artefacts, level shifts, outliers, polynomial trends, and low-frequency contamination;
- transparent failure analysis and validity-rate reporting;
- manifest-driven, provenance-complete, reproducible benchmark execution.

---

## Why this project exists

There is currently no widely adopted, comprehensive, reproducible benchmark specifically designed for long-range dependence estimation that simultaneously addresses:

- canonical synthetic processes with known targets;
- contamination-induced estimator instability;
- uncertainty quantification and interval coverage;
- observational biomedical time series with no benchmark truth;
- extensible enrolment of new estimators under a common interface.

`lrdbench` aims to fill that gap.

It is especially intended to support the careful evaluation of the hypothesis that many classical second-order LRD estimators behave well in their intended stationary finite-variance regime, but become unstable, miscalibrated, or non-identifiable under nonstationarity, heavy-tailed fluctuations, artefacts, and other out-of-regime conditions.

---

## Scope

`lrdbench` is a **research benchmark framework**. It is **not**:

- a clinical decision system;
- a diagnostic tool;
- a guarantee of “true LRD” in arbitrary empirical signals;
- a universal ranking oracle for all estimators in all regimes.

Benchmark results must always be interpreted in light of:

- the declared benchmark mode;
- the target estimand;
- the source specification;
- the contamination design;
- the metric definitions;
- the aggregation and leaderboard rules.

See [`RESEARCH_USAGE.md`](RESEARCH_USAGE.md) for the full policy.

---

## Core features

### Benchmark modes
- **Ground-truth mode**
  - bias, MAE, RMSE
  - empirical coverage
  - interval width
  - validity rate
  - runtime and efficiency

- **Stress-test mode**
  - estimate drift
  - degradation ratios
  - validity collapse
  - coverage collapse
  - robustness leaderboards

- **Observational mode**
  - instability across windows
  - preprocessing sensitivity
  - resampling variability
  - failure analysis
  - stability leaderboards

### Supported data sources
- implemented synthetic generators:
  - fGn
  - fBm
  - ARFIMA(0,d,0)
  - MRW
  - fOU
- contaminated synthetic pipelines
- custom CSV datasets
- future observational/API-based datasets

### Reporting
- HTML reports
- Markdown reports
- CSV exports
- Parquet result stores
- JSON metadata exports
- LaTeX tables for publication workflows

### Extensibility
- pluggable estimator interface
- manifest-driven benchmark runs
- explicit estimator metadata and estimand declarations
- registry-based component enrolment

---

## Design principles

`lrdbench` is built around a few non-negotiable principles:

1. **Explicit estimands**  
   Every estimator must declare the quantity it is intended to estimate.

2. **Mode-aware evaluation**  
   Truth-based metrics are not used where truth does not exist.

3. **Failure transparency**  
   Invalid outputs, crashes, and missing uncertainty are recorded explicitly.

4. **Provenance preservation**  
   Every benchmark result is traceable to a manifest, source, estimator configuration, and software version.

5. **Reproducibility first**  
   A benchmark run should be reproducible from a single manifest plus the relevant package version and data sources.

---

## Installation

### Core installation

```bash
pip install lrdbench
