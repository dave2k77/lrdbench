from __future__ import annotations

import numpy as np
from numpy.linalg import cholesky
from scipy.signal import fftconvolve, lfilter


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
    # FFT convolution: O((n+trunc) log(n+trunc)) vs O(n*trunc) for the direct
    # method. The truncated MA filter can have ~50k taps, so the direct
    # ``np.convolve`` dominates generation cost for the larger benchmark suites.
    x = fftconvolve(eps, psi, mode="valid")[:n]
    return float(sigma) * x


def simulate_mrw(
    n: int,
    hurst: float,
    rng: np.random.Generator,
    *,
    sigma: float = 1.0,
    lambda2: float = 0.02,
    integral_scale: int | None = None,
) -> np.ndarray:
    """Approximate lognormal multifractal random walk increments.

    The implementation uses fGn innovations modulated by a correlated lognormal
    volatility field. It is intended as a reproducible benchmark generator, not
    an exact Bacry-Muzy simulation.
    """
    if n < 2:
        raise ValueError("n must be at least 2 for MRW")
    if not (0.0 < hurst < 1.0):
        raise ValueError("H must lie in (0, 1) for MRW")
    if lambda2 < 0.0:
        raise ValueError("lambda2 must be non-negative for MRW")
    if integral_scale is None:
        integral_scale = max(8, n // 4)
    scale_len = int(np.clip(integral_scale, 2, n))

    base = simulate_fgn(n, hurst, rng, sigma=1.0)
    if lambda2 == 0.0:
        return float(sigma) * base

    kernel = 1.0 / np.sqrt(np.arange(1, scale_len + 1, dtype=float))
    kernel = kernel / float(np.sqrt(np.sum(kernel * kernel)))
    white = rng.standard_normal(n + scale_len - 1)
    field = np.convolve(white, kernel, mode="valid")[:n]
    field = field - float(np.mean(field))
    sd = float(np.std(field))
    if sd < 1e-12:
        raise ValueError("failed to construct non-degenerate MRW volatility field")
    field = field / sd

    omega = np.sqrt(float(lambda2)) * field - 0.5 * float(lambda2)
    return np.asarray(float(sigma) * base * np.exp(omega), dtype=float)


def simulate_fou(
    n: int,
    hurst: float,
    theta: float,
    rng: np.random.Generator,
    *,
    sigma: float = 1.0,
    dt: float = 1.0,
    burnin: int | None = None,
) -> np.ndarray:
    """Discrete fractional Ornstein-Uhlenbeck path driven by fGn innovations.

    This implementation uses a first-order Euler–Maruyama-style discretisation:
    ``x_i = rho * x_{i-1} + epsilon_i`` where ``rho = exp(-theta*dt)`` and
    ``epsilon`` is fGn scaled by ``sigma * dt**H``. It is **not** an exact
    simulation of the continuous fractional Ornstein–Uhlenbeck process; it is
    a reproducible benchmark-grade approximation suitable for moderate ``dt``.
    """
    if n < 2:
        raise ValueError("n must be at least 2 for fOU")
    if not (0.0 < hurst < 1.0):
        raise ValueError("H must lie in (0, 1) for fOU")
    if theta <= 0.0:
        raise ValueError("theta must be positive for fOU")
    if dt <= 0.0:
        raise ValueError("dt must be positive for fOU")
    if burnin is None:
        burnin = min(max(4 * n, 64), 4096)
    burn = max(0, int(burnin))

    total = n + burn
    innovations = simulate_fgn(total, hurst, rng, sigma=float(sigma) * (float(dt) ** hurst))
    rho = float(np.exp(-float(theta) * float(dt)))
    x = np.zeros(total, dtype=float)
    for i in range(1, total):
        x[i] = rho * x[i - 1] + innovations[i]
    out = x[burn:]
    return out - float(np.mean(out))


def simulate_multitimescale(
    n: int,
    rng: np.random.Generator,
    *,
    n_components: int = 8,
    tau_min: float = 1.5,
    tau_max: float = 16.0,
    beta_target: float = 1.0,
    sigma: float = 1.0,
    burnin: int | None = None,
) -> np.ndarray:
    """Superposition of AR(1) processes with geometrically-spread timescales.

    Builds ``x_t = sum_i sqrt(w_i) * u_i,t`` where each ``u_i`` is a unit-variance
    AR(1) with decay ``rho_i = exp(-1/tau_i)`` driven by independent white noise,
    and the timescales ``tau_i`` are geometrically spaced over ``[tau_min, tau_max]``.
    The weights ``w_i ~ tau_i**beta_target`` shape the aggregate spectral density to
    approximate ``S(f) ~ f^(-beta_target)`` across the band ``[1/tau_max, 1/tau_min]``.

    A *finite* sum of exponentially-decaying components has a summable
    autocovariance and a bounded, strictly positive spectral density at zero
    frequency -- it is genuinely short-memory (Hurst 0.5, no long-range
    dependence). Over finite samples, however, the spread of timescales mimics
    power-law scaling and can fool LRD estimators. This makes it a controlled null
    for true-vs-apparent-LRD discrimination.
    """
    if n < 2:
        raise ValueError("n must be at least 2 for multi_timescale")
    if n_components < 1:
        raise ValueError("n_components must be >= 1")
    if not (0.0 < tau_min <= tau_max):
        raise ValueError("require 0 < tau_min <= tau_max")

    if n_components == 1:
        taus = np.asarray([float(tau_min)])
    else:
        ratios = np.arange(n_components, dtype=float) / (n_components - 1)
        taus = float(tau_min) * (float(tau_max) / float(tau_min)) ** ratios
    rhos = np.exp(-1.0 / taus)
    weights = taus**float(beta_target)
    weights = weights / float(np.sum(weights))

    if burnin is None:
        burnin = int(min(max(4.0 * float(tau_max), 64.0), 8192.0))
    burn = max(0, int(burnin))
    total = n + burn

    x = np.zeros(total, dtype=float)
    for rho, w in zip(rhos, weights, strict=True):
        # Unit-variance AR(1): innovation std = sqrt(1 - rho**2).
        innov = rng.standard_normal(total) * float(np.sqrt(1.0 - rho**2))
        comp = lfilter([1.0], [1.0, -float(rho)], innov)
        x += float(np.sqrt(w)) * comp

    out = x[burn:]
    out = out - float(np.mean(out))
    std = float(np.std(out))
    if std > 0.0:
        out = out / std
    scaled: np.ndarray = float(sigma) * out
    return scaled
