from __future__ import annotations

import numpy as np

from lrdbench.examples.custom_estimator import build_variance_ratio_estimator
from lrdbench.registries import EstimatorRegistry
from lrdbench.testing import (
    assert_invalid_estimate,
    estimator_spec,
    smoke_fit_estimator,
    synthetic_series_record,
)


def test_custom_estimator_example_smoke_fit() -> None:
    spec = estimator_spec(
        name="VarianceRatio",
        family="external",
        assumptions=("finite_variance",),
        params={"min_n": 32},
    )
    estimator = build_variance_ratio_estimator(spec)

    result = smoke_fit_estimator(
        estimator,
        np.sin(np.linspace(0.0, 12.0, 128)),
        min_value=0.0,
        max_value=1.0,
    )

    assert result.estimator_version == "0.1.0"
    assert result.diagnostics["example_only"] is True


def test_custom_estimator_example_reports_invalid_short_signal() -> None:
    spec = estimator_spec(name="VarianceRatio", params={"min_n": 32})
    estimator = build_variance_ratio_estimator(spec)

    result = estimator.fit(synthetic_series_record(np.arange(8)))

    assert_invalid_estimate(result, reason_contains="insufficient_signal")


def test_custom_estimator_example_registers_with_registry() -> None:
    registry = EstimatorRegistry()
    registry.register("VarianceRatio", build_variance_ratio_estimator)
    spec = estimator_spec(name="VarianceRatio", params={"min_n": 32})

    estimator = registry.get("VarianceRatio")(spec)
    result = estimator.fit(synthetic_series_record(np.linspace(0.0, 1.0, 64)))

    assert result.valid
