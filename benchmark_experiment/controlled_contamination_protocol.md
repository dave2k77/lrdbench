# Controlled Contamination Benchmark Protocol

This runbook describes how to prepare, run, and analyse a large benchmark intended to quantify how
classical long-range dependence (LRD) estimators destabilise under controlled contamination.

The experiment should be interpreted as model-relative. It can show how estimators behave under
declared generators, sample sizes, contamination operators, severity settings, and estimator
configuration choices. It should not be presented as a universal claim about arbitrary empirical
signals.

## 1. Define the Experimental Claim

State the claim before running the benchmark:

> For classical LRD estimators, how much do point estimates, validity, interval calibration, and
> estimator rankings degrade under controlled nonstationarity, outliers, trends, and heavy-tailed
> noise, relative to clean synthetic records with known truth?

Record the intended interpretation limits:

- claims are relative to the manifest;
- truth-based claims are relative to synthetic generator truth;
- stress-test conclusions depend on contamination design and severity;
- observational-data conclusions are outside the scope of this experiment unless a separate
  observational manifest is added.

## 2. Start From the Existing Stress Manifest

Use the stable public-medium stress suite as the baseline:

```bash
configs/suites/public_medium_stress_contamination.yaml
```

For the benchmark-paper comparison that includes data-driven baselines, use the tracked experiment
template:

```bash
benchmark_experiment/data_driven_stress_contamination.yaml
```

This manifest keeps the stress-test design but adds:

- `ml_training` for run-local supervised training;
- `MLRandomForest` and `MLSVR` feature-based baselines;
- `MLCNN` and `MLLSTM` neural baselines;
- model artefact export under `reports/benchmark_experiment/data_driven_stress/<run_id>/ml_models/`.

Copy it instead of editing the public reference suite:

```bash
cp configs/suites/public_medium_stress_contamination.yaml \
  configs/suites/large_stress_contamination.yaml
```

The copied manifest should remain in `mode: stress_test`.

## 3. Expand the Experimental Grid

Expand the source grid deliberately.

Recommended memory regimes:

- short-memory boundary: `H: 0.5`;
- weak LRD: `H: 0.6`;
- moderate LRD: `H: 0.7`;
- strong LRD: `H: 0.8`.

Recommended sample sizes:

```yaml
n: [512, 1024, 2048, 4096]
```

Recommended replicate count:

```yaml
replicates: 20
```

Use more replicates, such as `50`, when runtime and storage are acceptable.

Expand contamination severity:

- `level_shift`: multiple shift magnitudes;
- `outliers`: multiple rates and amplitudes;
- `polynomial_trend`: multiple orders and strengths;
- `heavy_tail_noise`: multiple degrees of freedom and scales.

The final grid should be large enough for stable aggregate summaries, but still stratified enough
that every result can be interpreted by generator, true `H`, sample size, contamination operator,
severity, estimator, and estimator variant.

## 4. Select Estimators

List available estimators:

```bash
lrdbench list-estimators
```

Include the classical estimators relevant to the claim, for example:

- `RS`;
- `DFA`;
- `DMA`;
- `GHE`;
- `GPH`;
- `ModifiedLocalWhittle`;
- `WaveletOLS`.

To compare against data-driven approaches, include the built-in supervised baselines:

- `MLRandomForest`;
- `MLSVR`;
- `MLCNN`;
- `MLLSTM`.

Install dependencies according to the estimator set:

```bash
pip install -e ".[ml,reports]"          # RF/SVR only
pip install -e ".[data-driven,reports]" # RF/SVR/CNN/LSTM
```

On some Linux platforms, the default PyTorch wheel may pull CUDA packages. If the experiment host
does not need GPU support, install a CPU-only PyTorch build before installing/running the `nn`
baselines, or run an RF/SVR-only manifest by removing `MLCNN` and `MLLSTM`.

Review estimator assumptions before finalising the set:

```bash
docs/estimator_status.md
```

Include only estimators whose target estimand and assumptions are meaningful for the synthetic
regimes in the manifest.

For data-driven estimators, make the training distribution explicit in the manifest. The
benchmark-experiment template uses a separate `ml_training.source` grid and repeats the declared
contaminations inside `ml_training.contamination` so supervised models can learn from the same
artefact classes being tested.

```yaml
ml_training:
  enabled: true
  target_estimand: hurst_scaling_proxy
  validation_fraction: 0.2
  source:
    type: generator_grid
    generators:
      - family: fGn
        params:
          H: [0.35, 0.45, 0.55, 0.65, 0.75, 0.85]
          n: [512, 1024, 2048]
          sigma: [1.0]
        replicates: 20
  contamination:
    include_clean: true
    operators:
      - name: level_shift
        params:
          shift: [0.25, 0.5, 0.75]
```

Archive `ml_models/training_summary.json` and the model artefact hashes with the final run outputs.

## 5. Add Scale and Window Variants

For scale-dependent estimators, add variants so the benchmark can distinguish estimator-level
instability from tuning sensitivity.

Example:

```yaml
estimators:
  - name: DFA
    family: temporal
    target_estimand: hurst_scaling_proxy
    supports_ci: false
    params:
      min_scale: 8
      max_scale: 256
      detrend_order: 1
    variants:
      - name: short_scales
        params:
          min_scale: 8
          max_scale: 64
      - name: medium_scales
        params:
          min_scale: 16
          max_scale: 256
      - name: long_scales
        params:
          min_scale: 64
          max_scale: 512
```

Variants are materialised as names such as `DFA::short_scales`.

## 6. Choose Metrics

Include metrics that expose destabilisation directly:

