from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from lrdbench.contaminations._common import build_contaminated_series
from lrdbench.interfaces import BaseContamination
from lrdbench.schema import SeriesRecord


class PolynomialTrendContamination(BaseContamination):
    VERSION = "0.1.0"

    @property
    def name(self) -> str:
        return "polynomial_trend"

    @property
    def family(self) -> str:
        return "trend"

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
        n = x.size
        order = int(params["order"])
        strength = float(params["strength"])
        t = np.linspace(-1.0, 1.0, n, dtype=float)
        trend = np.zeros_like(t, dtype=float)
        for k in range(1, order + 1):
            trend = trend + t**k
        trend = trend - float(np.mean(trend))
        scale = float(np.std(x)) + 1e-12
        x2 = x + strength * scale * (trend / (float(np.std(trend)) + 1e-12))
        return build_contaminated_series(
            record,
            new_record_id=new_record_id,
            values=x2,
            manifest_id=manifest_id,
            op_name=self.name,
            op_family=self.family,
            op_params=params,
            op_version=self.version,
        )
