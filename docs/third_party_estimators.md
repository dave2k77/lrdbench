# Third-Party Estimator Workflow

External estimators are supported **both** through automatic plugin discovery and through the
programmatic runner by passing a custom `EstimatorRegistry`.

The repository includes a complete programmatic example in `examples/custom_estimator_benchmark.py`.

## Quickstart: Plugin Discovery

1. Create a Python module (or package) that defines `ENTRY_POINTS`:

```python
# my_estimator.py
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord

__version__ = "1.0.0"

def _build_my_estimator(spec: EstimatorSpec) -> BaseEstimator:
    class MyEstimator(BaseEstimator):
        @property
        def spec(self) -> EstimatorSpec:
            return spec

        def fit(self, record: SeriesRecord) -> EstimateResult:
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=spec.name,
                point=0.7,
                valid=True,
                estimator_version="1.0.0",
            )

    return MyEstimator()

ENTRY_POINTS = {
    "MyEstimator": _build_my_estimator,
}
```

2. Expose it via an environment variable:

```bash
# Option A: importable module
export LRD_BENCH_ESTIMATOR_PLUGIN="my_package.my_estimator"

# Option B: direct file path
export LRD_BENCH_ESTIMATOR_PLUGIN_PATH="/path/to/my_estimator.py"

# Colon-separated list for multiple plugins
export LRD_BENCH_ESTIMATOR_PLUGIN="pkg1.estimators:pkg2.estimators"
```

3. Run the benchmark normally:

```bash
lrdbench run my_manifest.yaml
```

The plugin is discovered automatically and the estimator becomes available under the name declared
in `ENTRY_POINTS`.

## Inspection

List discovered plugins without running a benchmark:

```bash
lrdbench list-plugins
```

Show only built-in estimators (skip plugin discovery):

```bash
lrdbench list-estimators --no-plugins
```

## Programmatic Path

If you prefer explicit registration without environment variables:

```python
from lrdbench.examples.custom_estimator import build_variance_ratio_estimator
from lrdbench.registries import EstimatorRegistry
from lrdbench.runner import BenchmarkRunner

registry = EstimatorRegistry()
registry.register("VarianceRatio", build_variance_ratio_estimator)
runner = BenchmarkRunner(estimators=registry, discover_plugins=False)
```

## Safety

Plugin loading is safe by default: a broken plugin cannot crash the benchmark loop. Import failures
and invalid `ENTRY_POINTS` are captured as structured warnings in `BenchmarkRunOutput.plugin_provenance`.
Built-in estimators always take precedence when a plugin name collides with a built-in registry entry.

## Data-Driven Built-ins

Built-in data-driven baselines (`MLRandomForest`, `MLSVR`, `MLCNN`, `MLLSTM`) are not third-party
estimators. Use the packaged registry names with a manifest `ml_training` block instead. See
[Data-driven estimators](data_driven_estimators.md).
