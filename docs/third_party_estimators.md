# Third-Party Estimator Workflow

The public CLI currently runs packaged built-in estimators. External estimators are supported
through the programmatic runner by passing a custom `EstimatorRegistry`.

The repository includes a complete example in `examples/custom_estimator_benchmark.py`.

## Run The Example

From a source checkout:

```bash
python examples/custom_estimator_benchmark.py
```

The script:

1. registers `lrdbench.examples.custom_estimator.VarianceRatioEstimator`;
2. builds a small ground-truth manifest in memory;
3. runs `BenchmarkRunner(estimators=registry)`;
4. writes the usual report and raw result store.

Validate the generated output:

```bash
lrdbench validate-output reports/custom_estimator/<run_id>
```

## Manifest Shape

The estimator entry uses the same manifest fields as built-in estimators:

```yaml
estimators:
  - name: VarianceRatio
    family: external
    target_estimand: hurst_scaling_proxy
    assumptions: [finite_variance, example_only]
    supports_ci: false
    supports_diagnostics: true
    params:
      min_n: 32
```

The custom registry must register a builder with the same name:

```python
registry = EstimatorRegistry()
registry.register("VarianceRatio", build_variance_ratio_estimator)
runner = BenchmarkRunner(estimators=registry)
```

## Current Boundary

This workflow is intentionally explicit. It avoids implicit plugin loading and makes third-party
estimator provenance clear in scripts and benchmark submissions. CLI plugin discovery may be added
later, but external estimators can already be benchmarked consistently through this runner path.
