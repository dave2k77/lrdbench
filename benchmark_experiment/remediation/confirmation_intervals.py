"""Fixed interval comparators for the scoped confirmation protocol.

No benchmark truth enters this module. Interval availability requires every
requested statistic draw; failed/invalid draws stay aligned in the stored arrays.
"""

from __future__ import annotations

import time

import numpy as np

from lrdbench.bootstrap import circular_block_resample
from lrdbench.estimators.geometric import _ghe_hurst, _higuchi_hurst_proxy, _path_from_increments
from lrdbench.estimators.spectral import _log_periodogram_regression_d

try:
    from . import confirmation_batch as batch
    from . import interval_candidates as ci
    from . import run_mean_comparison as mean
except ImportError:
    import confirmation_batch as batch
    import interval_candidates as ci
    import run_mean_comparison as mean

METHODS = ("GPH::narrow_band", "Higuchi", "GHE")
CANDIDATES = (
    "cbc_raw_percentile",
    "cbc_raw_basic",
    "cbc_centered_percentile",
    "cbc_centered_basic",
    "unknown_fgn_centered_basic",
)


def statistic(x, method):
    """Match the frozen classical point roster, including its GHE lag rule."""
    if method == "GPH::narrow_band":
        d = _log_periodogram_regression_d(x, m=32, taper=None)
        return None if d is None else d + 0.5
    path = _path_from_increments(x)
    if method == "Higuchi":
        return _higuchi_hurst_proxy(path, k_max=32)
    if method == "GHE":
        return _ghe_hurst(path, n_scales=18, h_min=1, h_max=len(path) // 8, q=1.0)
    raise ValueError("Unsupported frozen interval method.")


def evaluate(samples, method):
    return batch.evaluate(samples, method, statistic)


def aligned_interval(point, values, *, center, construction, requested, nominal=0.95):
    if len(values) != requested or not np.isfinite(values).all():
        return None, "incomplete_or_nonfinite_bootstrap_draws"
    interval = ci.bootstrap_interval(
        point, values, center=center, method=construction, nominal=nominal
    )
    return interval, None if interval is not None else "invalid_point_or_bootstrap_center"


def fit_record(x, *, seeds, draws=1999, prefixes=None):
    """Two physical pools, nine statistic streams, sixteen interval comparisons.

    Prefix intervals support numerical-stability rehearsal; confirmatory use has
    exactly the one predeclared draw count. No data-dependent stopping rule.
    """
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or len(x) < 512 or not np.isfinite(x).all():
        raise ValueError("This interval study requires finite vectors of length >= 512.")
    if type(draws) is not int or draws < 5 or set(seeds) != {"cbc", "fgn"}:
        raise ValueError("Explicit pool seeds and at least five draws are required.")
    prefixes = sorted(set(prefixes or [draws]))
    if any(type(b) is not int or not 5 <= b <= draws for b in prefixes):
        raise ValueError("Invalid stored draw prefix.")
    start = time.perf_counter()
    points, point_failures = {}, {}
    for treatment, values in (("raw", x), ("centered", mean.centered(x))):
        for method in METHODS:
            key = f"{treatment}:{method}"
            try:
                value = statistic(values, method)
                points[key] = value if value is not None and np.isfinite(value) else None
                if points[key] is None:
                    point_failures[key] = "nonfinite_point"
            except Exception as exc:
                points[key] = None
                point_failures[key] = f"exception:{type(exc).__name__}:{exc}"
    point_seconds = time.perf_counter() - start
    start = time.perf_counter()
    try:
        model = mean.fit_unknown_mean_fgn(x)
        model_failure = None
    except Exception as exc:
        model, model_failure = None, f"exception:{type(exc).__name__}:{exc}"
    model_seconds = time.perf_counter() - start
    pools, intervals = {}, []
    for pool in ("cbc", "fgn"):
        start = time.perf_counter()
        rng = np.random.default_rng(seeds[pool])
        failure = None
        try:
            if pool == "cbc":
                samples = np.asarray(
                    [circular_block_resample(x, rng, len(x) // 16) for _ in range(draws)]
                )
            elif model is not None:
                samples = ci.fitted_fgn_samples(model, len(x), draws, rng) + model["mean"]
            else:
                samples = np.empty((0, len(x)))
                failure = model_failure
        except Exception as exc:
            samples = np.empty((0, len(x)))
            failure = f"exception:{type(exc).__name__}:{exc}"
        generation_seconds = time.perf_counter() - start
        stats_start = time.perf_counter()
        statistics, accounting = {}, {}
        for treatment in ("raw", "centered") if pool == "cbc" else ("centered",):
            transformed = samples if treatment == "raw" else mean.centered(samples)
            for method in METHODS:
                key = f"{treatment}:{method}"
                distribution, counts = evaluate(transformed, method)
                statistics[key], accounting[key] = distribution.tolist(), counts
                center = points[key] if pool == "cbc" else model["H"] if model else None
                for construction in ("percentile", "basic") if pool == "cbc" else ("basic",):
                    candidate = (
                        f"cbc_{treatment}_{construction}"
                        if pool == "cbc"
                        else "unknown_fgn_centered_basic"
                    )
                    for b in prefixes:
                        interval, reason = (
                            (None, failure or point_failures.get(key) or "model_failure")
                            if center is None
                            else aligned_interval(
                                points[key],
                                distribution[:b],
                                center=center,
                                construction=construction,
                                requested=b,
                            )
                        )
                        intervals.append(
                            {
                                "method": method,
                                "candidate": candidate,
                                "treatment": treatment,
                                "draws": b,
                                "point": points[key],
                                "ci_low": interval[0] if interval else None,
                                "ci_high": interval[1] if interval else None,
                                "nominal": 0.95,
                                "available": interval is not None,
                                "unavailable_reason": reason,
                                "pool": pool,
                            }
                        )
        pools[pool] = {
            "seed": seeds[pool],
            "requested_records": draws,
            "generated_records": len(samples),
            "generation_failure": failure,
            "generation_seconds": generation_seconds,
            "statistic_seconds": time.perf_counter() - stats_start,
            "statistics": statistics,
            "accounting": accounting,
        }
    interval = ci.gph_asymptotic_interval(
        points["raw:GPH::narrow_band"], len(x), m=32, nominal=0.95
    )
    for b in prefixes:
        intervals.append(
            {
                "method": "GPH::narrow_band",
                "candidate": "gph_normal_raw",
                "treatment": "raw",
                "draws": b,
                "point": points["raw:GPH::narrow_band"],
                "ci_low": interval[0] if interval else None,
                "ci_high": interval[1] if interval else None,
                "nominal": 0.95,
                "available": interval is not None,
                "unavailable_reason": None if interval else "invalid_point",
                "pool": None,
            }
        )
    return {
        "points": points,
        "point_failures": point_failures,
        "model": model,
        "model_failure": model_failure,
        "point_seconds": point_seconds,
        "model_seconds": model_seconds,
        "pools": pools,
        "intervals": intervals,
    }
