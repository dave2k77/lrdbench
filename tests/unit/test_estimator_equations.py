from __future__ import annotations

import numpy as np
import pytest
import pywt

from lrdbench.defaults import build_default_estimator_registry
from lrdbench.enums import SourceType
from lrdbench.estimators.geometric import (
    _ghe_hurst,
    _higuchi_fractal_dimension,
    _path_from_increments,
)
from lrdbench.estimators.spectral import _log_periodogram_regression_d
from lrdbench.estimators.wavelet import (
    _collect_detail_scales,
    _hurst_from_log2_slope,
    _ols_slope_log2,
)
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def _exact_spectrum(d: float, n: int = 1024) -> np.ndarray:
    """Inverse-DFT signal whose periodogram follows the fractional-noise spectrum exactly."""
    frequencies = np.fft.rfftfreq(n)[1:]
    spectral_density = np.abs(1.0 - np.exp(-2j * np.pi * frequencies)) ** (-2 * d)
    phase = np.random.default_rng(341).uniform(-np.pi, np.pi, frequencies.size)
    coefficients = np.zeros(n // 2 + 1, dtype=complex)
    coefficients[1:] = np.sqrt(n * spectral_density) * np.exp(1j * phase)
    coefficients[-1] = np.sqrt(n * spectral_density[-1])
    return np.fft.irfft(coefficients, n=n)


def _fit(
    name: str, values: np.ndarray, target: str = "hurst_scaling_proxy", **params: object
) -> EstimateResult:
    record = SeriesRecord(
        record_id="equation",
        values=values,
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="mathematical_check",
    )
    spec = EstimatorSpec(
        name=name,
        family="check",
        target_estimand=target,
        assumptions=(),
        supports_ci=True,
        supports_diagnostics=True,
        parameter_schema={"n_bootstrap": 0, **params},
    )
    return build_default_estimator_registry().get(name)(spec).fit(record)


@pytest.mark.parametrize("d", [-0.35, 0.0, 0.2, 0.4, 0.8])
@pytest.mark.parametrize("m", [16, 32, 128])
def test_log_periodogram_recovers_known_spectral_exponent_exactly(d: float, m: int) -> None:
    assert _log_periodogram_regression_d(_exact_spectrum(d), m=m) == pytest.approx(d, abs=1e-12)


@pytest.mark.parametrize(
    "name,target,expected",
    [
        ("GPH", "long_memory_parameter", 0.2),
        ("Periodogram", "long_memory_parameter", 0.2),
        ("GPH", "hurst_scaling_proxy", 0.7),
        ("PeriodogramBeta", "spectral_exponent_beta", 0.4),
    ],
)
def test_spectral_public_estimators_preserve_target_scale(
    name: str, target: str, expected: float
) -> None:
    result = _fit(name, _exact_spectrum(0.2), target, m=64)
    assert result.valid
    assert result.point == pytest.approx(expected, abs=1e-12)


def test_log_periodogram_is_amplitude_and_offset_invariant_and_rejects_constants() -> None:
    x = _exact_spectrum(-0.2)
    assert _log_periodogram_regression_d(1e-10 * x) == pytest.approx(-0.2, abs=1e-12)
    assert _log_periodogram_regression_d(-7 * x + 300) == pytest.approx(-0.2, abs=1e-12)
    assert _log_periodogram_regression_d(np.ones(256)) is None
    assert _log_periodogram_regression_d(np.full(256, np.nan)) is None


def test_higuchi_linear_graph_has_dimension_one_without_clipping() -> None:
    x = np.linspace(-3, 5, 512)
    assert _higuchi_fractal_dimension(x, k_max=32) == pytest.approx(1, abs=1e-12)
    assert _higuchi_fractal_dimension(np.ones(512), k_max=32) is None


def test_higuchi_brownian_graph_dimension_matches_known_limit() -> None:
    dimensions = [
        _higuchi_fractal_dimension(
            np.cumsum(np.random.default_rng(seed).normal(size=2048)), k_max=32
        )
        for seed in range(20)
    ]
    assert all(d is not None for d in dimensions)
    assert 1.45 < np.mean(dimensions) < 1.55
    assert np.std(dimensions) > 0.005  # No saturation at an artificial boundary.


@pytest.mark.parametrize("q", [1.0, 2.0, 3.0])
def test_ghe_uses_raw_absolute_moments_and_has_no_half_fallback(q: float) -> None:
    x = np.arange(512.0)
    assert _ghe_hurst(x, q=q, h_max=32) == pytest.approx(1, abs=1e-12)
    assert _ghe_hurst(-7 * x + 500, q=q, h_max=32) == pytest.approx(1, abs=1e-12)
    assert _ghe_hurst(np.zeros(512), q=q) is None


@pytest.mark.parametrize("q", [1.0, 2.0])
def test_ghe_brownian_scaling_and_white_noise_path_are_distinct(q: float) -> None:
    estimates = [
        _ghe_hurst(np.cumsum(np.random.default_rng(seed).normal(size=2048)), q=q, h_max=32)
        for seed in range(20)
    ]
    assert 0.45 < np.mean(estimates) < 0.55
    raw_noise = _ghe_hurst(np.random.default_rng(22).normal(size=8192), q=q, h_max=32)
    assert raw_noise is not None and abs(raw_noise) < 0.05


def test_ghe_rejects_legacy_forced_value_and_invalid_moments() -> None:
    with pytest.raises(ValueError, match="removed"):
        _ghe_hurst(np.arange(512.0), flat_slope_tol=0.08)
    for q in (0, -1, np.nan, np.inf):
        with pytest.raises(ValueError, match="q > 0"):
            _ghe_hurst(np.arange(512.0), q=q)


@pytest.mark.parametrize("name", ["Higuchi", "GHE"])
def test_declared_increment_adapter_equals_fitting_the_integrated_path(name: str) -> None:
    increments = np.random.default_rng(22).normal(size=1024)
    adapted = _fit(name, increments, input_representation="increments")
    direct = _fit(name, _path_from_increments(increments), input_representation="path")
    assert adapted.valid and direct.valid
    assert adapted.point == direct.point
    assert adapted.diagnostics["input_representation"] == "increments"
    assert direct.diagnostics["input_representation"] == "path"
    assert _fit(name, increments, input_representation="guess").valid is False


@pytest.mark.parametrize("name", ["Higuchi", "GHE"])
def test_path_bootstrap_resamples_increments_then_reconstructs_the_path(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import lrdbench.bootstrap as bootstrap

    increments = np.random.default_rng(123).normal(size=256)
    path = _path_from_increments(increments)
    calls = []

    def identity_resample(x: np.ndarray, rng: np.random.Generator, block_len: int) -> np.ndarray:
        calls.append(x.copy())
        return x.copy()

    monkeypatch.setattr(bootstrap, "circular_block_resample", identity_resample)
    result = _fit(name, path, input_representation="path", n_bootstrap=8)
    assert result.valid and len(calls) == 8
    for values in calls:
        np.testing.assert_allclose(values, increments, atol=1e-14)
    assert result.bootstrap_cis[0][1] == pytest.approx(result.point, abs=1e-12)
    assert result.bootstrap_cis[0][2] == pytest.approx(result.point, abs=1e-12)
    assert result.diagnostics["bootstrap_representation"] == "increments"


@pytest.mark.parametrize("hurst", [0.2, 0.5, 0.8])
def test_wavelet_octave_order_and_fgn_mapping_on_constructed_coefficients(hurst: float) -> None:
    n = 1024
    coefficients = [np.zeros(1)]
    for level in range(10, 0, -1):
        count = n // 2**level
        signs = np.tile([-1.0, 1.0], (count + 1) // 2)[:count]
        variance = 2 ** (level * (2 * hurst - 1))
        coefficients.append(signs * np.sqrt(variance * (count - 1) / count))
    x = pywt.waverec(coefficients, "haar", mode="symmetric")
    packed = _collect_detail_scales(x, wavelet="haar", j_drop_high=1, j_drop_low=2)
    assert packed is not None
    levels, variances, counts = packed
    np.testing.assert_array_equal(levels, np.arange(8, 1, -1))
    np.testing.assert_allclose(variances, 2 ** (levels * (2 * hurst - 1)), rtol=1e-12)
    assert _hurst_from_log2_slope(_ols_slope_log2(levels, variances)) == pytest.approx(
        hurst, abs=1e-12
    )
