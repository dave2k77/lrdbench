"""Independent numerical references for the remaining classical benchmark methods."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.polynomial import Polynomial
from scipy.integrate import quad
from scipy.optimize import minimize

from lrdbench.defaults import build_default_estimator_registry
from lrdbench.enums import SourceType
from lrdbench.estimators import spectral, temporal, wavelet
from lrdbench.generators import _signal
from lrdbench.generators.arfima import ARFIMAGenerator
from lrdbench.schema import EstimatorSpec, SeriesRecord


def _fit(name, x, **params):
    record = SeriesRecord("reference", x, None, None, SourceType.SYNTHETIC, "reference")
    spec = EstimatorSpec(
        name,
        "reference",
        "hurst_scaling_proxy",
        (),
        True,
        True,
        parameter_schema={"n_bootstrap": 0, **params},
    )
    return build_default_estimator_registry().get(name)(spec).fit(record)


def _scales(minimum=8, maximum=96, ratio=1.25):
    scales = [minimum]
    while (following := max(scales[-1] + 1, round(scales[-1] * ratio))) <= maximum:
        scales.append(following)
    return scales


def _slope(scales, values):
    return Polynomial.fit(np.log(scales), np.log(values), 1).convert().coef[1]


def test_rs_matches_hand_range_and_gaussian_expected_value():
    assert temporal._rs_value(np.array([-1.0, 1.0])) == 1.0
    rng = np.random.default_rng(726)
    x = rng.normal(size=(32768, 16))
    centered = x - x.mean(axis=1, keepdims=True)
    paths = np.column_stack((np.zeros(len(x)), centered.cumsum(axis=1)))
    ratios = np.ptp(paths, axis=1) / np.sqrt(np.mean(centered**2, axis=1))
    mean_error = abs(ratios.mean() - temporal._anis_lloyd_expected_rs(16))
    assert mean_error < 5 * ratios.std(ddof=1) / np.sqrt(len(x))
    # Avoid the former absolute signal-amplitude threshold.
    assert temporal._rs_value(x[0] * 1e-15) == pytest.approx(temporal._rs_value(x[0]))


@pytest.mark.parametrize("correction", [False, True])
def test_rs_multiscale_regression_matches_independent_numpy_reference(correction):
    x = np.random.default_rng(67).normal(size=512)
    scales = _scales(ratio=1.5)
    values = []
    for m in scales:
        blocks = x[: len(x) // m * m].reshape(-1, m)
        centered = blocks - blocks.mean(axis=1, keepdims=True)
        paths = np.column_stack((np.zeros(len(blocks)), centered.cumsum(axis=1)))
        value = np.mean(np.ptp(paths, axis=1) / np.sqrt(np.mean(centered**2, axis=1)))
        if correction:
            value /= temporal._anis_lloyd_expected_rs(m)
        values.append(value)
    expected = _slope(scales, values) + (0.5 if correction else 0)
    assert temporal._rs_hurst_proxy(
        x, min_scale=8, max_scale=96, use_correction=correction
    ) == pytest.approx(expected)


@pytest.mark.parametrize("order", [0, 1, 2])
def test_dfa_and_residual_variance_match_projection_reference(order):
    x = np.random.default_rng(26).normal(size=512) + np.linspace(-1.0, 1.0, 512)
    profile = np.cumsum(x - np.mean(x))
    scales = _scales()
    mse = []
    for m in scales:
        segments = profile[: len(x) // m * m].reshape(-1, m)
        # Orthogonal projection, independently of the production per-block least-squares fit.
        basis = np.polynomial.legendre.legvander(np.linspace(-1.0, 1.0, m), order)
        q, _ = np.linalg.qr(basis)
        residual = segments @ (np.eye(m) - q @ q.T)
        mse.append(np.mean(residual**2))
    expected_dfa = 0.5 * _slope(scales, mse)
    expected_residual = 0.5 * _slope(
        scales, np.asarray(mse) * np.asarray(scales) / (np.asarray(scales) - 1)
    )
    assert temporal._dfa_hurst(x, min_scale=8, max_scale=96, detrend_order=order) == pytest.approx(
        expected_dfa, abs=1e-10
    )
    assert temporal._variance_residual_hurst(
        x, min_scale=8, max_scale=96, scale_ratio=1.25, detrend_order=order
    ) == pytest.approx(expected_residual, abs=1e-10)


def test_backward_dma_matches_explicit_window_reference():
    x = np.random.default_rng(27).normal(size=512)
    profile = np.cumsum(x - x.mean())
    scales = _scales()
    rms = []
    for m in scales:
        residual = [profile[t] - np.mean(profile[t - m + 1 : t + 1]) for t in range(m - 1, len(x))]
        rms.append(np.sqrt(np.mean(np.square(residual))))
    assert temporal._dma_hurst(x, min_scale=8, max_scale=96) == pytest.approx(_slope(scales, rms))


def test_aggregation_estimators_match_grouped_mean_definitions():
    x = np.random.default_rng(28).normal(size=512)
    scales = _scales(ratio=1.5)
    moments, variances = [], []
    for m in scales:
        means = np.array([np.mean(x[start : start + m]) for start in range(0, len(x) - m + 1, m)])
        centered = means - np.mean(means)
        moments.append(np.mean(np.abs(centered)))
        variances.append(np.dot(centered, centered) / (len(means) - 1))
    assert temporal._absolute_moment_hurst(x, min_scale=8, max_scale=96) == pytest.approx(
        1 + _slope(scales, moments)
    )
    assert temporal._variance_aggregation_hurst(x, min_scale=8, max_scale=96) == pytest.approx(
        1 + 0.5 * _slope(scales, variances)
    )


def test_out_of_model_slopes_are_preserved_and_labelled():
    x = np.arange(512, dtype=float)
    result = _fit("DFA", x, min_scale=8, max_scale=96)
    assert result.valid and result.point > 1.9
    assert result.diagnostics["point_clipped"] is False
    assert result.diagnostics["outside_nominal_hurst_range"] is True
    assert "estimate_outside_nominal_hurst_range" in result.warnings
    assert wavelet._hurst_from_log2_slope(2.0) == 1.5
    assert wavelet._hurst_from_log2_slope(-2.0) == -0.5


@pytest.mark.parametrize(
    "name",
    [
        "RS",
        "DFA",
        "DMA",
        "AbsoluteMoment",
        "Variance",
        "VarianceResidual",
        "GPH",
        "WhittleMLE",
        "ModifiedLocalWhittle",
        "WaveletOLS",
        "Higuchi",
        "GHE",
    ],
)
@pytest.mark.parametrize("bad", ["constant", "nonfinite"])
def test_classical_roster_rejects_undefined_scaling_inputs(name, bad):
    x = np.ones(512) if bad == "constant" else np.r_[np.nan, np.arange(511)]
    result = _fit(name, x)
    assert not result.valid and result.point is None


def _spectral_series(d, kind, n=1024):
    omega = 2 * np.pi * np.fft.rfftfreq(n)[1:]
    base = np.abs(1 - np.exp(-1j * omega)) if kind == "arfima" else omega
    coefficients = np.r_[0.0, np.sqrt(n) * base ** (-d)].astype(complex)
    return np.fft.irfft(coefficients, n=n)


@pytest.mark.parametrize("d", [-0.35, 0.0, 0.2, 0.4])
def test_whittle_fits_match_exact_model_spectra(d):
    assert spectral._whittle_arfima_d(_spectral_series(d, "arfima"), m=64) == pytest.approx(
        d, abs=3e-6
    )
    assert spectral._modified_local_whittle_d(_spectral_series(d, "power"), m=64) == pytest.approx(
        d, abs=3e-6
    )


def test_profile_whittle_likelihood_matches_analytical_scale_minimizer():
    omega = np.linspace(0.01, 1.0, 64)
    periodogram = np.random.default_rng(74).exponential(size=64)
    d = 0.27
    shape = np.abs(1 - np.exp(-1j * omega)) ** (-2 * d)
    optimum = np.mean(periodogram / shape)
    expected = np.log(optimum) + np.mean(np.log(shape)) + 1.0
    assert spectral._whittle_profile_negloglik(d, omega, periodogram) == pytest.approx(expected)


def test_whittle_constraints_are_reported_as_optimization_boundaries():
    result = _fit("WhittleMLE", _spectral_series(0.7, "arfima"), m=64)
    assert result.valid and result.diagnostics["optimization_boundary_hit"]
    assert result.diagnostics["optimization_bounds_d"] == (-0.49, 0.49)


def test_wavelet_likelihood_profile_matches_joint_scale_and_h_fit(monkeypatch):
    j = np.arange(1.0, 7.0)
    variance = np.array([0.3, 1.0, 1.8, 1.1, 6.0, 8.0])
    counts = np.array([512.0, 256.0, 128.0, 64.0, 32.0, 16.0])
    monkeypatch.setattr(
        wavelet, "_collect_detail_scales", lambda *args, **kwargs: (j, variance, counts)
    )

    def joint(theta):
        log_variance = theta[0] + (2 * theta[1] - 1) * j * np.log(2)
        return np.sum(counts * (log_variance + variance * np.exp(-log_variance)))

    reference = minimize(
        joint, [0.0, 0.7], bounds=[(-10.0, 10.0), (0.06, 0.994)], method="L-BFGS-B"
    )
    assert reference.success
    result = wavelet._wavelet_whittle_h(np.zeros(512), wavelet="db2", j_drop_high=1, j_drop_low=1)
    assert result == pytest.approx(reference.x[1], abs=1e-5)


class _BasisNoise:
    def __init__(self, column):
        self.column = column

    def standard_normal(self, n):
        return np.eye(n)[:, self.column]


@pytest.mark.parametrize("hurst", [0.1, 0.5, 0.9])
def test_fgn_and_fbm_covariance_operators_include_declared_jitter(hurst):
    n, sigma = 9, 2.0
    # Recover the simulator's complete linear map, without a sampling-error tolerance.
    fgn_factor = np.column_stack(
        [_signal.simulate_fgn(n, hurst, _BasisNoise(k), sigma=sigma) for k in range(n)]
    )
    fbm_factor = np.column_stack(
        [_signal.simulate_fbm(n + 1, hurst, _BasisNoise(k), sigma=sigma)[1:] for k in range(n)]
    )
    times = np.arange(n + 1)
    fbm_cov = (
        times[:, None] ** (2 * hurst)
        + times[None, :] ** (2 * hurst)
        - np.abs(times[:, None] - times[None, :]) ** (2 * hurst)
    ) / 2
    differencing = np.diff(np.eye(n + 1), axis=0)
    fgn_cov = differencing @ fbm_cov @ differencing.T
    assert np.allclose(
        fgn_factor @ fgn_factor.T, sigma**2 * (fgn_cov + 1e-10 * np.eye(n)), atol=1e-11
    )
    assert np.allclose(
        fbm_factor @ fbm_factor.T, sigma**2 * (fbm_cov[1:, 1:] + 1e-10 * np.eye(n)), atol=1e-11
    )


@pytest.mark.parametrize("d", [-0.35, 0.0, 0.2, 0.4])
def test_arfima_covariance_matches_independent_fourier_integral(d):
    covariance = _signal.arfima_autocovariance(d, 8)
    for k in range(8):
        value, error = quad(
            lambda w, lag=k: (2 * np.sin(w / 2)) ** (-2 * d) * np.cos(lag * w) / np.pi,
            0.0,
            np.pi,
            epsabs=1e-9,
            limit=200,
        )
        assert abs(covariance[k] - value) < max(1e-8, 5 * error)
    factor = np.column_stack(
        [
            _signal.simulate_arfima_zero_d_zero(8, d, _BasisNoise(k), method="cholesky")
            for k in range(8)
        ]
    )
    lags = np.abs(np.arange(8)[:, None] - np.arange(8)[None, :])
    assert np.allclose(factor @ factor.T, covariance[lags], atol=1e-12)


def test_arfima_legacy_is_preserved_and_exact_algorithm_is_explicit():
    seed, n, d = 567, 64, 0.25
    trunc = 10 * n
    rng = np.random.default_rng(seed)
    coefficients = _signal.arfima_ma_coefficients(d, trunc)
    expected = np.convolve(rng.standard_normal(n + trunc), coefficients, mode="valid")[:n]
    assert np.allclose(
        _signal.simulate_arfima_zero_d_zero(n, d, np.random.default_rng(seed)), expected, atol=1e-12
    )
    record = ARFIMAGenerator().generate(
        record_id="exact",
        params={"n": n, "d": d, "method": "cholesky"},
        seed=seed,
        manifest_id="check",
    )
    assert record.annotations["simulation_method"] == "cholesky"
    assert record.annotations["ma_truncation_lag"] is None
    assert record.truth.target_value == d


@pytest.mark.parametrize("hurst", [0.0, 1.0, -0.1, np.nan])
def test_gaussian_generators_reject_invalid_hurst(hurst):
    for simulator in (_signal.simulate_fgn, _signal.simulate_fbm):
        with pytest.raises(ValueError, match="H"):
            simulator(8, hurst, np.random.default_rng(0))
