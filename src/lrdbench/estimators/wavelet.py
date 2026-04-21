from __future__ import annotations

import numpy as np
import pywt
from scipy.optimize import minimize_scalar

from lrdbench.estimators._fit_utils import fit_with_block_bootstrap
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def _collect_detail_scales(
    x: np.ndarray,
    *,
    wavelet: str,
    j_drop_high: int,
    j_drop_low: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Return (j_index 1..J finest-to-coarse, sample variance, n_k) per retained detail level."""
    x = np.asarray(x, dtype=float)
    if x.size < 128:
        return None
    x = x - np.mean(x)
    max_level = pywt.dwt_max_level(x.size, pywt.Wavelet(wavelet).dec_len)
    if max_level < 3:
        return None
    coeffs = pywt.wavedec(x, wavelet=wavelet, mode="symmetric", level=max_level)
    details = coeffs[1:]
    j_keep: list[float] = []
    v_keep: list[float] = []
    n_keep: list[float] = []
    for idx, d in enumerate(details, start=1):
        if idx <= j_drop_high or idx > len(details) - j_drop_low:
            continue
        if d.size < 2:
            continue
        v = float(np.var(d, ddof=1))
        v = max(v, 1e-30)
        j_keep.append(float(idx))
        v_keep.append(v)
        n_keep.append(float(d.size))
    if len(j_keep) < 3:
        return None
    return (
        np.asarray(j_keep, dtype=float),
        np.asarray(v_keep, dtype=float),
        np.asarray(n_keep, dtype=float),
    )


def _ols_slope_log2(j: np.ndarray, v: np.ndarray) -> float | None:
    log2v = np.log2(np.maximum(v, 1e-30))
    jm = float(np.mean(j))
    ym = float(np.mean(log2v))
    denom = float(np.sum((j - jm) ** 2))
    if denom < 1e-20:
        return None
    s = float(np.sum((j - jm) * (log2v - ym)) / denom)
    return s if np.isfinite(s) else None


def _wls_slope_log2(j: np.ndarray, v: np.ndarray, n: np.ndarray) -> float | None:
    """Inverse-variance weighted regression (Bardet-type weights on OLS scale)."""
    log2v = np.log2(np.maximum(v, 1e-30))
    w = np.maximum(n, 1.0)
    w = w / float(np.sum(w))
    jm = float(np.sum(w * j))
    ym = float(np.sum(w * log2v))
    num = float(np.sum(w * (j - jm) * (log2v - ym)))
    denom = float(np.sum(w * (j - jm) ** 2))
    if denom < 1e-20:
        return None
    s = num / denom
    return s if np.isfinite(s) else None


def _hurst_from_log2_slope(slope: float | None) -> float | None:
    if slope is None or not np.isfinite(slope):
        return None
    h = 0.5 * (slope + 2.0)
    return float(np.clip(h, 1e-4, 1.0 - 1e-4))


def _wavelet_whittle_h(
    x: np.ndarray,
    *,
    wavelet: str,
    j_drop_high: int,
    j_drop_low: int,
) -> float | None:
    packed = _collect_detail_scales(
        x, wavelet=wavelet, j_drop_high=j_drop_high, j_drop_low=j_drop_low
    )
    if packed is None:
        return None
    j_arr, v_arr, n_arr = packed

    def nll(h: float) -> float:
        if not 0.05 < h < 0.995:
            return 1e12
        beta = 2.0 * h - 2.0
        mu = 2.0 ** (beta * j_arr)
        den = float(np.sum(n_arr * mu))
        if den <= 0.0 or not np.isfinite(den):
            return 1e12
        c_scale = float(np.sum(n_arr * v_arr) / den)
        if c_scale <= 0.0 or not np.isfinite(c_scale):
            return 1e12
        pred = c_scale * mu
        return float(np.sum(n_arr * (np.log(pred) + v_arr / pred)))

    res = minimize_scalar(nll, bounds=(0.06, 0.994), method="bounded")
    if not res.success or not np.isfinite(res.fun):
        return None
    return float(np.clip(res.x, 1e-4, 1.0 - 1e-4))


def _wavelet_jensen_h(
    x: np.ndarray,
    *,
    wavelet: str,
    fine_band: tuple[int, int],
    coarse_band: tuple[int, int],
) -> float | None:
    """Two-band linear bias correction (Jensen-style extrapolation on log-scale slopes)."""
    x = np.asarray(x, dtype=float)
    if x.size < 256:
        return None

    def band_slope(lo: int, hi: int) -> float | None:
        packed = _collect_detail_scales(x, wavelet=wavelet, j_drop_high=0, j_drop_low=0)
        if packed is None:
            return None
        j, v, n = packed
        mask = (j >= lo) & (j <= hi)
        if int(np.sum(mask)) < 2:
            return None
        return _wls_slope_log2(j[mask], v[mask], n[mask])

    s1 = band_slope(fine_band[0], fine_band[1])
    s2 = band_slope(coarse_band[0], coarse_band[1])
    h1 = _hurst_from_log2_slope(s1)
    h2 = _hurst_from_log2_slope(s2)
    if h1 is None or h2 is None:
        return None
    h_lin = 2.0 * h1 - h2
    return float(np.clip(h_lin, 1e-4, 1.0 - 1e-4))


class WaveletAbryVeitchEstimator(BaseEstimator):
    """Abry–Veitch-type log-scale regression on wavelet detail variances (Hurst proxy)."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)
        wavelet = str(params.get("wavelet", "db4"))
        j_hi = int(params.get("j_drop_high", 2))
        j_lo = int(params.get("j_drop_low", 2))

        def stat(z: np.ndarray) -> float | None:
            packed = _collect_detail_scales(z, wavelet=wavelet, j_drop_high=j_hi, j_drop_low=j_lo)
            if packed is None:
                return None
            j, v, _ = packed
            return _hurst_from_log2_slope(_ols_slope_log2(j, v))

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_wavelet_av",
            seed_offset=401,
        )


