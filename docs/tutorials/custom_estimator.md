# Custom Estimator

Custom estimators are enrolled through an `EstimatorRegistry`. This keeps estimator code separate
from the benchmark manifest while preserving metadata about assumptions, target estimand, confidence
interval support, and diagnostics.

## Run the example

```bash
python examples/custom_estimator_benchmark.py
```

The script registers a small variance-ratio example estimator, builds a ground-truth manifest in
Python, and writes a report under `reports/custom_estimator/`.

## Register an estimator

The example uses:

```python
from lrdbench.examples.custom_estimator import build_variance_ratio_estimator
from lrdbench.registries import EstimatorRegistry

registry = EstimatorRegistry()
registry.register("VarianceRatio", build_variance_ratio_estimator)
```

The manifest then refers to the registered name:

```python
{
    "name": "VarianceRatio",
    "family": "external",
    "target_estimand": "hurst_scaling_proxy",
    "assumptions": ["finite_variance", "example_only"],
    "supports_ci": False,
    "supports_diagnostics": True,
}
```

## Run with the custom registry

```python
from pathlib import Path

from lrdbench.manifest import manifest_from_mapping
from lrdbench.runner import BenchmarkRunner

manifest = manifest_from_mapping(custom_estimator_manifest())
out = BenchmarkRunner(estimators=registry).run(manifest, base_dir=Path.cwd())
```

## Metadata expectations

Custom estimator metadata is part of the scientific record. Set these fields carefully:

- `target_estimand`: the quantity the estimator is intended to estimate;
- `assumptions`: stationarity, finite variance, sampling, or other conditions needed for
  interpretation;
- `supports_ci`: whether interval metrics can be evaluated;
- `supports_diagnostics`: whether diagnostic outputs are expected;
- `family`: a coarse grouping used in reports.

If an estimator is exploratory, label it that way in the assumptions or manifest name. Do not rely
on leaderboard rank alone when comparing estimators with different target estimands.
