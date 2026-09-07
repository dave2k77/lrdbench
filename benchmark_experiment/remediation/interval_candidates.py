"""Experimental interval candidates with explicit model assumptions.

These research helpers do not change the package's default confidence intervals.
The fGn likelihood assumes a known zero mean and unknown H and marginal variance.
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np
from scipy.linalg import cholesky, solve_triangular, toeplitz
from scipy.optimize import minimize_scalar
from scipy.stats import norm

from lrdbench.estimators.geometric import (
    _ghe_hurst,
    _higuchi_hurst_proxy,
    _path_from_increments,
)
from lrdbench.estimators.spectral import _log_periodogram_regression_d

METHODS = ("GPH", "Higuchi", "GHE")
H_BOUNDS = (0.01, 0.99)


def statistic(x, method):
    if method == "GPH":
        d = _log_periodogram_regression_d(x, m=32, taper=None)
        return None if d is None else d + 0.5
    path = _path_from_increments(x)
    if method == "Higuchi":
        return _higuchi_hurst_proxy(path, k_max=32)
    if method == "GHE":
        return _ghe_hurst(path, h_max=32, q=1.0)
    raise ValueError(f"Unsupported candidate method: {method}")


def fgn_covariance(n, h):
    if not 0 < h < 1 or n < 2:
        raise ValueError("fGn requires n >= 2 and 0 < H < 1")
    k = np.arange(n, dtype=float)
    return (np.abs(k - 1) ** (2 * h) - 2 * k ** (2 * h) + (k + 1) ** (2 * h)) / 2


def profiled_fgn_likelihood(x, h):
    """Twice negative log likelihood after profiling sigma², up to constants.

    Q=x'R(H)^-1 x, sigma²=Q/n; objective=n log(Q/n)+log|R(H)|.
    Known mean zero: no sample demeaning and no fitted mean nuisance parameter.
    """
    factor = cholesky(toeplitz(fgn_covariance(len(x), h)), lower=True, check_finite=False)
    whitened = solve_triangular(factor, x, lower=True, check_finite=False)
    variance = float(np.dot(whitened, whitened) / len(x))
    if not math.isfinite(variance) or variance <= 0:
        raise ValueError("Nonpositive/nonfinite fitted variance")
    objective = len(x) * math.log(variance) + 2 * np.log(np.diag(factor)).sum()
    return float(objective), variance


def fit_zero_mean_fgn(x):
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or len(x) < 64 or not np.isfinite(x).all() or np.ptp(x) == 0:
        raise ValueError("fGn fitting requires a finite nonconstant vector of length >= 64")
    scale = float(np.max(np.abs(x)))
    normalized = x / scale
    grid = np.linspace(*H_BOUNDS, 11)
    objectives = [profiled_fgn_likelihood(normalized, h)[0] for h in grid]
    index = int(np.argmin(objectives))
    bracket = (grid[max(0, index - 1)], grid[min(len(grid) - 1, index + 1)])
    result = minimize_scalar(
        lambda h: profiled_fgn_likelihood(normalized, h)[0],
        bounds=bracket,
        method="bounded",
        options={"xatol": 1e-5, "maxiter": 100},
    )
    if not result.success or not math.isfinite(result.fun):
        raise ValueError("fGn likelihood optimizer failed")
    h = float(result.x) if result.fun <= objectives[index] else float(grid[index])
    objective, variance = profiled_fgn_likelihood(normalized, h)
    return {
        "model": "stationary_gaussian_fgn_known_zero_mean",
        "H": h,
        "sigma": math.sqrt(variance) * scale,
        "mean": 0.0,
        "objective": objective + 2 * len(x) * math.log(scale),
        "bounds": H_BOUNDS,
        "boundary_hit": min(h - H_BOUNDS[0], H_BOUNDS[1] - h) <= 1e-3,
        "optimizer_success": True,
        "covariance_diagonal_jitter": 0.0,
    }


def fitted_fgn_samples(model, n, draws, rng):
    """Draw independent records from the fitted model; no use of benchmark truth."""
    if draws < 1:
        raise ValueError("At least one draw is required")
    factor = cholesky(toeplitz(fgn_covariance(n, model["H"])), lower=True, check_finite=False)
    # Each row consumes one record of random innovations, preserving RNG prefixes.
    noise = rng.normal(size=(draws, n))
    return model["sigma"] * (factor @ noise.T).T


def evaluate_draws(samples, method):
    values, invalid, failed = [], 0, 0
    reasons = Counter()
    for x in samples:
        try:
            value = statistic(x, method)
        except Exception as exc:
            failed += 1
            reasons[f"exception:{type(exc).__name__}"] += 1
            continue
        if value is None or not math.isfinite(value):
            invalid += 1
            reasons["invalid_statistic"] += 1
        else:
            values.append(value)
    return np.asarray(values), {
        "attempted": len(samples),
        "used": len(values),
        "invalid": invalid,
        "failed": failed,
        "failure_reasons": dict(reasons),
    }


def bootstrap_interval(point, samples, *, center, method, nominal=0.95):
    """Percentile or error-pivot interval; center is the bootstrap model target.

    Basic: [T(x)-q_hi(T* - center), T(x)-q_lo(T* - center)].
    For a plug-in model fitted by another estimator, center need not equal T(x).
    """
    samples = np.asarray(samples, dtype=float)
    if not 0 < nominal < 1 or method not in {"percentile", "basic"}:
        raise ValueError("Invalid interval level or construction")
    if point is None or not math.isfinite(point) or not math.isfinite(center):
        return None
    if samples.ndim != 1 or len(samples) < 5 or not np.isfinite(samples).all():
        return None
    tail = (1 - nominal) / 2
    lower, upper = np.quantile(samples, [tail, 1 - tail], method="linear")
    if method == "basic":
        lower, upper = point + center - upper, point + center - lower
    return float(lower), float(upper)


def gph_asymptotic_interval(point, n, *, m=32, nominal=0.95):
    """Un-tapered log-periodogram normal approximation using actual OLS design.

    Working log-periodogram error variance pi²/6 gives Var(d_hat)=pi²/(6 Sxx).
    Sxx/m -> 4 for this squared-sine regressor, hence pi²/(24 m) asymptotically.
    No finite-sample coverage guarantee and no claim that short-memory bias vanishes.
    """
    if n < 64 or not 2 <= m < n // 2 or not 0 < nominal < 1:
        raise ValueError("Invalid untapered GPH design")
    if point is None or not math.isfinite(point):
        return None
    regressor = np.log(4 * np.sin(np.pi * np.arange(1, m + 1) / n) ** 2)
    se = math.sqrt(np.pi**2 / (6 * np.sum((regressor - regressor.mean()) ** 2)))
    radius = float(norm.ppf((1 + nominal) / 2)) * se
    return float(point - radius), float(point + radius)
