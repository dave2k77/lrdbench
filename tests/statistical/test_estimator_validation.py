from __future__ import annotations

import numpy as np
import pytest

from lrdbench.defaults import build_default_estimator_registry
from lrdbench.enums import SourceType
from lrdbench.generators._signal import simulate_arfima_zero_d_zero, simulate_fgn
from lrdbench.schema import EstimatorSpec, SeriesRecord


def _record(values: np.ndarray) -> SeriesRecord:
    return SeriesRecord(
        record_id="validation_record",
        values=values,
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="synthetic_validation",
        truth=None,
    )


def _fit_point(
    estimator_name: str,
    values: np.ndarray,
    *,
    target_estimand: str,
    params: dict[str, object],
) -> float:
    registry = build_default_estimator_registry()
    spec = EstimatorSpec(
        name=estimator_name,
        family="validation",
        target_estimand=target_estimand,
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
        parameter_schema=params,
    )
    out = registry.get(estimator_name)(spec).fit(_record(values))
    assert out.valid, (estimator_name, out.failure_reason)
    assert out.point is not None
    return float(out.point)


@pytest.mark.statistical
def test_baseline_hurst_estimators_order_low_and_high_hurst_fgn() -> None:
    estimators = {
        "RS": {"n_bootstrap": 0, "bootstrap_block_len": 32},
        "DFA": {"n_bootstrap": 0, "min_scale": 8, "max_scale": 192, "detrend_order": 1},
        "DMA": {"n_bootstrap": 0, "min_scale": 8, "max_scale": 192},
    }

    for estimator_name, params in estimators.items():
        low_points = [
            _fit_point(
                estimator_name,
                simulate_fgn(1024, 0.35, np.random.default_rng(seed + 10)),
                target_estimand="hurst_scaling_proxy",
                params=params,
            )
            for seed in range(4)
        ]
        high_points = [
            _fit_point(
                estimator_name,
                simulate_fgn(1024, 0.75, np.random.default_rng(seed + 20)),
                target_estimand="hurst_scaling_proxy",
                params=params,
            )
            for seed in range(4)
        ]

        assert float(np.mean(low_points)) < 0.55, estimator_name
        assert float(np.mean(high_points)) > 0.55, estimator_name
        assert float(np.mean(high_points)) - float(np.mean(low_points)) > 0.15, estimator_name


@pytest.mark.statistical
def test_baseline_spectral_estimators_order_short_and_long_memory_arfima() -> None:
    estimators = {
        "GPH": {"n_bootstrap": 0, "bootstrap_block_len": 64},
        "Periodogram": {"n_bootstrap": 0, "bootstrap_block_len": 64},
        "WhittleMLE": {"n_bootstrap": 0, "bootstrap_block_len": 64},
        "ModifiedLocalWhittle": {"n_bootstrap": 0, "bootstrap_block_len": 64},
    }

    for estimator_name, params in estimators.items():
        short_memory_points = [
            _fit_point(
                estimator_name,
                simulate_arfima_zero_d_zero(2048, 0.0, np.random.default_rng(seed + 50)),
                target_estimand="long_memory_parameter",
                params=params,
            )
            for seed in range(4)
        ]
        long_memory_points = [
            _fit_point(
                estimator_name,
                simulate_arfima_zero_d_zero(2048, 0.35, np.random.default_rng(seed + 60)),
                target_estimand="long_memory_parameter",
                params=params,
            )
            for seed in range(4)
        ]

        assert abs(float(np.mean(short_memory_points))) < 0.15, estimator_name
        assert float(np.mean(long_memory_points)) > 0.12, estimator_name
        assert (
            float(np.mean(long_memory_points)) - float(np.mean(short_memory_points)) > 0.12
        ), estimator_name
