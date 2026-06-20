from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from lrdbench.interfaces import BasePreprocessing
from lrdbench.preprocessing._common import build_preprocessed_series, standardize
from lrdbench.schema import SeriesRecord


def _rolling_mean_std(
    x: np.ndarray,
    *,
    window: int,
    center: bool,
    eps: float,
) -> tuple[np.ndarray, np.ndarray]:
    if window < 2:
        raise ValueError("rolling window must be at least 2")
    if window > x.size:
        raise ValueError("rolling window must not exceed record length")
    if center:
        pad_left = window // 2
        pad_right = window - 1 - pad_left
    else:
        pad_left = window - 1
        pad_right = 0
    mode = "reflect" if x.size > 1 else "edge"
    xp = np.pad(np.asarray(x, dtype=float), (pad_left, pad_right), mode=mode)
    c1 = np.concatenate(([0.0], np.cumsum(xp)))
    c2 = np.concatenate(([0.0], np.cumsum(xp * xp)))
    sums = c1[window:] - c1[:-window]
    sums2 = c2[window:] - c2[:-window]
    mean = sums / float(window)
    var = np.maximum(sums2 / float(window) - mean * mean, 0.0)
    return mean, np.sqrt(var + eps)


def _latent_array(record: SeriesRecord, key: str) -> np.ndarray:
    value = record.latent_components.get(key)
    if value is None:
        raise ValueError(f"record {record.record_id!r} has no latent component {key!r}")
    arr = np.asarray(value, dtype=float)
    if arr.shape != record.values.shape:
        raise ValueError(
            f"latent component {key!r} shape {arr.shape} does not match values {record.values.shape}"
        )
    return arr


class RollingZScorePreprocessing(BasePreprocessing):
    VERSION = "0.1.0"

    @property
    def name(self) -> str:
        return "rolling_zscore"

    @property
    def family(self) -> str:
        return "empirical_variance"

    @property
    def kind(self) -> str:
        return "empirical"

    @property
    def version(self) -> str:
        return self.VERSION

    def apply(
        self,
        record: SeriesRecord,
        *,
        params: Mapping[str, Any],
        seed: int | None,
        manifest_id: str | None,
        new_record_id: str,
    ) -> SeriesRecord:
        _ = seed
        x = np.asarray(record.values, dtype=float)
        window = int(params.get("window", 128))
        eps = float(params.get("eps", 1e-8))
        center = bool(params.get("center", True))
        mean, std = _rolling_mean_std(x, window=window, center=center, eps=eps)
        corrected = standardize((x - mean) / std)
        return build_preprocessed_series(
            record,
            new_record_id=new_record_id,
            values=corrected,
            manifest_id=manifest_id,
            op_name=self.name,
            op_family=self.family,
            op_kind=self.kind,
            op_params=params,
            op_version=self.version,
            correction_target="local_mean_variance",
        )


class PolynomialDetrendPreprocessing(BasePreprocessing):
    VERSION = "0.1.0"

    @property
    def name(self) -> str:
        return "polynomial_detrend"

    @property
    def family(self) -> str:
        return "empirical_trend"

    @property
    def kind(self) -> str:
        return "empirical"

    @property
    def version(self) -> str:
        return self.VERSION

    def apply(
        self,
        record: SeriesRecord,
        *,
        params: Mapping[str, Any],
        seed: int | None,
        manifest_id: str | None,
        new_record_id: str,
    ) -> SeriesRecord:
        _ = seed
        x = np.asarray(record.values, dtype=float)
        order = int(params.get("order", 1))
        if order < 0:
            raise ValueError("polynomial detrend order must be non-negative")
        t = np.linspace(-1.0, 1.0, x.size, dtype=float)
        coef = np.polyfit(t, x, deg=order)
        trend = np.polyval(coef, t)
        corrected = standardize(x - trend)
        return build_preprocessed_series(
            record,
            new_record_id=new_record_id,
            values=corrected,
            manifest_id=manifest_id,
            op_name=self.name,
            op_family=self.family,
            op_kind=self.kind,
            op_params=params,
            op_version=self.version,
            correction_target="trend",
        )


