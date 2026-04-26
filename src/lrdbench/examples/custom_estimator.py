from __future__ import annotations

import time

import numpy as np

from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


class VarianceRatioEstimator(BaseEstimator):
    """Minimal external estimator example for contributor documentation."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        t0 = time.perf_counter()
        try:
            x = np.asarray(record.values, dtype=float)
            min_n = int(self._spec.parameter_schema.get("min_n", 32))
            if x.size < min_n:
                return EstimateResult(
                    record_id=record.record_id,
                    estimator_name=self._spec.name,
                    point=None,
                    runtime_seconds=time.perf_counter() - t0,
                    valid=False,
                    failure_reason="insufficient_signal_for_variance_ratio",
                    estimator_version=self.VERSION,
                )

            centred = x - float(np.mean(x))
            first_diff = np.diff(centred)
            long_var = float(np.var(centred, ddof=0))
            short_var = float(np.var(first_diff, ddof=0))
            if long_var <= 0.0 or short_var <= 0.0:
                return EstimateResult(
                    record_id=record.record_id,
                    estimator_name=self._spec.name,
                    point=None,
                    runtime_seconds=time.perf_counter() - t0,
                    valid=False,
                    failure_reason="degenerate_signal_for_variance_ratio",
                    estimator_version=self.VERSION,
                )

            # This is a bounded demonstration statistic, not a validated Hurst estimator.
            point = float(np.clip(long_var / (long_var + short_var), 0.0, 1.0))
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self._spec.name,
                point=point,
                runtime_seconds=time.perf_counter() - t0,
                valid=True,
                diagnostics={
                    "long_variance": long_var,
                    "diff_variance": short_var,
                    "example_only": True,
                },
                estimator_version=self.VERSION,
            )
        except Exception as exc:  # noqa: BLE001
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self._spec.name,
                point=None,
                runtime_seconds=time.perf_counter() - t0,
                valid=False,
                failure_reason=f"exception:{type(exc).__name__}:{exc}",
                estimator_version=self.VERSION,
            )


def build_variance_ratio_estimator(spec: EstimatorSpec) -> VarianceRatioEstimator:
    return VarianceRatioEstimator(spec)
