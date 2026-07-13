"""Timescale estimators: characteristic autocorrelation-decay time ``tau``.

These estimators target the ``timescale_tau`` estimand -- the exponential
decay constant ``tau0`` of the autocorrelation function, ``rho(k) = exp(-k / tau0)``.
``tau`` is reported in **samples** (the fOU mean-reversion truth ``tau = 1/(theta*dt)``
is likewise defined in samples). For a true long-range-dependent process the ACF
decays as a power law rather than an exponential, so an exponential fit is
misspecified and ``tau`` becomes fit-window dependent -- this is the intended
diagnostic contrast between multi-timescale and scale-free dynamics, not a bug.
"""

from __future__ import annotations

import numpy as np

from lrdbench.estimators._fit_utils import fit_with_block_bootstrap
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def _autocorrelation(x: np.ndarray, max_lag: int) -> np.ndarray:
    """Biased sample autocorrelation ``rho[0..max_lag]`` via FFT (rho[0] == 1)."""
    n = x.size
    x = x - np.mean(x)
    nfft = 1
    while nfft < 2 * n:
        nfft *= 2
    f = np.fft.rfft(x, nfft)
    acf = np.fft.irfft(f * np.conj(f), nfft)[: max_lag + 1]
    if acf[0] <= 0.0:
        return np.zeros(max_lag + 1)
    normed: np.ndarray = acf / acf[0]
    return normed


def _acf_exponential_tau(
    x: np.ndarray, *, max_lag: int | None = None, rho_floor: float = 0.1
) -> float | None:
    """Effective timescale ``tau0`` from a log-linear fit of the ACF.

    Fits ``log rho(k) = a - k / tau0`` (free intercept) over the clean
    exponential regime of the autocorrelation -- lags ``k >= 1`` while
    ``rho(k) >= rho_floor`` (default 0.1), or up to an explicit ``max_lag``.
    Restricting to ``rho >= rho_floor`` excludes the noisy small-``rho`` tail
    where the sample ACF sits above the true exponential (noise floor) and
    otherwise flattens the fitted slope, inflating ``tau``. Returns
    ``tau0 = -1 / slope``, or ``None`` (recorded as an invalid estimate) when the
    series is too short, the ACF does not decay, or the fit is degenerate.
    """
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 16:
        return None
    if np.dot(x - np.mean(x), x - np.mean(x)) <= 0.0:
        return None

    cap = n // 4 if max_lag is None else min(int(max_lag), n - 1)
    cap = max(cap, 2)
    acf = _autocorrelation(x, cap)

    if max_lag is None:
        # Fit within the leading exponential band rho(k) >= rho_floor.
        below = np.where(acf[1:] < rho_floor)[0]
        upper = int(below[0]) if below.size else cap
    else:
        upper = cap
    upper = min(upper, cap)
    if upper < 3:
        return None

    lags = np.arange(1, upper + 1, dtype=float)
    rho = acf[1 : upper + 1]
    mask = rho > 1e-6
    if int(mask.sum()) < 3:
        return None

    k = lags[mask]
    y = np.log(rho[mask])
    kbar = float(k.mean())
    ybar = float(y.mean())
    denom = float(np.sum((k - kbar) ** 2))
    if denom <= 0.0:
        return None
    slope = float(np.sum((k - kbar) * (y - ybar)) / denom)
    if slope >= -1e-8:  # flat or growing ACF -> no finite decay timescale
        return None
    tau = -1.0 / slope
    if not np.isfinite(tau) or tau <= 0.0:
        return None
    return float(tau)


class ACFDecayEstimator(BaseEstimator):
    """Autocorrelation-decay timescale ``tau`` (log-linear ACF fit).

    Targets the ``timescale_tau`` estimand, reporting the exponential decay
    constant in samples. Correctly specified for AR(1)/OU-type single-timescale
    dynamics; deliberately misspecified (and thus window-dependent) under true
    long-range dependence.
    """

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)
        max_lag = int(params["max_lag"]) if params.get("max_lag") is not None else None
        rho_floor = float(params.get("rho_floor", 0.1))

        def stat(z: np.ndarray) -> float | None:
            return _acf_exponential_tau(z, max_lag=max_lag, rho_floor=rho_floor)

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="acf_has_no_finite_decay_timescale",
            seed_offset=211,
        )
