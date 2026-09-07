from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from lrdbench.contaminations._common import build_contaminated_series
from lrdbench.interfaces import BaseContamination
from lrdbench.schema import SeriesRecord


class LevelShiftContamination(BaseContamination):
    """Legacy whole-record constant offset; this operator does not insert a step."""

    VERSION = "0.1.0"

    @property
    def name(self) -> str:
        return "level_shift"

    @property
    def family(self) -> str:
        return "level"

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
        shift = float(params["shift"])
        scale = float(np.std(x)) + 1e-12
        x2 = x + shift * scale
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


class ConstantOffsetContamination(LevelShiftContamination):
    """Explicit name for the legacy whole-record offset control."""

    @property
    def name(self) -> str:
        return "constant_offset"


class StepChangeContamination(LevelShiftContamination):
    """Add ``shift * std(x)`` from sample ``floor(position * n)`` onward.

    The default position is the midpoint. Amplitude uses the population standard
    deviation of the clean input. Both segments must contain at least one sample.
    """

    @property
    def name(self) -> str:
        return "step_change"

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
        shift = float(params["shift"])
        position = float(params.get("position", 0.5))
        if x.ndim != 1 or x.size < 2 or not np.isfinite(x).all():
            raise ValueError("step_change requires a finite one-dimensional series of length >= 2")
        if not np.isfinite(shift) or not 0.0 < position < 1.0:
            raise ValueError("step_change requires finite shift and 0 < position < 1")
        index = int(np.floor(position * x.size))
        if not 1 <= index < x.size:
            raise ValueError("step_change position must leave two nonempty segments")
        x2 = x.copy()
        x2[index:] += shift * float(np.std(x))
        return build_contaminated_series(
            record,
            new_record_id=new_record_id,
            values=x2,
            manifest_id=manifest_id,
            op_name=self.name,
            op_family=self.family,
            op_params={**params, "position": position},
            op_version=self.version,
        )
