# Benchmark Paper Spine

This outline is for a results-focused benchmark paper using `lrdbench` to quantify how classical
long-range dependence (LRD) estimators behave under controlled contamination.

## Working Title

Classical Long-Range Dependence Estimators Destabilise Under Controlled Contamination: A
Reproducible Benchmark Study

## Core Claim

Classical LRD estimators can produce unstable, biased, or misleading outputs when their idealised
assumptions are violated by controlled nonstationarity, outliers, trends, and heavy-tailed noise.
The paper quantifies this effect across estimator families, memory regimes, sample sizes, and
contamination severities.

## Paper Type

This is a scientific benchmark/results paper, not primarily a software paper.

The software paper should argue that `lrdbench` is useful infrastructure. This benchmark paper
should use that infrastructure to make empirical claims about estimator behaviour.

## Abstract

Cover:

- the scientific problem: LRD estimation is sensitive and widely used;
- the gap: robustness under realistic contamination is not systematically quantified;
- the method: reproducible benchmark over synthetic clean and contaminated records;
- the estimators: classical time-domain, spectral, and wavelet families, with data-driven
  RF/SVR/CNN/LSTM baselines as a supervised comparator;
- the main outcomes: drift, degradation, validity collapse, uncertainty behaviour, disagreement,
  and false-positive behaviour;
- the conclusion: estimator outputs must be interpreted conditionally on assumptions, contamination,
  and tuning.

## 1. Introduction

Motivate:

- LRD and Hurst-style estimation are common in time-series analysis;
- many scientific applications use finite, noisy, contaminated, or nonstationary records;
- classical estimators often assume stationarity, finite variance, scale regimes, or clean
  self-similar structure;
- contamination can mimic or obscure LRD;
- users need quantitative guidance, not only theoretical warnings.

End with contributions:

- a controlled contamination benchmark across estimator families;
- paired clean-versus-contaminated comparisons;
- stratified results by contamination type, severity, memory regime, and sample size;
- uncertainty-aware summaries and failure analysis;
- reproducible manifests and result artefacts.

## 2. Background

Explain enough for readers:

- long-range dependence and Hurst-style quantities;
- distinction between estimands such as Hurst scaling proxy and memory parameter;
- classical estimator families:
  - rescaled range;
  - DFA;
  - DMA;
  - spectral/log-periodogram methods;
- local Whittle-style methods;
- wavelet log-scale methods;
- data-driven supervised baselines:
  - random forest regression;
  - support vector regression;
  - convolutional neural networks;
  - LSTM recurrent neural networks;
- why estimator assumptions matter.

Avoid overclaiming that all estimators target exactly the same estimand.

## 3. Benchmark Design

Describe the manifest-driven design:

- clean synthetic records with declared truth;
- contaminated records paired to clean records;
- same estimators run on both clean and contaminated records;
- mode-specific metrics;
- benchmark-level uncertainty;
- raw outputs retained for audit.
- run-local supervised training for data-driven baselines via the manifest `ml_training` block.

State that the benchmark is model-relative and controlled, not observational proof.

## 4. Synthetic Data Regimes

Define the generator grid:

- generator family, such as fGn;
- true memory regimes, for example `H = 0.5, 0.6, 0.7, 0.8`;
- sample sizes, for example `n = 512, 1024, 2048, 4096`;
- replicate count;
- random seed policy.

Explain why these regimes matter:

- `H = 0.5` tests short-memory boundary and false-positive behaviour;
- larger `H` values test increasing LRD strength;
- larger `n` values test whether instability diminishes or persists with sample size.

## 5. Contamination Design

Describe each contamination operator:

- level shifts;
- outliers;
- polynomial trends;
- heavy-tail noise.

For each one, specify:

- parameter grid;
- severity interpretation;
- scientific motivation;
- expected way it could destabilise estimators.

Suggested table:

| Operator | Parameters | Interpretation | Expected failure mode |
| --- | --- | --- | --- |
| level shift | shift magnitude | abrupt nonstationarity | inflated apparent persistence |
| outliers | rate, amplitude | sparse artefacts | unstable range or scale estimates |
| polynomial trend | order, strength | smooth nonstationarity | trend mistaken for scaling |
| heavy-tail noise | df, scale | finite-sample extremes | interval and slope instability |

## 6. Estimators

List included estimators and variants:

- estimator name;
- family;
- target estimand;
- assumptions;
- parameter settings;
- uncertainty support;
- variants, if any.

Make estimator assumptions visible. This protects the paper from implying that all failures are
bugs rather than assumption violations.

For data-driven estimators, also report:

- the exact `ml_training` grid;
- whether contaminations were included in training;
- train/validation split;
- training summary metrics;
- model artefact hashes.

The benchmark-experiment template manifest is:

```text
benchmark_experiment/data_driven_stress_contamination.yaml
```

