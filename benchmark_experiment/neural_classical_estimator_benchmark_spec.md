# Neural Classical Estimator Benchmark Specification

## Purpose

This document specifies a committee-facing benchmark campaign for evaluating classical long-range
dependence (LRD) and Hurst-style estimators on neural time series.

The central scientific aim is to show, reproducibly and conservatively, how classical estimators can
become unstable, miscalibrated, or failure-prone when applied to neural data whose properties violate
ideal stationary, finite-variance, clean-scaling assumptions. The benchmark is designed to expose:

- point-estimate instability and drift;
- uncertainty and confidence-interval degradation;
- validity failures and missing uncertainty output;
- estimator disagreement across families;
- scale/window/tuning sensitivity;
- failure modes that affect interpretation of neural LRD claims.

The benchmark must not claim that observational neural records contain or do not contain true LRD.
Truth-based conclusions are restricted to synthetic and controlled stress-test tracks. Neural-data
conclusions are observational stability, sensitivity, disagreement, and failure-analysis claims.

## Committee-Facing Claims

The benchmark should support the following claims when the output evidence is consistent with them:

1. Classical LRD estimators behave differently under clean synthetic assumptions than under
   contaminated or neural-like conditions.
2. Contamination can inflate, suppress, or destabilise Hurst-style and long-memory estimates.
3. Estimator-provided confidence intervals can be unavailable, too wide, too narrow, or empirically
   miscalibrated under controlled departures from assumptions.
4. Neural observational records show estimator sensitivity to preprocessing, segmentation,
   scale-window choice, and estimator family.
5. Invalid estimates and missing uncertainty outputs are part of the scientific result and must be
   reported beside accuracy, drift, and stability summaries.

The benchmark should explicitly avoid these claims:

- that a high Hurst-type estimate on neural data proves genuine LRD;
- that observational neural data provide benchmark truth;
- that a leaderboard rank is a universal estimator ranking;
- that all estimators target the same mathematical estimand;
- that synthetic robustness transfers automatically to a particular neural dataset.

## Evidence Tracks

The campaign has three linked tracks.

### Track A: Synthetic Ground-Truth Calibration

Purpose:

- establish clean-regime estimator behaviour under declared truth;
- quantify finite-sample bias, validity, runtime, and confidence-interval behaviour;
- provide the baseline against which stress-test degradation is interpreted.

Recommended source design:

```yaml
mode: ground_truth
source:
  type: generator_grid
  generators:
    - family: fGn
      params:
        H: [0.5, 0.6, 0.7, 0.8]
        n: [512, 1024, 2048, 4096]
        sigma: [1.0]
      replicates: 20
```

Optional secondary synthetic families may be added only if their target truth and estimator
compatibility are explained:

- `ARFIMA` for long-memory parameter estimators;
- `fBm` for Hurst-scaling comparators;
- `fOU` or `MRW` as exploratory non-canonical comparators.

### Track B: Controlled Stress Testing

Purpose:

- quantify how clean synthetic performance changes under controlled neural-like adverse conditions;
- estimate point-estimate drift, degradation, validity collapse, coverage collapse, and disagreement;
- connect synthetic assumption violations to plausible neural-data artefacts.

Recommended source design:

```yaml
mode: stress_test
source:
  type: generator_grid
  generators:
    - family: fGn
      params:
        H: [0.5, 0.6, 0.7, 0.8]
        n: [512, 1024, 2048, 4096]
        sigma: [1.0]
      replicates: 20
```

Recommended contamination families:

| Operator | Parameter grid | Neural interpretation | Expected estimator failure |
| --- | --- | --- | --- |
| `level_shift` | `shift: [0.25, 0.5, 0.75]` | state change, baseline jump, recording transition | inflated persistence, drift, invalid paired comparisons |
| `outliers` | `rate: [0.005, 0.01, 0.05]`, `amplitude: [4.0, 8.0]` | spikes, movement artefacts, amplifier transients | range/scale instability, interval widening, validity collapse |
| `polynomial_trend` | `order: [1, 2]`, `strength: [0.25, 0.5, 1.0]` | slow drift, impedance change, arousal trend | trend mistaken for scale-free structure |
| `heavy_tail_noise` | `df: [3.0, 5.0]`, `scale: [0.5, 1.0]` | bursty noise and finite-sample extremes | unstable slopes, misleading intervals, estimator disagreement |

