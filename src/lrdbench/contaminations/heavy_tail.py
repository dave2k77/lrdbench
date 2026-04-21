from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from scipy import stats

from lrdbench.contaminations._common import build_contaminated_series
from lrdbench.interfaces import BaseContamination
from lrdbench.schema import SeriesRecord


class HeavyTailNoiseContamination(BaseContamination):
    VERSION = "0.1.0"

    @property
    def name(self) -> str:
        return "heavy_tail_noise"

    @property
    def family(self) -> str:
        return "heavy_tail"

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
        df = float(params.get("df", params.get("alpha", 5.0)))
        scale = float(params["scale"])
        rng = np.random.default_rng(seed)
        noise = stats.t.rvs(df, size=x.size, random_state=rng)
        noise = noise / (float(np.std(noise)) + 1e-12)
        s = float(np.std(x)) + 1e-12
        x2 = x + scale * s * noise
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
