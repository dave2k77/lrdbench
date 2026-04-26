# Adding Estimators

This guide shows the shortest path for adding and testing an estimator outside the built-in
registry.

## 1. Implement `BaseEstimator`

Create a class that stores its `EstimatorSpec` and returns `EstimateResult` from `fit`.

```python
from __future__ import annotations

import time
import numpy as np

from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


class MyEstimator(BaseEstimator):
    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        t0 = time.perf_counter()
        x = np.asarray(record.values, dtype=float)
        if x.size < 32:
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self.spec.name,
                point=None,
                runtime_seconds=time.perf_counter() - t0,
                valid=False,
                failure_reason="insufficient_signal_for_my_estimator",
                estimator_version=self.VERSION,
            )
        point = float(np.clip(np.var(x) / (np.var(x) + np.var(np.diff(x))), 0.0, 1.0))
        return EstimateResult(
            record_id=record.record_id,
            estimator_name=self.spec.name,
            point=point,
            runtime_seconds=time.perf_counter() - t0,
            valid=True,
            diagnostics={"example_only": True},
            estimator_version=self.VERSION,
        )


def build_my_estimator(spec: EstimatorSpec) -> MyEstimator:
    return MyEstimator(spec)
```

## 2. Smoke Test The Estimator

```python
import numpy as np

from lrdbench.testing import estimator_spec, smoke_fit_estimator

spec = estimator_spec(
    name="MyEstimator",
    family="external",
    target_estimand="hurst_scaling_proxy",
    assumptions=("finite_variance",),
    params={"min_n": 32},
)

out = smoke_fit_estimator(
    build_my_estimator(spec),
    np.sin(np.linspace(0.0, 12.0, 128)),
    min_value=0.0,
    max_value=1.0,
)
```

Also test invalid paths:

```python
from lrdbench.testing import assert_invalid_estimate, synthetic_series_record

out = build_my_estimator(spec).fit(synthetic_series_record([1.0, 2.0]))
assert_invalid_estimate(out, reason_contains="insufficient_signal")
```

## 3. Register Programmatically

```python
from lrdbench.registries import EstimatorRegistry
from lrdbench.runner import BenchmarkRunner

registry = EstimatorRegistry()
registry.register("MyEstimator", build_my_estimator)

runner = BenchmarkRunner(estimators=registry)
```

The manifest estimator entry should use the same name:

```yaml
estimators:
  - name: MyEstimator
    family: external
    target_estimand: hurst_scaling_proxy
    assumptions: [finite_variance]
    supports_ci: false
    supports_diagnostics: true
    params:
      min_n: 32
```

## 4. Contributor Expectations

Before proposing an estimator for the built-in registry, include:

- a clear target estimand;
- assumptions and operating regime;
- parameter defaults;
- invalid-input behavior;
- diagnostics, if available;
- uncertainty behavior, if available;
- at least one smoke test and one invalid-input test;
- a short note on known failure modes.

For public benchmark comparisons, report the manifest, estimator metadata, output contract version,
and generated `artefacts/artefact_index.csv`.
