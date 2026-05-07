from __future__ import annotations

import time

import numpy as np

from lrdbench.bootstrap import bootstrap_statistic_distribution, symmetric_percentile_cis
from lrdbench.estimators._fit_utils import fit_with_block_bootstrap
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def _rs_hurst_proxy(x: np.ndarray) -> float | None:
    x = np.asarray(x, dtype=float)
    if x.size < 16:
        return None
    x = x - np.mean(x)
    y = np.cumsum(x)
    r = float(np.max(y) - np.min(y))
    s = float(np.std(x, ddof=0))
    if s < 1e-12 or r < 1e-12:
        return None
    n = x.size
    return float(np.log(r / s) / np.log(n))


class RSEstimator(BaseEstimator):
    """Rescaled-range Hurst proxy with optional block-bootstrap CIs (Phase 2)."""

    VERSION = "0.2.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        t0 = time.perf_counter()
        params = dict(self._spec.parameter_schema)
        n_boot = int(params.get("n_bootstrap", 200))
        block_len = int(params.get("bootstrap_block_len", 0)) or max(4, record.values.size // 10)
        levels_raw = params.get("ci_levels")
        ci_levels = tuple(float(x) for x in levels_raw) if levels_raw is not None else (0.95,)
        seed = 0
        if record.provenance is not None and record.provenance.seed is not None:
            seed = int(record.provenance.seed)
        rng = np.random.default_rng(seed & (2**32 - 1))

        try:
            h = _rs_hurst_proxy(record.values)
            dt = time.perf_counter() - t0
            if h is None:
                return EstimateResult(
                    record_id=record.record_id,
                    estimator_name=self._spec.name,
                    point=None,
                    runtime_seconds=dt,
                    valid=False,
                    failure_reason="insufficient_signal_for_rs",
                    estimator_version=self.VERSION,
                )

            samples = bootstrap_statistic_distribution(
                record.values,
                rng,
                _rs_hurst_proxy,
                n_boot=n_boot,
                block_len=block_len,
            )
            cis = symmetric_percentile_cis(samples, ci_levels) if samples.size >= 5 else ()
            bstd = float(np.std(samples)) if samples.size >= 2 else None
            ci_low = ci_high = None
            for a, lo, hi in cis:
                if abs(a - 0.95) < 1e-9:
                    ci_low, ci_high = lo, hi
                    break
            if cis and (ci_low is None):
                ci_low, ci_high = cis[-1][1], cis[-1][2]

            diag: dict[str, object] = {
                "ci_method": "circular_block_bootstrap",
                "n_bootstrap": n_boot,
                "bootstrap_block_len": block_len,
                "bootstrap_replicates_used": int(samples.size),
                "bootstrap_point_std": bstd,
            }
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self._spec.name,
                point=h,
                ci_low=ci_low,
                ci_high=ci_high,
                runtime_seconds=dt,
                valid=True,
                estimator_version=self.VERSION,
                diagnostics=diag,
                bootstrap_cis=cis,
            )
        except Exception as exc:  # noqa: BLE001
            dt = time.perf_counter() - t0
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self._spec.name,
                point=None,
                runtime_seconds=dt,
                valid=False,
                failure_reason=f"exception:{type(exc).__name__}:{exc}",
                estimator_version=self.VERSION,
            )


def _dfa_hurst(
    x: np.ndarray,
    *,
    detrend_order: int = 1,
    min_scale: int = 16,
    max_scale: int | None = None,
) -> float | None:
    """DFA scaling exponent as Hurst proxy (profile DFA on mean-centred series)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 64:
        return None
    x = x - np.mean(x)
    y = np.cumsum(x)
    if max_scale is None:
        max_scale = max(min_scale + 4, n // 4)
    max_scale = min(max_scale, n // 2)
    if max_scale <= min_scale:
        return None
    scales = []
    s = min_scale
    while s <= max_scale:
        scales.append(int(s))
        s = int(max(s + 1, int(round(s * 1.25))))
    log_s: list[float] = []
    log_f: list[float] = []
    order = max(0, int(detrend_order))
    for box in scales:
        if box < order + 2:
            continue
        n_seg = n // box
        if n_seg < 2:
            continue
        rss = 0.0
        count = 0
        t = np.arange(box, dtype=float)
        for seg in range(n_seg):
            sl = slice(seg * box, (seg + 1) * box)
            seg_y = y[sl]
            if order == 0:
                fit = np.full_like(seg_y, float(np.mean(seg_y)))
            else:
                a = np.vander(t, order + 1, increasing=True)
                coef, _, _, _ = np.linalg.lstsq(a, seg_y, rcond=None)
                fit = a @ coef
            resid = seg_y - fit
            rss += float(np.sum(resid * resid))
            count += box
        if count == 0 or rss <= 0.0:
            continue
        f = float(np.sqrt(rss / count))
        if f <= 0.0:
            continue
        log_s.append(np.log(float(box)))
        log_f.append(np.log(f))
    if len(log_s) < 3:
        return None
    xs = np.asarray(log_s, dtype=float)
    ys = np.asarray(log_f, dtype=float)
    xm = float(np.mean(xs))
    ym = float(np.mean(ys))
    denom = float(np.sum((xs - xm) ** 2))
    if denom < 1e-20:
        return None
    alpha = float(np.sum((xs - xm) * (ys - ym)) / denom)
    if not np.isfinite(alpha):
        return None
    return float(np.clip(alpha, 1e-4, 1.0 - 1e-4))


class DFAEstimator(BaseEstimator):
    """Detrended fluctuation analysis (DFA) scaling exponent as a Hurst proxy."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)

        def stat(z: np.ndarray) -> float | None:
            return _dfa_hurst(
                z,
                detrend_order=int(params.get("detrend_order", 1)),
                min_scale=int(params.get("min_scale", 16)),
                max_scale=int(params["max_scale"]) if params.get("max_scale") is not None else None,
            )

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_dfa",
            seed_offset=0,
        )


