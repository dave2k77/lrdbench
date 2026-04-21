from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np

from lrdbench.bootstrap import bootstrap_statistic_distribution, symmetric_percentile_cis
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def fit_with_block_bootstrap(
    record: SeriesRecord,
    spec: EstimatorSpec,
    *,
    statistic: Callable[[np.ndarray], float | None],
    estimator_version: str,
    failure_reason: str,
    seed_offset: int = 0,
) -> EstimateResult:
    """Run point estimate plus optional circular block-bootstrap CIs (RS/GPH pattern)."""
    t0 = time.perf_counter()
    params = dict(spec.parameter_schema)
    n_boot = int(params.get("n_bootstrap", 200))
    block_len = int(params.get("bootstrap_block_len", 0)) or max(4, record.values.size // 10)
    levels_raw = params.get("ci_levels")
    ci_levels = tuple(float(x) for x in levels_raw) if levels_raw is not None else (0.95,)
    seed = seed_offset
    if record.provenance is not None and record.provenance.seed is not None:
        seed = int(record.provenance.seed) + seed_offset
    rng = np.random.default_rng(seed & (2**32 - 1))

    try:
        point = statistic(record.values)
        dt = time.perf_counter() - t0
        if point is None or not np.isfinite(point):
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=spec.name,
                point=None,
                runtime_seconds=dt,
                valid=False,
                failure_reason=failure_reason,
                estimator_version=estimator_version,
            )

        samples = bootstrap_statistic_distribution(
            record.values,
            rng,
            statistic,
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
            estimator_name=spec.name,
            point=float(point),
            ci_low=ci_low,
            ci_high=ci_high,
            runtime_seconds=dt,
            valid=True,
            estimator_version=estimator_version,
            diagnostics=diag,
            bootstrap_cis=cis,
        )
    except Exception as exc:  # noqa: BLE001
        dt = time.perf_counter() - t0
        return EstimateResult(
            record_id=record.record_id,
            estimator_name=spec.name,
            point=None,
            runtime_seconds=dt,
            valid=False,
            failure_reason=f"exception:{type(exc).__name__}:{exc}",
            estimator_version=estimator_version,
        )
