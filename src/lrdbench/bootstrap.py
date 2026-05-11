from __future__ import annotations

from collections.abc import Callable

import numpy as np


def circular_block_resample(x: np.ndarray, rng: np.random.Generator, block_len: int) -> np.ndarray:
    """Circular block bootstrap resample of the same length as ``x``.

    The series is treated as circular (wrap-around at the boundaries) to
    avoid edge artefacts. Blocks are concatenated until the desired length
    is reached, then truncated.

    Args:
        x: 1-D input array.
        rng: NumPy random generator instance.
        block_len: Block length in samples. Clamped to ``[1, len(x)]``.

    Returns:
        A resampled array of the same shape as ``x``.
    """
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
    """Compute a bootstrap distribution for ``statistic`` using circular block resampling.

    Only finite replicate values are retained; ``None`` or non-finite results
    are silently dropped. This is important for estimators that may fail on
    short resampled blocks.

    Args:
        x: 1-D input array (the original time series).
        rng: NumPy random generator instance.
        statistic: Function that takes a 1-D array and returns a scalar or ``None``.
        n_boot: Number of bootstrap replicates.
        block_len: Block length in samples. A common pragmatic default is
            ``max(4, n // 10)``.

    Returns:
        1-D array of finite bootstrap replicates.
    """
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
    """Symmetric percentile confidence intervals from bootstrap samples.

    For each nominal level ``alpha`` the interval is
    ``[q_{(1-alpha)/2}, q_{1-(1-alpha)/2}]`` where ``q`` denotes the sample
    quantile of the bootstrap distribution.

    Args:
        samples: 1-D array of bootstrap replicates (e.g. from
            :func:`bootstrap_statistic_distribution`).
        alphas: Nominal coverage levels (e.g. ``(0.95, 0.99)``). Invalid
            values outside ``(0, 1)`` are skipped.

    Returns:
        Tuple of ``(alpha, lower, upper)`` for each valid, deduplicated alpha.
        Empty if ``samples`` has no elements.
    """
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
