from __future__ import annotations

import time

import numpy as np

from lrdbench.bootstrap import bootstrap_statistic_distribution, symmetric_percentile_cis
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
