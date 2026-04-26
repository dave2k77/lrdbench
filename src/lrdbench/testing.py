from __future__ import annotations

import numpy as np

from lrdbench.enums import SourceType
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def synthetic_series_record(
    values: np.ndarray | list[float],
    *,
    record_id: str = "test_record",
    source_name: str = "test",
) -> SeriesRecord:
    return SeriesRecord(
        record_id=record_id,
        values=np.asarray(values, dtype=float),
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name=source_name,
        truth=None,
    )


def estimator_spec(
    *,
    name: str = "CandidateEstimator",
    family: str = "external",
    target_estimand: str = "hurst_scaling_proxy",
    assumptions: tuple[str, ...] = (),
    supports_ci: bool = False,
    supports_diagnostics: bool = True,
    params: dict[str, object] | None = None,
    version: str | None = None,
) -> EstimatorSpec:
    return EstimatorSpec(
        name=name,
        family=family,
        target_estimand=target_estimand,
        assumptions=assumptions,
        supports_ci=supports_ci,
        supports_diagnostics=supports_diagnostics,
        parameter_schema={} if params is None else dict(params),
        version=version,
    )


def assert_valid_estimate(
    result: EstimateResult,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> None:
    assert result.valid, result.failure_reason
    assert result.point is not None
    value = float(result.point)
    if min_value is not None:
        assert value >= min_value
    if max_value is not None:
        assert value <= max_value


def assert_invalid_estimate(result: EstimateResult, *, reason_contains: str | None = None) -> None:
    assert not result.valid
    assert result.point is None
    assert result.failure_reason is not None
    if reason_contains is not None:
        assert reason_contains in result.failure_reason


def smoke_fit_estimator(
    estimator: BaseEstimator,
    values: np.ndarray | list[float],
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> EstimateResult:
    result = estimator.fit(synthetic_series_record(values))
    assert_valid_estimate(result, min_value=min_value, max_value=max_value)
    return result
