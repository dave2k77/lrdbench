from __future__ import annotations

import numpy as np
import pytest

from lrdbench.schema import EstimateResult
from lrdbench.testing import (
    assert_invalid_estimate,
    assert_valid_estimate,
    estimator_spec,
    smoke_fit_estimator,
    synthetic_series_record,
)


class ConstantEstimator:
    def fit(self, record):
        return EstimateResult(record_id=record.record_id, estimator_name="Constant", point=0.5)


def test_synthetic_series_record_builds_minimal_record() -> None:
    rec = synthetic_series_record([1.0, 2.0, 3.0], record_id="r")
    assert rec.record_id == "r"
    assert rec.values.tolist() == [1.0, 2.0, 3.0]
    assert rec.truth is None


def test_estimator_spec_helper_sets_external_defaults() -> None:
    spec = estimator_spec(params={"window": 16})
    assert spec.name == "CandidateEstimator"
    assert spec.family == "external"
    assert spec.parameter_schema == {"window": 16}


def test_assert_valid_estimate_checks_bounds() -> None:
    result = EstimateResult(record_id="r", estimator_name="E", point=0.2, valid=True)
    assert_valid_estimate(result, min_value=0.0, max_value=1.0)
    with pytest.raises(AssertionError):
        assert_valid_estimate(result, min_value=0.3)


def test_assert_invalid_estimate_checks_reason() -> None:
    result = EstimateResult(
        record_id="r",
        estimator_name="E",
        point=None,
        valid=False,
        failure_reason="insufficient_signal_for_e",
    )
    assert_invalid_estimate(result, reason_contains="insufficient_signal")


def test_smoke_fit_estimator_runs_candidate() -> None:
    out = smoke_fit_estimator(ConstantEstimator(), np.arange(64), min_value=0.0, max_value=1.0)
    assert out.point == 0.5
