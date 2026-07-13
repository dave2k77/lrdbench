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
from lrdbench.estimators.spectral import _log_periodogram_regression_d
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
