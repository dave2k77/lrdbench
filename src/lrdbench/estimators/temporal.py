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
        ci_levels = (
            tuple(float(x) for x in levels_raw) if levels_raw is not None else (0.95,)
        )
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