- `bias`;
- `mae`;
- `rmse`;
- `estimate_drift`;
- `relative_degradation_ratio`;
- `validity_rate`;
- `runtime`;
- `cross_estimator_dispersion`;
- `pairwise_estimator_disagreement`;
- `family_level_disagreement`;
- `parameter_variant_sensitivity`;
- `max_variant_drift`.

Include interval metrics when estimators provide confidence intervals:

```yaml
- name: coverage
  levels: [0.95]
- name: ci_width
  levels: [0.95]
- name: coverage_error
  levels: [0.95]
- name: coverage_collapse
  levels: [0.95]
```

For short-memory/null regimes, consider `false_positive_lrd_rate` if the manifest and metric
configuration define the relevant threshold.

Headline destabilisation metrics should be:

- `estimate_drift`;
- `relative_degradation_ratio`;
- `validity_rate`;
- `coverage_collapse`;
- `pairwise_estimator_disagreement`;
- `max_variant_drift`.

## 7. Enable Benchmark-Level Uncertainty

Use benchmark uncertainty for aggregate claims.

Recommended block:

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
    - pairwise_estimator_disagreement
    - max_variant_drift
  paired: true
  paired_metrics:
    - estimate_drift
    - relative_degradation_ratio
    - mae
```

Paired bootstrap comparisons are important because estimators are evaluated on the same records.

## 8. Configure Execution

Use parallel execution and a trusted estimate cache for large runs:

```yaml
execution:
  max_workers: 8
  estimate_cache_dir: reports/cache/large_stress_contamination
  cache_read: true
  cache_write: true
```

For strict from-scratch reproduction checks, disable cache reads or use an empty cache directory:

```yaml
execution:
  cache_read: false
  cache_write: false
```

Only use estimate caches from trusted locations because the cache stores pickled Python objects.

## 9. Validate Before Running

Validate the manifest:

```bash
lrdbench validate configs/suites/large_stress_contamination.yaml
lrdbench validate benchmark_experiment/data_driven_stress_contamination.yaml
```

Estimate the run size:

```text
clean_records = generator combinations * replicates
contaminated_records = clean_records * contamination combinations
records = clean_records + contaminated_records
fits = records * enrolled estimators including variants
```

If the number of fits is larger than expected, reduce the grid before running.

## 10. Run a Pilot

Create a pilot manifest before the full run:

- fewer `H` values;
- fewer `n` values;
- `replicates: 2`;
- same contamination structure;
- same estimators;
- same output formats.

Run and validate the pilot:

```bash
lrdbench run configs/suites/large_stress_contamination_pilot.yaml
lrdbench validate-output reports/<export_root>/<run_id>
```

Inspect:

- `tables/failures.csv`;
- `tables/failure_map.csv`;
- `tables/stress_metrics.csv`;
- `tables/benchmark_uncertainty.csv`;
- `tables/estimator_disagreement.csv`;
- `tables/scale_window_sensitivity.csv`;
- `html/report.html`.

Scale up only after the pilot produces complete and interpretable outputs.

## 11. Run the Full Benchmark

Run the full manifest:

```bash
lrdbench run configs/suites/large_stress_contamination.yaml
```

Record the printed `run_id`.

Validate the output:

```bash
lrdbench validate-output reports/<export_root>/<run_id>
```

Archive the following:

- exact manifest YAML;
- package version or Git commit;
- `manifest/environment.json`;
- `artefacts/artefact_index.csv`;
- `raw/records.csv`;
- `raw/estimates.csv`;
- `raw/metrics.csv`;
- all `tables/*.csv`;
- `html/report.html`;
- generated figures and LaTeX tables when requested.

## 12. Analyse in Layers

Start with high-level summaries:

- `tables/leaderboard.csv`;
- `tables/stress_metrics.csv`;
- `tables/failures.csv`;
- `tables/benchmark_uncertainty.csv`;
- `tables/estimator_disagreement.csv`;
- `tables/scale_window_sensitivity.csv`.

Core analysis questions:

- Which contamination produces the largest estimate drift?
- Does drift increase monotonically with severity?
- Are failures concentrated in specific estimators or regimes?
- Does apparent accuracy survive once validity rate is considered?
- Do estimator rankings change between clean and contaminated records?
- Are scale/window variants more unstable than estimator families?
- Are confidence intervals missing, too wide, or miscalibrated?
- Do short-memory/null settings produce false LRD under contamination?

## 13. Stratify the Results

Do not report only balanced-global summaries. Stratify by:

- contamination operator;
- severity;
- true `H`;
- sample size `n`;
- estimator;
- estimator family;
- scale/window variant;
- clean versus contaminated record pairing.

Most useful plots and tables:

- drift by contamination type and severity;
- relative degradation by estimator;
- validity collapse by estimator and contamination;
- false-positive LRD rate under `H=0.5`;
- pairwise estimator disagreement heatmap;
- variant sensitivity heatmap;
- benchmark uncertainty intervals for headline metrics.

## 14. Interpret Conservatively

Prefer claims of this form:

> Under declared fGn regimes with controlled level shifts, outliers, polynomial trends, and
> heavy-tail noise, estimator X showed mean drift of Y with 95% benchmark CI Z, while estimator Y
> remained more stable in these strata.

Avoid universal claims such as:

> Estimator X is unreliable.

The supported claim is regime-specific and manifest-specific.

## 15. Archive and Report

Create a result archive containing:

- manifest;
- package version or commit hash;
- environment file;
- output contract version;
- raw result store;
- summary tables;
- generated figures;
- notes describing intended interpretation.

When writing the result summary, report:

- manifest ID;
- package version or commit;
- run ID;
- generator families and parameter grid;
- contamination operators and severity grid;
- estimator set and variants;
- seed policy;
- benchmark uncertainty settings;
- validation status from `lrdbench validate-output`.
