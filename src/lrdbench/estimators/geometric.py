from __future__ import annotations

import numpy as np

from lrdbench.estimators._fit_utils import fit_with_block_bootstrap
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def _higuchi_fractal_dimension(x: np.ndarray, *, k_max: int | None = None) -> float | None:
    """Higuchi (1988) fractal dimension D from log–log slope of curve length L(k) vs 1/k."""
    x = np.asarray(x, dtype=float)
    n = int(x.size)
    if n < 64:
        return None
    if k_max is None:
        k_max = max(8, min(64, n // 8))
    k_max = int(np.clip(k_max, 4, n // 4))
    log_inv_k: list[float] = []
    log_l: list[float] = []
    for k in range(1, k_max + 1):
        lm: list[float] = []
        for m in range(k):
            n_terms = int(np.floor((n - m - 1) / k))
            if n_terms <= 0:
                continue
            ll = 0.0
            for i in range(1, n_terms + 1):
                ll += abs(float(x[m + i * k] - x[m + (i - 1) * k]))
            ll = ll * (n - 1) / (n_terms * k)
            lm.append(ll)
        if not lm:
            continue
        lk = float(np.mean(lm))
        if lk <= 0.0 or not np.isfinite(lk):
            continue
        log_inv_k.append(float(np.log(1.0 / k)))
        log_l.append(float(np.log(lk)))
    if len(log_inv_k) < 4:
        return None
    xs = np.asarray(log_inv_k, dtype=float)
    ys = np.asarray(log_l, dtype=float)
    xm = float(np.mean(xs))
    ym = float(np.mean(ys))
    denom = float(np.sum((xs - xm) ** 2))
    if denom < 1e-20:
        return None
    d = float(np.sum((xs - xm) * (ys - ym)) / denom)
    if not np.isfinite(d):
        return None
    return float(np.clip(d, 1.0 + 1e-4, 2.0 - 1e-4))


def _higuchi_hurst_proxy(x: np.ndarray, *, k_max: int | None = None) -> float | None:
    """Hurst-style proxy from graph dimension: H ≈ 2 − D (self-affine graph heuristic)."""
    d = _higuchi_fractal_dimension(x, k_max=k_max)
    if d is None:
        return None
    h = 2.0 - d
    return float(np.clip(h, 1e-4, 1.0 - 1e-4))


def _ghe_hurst(
    x: np.ndarray,
    *,
    n_scales: int = 16,
    h_min: int = 1,
    flat_slope_tol: float = 0.08,
) -> float | None:
    """Geometric Hurst proxy: multiscale log–log slope of squared-increment variance vs lag.

    Uses geometrically spaced integer lags; for clear scaling, H ≈ slope/2; flat slope → 0.5.
    """
    x = np.asarray(x, dtype=float)
    n = int(x.size)
    if n < 128:
        return None
    x = x - np.mean(x)
    h_max = max(h_min + 2, n // 8)
    hs = np.unique(
        np.round(np.geomspace(float(h_min), float(h_max), num=max(6, int(n_scales)))).astype(int)
    )
    log_h: list[float] = []
    log_v: list[float] = []
    for h in hs:
        if h < 1 or h >= n // 2:
            continue
        dlt = x[h:] - x[:-h]
        v = float(np.var(dlt, ddof=0))
        v = max(v, 1e-30)
        log_h.append(float(np.log(float(h))))
        log_v.append(float(np.log(v)))
    if len(log_h) < 4:
        return None
    xh = np.asarray(log_h, dtype=float)
    yv = np.asarray(log_v, dtype=float)
    xm = float(np.mean(xh))
    ym = float(np.mean(yv))
    denom = float(np.sum((xh - xm) ** 2))
    if denom < 1e-20:
        return None
    slope = float(np.sum((xh - xm) * (yv - ym)) / denom)
    if not np.isfinite(slope):
        return None
    if abs(slope) < float(flat_slope_tol):
        return 0.5
    h_est = 0.5 * slope
    return float(np.clip(h_est, 1e-4, 1.0 - 1e-4))


class HiguchiEstimator(BaseEstimator):
    """Higuchi fractal length curve; Hurst proxy H ≈ 2 − D for the time-series graph."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)

        def stat(z: np.ndarray) -> float | None:
            km = int(params["k_max"]) if params.get("k_max") is not None else None
            return _higuchi_hurst_proxy(z, k_max=km)

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_higuchi",
            seed_offset=919,
        )


class GHEEstimator(BaseEstimator):
    """Geometric Hurst estimator: multiscale variance scaling of lagged increments."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)

        def stat(z: np.ndarray) -> float | None:
            return _ghe_hurst(
                z,
                n_scales=int(params.get("n_scales", 16)),
                h_min=int(params.get("h_min", 1)),
                flat_slope_tol=float(params.get("flat_slope_tol", 0.08)),
            )

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_ghe",
            seed_offset=1021,
        )