def _dma_hurst(
    x: np.ndarray,
    *,
    min_scale: int = 8,
    max_scale: int | None = None,
) -> float | None:
    """Detrended moving average (DMA) scaling exponent as Hurst proxy."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 64:
        return None
    x = x - np.mean(x)
    y = np.cumsum(x)
    if max_scale is None:
        max_scale = max(min_scale + 4, n // 4)
    max_scale = min(max_scale, n // 2)
    if max_scale <= min_scale:
        return None
    scales: list[int] = []
    s = min_scale
    while s <= max_scale:
        scales.append(int(s))
        s = int(max(s + 1, int(round(s * 1.25))))
    log_s: list[float] = []
    log_f: list[float] = []
    for w in scales:
        if w < 2 or w > n:
            continue
        ma = np.convolve(y, np.ones(w, dtype=float) / float(w), mode="valid")
        z = y[w - 1 :] - ma
        if z.size < 4:
            continue
        f = float(np.sqrt(np.mean(z * z)))
        if f <= 0.0:
            continue
        log_s.append(np.log(float(w)))
        log_f.append(np.log(f))
    if len(log_s) < 3:
        return None
    xs = np.asarray(log_s, dtype=float)
    ys = np.asarray(log_f, dtype=float)
    xm = float(np.mean(xs))
    ym = float(np.mean(ys))
    denom = float(np.sum((xs - xm) ** 2))
    if denom < 1e-20:
        return None
    alpha = float(np.sum((xs - xm) * (ys - ym)) / denom)
    if not np.isfinite(alpha):
        return None
    return float(np.clip(alpha, 1e-4, 1.0 - 1e-4))


class DMAEstimator(BaseEstimator):
    """Detrended moving-average fluctuation scaling (Hurst proxy)."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)

        def stat(z: np.ndarray) -> float | None:
            return _dma_hurst(
                z,
                min_scale=int(params.get("min_scale", 8)),
                max_scale=int(params["max_scale"]) if params.get("max_scale") is not None else None,
            )

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_dma",
            seed_offset=17,
        )