class WaveletBardetEstimator(BaseEstimator):
    """Weighted log-scale regression (Bardet-type wavelet Hurst proxy)."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)
        wavelet = str(params.get("wavelet", "db4"))
        j_hi = int(params.get("j_drop_high", 1))
        j_lo = int(params.get("j_drop_low", 2))

        def stat(z: np.ndarray) -> float | None:
            packed = _collect_detail_scales(z, wavelet=wavelet, j_drop_high=j_hi, j_drop_low=j_lo)
            if packed is None:
                return None
            j, v, n = packed
            return _hurst_from_log2_slope(_wls_slope_log2(j, v, n))

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_wavelet_bardet",
            seed_offset=503,
        )


class WaveletOLSEstimator(BaseEstimator):
    """Plain OLS on log2 wavelet detail variances vs scale index (log-scale regression)."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)
        wavelet = str(params.get("wavelet", "db4"))
        j_hi = int(params.get("j_drop_high", 1))
        j_lo = int(params.get("j_drop_low", 1))

        def stat(z: np.ndarray) -> float | None:
            packed = _collect_detail_scales(z, wavelet=wavelet, j_drop_high=j_hi, j_drop_low=j_lo)
            if packed is None:
                return None
            j, v, _ = packed
            return _hurst_from_log2_slope(_ols_slope_log2(j, v))

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_wavelet_ols",
            seed_offset=607,
        )


class WaveletJensenEstimator(BaseEstimator):
    """Two-band wavelet slope extrapolation (Jensen-style bias reduction)."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)
        wavelet = str(params.get("wavelet", "db4"))
        fb = params.get("fine_band", (2, 4))
        cb = params.get("coarse_band", (4, 6))
        fine_band = (int(fb[0]), int(fb[1]))
        coarse_band = (int(cb[0]), int(cb[1]))

        def stat(z: np.ndarray) -> float | None:
            return _wavelet_jensen_h(
                z, wavelet=wavelet, fine_band=fine_band, coarse_band=coarse_band
            )

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_wavelet_jensen",
            seed_offset=709,
        )


class WaveletWhittleEstimator(BaseEstimator):
    """Wavelet-domain Gaussian Whittle-type fit to detail variances across scales."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)
        wavelet = str(params.get("wavelet", "db4"))
        j_hi = int(params.get("j_drop_high", 1))
        j_lo = int(params.get("j_drop_low", 1))

        def stat(z: np.ndarray) -> float | None:
            return _wavelet_whittle_h(z, wavelet=wavelet, j_drop_high=j_hi, j_drop_low=j_lo)

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_wavelet_whittle",
            seed_offset=811,
        )
