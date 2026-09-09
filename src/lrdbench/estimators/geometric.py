from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import numpy as np

from lrdbench.estimators._fit_utils import fit_with_block_bootstrap
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def _higuchi_fractal_dimension(x: np.ndarray, *, k_max: int | None = None) -> float | None:
    """Higuchi (1988) fractal dimension D from log–log slope of curve length L(k) vs 1/k."""
    x = np.asarray(x, dtype=float)
    n = int(x.size)
    if x.ndim != 1 or n < 64 or not np.isfinite(x).all():
        return None
    if k_max is None:
        k_max = max(8, min(64, n // 8))
    k_max = int(np.clip(k_max, 4, n // 4))
    log_inv_k: list[float] = []
    log_l: list[float] = []
    for k in range(1, k_max + 1):
        # Every lag-k difference belongs to exactly one offset class t % k.
        # Group the sums at once; retain each offset's original term count and
        # Higuchi (1988), p. 278 normalization, including the final /k.
        differences = np.abs(x[k:] - x[:-k])
        sums = np.bincount(np.arange(n - k) % k, weights=differences, minlength=k)
        n_terms = (n - np.arange(k) - 1) // k
        lk = float(np.mean(sums * (n - 1) / (n_terms * k * k)))
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
    return d


def _higuchi_hurst_proxy(x: np.ndarray, *, k_max: int | None = None) -> float | None:
    """Hurst-style proxy from graph dimension: H ≈ 2 − D (self-affine graph heuristic)."""
    d = _higuchi_fractal_dimension(x, k_max=k_max)
    if d is None:
        return None
    h = 2.0 - d
    return h


def _ghe_hurst(
    x: np.ndarray,
    *,
    n_scales: int = 16,
    h_min: int = 1,
    h_max: int | None = None,
    q: float = 2.0,
    flat_slope_tol: float = 0.0,
) -> float | None:
    """Generalized Hurst H(q) from mean absolute q-th path increments.

    Fit log(mean(abs(X[t+lag]-X[t])**q)) against log(lag), then divide
    the slope by q (Di Matteo et al., 2003, equations 1–2). Their lag-independent
    normalization affects only the intercept and is omitted here. There is no
    automatic detrending, clipping or flat-slope substitution.
    """
    if flat_slope_tol != 0.0:
        raise ValueError("flat_slope_tol must be 0: the forced 0.5 heuristic has been removed")
    if not np.isfinite(q) or q <= 0 or h_min < 1 or n_scales < 4:
        raise ValueError("GHE requires finite q > 0, h_min >= 1 and n_scales >= 4")
    x = np.asarray(x, dtype=float)
    n = int(x.size)
    if x.ndim != 1 or n < 128 or not np.isfinite(x).all():
        return None
    x = x - np.mean(x)
    scale = float(np.max(np.abs(x)))
    if scale == 0.0:
        return None
    x = x / scale
    h_max = n // 8 if h_max is None else int(h_max)
    if not h_min < h_max < n // 2:
        raise ValueError("GHE requires h_min < h_max < n/2")
    hs = np.unique(
        np.round(np.geomspace(float(h_min), float(h_max), num=int(n_scales))).astype(int)
    )
    log_h: list[float] = []
    log_v: list[float] = []
    for h in hs:
        if h < 1 or h >= n // 2:
            continue
        dlt = x[h:] - x[:-h]
        v = float(np.mean(np.abs(dlt) ** q))
        if not np.isfinite(v) or v <= 0.0:
            continue
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
    return slope / q


def _path_from_increments(x: np.ndarray) -> np.ndarray:
    """Declared adapter: X[0] = 0 and X[t+1] = X[t] + x[t], without demeaning."""
    return np.concatenate((np.zeros(1), np.cumsum(x)))


def _fit_geometric(
    record: SeriesRecord,
    spec: EstimatorSpec,
    *,
    path_statistic: Callable[[np.ndarray], float | None],
    version: str,
    failure_reason: str,
    seed_offset: int,
) -> EstimateResult:
    representation = str(spec.parameter_schema.get("input_representation", "path"))
    if representation not in {"path", "increments"}:
        return EstimateResult(
            record_id=record.record_id,
            estimator_name=spec.name,
            point=None,
            valid=False,
            failure_reason="input_representation_must_be_path_or_increments",
            estimator_version=version,
        )

    def from_increments(z: np.ndarray) -> float | None:
        return path_statistic(_path_from_increments(z))

    result = fit_with_block_bootstrap(
        record,
        spec,
        statistic=path_statistic if representation == "path" else from_increments,
        bootstrap_values=np.diff(record.values) if representation == "path" else record.values,
        bootstrap_statistic=from_increments,
        estimator_version=version,
        failure_reason=failure_reason,
        seed_offset=seed_offset,
    )
    warnings = result.warnings
    if "input_representation" not in spec.parameter_schema:
        warnings += ("input_representation_defaulted_to_path",)
    outside = result.point is not None and not 0.0 <= result.point <= 1.0
    if outside:
        warnings += ("estimate_outside_nominal_hurst_range",)
    return replace(
        result,
        warnings=warnings,
        diagnostics={
            **result.diagnostics,
            "input_representation": representation,
            "point_transform": "cumulative_sum_with_zero_origin"
            if representation == "increments"
            else "none",
            "bootstrap_representation": "increments",
            "bootstrap_calibration": "not_established",
            "point_clipped": False,
            "outside_nominal_hurst_range": outside,
            "method_parameters": dict(spec.parameter_schema),
        },
    )


class HiguchiEstimator(BaseEstimator):
    """Higuchi fractal length curve; Hurst proxy H ≈ 2 − D for the time-series graph."""

    VERSION = "0.3.0"

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

        result = _fit_geometric(
            record,
            self._spec,
            path_statistic=stat,
            version=self.VERSION,
            failure_reason="insufficient_signal_for_higuchi",
            seed_offset=919,
        )
        return replace(
            result,
            diagnostics={
                **result.diagnostics,
                "fractal_dimension": 2.0 - result.point if result.point is not None else None,
            },
        )


class GHEEstimator(BaseEstimator):
    """Generalized Hurst estimator: scaling of absolute q-th path increments.

    Parameters read from ``params``:

    - ``n_scales`` (int, default 16) – number of geometric lags.
    - ``h_min`` (int, default 1) – minimum lag in samples.
    - ``h_max`` (int, default path length // 8) – maximum lag in samples.
    - ``q`` (float, default 2) – positive moment order, e.g. 1 for absolute increments.
    - ``input_representation`` (default ``path``) – ``increments`` integrates first.
    - ``flat_slope_tol`` – only zero is accepted; the old heuristic is removed.
    """

    VERSION = "0.2.0"

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
                h_max=int(params["h_max"]) if params.get("h_max") is not None else None,
                q=float(params.get("q", 2.0)),
                flat_slope_tol=float(params.get("flat_slope_tol", 0.0)),
            )

        return _fit_geometric(
            record,
            self._spec,
            path_statistic=stat,
            version=self.VERSION,
            failure_reason="insufficient_signal_for_ghe",
            seed_offset=1021,
        )
