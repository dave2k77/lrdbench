from __future__ import annotations

import numpy as np

from lrdbench.enums import SourceType
from lrdbench.execution import estimate_cache_key
from lrdbench.schema import EstimatorSpec, SeriesRecord


def _dummy_record(record_id: str, values: list[float]) -> SeriesRecord:
    return SeriesRecord(
        record_id=record_id,
        values=np.asarray(values, dtype=float),
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="test",
        truth=None,
    )


def _dummy_espec(name: str = "RS", **params: object) -> EstimatorSpec:
    return EstimatorSpec(
        name=name,
        family="time_domain",
        target_estimand="hurst_scaling_proxy",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
        parameter_schema=params,
    )


def test_estimate_cache_key_stable_for_identical_inputs() -> None:
    r1 = _dummy_record("a", [0.0, 1.0, -1.0])
    r2 = _dummy_record("a", [0.0, 1.0, -1.0])
    e = _dummy_espec(n_bootstrap=10)
    assert estimate_cache_key(r1, e) == estimate_cache_key(r2, e)


def test_estimate_cache_key_differs_when_params_change() -> None:
    r = _dummy_record("a", [0.0, 1.0])
    e1 = _dummy_espec(n_bootstrap=10)
    e2 = _dummy_espec(n_bootstrap=11)
    assert estimate_cache_key(r, e1) != estimate_cache_key(r, e2)
