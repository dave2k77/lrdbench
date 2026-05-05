# Data-Driven Estimators

`lrdbench` includes experimental supervised baselines for comparing classical LRD estimators with
data-driven approaches under the same benchmark protocol.

Built-in data-driven estimators:

- `MLRandomForest`: scikit-learn random forest regressor.
- `MLSVR`: scikit-learn support vector regressor.
- `MLCNN`: PyTorch 1D convolutional neural-network regressor.
- `MLLSTM`: PyTorch LSTM regressor.

All four currently target `hurst_scaling_proxy`. They are baselines, not reference-grade LRD
estimators. Interpret their results relative to the manifest-declared training distribution.

## Installation

Feature-based ML baselines:

```bash
pip install "lrdbench[ml,reports]"
```

Neural-network baselines:

```bash
pip install "lrdbench[nn,reports]"
```

From a source checkout:

```bash
pip install -e ".[ml,reports]"
```

The packaged `smoke_data_driven` suite uses `MLRandomForest` and `MLSVR`, so it does not require
PyTorch.

## Programmatic example

The repository includes a complete script:

```bash
python examples/data_driven_baseline_benchmark.py
```

It builds a small stress-test manifest in memory, trains `MLRandomForest` and `MLSVR`, benchmarks
them against `RS`, and prints the report and model artefact paths.

## Run the smoke suite

From an installed package:

```bash
lrdbench validate smoke_data_driven
lrdbench run smoke_data_driven
```

From a source checkout:

```bash
lrdbench validate configs/suites/smoke_data_driven.yaml
lrdbench run configs/suites/smoke_data_driven.yaml
```

The run writes trained model artefacts under:

```text
reports/<run_id>/ml_models/
```

The raw artefact table records the model files and training summary:

```text
reports/<run_id>/raw/artefacts.csv
```

## Manifest shape

Data-driven estimators use the same `estimators` list as classical estimators, plus a top-level
`ml_training` block:

```yaml
ml_training:
  enabled: true
  target_estimand: hurst_scaling_proxy
  validation_fraction: 0.25
  source:
    type: generator_grid
    generators:
      - family: fGn
        params:
          H: [0.35, 0.5, 0.65, 0.8]
          n: [128]
          sigma: [1.0]
        replicates: 2
  contamination:
    include_clean: true
    operators:
      - name: level_shift
        params:
          shift: [0.2]

estimators:
  - name: RS
    family: time_domain
    target_estimand: hurst_scaling_proxy
    supports_ci: false
    supports_diagnostics: true
    params:
      n_bootstrap: 0
  - name: MLRandomForest
    family: data_driven
    target_estimand: hurst_scaling_proxy
    assumptions: [trained_on_manifest_synthetic_distribution]
    supports_ci: false
    supports_diagnostics: true
    params:
      n_estimators: 100
      random_state: 7
      max_lag: 16
```

`ml_training.source` is independent of the benchmark evaluation source. The runner trains models
once per run, writes model artefacts, injects the trained model paths into estimator metadata, and
then executes the normal `(record, estimator)` fit loop.

## Pretrained artefacts

For frozen model comparisons, provide a model path directly in estimator params and omit
`ml_training`:

```yaml
estimators:
  - name: MLRandomForest
    family: data_driven
    target_estimand: hurst_scaling_proxy
    supports_ci: false
    supports_diagnostics: true
    params:
      model_path: reports/example/ml_models/MLRandomForest.pkl
```

Use only trusted model artefacts. The scikit-learn baselines use pickle-compatible artefacts.

## Interpretation

Data-driven baselines can be useful for testing whether supervised models learn robustness patterns
that classical estimators miss under declared contaminations. They also introduce new risks:

- training distribution shift;
- leakage if training and evaluation grids are not kept distinct;
- overfitting on small training grids;
- hyperparameter sensitivity;
- no estimator-level confidence intervals in the initial implementation.

When reporting these results, include the benchmark manifest, `ml_training` block, estimator
metadata table, and `ml_models/training_summary.json`.
