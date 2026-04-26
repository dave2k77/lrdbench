# Estimator Contract

Estimators implement `lrdbench.interfaces.BaseEstimator`.

```python
class BaseEstimator:
    @property
    def spec(self) -> EstimatorSpec: ...

    def fit(self, record: SeriesRecord) -> EstimateResult: ...
```

An estimator receives an `EstimatorSpec` at construction time and returns one `EstimateResult` for
each `SeriesRecord`.

## Required Metadata

Each enrolled estimator must declare:

- `name`: stable estimator name used in manifests and result tables.
- `family`: method family, for example `temporal`, `spectral`, `wavelet`, `geometric`, or
  `external`.
- `target_estimand`: the quantity being estimated, such as `hurst_scaling_proxy` or
  `long_memory_parameter`.
- `assumptions`: short strings describing operating assumptions.
- `supports_ci`: whether estimator-level intervals may be emitted.
- `supports_diagnostics`: whether diagnostics are meaningful.
- `parameter_schema`: manifest parameters passed to the implementation.
- `version`: optional implementation version.

## Fit Results

`fit(record)` should return `EstimateResult` with:

- `record_id` and `estimator_name`;
- `point` as a finite float when valid, otherwise `None`;
- `valid=True` for usable estimates;
- `valid=False` with `failure_reason` for short, degenerate, unsupported, or failed fits;
- `runtime_seconds` when available;
- `diagnostics` for structured implementation details;
- `bootstrap_cis` or `ci_low`/`ci_high` when estimator-level uncertainty is supported.

Do not raise for ordinary invalid inputs such as short signals. Return an invalid
`EstimateResult`. Use exception failure reasons only for unexpected implementation failures:

```text
exception:<ExceptionType>:<message>
```

## Minimal Example

The package includes an executable example in `lrdbench.examples.custom_estimator`.

```python
from lrdbench.examples.custom_estimator import build_variance_ratio_estimator
from lrdbench.testing import estimator_spec, smoke_fit_estimator

spec = estimator_spec(
    name="VarianceRatio",
    family="external",
    assumptions=("finite_variance",),
    params={"min_n": 32},
)
estimator = build_variance_ratio_estimator(spec)
result = smoke_fit_estimator(estimator, [0.1, 0.2, 0.4, 0.8] * 16, min_value=0.0, max_value=1.0)
```

This example statistic is for integration demonstration only. It is not a validated LRD estimator.

## Registry Enrolment

Estimators are enrolled through an `EstimatorRegistry` builder:

```python
from lrdbench.examples.custom_estimator import build_variance_ratio_estimator
from lrdbench.registries import EstimatorRegistry

registry = EstimatorRegistry()
registry.register("VarianceRatio", build_variance_ratio_estimator)
```

Programmatic benchmark runs can pass a custom registry:

```python
from lrdbench.runner import BenchmarkRunner

runner = BenchmarkRunner(estimators=registry)
```

The public CLI currently exposes built-in estimators. Third-party CLI/plugin discovery is planned
for the external contributor beta.

## Test Utilities

`lrdbench.testing` provides small helpers for estimator authors:

- `synthetic_series_record(values)`;
- `estimator_spec(...)`;
- `assert_valid_estimate(result, min_value=..., max_value=...)`;
- `assert_invalid_estimate(result, reason_contains=...)`;
- `smoke_fit_estimator(estimator, values, min_value=..., max_value=...)`.

Use these helpers in contributor tests before running full benchmark manifests.
