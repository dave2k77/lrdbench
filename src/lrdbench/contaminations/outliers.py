from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from lrdbench.contaminations._common import build_contaminated_series
from lrdbench.interfaces import BaseContamination
from lrdbench.schema import SeriesRecord


class OutliersContamination(BaseContamination):
    VERSION = "0.1.0"

    @property
    def name(self) -> str:
        return "outliers"

    @property
    def family(self) -> str:
        return "impulsive"

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
        x = np.asarray(record.values, dtype=float)
        n = x.size
        rate = float(params["rate"])
        amplitude = float(params["amplitude"])
        rng = np.random.default_rng(seed)
        x2 = x.copy()
        k = max(1, int(round(rate * n)))
        idx = rng.choice(n, size=k, replace=False)
        scale = float(np.std(x)) + 1e-12
        signs = rng.choice([-1.0, 1.0], size=k)
        x2[idx] = x2[idx] + signs * amplitude * scale
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
