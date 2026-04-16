from __future__ import annotations

import time

import numpy as np

from lrdbench.bootstrap import bootstrap_statistic_distribution, symmetric_percentile_cis
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