If low-frequency contamination is not already represented by `polynomial_trend` and `level_shift`,
document it as an extension requirement before implementing a new contamination operator.

### Track C: Observational Neural Stability

Purpose:

- evaluate classical estimators on real LFP/EEG-like neural segments without truth-based claims;
- quantify stability, preprocessing sensitivity, CI width, validity, runtime, and estimator
  disagreement;
- identify which estimators and parameter variants fail or diverge on neural data.

Input format:

```yaml
mode: observational
source:
  type: csv_series_index
  series:
    - record_id: subject01_session01_channelA_conditionX_segment0001
      path: data/neural/subject01_session01_channelA_conditionX_segment0001.csv
      value_column: value
```

Each CSV should contain one numeric time-series column. The specification assumes the data are
already segmented into analysis-ready LFP/EEG-like records.

Required neural-data provenance to record outside or beside the manifest:

- subject/session/channel/condition identifiers;
- sampling rate before and after any resampling;
- filter settings and notch-filter settings;
- artefact rejection rules;
- normalisation or centring rules;
- segment duration and overlap;
- excluded channels or segments;
- missing-data handling;
- whether segments are resting-state, task, stimulation, seizure, sleep-stage, or other condition.

Observational neural conclusions must use only truth-free metrics.

## Estimator Set

The primary benchmark is classical-only. Do not include `MLRandomForest`, `MLSVR`, `MLCNN`, or
`MLLSTM` in the committee benchmark unless a separate appendix is explicitly created for
non-classical comparators.

Recommended primary estimators:

| Estimator | Family | Target estimand | Committee role |
| --- | --- | --- | --- |
| `RS` | temporal | `hurst_scaling_proxy` | classical baseline; finite-sample and contamination sensitivity |
| `DFA` | temporal | `hurst_scaling_proxy` | detrended fluctuation comparator; scale-window sensitivity |
| `DMA` | temporal | `hurst_scaling_proxy` | moving-average fluctuation comparator |
| `AbsoluteMoment` | temporal | `hurst_scaling_proxy` | aggregation-style scaling comparator |
| `Variance` | temporal | `hurst_scaling_proxy` | aggregated variance comparator |
| `VarianceResidual` | temporal | `hurst_scaling_proxy` | residual aggregation comparator |
| `GHE` | geometric | `hurst_scaling_proxy` | increment-scaling comparator |
| `Higuchi` | geometric | `hurst_scaling_proxy` | graph-dimension comparator |
| `WaveletOLS` | wavelet | `hurst_scaling_proxy` | wavelet log-scale comparator |
| `WaveletAbryVeitch` | wavelet | `hurst_scaling_proxy` | exploratory wavelet comparator, label as experimental |
| `WaveletBardet` | wavelet | `hurst_scaling_proxy` | exploratory wavelet comparator, label as experimental |
| `GPH` | spectral | `long_memory_parameter` | low-frequency log-periodogram comparator |
| `Periodogram` | spectral | `long_memory_parameter` | spectral slope comparator |
| `WhittleMLE` | spectral | `long_memory_parameter` | ARFIMA-style likelihood comparator |
| `ModifiedLocalWhittle` | spectral | `long_memory_parameter` | local Whittle comparator |

Do not collapse `hurst_scaling_proxy` and `long_memory_parameter` into a single estimand in the
write-up. For mixed-estimand figures, label the panels or group estimators by target.

## Parameter Variants

The benchmark should include variants for estimators whose conclusions depend on scale windows,
bandwidth, lag ranges, wavelet levels, or detrending order.

Recommended variant design:

- `DFA`: short, balanced, and long scale windows; detrending orders 1 and 2 if runtime allows.
- `DMA`: short, balanced, and long window ranges.
- `GPH` and `Periodogram`: low, medium, and high `m` bandwidth settings; include `taper: none` and
  `taper: cosine` where relevant.
- `ModifiedLocalWhittle`: low, medium, and high bandwidth settings.
- `WaveletOLS`: wavelet family and level-drop variants.
- `RS`: with and without `use_anis_lloyd_correction` for finite-sample sensitivity.

