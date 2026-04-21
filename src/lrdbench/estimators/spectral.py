from __future__ import annotations

import time

import numpy as np
from scipy.optimize import minimize_scalar

from lrdbench.bootstrap import bootstrap_statistic_distribution, symmetric_percentile_cis
from lrdbench.estimators._fit_utils import fit_with_block_bootstrap
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def _gph_long_memory(x: np.ndarray, *, m: int | None = None) -> float | None:
    """Geweke–Porter–Hudak regression slope as a crude long-memory proxy near 0 frequency."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 64:
        return None
    x = x - np.mean(x)
    if m is None:
        m = max(2, int(n**0.5))
    m = min(m, n // 2 - 1)
    if m < 2:
        return None
    j = np.arange(1, m + 1, dtype=float)
    lam = 2.0 * np.pi * j / n
    fft = np.fft.rfft(x)
    periodogram = (np.abs(fft[1 : m + 1]) ** 2) / n
    periodogram = np.maximum(periodogram, 1e-20)
    log_freq = np.log(4.0 * np.sin(lam / 2.0) ** 2)
    log_per = np.log(periodogram)
    x_mean = float(np.mean(log_freq))
    y_mean = float(np.mean(log_per))
    denom = float(np.sum((log_freq - x_mean) ** 2))
    if denom < 1e-20:
        return None
    beta = float(np.sum((log_freq - x_mean) * (log_per - y_mean)) / denom)
    return float(-0.5 * beta)


class GPHEstimator(BaseEstimator):
    """Geweke–Porter–Hudak log-periodogram regression for long-memory parameter d."""

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
            seed = int(record.provenance.seed) + 7919
        rng = np.random.default_rng(seed & (2**32 - 1))

        try:
            d = _gph_long_memory(record.values)
            dt = time.perf_counter() - t0
            if d is None:
                return EstimateResult(
                    record_id=record.record_id,
                    estimator_name=self._spec.name,
                    point=None,
                    runtime_seconds=dt,
                    valid=False,
                    failure_reason="insufficient_signal_for_gph",
                    estimator_version=self.VERSION,
                )

            samples = bootstrap_statistic_distribution(
                record.values,
                rng,
                _gph_long_memory,
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
            if cis and ci_low is None:
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
                point=d,
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


def _log_periodogram_slope_d(x: np.ndarray, *, m: int | None = None) -> float | None:
    """Log-periodogram regression memory parameter (GPH-type) in (-0.5, 0.5)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 64:
        return None
    x = x - np.mean(x)
    if m is None:
        m = max(2, int(n**0.5))
    m = min(m, n // 2 - 1)
    if m < 2:
        return None
    j = np.arange(1, m + 1, dtype=float)
    lam = 2.0 * np.pi * j / n
    fft = np.fft.rfft(x)
    periodogram = (np.abs(fft[1 : m + 1]) ** 2) / n
    periodogram = np.maximum(periodogram, 1e-20)
    log_freq = np.log(4.0 * np.sin(lam / 2.0) ** 2)
    log_per = np.log(periodogram)
    x_mean = float(np.mean(log_freq))
    y_mean = float(np.mean(log_per))
    denom = float(np.sum((log_freq - x_mean) ** 2))
    if denom < 1e-20:
        return None
    beta = float(np.sum((log_freq - x_mean) * (log_per - y_mean)) / denom)
    d = float(-0.5 * beta)
    if not np.isfinite(d):
        return None
    return float(np.clip(d, -0.499, 0.499))


def _arfima_spectrum_shape(lam: np.ndarray, d: float) -> np.ndarray:
    h = np.abs(2.0 * np.sin(lam / 2.0)) ** (-2.0 * d)
    return np.maximum(h, 1e-12)


def _whittle_profile_negloglik(d: float, lam: np.ndarray, i_per: np.ndarray) -> float:
    if not -0.499 < d < 0.499:
        return 1e12
    h = _arfima_spectrum_shape(lam, d)
    sig2 = float(np.mean(i_per / h))
    if sig2 <= 0.0 or not np.isfinite(sig2):
        return 1e12
    f = (sig2 / (2.0 * np.pi)) * h
    return float(np.mean(np.log(f) + i_per / f))


def _whittle_arfima_d(x: np.ndarray, *, m: int | None = None) -> float | None:
    """Gaussian Whittle MLE for ARFIMA(0,d,0) spectral shape (fractional noise)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 128:
        return None
    x = x - np.mean(x)
    if m is None:
        m = max(8, n // 8)
    m = min(m, n // 2 - 1)
    if m < 8:
        return None
    j = np.arange(1, m + 1, dtype=float)
    lam = 2.0 * np.pi * j / n
    fft = np.fft.rfft(x)
    i_per = (np.abs(fft[1 : m + 1]) ** 2) / n
    i_per = np.maximum(i_per, 1e-20)
    res = minimize_scalar(
        _whittle_profile_negloglik,
        args=(lam, i_per),
        bounds=(-0.49, 0.49),
        method="bounded",
    )
    if not res.success or not np.isfinite(res.fun):
        return None
    return float(np.clip(res.x, -0.499, 0.499))


def _local_whittle_objective(d: float, lam: np.ndarray, i_per: np.ndarray) -> float:
    """Profile local Whittle (Robinson-type) objective R_m(d)."""
    if not -0.499 < d < 0.499:
        return 1e12
    g = float(np.mean((lam ** (2.0 * d)) * i_per))
    if g <= 0.0 or not np.isfinite(g):
        return 1e12
    return float(np.log(g) - 2.0 * d * float(np.mean(np.log(lam))))


def _modified_local_whittle_d(x: np.ndarray, *, m: int | None = None) -> float | None:
    """Modified local Whittle estimator of memory d (low-frequency band)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 256:
        return None
    x = x - np.mean(x)
    if m is None:
        m = max(8, int(n**0.55))
    m = min(m, n // 3)
    if m < 8:
        return None
    j = np.arange(1, m + 1, dtype=float)
    lam = 2.0 * np.pi * j / n
    fft = np.fft.rfft(x)
    i_per = (np.abs(fft[1 : m + 1]) ** 2) / n
    i_per = np.maximum(i_per, 1e-20)
    res = minimize_scalar(
        _local_whittle_objective,
        args=(lam, i_per),
        bounds=(-0.49, 0.49),
        method="bounded",
    )
    if not res.success or not np.isfinite(res.fun):
        return None
    return float(np.clip(res.x, -0.499, 0.499))


class PeriodogramRegressionEstimator(BaseEstimator):
    """Log-periodogram regression (memory parameter d, GPH-type)."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)

        def stat(z: np.ndarray) -> float | None:
            m = int(params["m"]) if params.get("m") is not None else None
            return _log_periodogram_slope_d(z, m=m)

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_periodogram",
            seed_offset=101,
        )


class WhittleMLEEstimator(BaseEstimator):
    """Gaussian Whittle likelihood for ARFIMA(0,d,0) spectral density."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)

        def stat(z: np.ndarray) -> float | None:
            m = int(params["m"]) if params.get("m") is not None else None
            return _whittle_arfima_d(z, m=m)

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_whittle",
            seed_offset=203,
        )


class ModifiedLocalWhittleEstimator(BaseEstimator):
    """Modified (Gaussian) local Whittle estimator of long-memory parameter d."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)

        def stat(z: np.ndarray) -> float | None:
            m = int(params["m"]) if params.get("m") is not None else None
            return _modified_local_whittle_d(z, m=m)

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_mlw",
            seed_offset=307,
        )
