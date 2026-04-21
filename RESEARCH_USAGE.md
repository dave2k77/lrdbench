# Research Usage Policy

## Scope

`lrdbench` is a research benchmark framework for the evaluation of long-range dependence (LRD) estimators across three benchmark settings:

1. **Ground-truth mode**: canonical synthetic time series with explicitly declared target truth.
2. **Stress-test mode**: synthetic time series subjected to controlled contaminations and adverse conditions.
3. **Observational mode**: real-world or user-provided time series for which no benchmark ground truth is available.

The framework is intended for methodological benchmarking, estimator comparison, robustness analysis, and reproducible research workflows.

It is **not** a clinical decision tool, a diagnostic device, or a validator of “true LRD” in arbitrary real-world signals.

---

## Core Principles

### 1. Explicit estimands
Every estimator enrolled in the framework must declare the quantity it is intended to estimate. The framework does not assume that all methods target the same mathematical object.

### 2. Mode-aware evaluation
Metrics must be interpreted according to benchmark mode. Truth-based metrics are admissible only where compatible benchmark truth exists.

### 3. Failure transparency
Estimator crashes, invalid outputs, numerical instability, missing uncertainty outputs, and warnings must be recorded explicitly. Silent failure suppression is not acceptable.

### 4. Provenance preservation
Every benchmark result must be traceable to a manifest, a source specification, estimator metadata, and software versioning information.

### 5. Reproducibility
Published results should be reproducible from the benchmark manifest, software version, seed policy, and exported result artefacts.

---

## What the Framework Is Designed to Support

`lrdbench` is designed to support the following research activities:

- reproducible comparison of LRD estimators on canonical benchmark processes;
- robustness studies under nonstationarity, heavy-tailed noise, artefacts, level shifts, outliers, and related adverse conditions;
- uncertainty-aware benchmarking, including interval width and empirical coverage where applicable;
- failure analysis and validity-rate analysis;
- enrolment and comparison of new estimators against baseline and classical methods;
- observational stability and sensitivity studies on biomedical or other empirical time series.

---

## What the Framework Does **Not** Claim

Use of `lrdbench` does **not** by itself establish any of the following:

- that an estimator identifies the “true” mechanism generating scale-free or long-memory-like behaviour in a real-world signal;
- that a high Hurst-type estimate on observational data implies genuine long-range dependence;
- that performance in one benchmark regime transfers automatically to another;
- that confidence intervals reported by an estimator are valid outside the assumptions under which they were derived;
- that a leaderboard rank is a universal statement of estimator superiority.

Benchmark results must always be interpreted relative to the declared benchmark mode, estimand compatibility, data-generating assumptions, and metric definitions.

---

## Benchmark Modes and Interpretation Rules

## Ground-truth mode

Ground-truth mode supports truth-based metrics such as:

- bias;
- mean absolute error;
- root mean squared error;
- empirical coverage;
- calibration error;
- validity rate;
- runtime.

Interpretation in this mode should focus on whether an estimator behaves well under benchmark conditions close to its intended theory regime.

## Stress-test mode

Stress-test mode supports degradation-oriented metrics such as:

- estimate drift;
- relative degradation ratio;
- validity collapse;
- coverage collapse;
- robustness-oriented leaderboard summaries.

Interpretation in this mode should focus on how estimator performance changes under controlled departures from ideal assumptions.

## Observational mode

Observational mode supports stability-oriented metrics such as:

- within-record instability;
- preprocessing sensitivity;
- resampling variability;
- observational failure rate;
- runtime and validity summaries.

In observational mode, truth-based accuracy claims are not admissible.

---

## Reporting Standards

Any publication, preprint, report, or presentation using `lrdbench` should report at least the following:

- benchmark mode;
- manifest identifier or manifest file;
- software version;
- estimator names and declared target estimands;
- source specification;
- contamination and preprocessing settings where applicable;
- metric definitions;
- aggregation rules;
- seed policy;
- failure and missing-output handling policy.

If a leaderboard is reported, the raw component metrics used to construct it should also be reported.

---

## Recommended Scientific Claims

The following kinds of claims are generally defensible when supported by benchmark evidence:

- an estimator performs accurately on a declared synthetic benchmark family;
- an estimator exhibits degraded accuracy or calibration under specified contamination classes;
- an estimator is comparatively more or less stable under declared observational perturbations;
- an estimator has lower failure rate or better validity properties on a specified benchmark suite;
- a proposed method outperforms a baseline under the metric and aggregation rules explicitly stated.

---

## Claims That Require Careful Qualification

The following claims require strong qualification and should not be made casually:

- that an estimator “detects true LRD” in observational biomedical data;
- that an estimator “separates nonstationarity from genuine LRD” unless the relevant benchmark explicitly tests identifiability under controlled confounding;
- that a benchmark result establishes universal superiority across all data regimes;
- that interval estimates remain calibrated outside the regime for which they were constructed.

---

## Estimator Enrolment Requirements

A new estimator should not be benchmarked unless it provides:

- a declared estimator name;
- a declared target estimand;
- implementation version information;
- parameter metadata;
- a structured output compatible with the framework;
- explicit failure signalling;
- a short description of assumptions or operating conditions.

Where possible, contributors should also provide:

- methodological references;
- uncertainty output behaviour;
- expected input requirements;
- known failure modes.

---

## Reproducibility Requirements

A benchmark result should be considered reproducible only if the following are available:

- the benchmark manifest;
- software version or commit hash;
- seed policy;
- estimator configuration;
- metric and leaderboard configuration;
- exported result store or equivalent machine-readable artefacts.

---

## Limitations

Users should be aware of the following limitations:

1. Different estimators may target related but non-identical quantities.
2. Synthetic benchmark truth is model-relative and must not be confused with universal truth.
3. Stress-test results depend on contamination design and severity specification.
4. Observational stability does not imply correctness.
5. A low runtime does not imply scientific adequacy.
6. A composite leaderboard score is a summary convenience, not a substitute for metric-level interpretation.

---

## Responsible Use

Users are encouraged to use `lrdbench` in a way that is:

- explicit about assumptions;
- conservative in interpretation;
- transparent about estimator failure;
- careful about estimand mismatch;
- honest about uncertainty.

The framework is especially well suited to testing the hypothesis that estimators built around second-order theory may become unstable or miscalibrated outside their intended stationary finite-variance regime. However, such conclusions should emerge from the benchmark evidence itself rather than being assumed in advance.

---

## Citation Guidance

If you use `lrdbench` in academic work, please cite:

1. the software release used;
2. any associated benchmark or methods paper, where applicable;
3. any estimator-specific references relevant to the methods benchmarked.

---

## Contact and Contribution

Contributions that improve estimator coverage, benchmark rigour, reporting transparency, or reproducibility are welcome. Contributors should ensure that any new method or benchmark component is documented clearly and integrated through the framework’s declared schema and interface contracts.