from __future__ import annotations

import numpy as np

from lrdbench.defaults import build_default_estimator_registry
from lrdbench.enums import SourceType
from lrdbench.estimators.data_driven import feature_vector, fixed_length_sequence
from lrdbench.estimators.geometric import _ghe_hurst
from lrdbench.estimators.spectral import _log_periodogram_regression_d, _log_periodogram_slope_d
from lrdbench.estimators.temporal import _anis_lloyd_expected_rs, _rs_hurst_proxy
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
        "AbsoluteMoment",
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
        "MLRandomForest",
        "MLSVR",
        "MLCNN",
        "MLLSTM",
        "Variance",
        "VarianceResidual",
    ):
        assert name in names


def test_data_driven_estimators_report_missing_optional_dependency() -> None:
    reg = build_default_estimator_registry()
    rec = _record(np.sin(np.linspace(0.0, 8.0, 128)))
    for est_name, package in (
        ("MLRandomForest", "scikit-learn"),
        ("MLSVR", "scikit-learn"),
        ("MLCNN", "torch"),
        ("MLLSTM", "torch"),
    ):
        spec = EstimatorSpec(
            name=est_name,
            family="data_driven",
            target_estimand="hurst_scaling_proxy",
            assumptions=(),
            supports_ci=False,
            supports_diagnostics=True,
            parameter_schema={"model_path": "/tmp/missing-model"},
        )
        out = reg.get(est_name)(spec).fit(rec)
        if out.valid:
            continue
        assert out.point is None
        assert out.failure_reason is not None
        assert out.failure_reason.startswith(
            f"missing_optional_dependency:{package}"
        ) or out.failure_reason.startswith("exception:")


def test_data_driven_preprocessing_is_fixed_shape_and_finite() -> None:
    x = np.sin(np.linspace(0.0, 12.0, 127))
    feats = feature_vector(x, max_lag=8)
    seq = fixed_length_sequence(x, length=64)
    assert feats.shape == (37,)
    assert seq.shape == (64,)
    assert np.all(np.isfinite(feats))
    assert np.all(np.isfinite(seq))


def test_rs_uses_multiscale_slope_not_full_record_ratio() -> None:
    rng = np.random.default_rng(44)
    x = simulate_fgn(2048, 0.7, rng, sigma=1.0)
    h = _rs_hurst_proxy(x, min_scale=16, max_scale=256, scale_ratio=1.5)
    assert h is not None
    full_record_ratio = _rs_hurst_proxy(x, min_scale=2048, max_scale=2048, scale_ratio=1.5)
    assert full_record_ratio is None
    assert 0.45 < h < 0.9


def test_rs_anis_lloyd_correction_reduces_white_noise_bias() -> None:
    expected = _anis_lloyd_expected_rs(64)
    assert expected > np.sqrt(64.0)

    rng = np.random.default_rng(45)
    x = rng.normal(size=2048)
    uncorrected = _rs_hurst_proxy(x, min_scale=16, max_scale=256, scale_ratio=1.5)
    corrected = _rs_hurst_proxy(
        x,
        use_correction=True,
        min_scale=16,
        max_scale=256,
        scale_ratio=1.5,
    )
    assert uncorrected is not None
    assert corrected is not None
    assert corrected < uncorrected
    assert abs(corrected - 0.5) < abs(uncorrected - 0.5)


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


def test_aggregation_hurst_estimators_fit_valid_on_fgn() -> None:
    rng = np.random.default_rng(43)
    x = simulate_fgn(4096, 0.7, rng, sigma=1.0)
    rec = _record(x)
    reg = build_default_estimator_registry()
    for est_name, params in (
        ("AbsoluteMoment", {"n_bootstrap": 12, "bootstrap_block_len": 64, "max_scale": 256}),
        ("Variance", {"n_bootstrap": 12, "bootstrap_block_len": 64, "max_scale": 256}),
        (
            "VarianceResidual",
            {
                "n_bootstrap": 12,
                "bootstrap_block_len": 64,
                "min_scale": 8,
                "max_scale": 256,
                "detrend_order": 1,
            },
        ),
    ):
        spec = EstimatorSpec(
            name=est_name,
            family="temporal",
            target_estimand="hurst_scaling_proxy",
            assumptions=(),
            supports_ci=True,
            supports_diagnostics=True,
            parameter_schema=params,
        )
        out = reg.get(est_name)(spec).fit(rec)
        assert out.valid, (est_name, out.failure_reason)
        assert out.point is not None
        assert 0.0 < float(out.point) < 1.0


def test_aggregation_hurst_estimators_report_invalid_for_short_signal() -> None:
    rec = _record(np.arange(32, dtype=float))
    reg = build_default_estimator_registry()
    for est_name in ("AbsoluteMoment", "Variance", "VarianceResidual"):
        spec = EstimatorSpec(
            name=est_name,
            family="temporal",
            target_estimand="hurst_scaling_proxy",
            assumptions=(),
            supports_ci=False,
            supports_diagnostics=True,
            parameter_schema={"n_bootstrap": 0},
        )
        out = reg.get(est_name)(spec).fit(rec)
        assert not out.valid
        assert out.point is None
        assert out.failure_reason is not None


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


def test_ghe_flat_slope_guard_can_be_disabled() -> None:
    x = np.sin(np.linspace(0.0, 40.0, 2048))
    guarded = _ghe_hurst(x, flat_slope_tol=10.0)
    unguarded = _ghe_hurst(x, flat_slope_tol=0.0)
    assert guarded == 0.5
    assert unguarded is not None
    assert unguarded != 0.5


def test_log_periodogram_alias_uses_shared_core_and_taper_is_case_insensitive() -> None:
    rng = np.random.default_rng(12)
    x = simulate_arfima_zero_d_zero(1024, 0.2, rng, sigma=1.0)
    direct = _log_periodogram_regression_d(x, m=32)
    alias = _log_periodogram_slope_d(x, m=32)
    tapered_lower = _log_periodogram_regression_d(x, m=32, taper="cosine")
    tapered_upper = _log_periodogram_regression_d(x, m=32, taper="COSINE")
    assert direct is not None
    assert alias == direct
    assert tapered_lower == tapered_upper


def test_gph_honours_bandwidth_parameter() -> None:
    rng = np.random.default_rng(13)
    x = simulate_arfima_zero_d_zero(2048, 0.25, rng, sigma=1.0)
    rec = _record(x)
    reg = build_default_estimator_registry()

    def fit_with_m(m: int) -> float:
        spec = EstimatorSpec(
            name="GPH",
            family="spectral",
            target_estimand="long_memory_parameter",
            assumptions=(),
            supports_ci=True,
            supports_diagnostics=True,
            parameter_schema={"n_bootstrap": 0, "bootstrap_block_len": 64, "m": m},
        )
        out = reg.get("GPH")(spec).fit(rec)
        assert out.valid, out.failure_reason
        assert out.point is not None
        assert out.diagnostics["m"] == m
        return float(out.point)

    assert fit_with_m(16) != fit_with_m(96)


def test_arfima_d_estimators_finite() -> None:
    rng = np.random.default_rng(7)
    d_true = 0.25
    x = simulate_arfima_zero_d_zero(2048, d_true, rng, sigma=1.0)
    rec = _record(x)
    reg = build_default_estimator_registry()
    for est_name in ("GPH", "Periodogram", "WhittleMLE", "ModifiedLocalWhittle"):
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
        "WaveletAbryVeitch": {
            "n_bootstrap": 0,
            "wavelet": "db2",
            "j_drop_low": 1,
            "j_drop_high": 1,
        },
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