def _aggregation_scales(
    n: int,
    *,
    min_scale: int,
    max_scale: int | None,
    scale_ratio: float = 1.5,
) -> list[int]:
    if n < 64:
        return []
    min_scale = max(2, int(min_scale))
    if max_scale is None:
        max_scale = max(min_scale + 2, n // 4)
    max_scale = min(int(max_scale), n // 2)
    if max_scale <= min_scale:
        return []
    scales: list[int] = []
    s = min_scale
    while s <= max_scale:
        scales.append(int(s))
        s = int(max(s + 1, round(s * max(1.01, float(scale_ratio)))))
    return scales


def _block_means(x: np.ndarray, block_size: int) -> np.ndarray:
    n_blocks = x.size // block_size
    if n_blocks < 2:
        return np.empty(0, dtype=float)
    trimmed = x[: n_blocks * block_size]
    return np.mean(trimmed.reshape(n_blocks, block_size), axis=1)


def _ols_slope(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(ys) < 3:
        return None
    x_arr = np.asarray(xs, dtype=float)
    y_arr = np.asarray(ys, dtype=float)
    xm = float(np.mean(x_arr))
    ym = float(np.mean(y_arr))
    denom = float(np.sum((x_arr - xm) ** 2))
    if denom < 1e-20:
        return None
    slope = float(np.sum((x_arr - xm) * (y_arr - ym)) / denom)
    if not np.isfinite(slope):
        return None
    return slope


def _absolute_moment_hurst(
    x: np.ndarray,
    *,
    min_scale: int = 2,
    max_scale: int | None = None,
    scale_ratio: float = 1.5,
) -> float | None:
    """Aggregated absolute first moment slope mapped to a Hurst proxy."""
    x = np.asarray(x, dtype=float)
    x = x - np.mean(x)
    log_m: list[float] = []
    log_moment: list[float] = []
    for m in _aggregation_scales(
        x.size, min_scale=min_scale, max_scale=max_scale, scale_ratio=scale_ratio
    ):
        agg = _block_means(x, m)
        if agg.size < 2:
            continue
        moment = float(np.mean(np.abs(agg - np.mean(agg))))
        if moment <= 0.0 or not np.isfinite(moment):
            continue
        log_m.append(np.log(float(m)))
        log_moment.append(np.log(moment))
    slope = _ols_slope(log_m, log_moment)
    if slope is None:
        return None
    return float(np.clip(slope + 1.0, 1e-4, 1.0 - 1e-4))


def _variance_aggregation_hurst(
    x: np.ndarray,
    *,
    min_scale: int = 2,
    max_scale: int | None = None,
    scale_ratio: float = 1.5,
) -> float | None:
    """Aggregated-series variance slope mapped to a Hurst proxy."""
    x = np.asarray(x, dtype=float)
    x = x - np.mean(x)
    log_m: list[float] = []
    log_var: list[float] = []
    for m in _aggregation_scales(
        x.size, min_scale=min_scale, max_scale=max_scale, scale_ratio=scale_ratio
    ):
        agg = _block_means(x, m)
        if agg.size < 2:
            continue
        var = float(np.var(agg, ddof=1))
        if var <= 0.0 or not np.isfinite(var):
            continue
        log_m.append(np.log(float(m)))
        log_var.append(np.log(var))
    slope = _ols_slope(log_m, log_var)
    if slope is None:
        return None
    return float(np.clip(0.5 * slope + 1.0, 1e-4, 1.0 - 1e-4))


def _variance_residual_hurst(
    x: np.ndarray,
    *,
    min_scale: int = 8,
    max_scale: int | None = None,
    scale_ratio: float = 1.5,
    detrend_order: int = 1,
) -> float | None:
    """Mean block residual variance slope mapped to a Hurst proxy."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 64:
        return None
    y = np.cumsum(x - np.mean(x))
    order = max(0, int(detrend_order))
    log_m: list[float] = []
    log_var: list[float] = []
    for m in _aggregation_scales(
        n, min_scale=min_scale, max_scale=max_scale, scale_ratio=scale_ratio
    ):
        if m < order + 2:
            continue
        n_blocks = n // m
        if n_blocks < 2:
            continue
        t = np.arange(m, dtype=float)
        design = np.vander(t, order + 1, increasing=True)
        block_vars: list[float] = []
        for idx in range(n_blocks):
            seg = y[idx * m : (idx + 1) * m]
            if order == 0:
                fit = np.full_like(seg, float(np.mean(seg)))
            else:
                coef, _, _, _ = np.linalg.lstsq(design, seg, rcond=None)
                fit = design @ coef
            resid = seg - fit
            if resid.size > 1:
                block_vars.append(float(np.var(resid, ddof=1)))
        if not block_vars:
            continue
        avg_var = float(np.mean(block_vars))
        if avg_var <= 0.0 or not np.isfinite(avg_var):
            continue
        log_m.append(np.log(float(m)))
        log_var.append(np.log(avg_var))
    slope = _ols_slope(log_m, log_var)
    if slope is None:
        return None
    return float(np.clip(0.5 * slope, 1e-4, 1.0 - 1e-4))


class AbsoluteMomentEstimator(BaseEstimator):
    """Absolute first moment of aggregated series as a Hurst proxy."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)

        def stat(z: np.ndarray) -> float | None:
            return _absolute_moment_hurst(
                z,
                min_scale=int(params.get("min_scale", 2)),
                max_scale=int(params["max_scale"]) if params.get("max_scale") is not None else None,
                scale_ratio=float(params.get("scale_ratio", 1.5)),
            )

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_absolute_moment",
            seed_offset=29,
        )


class VarianceEstimator(BaseEstimator):
    """Variance of aggregated series as a Hurst proxy."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)

        def stat(z: np.ndarray) -> float | None:
            return _variance_aggregation_hurst(
                z,
                min_scale=int(params.get("min_scale", 2)),
                max_scale=int(params["max_scale"]) if params.get("max_scale") is not None else None,
                scale_ratio=float(params.get("scale_ratio", 1.5)),
            )

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_variance",
            seed_offset=31,
        )


class VarianceResidualEstimator(BaseEstimator):
    """Variance of block residuals as a Hurst proxy."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)

        def stat(z: np.ndarray) -> float | None:
            return _variance_residual_hurst(
                z,
                min_scale=int(params.get("min_scale", 8)),
                max_scale=int(params["max_scale"]) if params.get("max_scale") is not None else None,
                scale_ratio=float(params.get("scale_ratio", 1.5)),
                detrend_order=int(params.get("detrend_order", 1)),
            )

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_variance_residual",
            seed_offset=37,
        )
