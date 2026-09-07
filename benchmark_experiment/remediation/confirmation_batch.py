"""Bounded-memory equation-equivalent bootstrap statistics for the fixed roster.

Rows with degenerate scales fall back to the scalar reference, preserving its
individual validity and exception accounting. This does not change package code.
"""

from __future__ import annotations

from collections import Counter

import numpy as np


def slope(regressor, values):
    centered = regressor - regressor.mean()
    return np.sum(centered * (values - values.mean(axis=1, keepdims=True)), axis=1) / np.sum(
        centered**2
    )


def statistics(samples, method):
    x = np.asarray(samples, dtype=float)
    if x.ndim != 2 or x.shape[1] < 512:
        raise ValueError("Batched confirmation statistics require rows of length >= 512.")
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite rows require scalar accounting.")
    if method == "GPH::narrow_band":
        x = x - x.mean(axis=1, keepdims=True)
        x = x / np.max(np.abs(x), axis=1, keepdims=True)
        x -= x.mean(axis=1, keepdims=True)
        periodogram = np.abs(np.fft.rfft(x, axis=1)[:, 1:33]) ** 2 / x.shape[1]
        regressor = np.log(4 * np.sin(np.pi * np.arange(1, 33) / x.shape[1]) ** 2)
        return 0.5 - slope(regressor, np.log(np.maximum(periodogram, 1e-20)))
    path = np.concatenate([np.zeros((len(x), 1)), np.cumsum(x, axis=1)], axis=1)
    n = path.shape[1]
    if method == "GHE":
        path -= path.mean(axis=1, keepdims=True)
        path /= np.max(np.abs(path), axis=1, keepdims=True)
        lags = np.unique(np.round(np.geomspace(1, n // 8, 18)).astype(int))
        moments = np.column_stack(
            [np.mean(np.abs(path[:, h:] - path[:, :-h]), axis=1) for h in lags]
        )
        return slope(np.log(lags.astype(float)), np.log(moments))
    if method == "Higuchi":
        lengths = []
        for k in range(1, 33):
            offsets = np.arange(n - k) % k
            terms = (n - np.arange(k) - 1) // k
            # Distribute mean-over-offset weights onto each lag difference.
            # This is the same sum as bincount -> normalize each offset -> mean.
            weights = (n - 1) / (terms[offsets] * k * k * k)
            lengths.append(np.sum(np.abs(path[:, k:] - path[:, :-k]) * weights, axis=1))
        return 2 - slope(np.log(1 / np.arange(1, 33)), np.log(np.column_stack(lengths)))
    raise ValueError("Unsupported fixed batched method.")


def evaluate(samples, method, scalar, *, batch_size=64):
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch_size must be positive.")
    values = np.full(len(samples), np.nan)
    invalid, failed, reasons = 0, 0, Counter()
    for start in range(0, len(samples), batch_size):
        stop = min(start + batch_size, len(samples))
        try:
            with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                result = statistics(samples[start:stop], method)
            fallback = np.flatnonzero(~np.isfinite(result))
            values[start:stop] = result
        except Exception:
            # Retry via the reference implementation so every row keeps its
            # actual failure reason; batch-level errors never drop a batch.
            fallback = np.arange(stop - start)
        values[start + fallback] = np.nan
        for i in fallback:
            try:
                value = scalar(samples[start + i], method)
                if value is None or not np.isfinite(value):
                    invalid += 1
                    reasons["nonfinite_statistic"] += 1
                else:
                    values[start + i] = value
            except Exception as exc:
                failed += 1
                reasons[f"exception:{type(exc).__name__}"] += 1
    return values, {
        "attempted": len(samples),
        "used": int(np.isfinite(values).sum()),
        "invalid": invalid,
        "failed": failed,
        "failure_reasons": dict(reasons),
    }
