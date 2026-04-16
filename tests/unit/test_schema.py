from __future__ import annotations

import numpy as np

from lrdbench.enums import SourceType
from lrdbench.schema import EstimatorSpec, TruthSpec


def test_truth_spec_immutable() -> None:
    t = TruthSpec(
        process_family="fGn",
        generating_params={"H": 0.5},
        target_estimand="hurst_scaling_proxy",
        target_value=0.5,
    )
    assert t.target_value == 0.5


def test_estimator_spec_requires_target() -> None:
    e = EstimatorSpec(
        name="RS",
        family="time_domain",
        target_estimand="hurst_scaling_proxy",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
    )
    assert e.target_estimand == "hurst_scaling_proxy"


def test_series_record_values_coerced() -> None:
    from lrdbench.schema import SeriesRecord

    r = SeriesRecord(
        record_id="r1",
        values=np.array([1.0, 2.0], dtype=np.float32),
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="test",
    )
    assert r.values.dtype == float