Variants should be analysed with `parameter_variant_sensitivity` and `max_variant_drift`. A high
variant sensitivity on neural records should be treated as evidence that the estimator result is
configuration-dependent, not as a resolved estimate of neural LRD.

## Metrics

### Synthetic Ground-Truth Metrics

Use:

- `bias`;
- `mae`;
- `rmse`;
- `validity_rate`;
- `runtime`;
- `cross_estimator_dispersion`;
- `pairwise_estimator_disagreement`;
- `parameter_variant_sensitivity`;
- `max_variant_drift`;
- `coverage`, `ci_width`, and `coverage_error` when estimators provide CIs.

For short-memory/null regimes, include:

- `false_positive_lrd_rate`.

### Stress-Test Metrics

Use:

- `bias`;
- `mae`;
- `estimate_drift`;
- `relative_degradation_ratio`;
- `validity_rate`;
- `runtime`;
- `cross_estimator_dispersion`;
- `pairwise_estimator_disagreement`;
- `parameter_variant_sensitivity`;
- `max_variant_drift`;
- `coverage`, `ci_width`, `coverage_error`, and `coverage_collapse` when CIs are available.

Headline stress metrics:

- `estimate_drift`;
- `relative_degradation_ratio`;
- `validity_rate`;
- `coverage_collapse`;
- `pairwise_estimator_disagreement`;
- `max_variant_drift`.

### Observational Neural Metrics

Use only truth-free metrics:

- `validity_rate`;
- `runtime`;
- `ci_width`;
- `instability`;
- `preprocessing_sensitivity`;
- `cross_estimator_dispersion`;
- `pairwise_estimator_disagreement`;
- `family_level_disagreement`;
- `parameter_variant_sensitivity`;
- `max_variant_drift`.

Do not use `bias`, `mae`, `rmse`, `coverage`, `coverage_error`, `coverage_collapse`, or
`false_positive_lrd_rate` on observational neural records.

## Benchmark-Level Uncertainty

Enable benchmark-level uncertainty for aggregate committee claims:

```yaml
uncertainty:
  enabled: true
  n_bootstrap: 1000
  ci_levels: [0.95]
  seed: 20260501
  metrics:
    - mae
    - estimate_drift
    - relative_degradation_ratio
    - validity_rate
    - parameter_variant_sensitivity
    - max_variant_drift
  paired: true
  paired_metrics:
    - mae
    - estimate_drift
```

Use estimator-level CIs to evaluate per-record interval behaviour and coverage in synthetic/stress
tracks. Use benchmark-level uncertainty to quantify uncertainty in aggregate benchmark summaries.
Keep these two uncertainty notions separate in the committee document.

## Report Configuration

Recommended report block:

```yaml
report:
  formats: [html, csv, latex]
  export_root: reports/neural_classical
  figure_set:
    - degradation_curve
    - disagreement_heatmap
    - sensitivity_heatmap
    - benchmark_uncertainty_intervals
    - false_positive_lrd
```

The final committee evidence package should include:

- HTML reports for inspection;
- CSV tables for audit and custom plotting;
- LaTeX tables for committee slides or appendix;
- raw records, estimates, metrics, and artefact metadata;
- manifest copies and environment snapshots;
- output-contract validation logs.

## Analysis Plan

### Primary Synthetic Analyses

1. Estimate bias, MAE, RMSE, validity, and runtime by estimator, `H`, and sample size.
2. Compare empirical coverage and CI width for estimators that emit confidence intervals.
3. Examine false-positive LRD rates at `H = 0.5`.
4. Report estimator disagreement and variant sensitivity under clean conditions.

### Primary Stress-Test Analyses

1. For each contamination family, plot estimate drift by severity and estimator family.
2. Report relative degradation ratios by estimator and contamination.
3. Quantify validity collapse and missing uncertainty by estimator.
4. Quantify coverage collapse where CIs are available.
5. Identify contamination types that cause family-level disagreement.
6. Compare whether larger `n` reduces instability or merely changes its expression.

### Primary Neural Analyses

1. Summarise estimator validity, CI width, instability, runtime, and preprocessing sensitivity across
   neural segments.