## 7. Metrics

Primary metrics:

- `estimate_drift`;
- `relative_degradation_ratio`;
- `mae`;
- `rmse`;
- `validity_rate`;
- `coverage_collapse`;
- `pairwise_estimator_disagreement`;
- `parameter_variant_sensitivity`;
- `max_variant_drift`;
- `false_positive_lrd_rate`, where appropriate.

Secondary metrics:

- runtime;
- confidence interval width;
- coverage error;
- failure and missing-output rates.

Define each metric in plain language and point to the exact manifest or metric catalog for formal
definitions.

## 8. Statistical Analysis Plan

Analyse:

- balanced-global summaries;
- stratum-level summaries;
- paired clean-versus-contaminated differences;
- bootstrap confidence intervals for aggregate metrics;
- paired bootstrap intervals for estimator differences;
- interaction patterns between contamination severity, sample size, and true `H`.

Pre-specify headline comparisons:

- drift by contamination operator and estimator;
- degradation by severity;
- validity collapse by estimator;
- disagreement between estimator families;
- false-positive behaviour at `H = 0.5`;
- tuning sensitivity for scale/window variants.

## 9. Reproducibility Protocol

Report:

- `lrdbench` version or Git commit;
- manifest ID;
- exact manifest file;
- for data-driven runs, exact `ml_training` block and model artefact hashes;
- random seed policy;
- package environment;
- output contract version;
- run ID;
- output validation status.

Keep:

- `manifest/environment.json`;
- `artefacts/artefact_index.csv`;
- raw records, estimates, and metrics;
- summary tables;
- generated figures.

## 10. Results

Suggested subsection order:

### 10.1 Overall Destabilisation

Balanced-global drift, degradation, validity, and disagreement.

### 10.2 Contamination-Specific Effects

Separate results for level shifts, outliers, polynomial trends, and heavy-tail noise.

### 10.3 Severity Response

Does destabilisation increase with contamination severity?

### 10.4 Dependence on Sample Size and True Memory

Does larger `n` help? Are weak-LRD regimes more vulnerable than strong-LRD regimes?

### 10.5 Estimator Family Differences

Compare time-domain, spectral, and wavelet families without treating the leaderboard as a universal
ranking.

### 10.6 Uncertainty and Calibration

Analyse missing intervals, coverage collapse, interval width, and coverage error.

### 10.7 Tuning Sensitivity

Report scale/window variant sensitivity and maximum variant drift.

### 10.8 Failure Analysis

Report invalid estimates, missing metric values, warnings, and concentrated failure strata.

## 11. Discussion

Interpret:

- which contamination types are most damaging;
- which estimators are most fragile under which regimes;
- whether some estimators degrade gracefully;
- whether tuning choices dominate estimator-family differences;
- why false-positive LRD under contamination matters;
- what this means for applied LRD studies.

Keep claims conditional:

- under the declared synthetic regimes;
- for the specific estimators and parameter settings;
- relative to model truth and benchmark metrics.

## 12. Practical Recommendations

Potential recommendations:

- do not report a single LRD estimate without estimator assumptions and diagnostics;
- use multiple estimator families where possible;
- report sensitivity to scale/window choices;
- stress-test estimators against plausible contaminations;
- report validity and failure rates;
- avoid interpreting observational estimates as truth-based accuracy;
- treat apparent LRD under trends, shifts, or heavy tails with caution.

## 13. Limitations

State:

- synthetic regimes are not exhaustive;
- contamination operators are simplified abstractions;
- estimator implementation choices affect results;
- finite grids cannot prove universal robustness or fragility;
- observational data are not directly addressed unless added separately;
- benchmark metrics are summaries, not replacements for theoretical analysis.

## 14. Conclusions

Return to the main finding:

- controlled contamination can materially destabilise classical LRD estimator outputs;
- the magnitude and form of destabilisation depend on estimator family, sample size, memory regime,
  contamination type, and tuning;
- reproducible stress testing should be part of responsible LRD estimator use.

## 15. Suggested Figures

High-priority figures:

- drift by estimator and contamination operator;
- degradation curves by contamination severity;
- pairwise estimator disagreement heatmap;
- false-positive LRD rate under `H = 0.5`;
- validity collapse by estimator and contamination;
- benchmark uncertainty intervals for headline metrics;
- scale/window sensitivity heatmap.

## 16. Suggested Tables

Tables:

- benchmark grid;
- estimator metadata and assumptions;
- contamination parameter grid;
- headline metric summaries with confidence intervals;
- failure-rate summary;
- leaderboard components, if used;
- reproducibility metadata.

## 17. Supplementary Material

Include:

- exact manifests;
- full raw CSV result store;
- full summary tables;
- output contract validation logs;
- environment JSON;
- additional stratified figures;
- sensitivity analyses with alternative grids or estimator variants.
