from __future__ import annotations

from collections.abc import Callable

import numpy as np


def circular_block_resample(x: np.ndarray, rng: np.random.Generator, block_len: int) -> np.ndarray:
    """Circular block bootstrap of the same length as x."""
    n = int(x.size)
    if n == 0:
        return x
    bl = max(1, min(block_len, n))
    out: list[float] = []
    while len(out) < n:
        start = int(rng.integers(0, n))
        for j in range(bl):
            out.append(float(x[(start + j) % n]))
    return np.asarray(out[:n], dtype=np.float64)


def bootstrap_statistic_distribution(
    x: np.ndarray,
    rng: np.random.Generator,
    statistic: Callable[[np.ndarray], float | None],
    *,
    n_boot: int,
    block_len: int,
) -> np.ndarray:
    """Return vector of bootstrap replicates (finite values only)."""
    reps: list[float] = []
    for _ in range(max(1, n_boot)):
        xb = circular_block_resample(x, rng, block_len)
        s = statistic(xb)
        if s is not None and np.isfinite(s):
            reps.append(float(s))
    return np.asarray(reps, dtype=np.float64)


def symmetric_percentile_cis(
    samples: np.ndarray, alphas: tuple[float, ...]
) -> tuple[tuple[float, float, float], ...]:
    """For each nominal alpha, CI = [q_{(1-alpha)/2}, q_{1-(1-alpha)/2}]."""
    if samples.size == 0:
        return ()
    out: list[tuple[float, float, float]] = []
    for alpha in sorted({float(a) for a in alphas}):
        if not 0.0 < alpha < 1.0:
            continue
        tail = (1.0 - alpha) / 2.0
        lo = float(np.quantile(samples, tail))
        hi = float(np.quantile(samples, 1.0 - tail))
        out.append((alpha, lo, hi))
    return tuple(out)