2. Stratify by available neural metadata: condition, channel/region, subject/session, segment length,
   and preprocessing pipeline.
3. Identify neural segments where estimator families disagree most strongly.
4. Identify estimators whose outputs depend heavily on scale/window variants.
5. Map failure modes to neural-data properties, such as artefact burden, nonstationarity, or segment
   length.

## Required Figures

For committee presentation, prepare these figures:

1. Clean synthetic accuracy panel: estimator error versus `H` and `n`.
2. Stress degradation panel: drift or degradation ratio by contamination family and severity.
3. CI behaviour panel: coverage, coverage collapse, and CI width for estimators with intervals.
4. Failure map: invalid estimates and missing uncertainty by estimator and stratum.
5. Estimator disagreement heatmap: pairwise disagreement across classical families.
6. Scale/window sensitivity heatmap: variant sensitivity for tuning-dependent estimators.
7. Neural observational panel: instability, preprocessing sensitivity, and disagreement across neural
   segments or conditions.

## Failure Mode Reporting

Use the existing failure taxonomy:

- `insufficient_signal`;
- `estimator_exception`;
- `missing_uncertainty`;
- `invalid_fit`.

Every result summary must include validity and missing-uncertainty context. Do not report clean
aggregate accuracy or stability values without also checking whether they were computed from a small
valid subset.

Report at least:

- invalid estimate count and rate by estimator and stratum;
- missing CI count and rate where CI metrics are requested;
- failure concentration by contamination type and neural segment metadata;
- raw estimator-specific `failure_reason` examples for major failure clusters.

## Execution Protocol

Use the local development environment:

```powershell
.venv\Scripts\lrdbench.exe validate <manifest>
.venv\Scripts\lrdbench.exe run <manifest> --dry-run --no-plugins
.venv\Scripts\lrdbench.exe run <manifest> --no-plugins
.venv\Scripts\lrdbench.exe validate-output <report_root>\<run_id>
```

Use `--no-plugins` for the committee benchmark unless a third-party estimator appendix is added.

Recommended execution settings:

```yaml
execution:
  max_workers: 4
  estimate_cache_dir: .lrdbench_cache/neural_classical
  cache_read: true
  cache_write: true
```

Use trusted local caches only. Cache paths are pickle-backed and should not be shared as untrusted
artefacts.

## Acceptance Criteria

The benchmark is ready for committee review when all of the following are true:

1. All manifests validate successfully.
2. Dry-run previews record expected grid sizes and estimator counts.
3. Full runs complete without unhandled exceptions.
4. `validate-output` passes for every final run.
5. Reports include estimator metadata, failures, disagreement, sensitivity, benchmark uncertainty,
   and raw artefact exports.
6. Synthetic/stress results include validity and CI/missing-uncertainty context beside accuracy and
   drift metrics.
7. Neural observational results avoid truth-based claims and report stability, sensitivity,
   disagreement, and failures only.
8. Committee figures are generated from archived CSV outputs, not manually copied values.
9. The final write-up includes manifest IDs, software version or commit hash, seeds, output contract
   version, and environment snapshots.

## Suggested Deliverables

- `benchmark_experiment/neural_classical_estimator_benchmark_spec.md`: this specification.
- `configs/suites/neural_classical_ground_truth.yaml`: clean synthetic calibration manifest.
- `configs/suites/neural_classical_stress.yaml`: controlled contamination manifest.
- `configs/suites/neural_classical_observational.yaml`: CSV-backed neural observational manifest.
- `reports/neural_classical/<run_id>/`: final run outputs.
- `benchmark_experiment/neural_classical_committee_summary.md`: final result narrative after runs.

## Interpretation Guardrails

Use conservative wording:

- "Estimator instability under declared conditions" rather than "the estimator is invalid."
- "Observational neural stability/disagreement" rather than "neural LRD truth."
- "Model-relative synthetic evidence" rather than "universal proof."
- "Confidence interval behaviour under benchmark assumptions" rather than "guaranteed uncertainty
  validity."

The central committee message should be that classical LRD estimators can be highly assumption-,
preprocessing-, contamination-, and tuning-sensitive on neural time series, and that failure/missing
uncertainty outputs materially affect the interpretation of any reported Hurst or long-memory
estimate.