class OracleGainPreprocessing(BasePreprocessing):
    VERSION = "0.1.0"

    @property
    def name(self) -> str:
        return "oracle_gain"

    @property
    def family(self) -> str:
        return "oracle_gain"

    @property
    def kind(self) -> str:
        return "oracle"

    @property
    def version(self) -> str:
        return self.VERSION

    def apply(
        self,
        record: SeriesRecord,
        *,
        params: Mapping[str, Any],
        seed: int | None,
        manifest_id: str | None,
        new_record_id: str,
    ) -> SeriesRecord:
        _ = seed
        eps = float(params.get("eps", 1e-8))
        gain = _latent_array(record, "gain")
        x = np.asarray(record.values, dtype=float)
        corrected = standardize((x - float(np.mean(x))) / (gain + eps))
        return build_preprocessed_series(
            record,
            new_record_id=new_record_id,
            values=corrected,
            manifest_id=manifest_id,
            op_name=self.name,
            op_family=self.family,
            op_kind=self.kind,
            op_params=params,
            op_version=self.version,
            correction_target="gain",
        )


class OracleDriftPreprocessing(BasePreprocessing):
    VERSION = "0.1.0"

    @property
    def name(self) -> str:
        return "oracle_drift"

    @property
    def family(self) -> str:
        return "oracle_drift"

    @property
    def kind(self) -> str:
        return "oracle"

    @property
    def version(self) -> str:
        return self.VERSION

    def apply(
        self,
        record: SeriesRecord,
        *,
        params: Mapping[str, Any],
        seed: int | None,
        manifest_id: str | None,
        new_record_id: str,
    ) -> SeriesRecord:
        _ = seed
        drift = _latent_array(record, "observed_drift")
        corrected = standardize(np.asarray(record.values, dtype=float) - drift)
        return build_preprocessed_series(
            record,
            new_record_id=new_record_id,
            values=corrected,
            manifest_id=manifest_id,
            op_name=self.name,
            op_family=self.family,
            op_kind=self.kind,
            op_params=params,
            op_version=self.version,
            correction_target="drift",
        )


class OracleStateZScorePreprocessing(BasePreprocessing):
    VERSION = "0.1.0"

    @property
    def name(self) -> str:
        return "oracle_state_zscore"

    @property
    def family(self) -> str:
        return "oracle_state"

    @property
    def kind(self) -> str:
        return "oracle"

    @property
    def version(self) -> str:
        return self.VERSION

    def apply(
        self,
        record: SeriesRecord,
        *,
        params: Mapping[str, Any],
        seed: int | None,
        manifest_id: str | None,
        new_record_id: str,
    ) -> SeriesRecord:
        _ = seed
        state = _latent_array(record, "state")
        x = np.asarray(record.values, dtype=float)
        bins = int(params.get("bins", 2))
        corrected = np.empty_like(x, dtype=float)
        unique = np.unique(state)
        if unique.size <= max(2, bins) and np.allclose(unique, np.round(unique)):
            labels = state
        else:
            qs = np.linspace(0.0, 1.0, bins + 1)
            edges = np.quantile(state, qs)
            labels = np.digitize(state, edges[1:-1], right=False)
        for label in np.unique(labels):
            mask = labels == label
            corrected[mask] = standardize(x[mask]) if int(np.sum(mask)) > 1 else 0.0
        return build_preprocessed_series(
            record,
            new_record_id=new_record_id,
            values=standardize(corrected),
            manifest_id=manifest_id,
            op_name=self.name,
            op_family=self.family,
            op_kind=self.kind,
            op_params=params,
            op_version=self.version,
            correction_target="state",
        )
