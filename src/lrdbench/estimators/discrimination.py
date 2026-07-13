"""Discrimination estimators: per-series decision scores for the ``lrd_class`` estimand.

A discriminator emits a score in ``[0, 1]`` (higher = stronger evidence of true
long-range dependence) rather than a scalar estimand. Scores are ranked/thresholded
by the classification metric family (roc_auc, balanced_accuracy, TPR, FPR).

``ThresholdHurstDiscriminator`` is the naive baseline: estimate a Hurst exponent
with a standard estimator, then squash it through a logistic centred at ``h0``. Its
ROC-AUC measures exactly how well a single scaling estimate separates true LRD from
short-memory (incl. multi-timescale) nulls -- the floor the Phase 2 results
characterised as a false-positive rate.
"""

from __future__ import annotations

import math

import numpy as np

from lrdbench.estimators._fit_utils import fit_with_block_bootstrap
from lrdbench.estimators.spectral import (
    _arfima_spectrum_shape,
    _log_periodogram_regression_d,
    _modified_local_whittle_d,
    _whittle_arfima_d,
)
from lrdbench.estimators.temporal import _dfa_hurst, _rs_hurst_proxy
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def _hurst_by_base(x: np.ndarray, base: str) -> float | None:
    if base == "dfa":
        return _dfa_hurst(x)
    if base == "rs":
        return _rs_hurst_proxy(x)
    if base == "gph":
        d = _log_periodogram_regression_d(x)
        return None if d is None else d + 0.5
    raise ValueError(f"unknown discriminator base: {base!r}")


def _logistic(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _dfa_fluctuation_curve(
    x: np.ndarray, *, detrend_order: int = 1, min_scale: int = 8, max_scale: int | None = None
) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (log scale, log fluctuation) points of the DFA curve, for slope analysis."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 64:
        return None
    y = np.cumsum(x - np.mean(x))
    if max_scale is None:
        max_scale = n // 4
    max_scale = min(max_scale, n // 2)
    order = max(0, int(detrend_order))
    scales: list[int] = []
    s = min_scale
    while s <= max_scale:
        scales.append(int(s))
        s = int(max(s + 1, round(s * 1.25)))
    log_s: list[float] = []
    log_f: list[float] = []
    for box in scales:
        if box < order + 2:
            continue
        n_seg = n // box
        if n_seg < 2:
            continue
        t = np.arange(box, dtype=float)
        rss = 0.0
        count = 0
        for seg in range(n_seg):
            seg_y = y[seg * box : (seg + 1) * box]
            if order == 0:
                fit = np.full_like(seg_y, float(np.mean(seg_y)))
            else:
                a = np.vander(t, order + 1, increasing=True)
                coef, _, _, _ = np.linalg.lstsq(a, seg_y, rcond=None)
                fit = a @ coef
            resid = seg_y - fit
            rss += float(np.sum(resid * resid))
            count += box
        if count == 0 or rss <= 0.0:
            continue
        log_s.append(math.log(float(box)))
        log_f.append(0.5 * math.log(rss / count))
    if len(log_s) < 4:
        return None
    return np.asarray(log_s, dtype=float), np.asarray(log_f, dtype=float)


def _band_slope(xs: np.ndarray, ys: np.ndarray) -> float | None:
    xm = float(np.mean(xs))
    denom = float(np.sum((xs - xm) ** 2))
    if denom < 1e-20:
        return None
    return float(np.sum((xs - xm) * (ys - float(np.mean(ys)))) / denom)


def _ar_yule_walker(x: np.ndarray, p: int) -> tuple[np.ndarray, float] | None:
    """Fit AR(p) by Yule-Walker; return (phi[1..p], innovation variance)."""
    x = np.asarray(x, dtype=float) - float(np.mean(x))
    n = x.size
    if n < p + 8:
        return None
    r = np.array([float(np.dot(x[: n - k], x[k:])) / n for k in range(p + 1)])
    if r[0] <= 0.0:
        return None
    toeplitz = np.array([[r[abs(i - j)] for j in range(p)] for i in range(p)])
    try:
        phi = np.linalg.solve(toeplitz, r[1 : p + 1])
    except np.linalg.LinAlgError:
        return None
    sigma2 = float(r[0] - float(np.dot(phi, r[1 : p + 1])))
    if sigma2 <= 0.0 or not np.isfinite(sigma2):
        return None
    return phi, sigma2


def _whittle_nll_sum(f: np.ndarray, i_per: np.ndarray) -> float:
    """Summed Whittle negative log-likelihood over frequencies for spectral density f."""
    f = np.maximum(f, 1e-20)
    return float(np.sum(np.log(f) + i_per / f))


class ThresholdHurstDiscriminator(BaseEstimator):
    """Baseline LRD discriminator: logistic squash of a Hurst estimate.

    Parameters (``parameter_schema``): ``base`` in {``dfa``, ``gph``, ``rs``}
    (default ``dfa``), ``h0`` decision centre (default 0.55), ``width`` logistic
    scale (default 0.05). Score = ``sigmoid((H - h0) / width)`` in ``[0, 1]``.
    """

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)
        base = str(params.get("base", "dfa")).lower()
        h0 = float(params.get("h0", 0.55))
        width = float(params.get("width", 0.05))

        def stat(z: np.ndarray) -> float | None:
            h = _hurst_by_base(z, base)
            if h is None or not np.isfinite(h):
                return None
            return _logistic((float(h) - h0) / width)

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_hurst_discriminator",
            seed_offset=311,
        )


