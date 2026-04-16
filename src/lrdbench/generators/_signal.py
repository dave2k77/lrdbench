from __future__ import annotations

import numpy as np
from numpy.linalg import cholesky


def fgn_autocovariance(hurst: float, n: int) -> np.ndarray:
    k = np.arange(n, dtype=np.float64)
    out: np.ndarray = 0.5 * (
        np.abs(k + 1.0) ** (2.0 * hurst)
        - 2.0 * np.abs(k) ** (2.0 * hurst)
        + np.abs(k - 1.0) ** (2.0 * hurst)
    )
    return out


def simulate_fgn(
    n: int,
    hurst: float,
    rng: np.random.Generator,
    *,
    sigma: float = 1.0,
) -> np.ndarray:
    """Exact Gaussian fGn via Cholesky of Toeplitz covariance (Phase 1; moderate n)."""
    if n < 2:
        raise ValueError("n must be at least 2 for fGn")
    g = fgn_autocovariance(hurst, n)
    # Build symmetric Toeplitz covariance
    i = np.arange(n)
    j = np.arange(n)
    cov = g[np.abs(i[:, None] - j[None, :])]
    # numerical PD guard
    cov = cov + np.eye(n) * 1e-10
    chol = cholesky(cov)
    z = rng.standard_normal(n)
    x = chol @ z
    return float(sigma) * x


def simulate_fbm(
    n: int,
    hurst: float,
    rng: np.random.Generator,
    *,
    sigma: float = 1.0,
) -> np.ndarray:
    """fBm samples B(0),...,B(n-1) with B(0)=0 via covariance of fBm on integer times."""
    if n < 2:
        raise ValueError("n must be at least 2 for fBm")
    idx = np.arange(1, n, dtype=float)
    m = idx.size
    ii, jj = np.meshgrid(idx, idx, indexing="ij")
    cov = 0.5 * (ii ** (2 * hurst) + jj ** (2 * hurst) - np.abs(ii - jj) ** (2 * hurst))
    cov = cov + np.eye(m) * 1e-10
    chol = cholesky(cov)
    z = rng.standard_normal(m)
    path_tail = float(sigma) * (chol @ z)
    path = np.zeros(n, dtype=float)
    path[1:] = path_tail
    return path


def arfima_ma_coefficients(d: float, trunc: int) -> np.ndarray:
    """MA(∞) coefficients of (1-B)^{-d} for stationary |d|<0.5."""
    if trunc < 1:
        raise ValueError("trunc must be positive")
    psi = np.zeros(trunc + 1, dtype=float)
    psi[0] = 1.0
    for j in range(1, trunc + 1):
        psi[j] = psi[j - 1] * (d + j - 1) / j
    return psi


def simulate_arfima_zero_d_zero(
    n: int,
    d: float,
    rng: np.random.Generator,
    *,
    sigma: float = 1.0,
) -> np.ndarray:
    """ARFIMA(0,d,0) via truncated fractional integration of Gaussian noise."""
    if not (-0.5 < d < 0.5):
        raise ValueError("d must lie in (-0.5, 0.5) for stationary ARFIMA(0,d,0)")
    trunc = min(10 * n, 50000)
    psi = arfima_ma_coefficients(d, trunc)
    eps = rng.standard_normal(n + trunc)
    x = np.convolve(eps, psi, mode="valid")[:n]
    return float(sigma) * x
