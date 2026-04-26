from __future__ import annotations

import numpy as np

from lrdbench.defaults import build_default_estimator_registry
from lrdbench.enums import SourceType
from lrdbench.generators._signal import simulate_arfima_zero_d_zero, simulate_fgn
from lrdbench.schema import EstimatorSpec, SeriesRecord


def _record(values: np.ndarray, record_id: str = "t0") -> SeriesRecord:
    return SeriesRecord(
        record_id=record_id,
        values=values,
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="test",
        truth=None,
    )


def test_default_registry_lists_new_estimators() -> None:
    reg = build_default_estimator_registry()
    names = set(reg.list())
    for name in (
        "DFA",
        "DMA",
        "Higuchi",
        "GHE",
        "Periodogram",
        "WhittleMLE",
        "ModifiedLocalWhittle",
        "WaveletAbryVeitch",
        "WaveletBardet",
        "WaveletOLS",
        "WaveletJensen",
        "WaveletWhittle",
    ):
        assert name in names


def test_fgn_hurst_estimators_near_truth() -> None:
    rng = np.random.default_rng(42)
    n = 4096
    h_true = 0.7
    x = simulate_fgn(n, h_true, rng, sigma=1.0)
    rec = _record(x)
    reg = build_default_estimator_registry()
    for est_name, target in (
        ("DFA", "hurst_scaling_proxy"),
        ("DMA", "hurst_scaling_proxy"),
        ("WaveletOLS", "hurst_scaling_proxy"),
    ):
        spec = EstimatorSpec(
            name=est_name,
            family="temporal" if est_name != "WaveletOLS" else "wavelet",
            target_estimand=target,
            assumptions=(),
            supports_ci=True,
            supports_diagnostics=True,
            parameter_schema={"n_bootstrap": 30, "bootstrap_block_len": 64},
        )
        out = reg.get(est_name)(spec).fit(rec)
        assert out.valid, (est_name, out.failure_reason)
        assert out.point is not None
        assert abs(float(out.point) - h_true) < 0.45


def test_higuchi_and_ghe_fit_valid() -> None:
    rng = np.random.default_rng(11)
    x = simulate_fgn(2048, 0.6, rng, sigma=1.0)
    rec = _record(x)
    reg = build_default_estimator_registry()
    for est_name in ("Higuchi", "GHE"):
        spec = EstimatorSpec(
            name=est_name,
            family="geometric",
            target_estimand="hurst_scaling_proxy",
            assumptions=(),
            supports_ci=True,
            supports_diagnostics=True,
            parameter_schema={"n_bootstrap": 12, "bootstrap_block_len": 64},
        )
        out = reg.get(est_name)(spec).fit(rec)
        assert out.valid, (est_name, out.failure_reason)
        assert out.point is not None
        assert 0.0 < float(out.point) < 1.0


def test_arfima_d_estimators_finite() -> None:
    rng = np.random.default_rng(7)
    d_true = 0.25
    x = simulate_arfima_zero_d_zero(2048, d_true, rng, sigma=1.0)
    rec = _record(x)
    reg = build_default_estimator_registry()
    for est_name in ("Periodogram", "WhittleMLE", "ModifiedLocalWhittle"):
        spec = EstimatorSpec(
            name=est_name,
            family="spectral",
            target_estimand="long_memory_parameter",
            assumptions=(),
            supports_ci=True,
            supports_diagnostics=True,
            parameter_schema={"n_bootstrap": 20, "bootstrap_block_len": 64},
        )
        out = reg.get(est_name)(spec).fit(rec)
        assert out.valid, (est_name, out.failure_reason)
        assert out.point is not None
        assert -0.49 < float(out.point) < 0.49


def test_wavelet_estimators_return_bounded_points_on_fgn() -> None:
    rng = np.random.default_rng(17)
    x = simulate_fgn(2048, 0.7, rng, sigma=1.0)
    rec = _record(x)
    reg = build_default_estimator_registry()
    params_by_name = {
        "WaveletAbryVeitch": {"n_bootstrap": 0, "wavelet": "db2", "j_drop_low": 1, "j_drop_high": 1},
        "WaveletBardet": {"n_bootstrap": 0, "wavelet": "db2", "j_drop_low": 1, "j_drop_high": 1},
        "WaveletOLS": {"n_bootstrap": 0, "wavelet": "db2", "j_drop_low": 1, "j_drop_high": 1},
        "WaveletJensen": {
            "n_bootstrap": 0,
            "wavelet": "db2",
            "fine_band": (2, 4),
            "coarse_band": (4, 6),
        },
        "WaveletWhittle": {"n_bootstrap": 0, "wavelet": "db2", "j_drop_low": 1, "j_drop_high": 1},
    }
    for est_name, params in params_by_name.items():
        spec = EstimatorSpec(
            name=est_name,
            family="wavelet",
            target_estimand="hurst_scaling_proxy",
            assumptions=(),
            supports_ci=False,
            supports_diagnostics=True,
            parameter_schema=params,
        )
        out = reg.get(est_name)(spec).fit(rec)
        assert out.valid, (est_name, out.failure_reason)
        assert out.point is not None
        assert 0.0 < float(out.point) < 1.0


def test_wavelet_estimators_report_invalid_for_short_signal() -> None:
    rec = _record(np.arange(32, dtype=float))
    reg = build_default_estimator_registry()
    for est_name in ("WaveletAbryVeitch", "WaveletBardet", "WaveletOLS", "WaveletWhittle"):
        spec = EstimatorSpec(
            name=est_name,
            family="wavelet",
            target_estimand="hurst_scaling_proxy",
            assumptions=(),
            supports_ci=False,
            supports_diagnostics=True,
            parameter_schema={"n_bootstrap": 0, "wavelet": "db2"},
        )
        out = reg.get(est_name)(spec).fit(rec)
        assert not out.valid
        assert out.point is None
        assert out.failure_reason is not None