def _lowfreq_spectral_score(x: np.ndarray, *, m_power: float, d0: float, width: float) -> float | None:
    """Local-Whittle memory parameter at low frequency, squashed to [0, 1].

    True LRD keeps a positive memory parameter as the frequency band shrinks to
    zero; a short-memory / multi-timescale spectrum flattens (bounded at f=0), so
    its low-frequency ``d`` collapses toward 0. Formalises GPH's robustness.
    """
    n = x.size
    m = max(6, int(n**m_power))
    d = _modified_local_whittle_d(x, m=m)
    if d is None:
        return None
    return _logistic((float(d) - d0) / width)


class LowFreqSpectralDiscriminator(BaseEstimator):
    """LRD discriminator from the low-frequency memory parameter (local Whittle)."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)
        m_power = float(params.get("m_power", 0.45))
        d0 = float(params.get("d0", 0.075))
        width = float(params.get("width", 0.05))

        def stat(z: np.ndarray) -> float | None:
            return _lowfreq_spectral_score(z, m_power=m_power, d0=d0, width=width)

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_lowfreq_spectral",
            seed_offset=313,
        )


def _scale_crossover_score(x: np.ndarray, *, h0: float, width: float) -> float | None:
    """Score from the large-scale DFA slope.

    Under true LRD the DFA exponent is scale-invariant and stays above 0.5 at all
    scales. A multi-timescale short-memory process crosses over to slope ~0.5 at
    scales beyond its largest timescale, so the large-scale-band slope drops.
    """
    curve = _dfa_fluctuation_curve(x)
    if curve is None:
        return None
    log_s, log_f = curve
    k = len(log_s)
    half = k // 2
    slope_high = _band_slope(log_s[half:], log_f[half:])
    if slope_high is None:
        return None
    return _logistic((slope_high - h0) / width)


class ScaleCrossoverDiscriminator(BaseEstimator):
    """LRD discriminator from scale-invariance of the DFA exponent (crossover)."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)
        h0 = float(params.get("h0", 0.55))
        width = float(params.get("width", 0.06))

        def stat(z: np.ndarray) -> float | None:
            return _scale_crossover_score(z, h0=h0, width=width)

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_scale_crossover",
            seed_offset=317,
        )


def _ic_model_select_score(x: np.ndarray, *, ar_orders: tuple[int, ...], scale: float) -> float | None:
    """Score from BIC comparison of ARFIMA(0,d,0) against short-memory AR(p).

    Uses the summed Whittle likelihood on a common frequency grid. If the
    fractionally-integrated model wins on BIC the series carries genuine
    long-range dependence; if a low-order AR wins it is short-memory (a
    multi-timescale superposition is well approximated by AR at bounded f).
    """
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 128:
        return None
    x = x - float(np.mean(x))
    m = n // 2 - 1
    j = np.arange(1, m + 1, dtype=float)
    lam = 2.0 * np.pi * j / n
    fft = np.fft.rfft(x)
    i_per = np.maximum((np.abs(fft[1 : m + 1]) ** 2) / n, 1e-20)

    d = _whittle_arfima_d(x, m=m)
    if d is None:
        return None
    h_shape = _arfima_spectrum_shape(lam, d)
    sig2_f = float(np.mean(i_per / h_shape))
    f_arfima = (sig2_f / (2.0 * np.pi)) * h_shape
    bic_arfima = 2.0 * _whittle_nll_sum(f_arfima, i_per) + 2.0 * math.log(m)

    bic_ar_best = None
    for p in ar_orders:
        fit = _ar_yule_walker(x, p)
        if fit is None:
            continue
        phi, sigma2 = fit
        transfer = np.ones_like(lam, dtype=complex)
        for k in range(1, p + 1):
            transfer -= phi[k - 1] * np.exp(-1j * k * lam)
        f_ar = (sigma2 / (2.0 * np.pi)) / np.maximum(np.abs(transfer) ** 2, 1e-20)
        bic_ar = 2.0 * _whittle_nll_sum(f_ar, i_per) + (p + 1) * math.log(m)
        if bic_ar_best is None or bic_ar < bic_ar_best:
            bic_ar_best = bic_ar
    if bic_ar_best is None:
        return None
    # Positive when ARFIMA has the lower (better) BIC -> evidence for LRD.
    return _logistic((bic_ar_best - bic_arfima) / scale)


class ICModelSelectDiscriminator(BaseEstimator):
    """LRD discriminator from BIC model comparison (ARFIMA(0,d,0) vs AR(p))."""

    VERSION = "0.1.0"

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        params = dict(self._spec.parameter_schema)
        orders_raw = params.get("ar_orders", [1, 2])
        ar_orders = tuple(int(o) for o in orders_raw)
        scale = float(params.get("scale", 4.0))

        def stat(z: np.ndarray) -> float | None:
            return _ic_model_select_score(z, ar_orders=ar_orders, scale=scale)

        return fit_with_block_bootstrap(
            record,
            self._spec,
            statistic=stat,
            estimator_version=self.VERSION,
            failure_reason="insufficient_signal_for_ic_model_select",
            seed_offset=319,
        )
