from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import numpy as np

from lrdbench.enums import SourceType
from lrdbench.generators._signal import simulate_fgn
from lrdbench.interfaces import BaseGenerator
from lrdbench.schema import ProvenanceRecord, SeriesRecord, TruthSpec


class FGNGenerator(BaseGenerator):
    @property
    def family(self) -> str:
        return "fGn"

    @property
    def version(self) -> str:
        return "0.1.0"

    def generate(
        self,
        *,
        record_id: str,
        params: Mapping[str, Any],
        seed: int | None,
        manifest_id: str | None,
    ) -> SeriesRecord:
        n = int(params["n"])
        hurst = float(params["H"])
        sigma = float(params.get("sigma", 1.0))
        rng = np.random.default_rng(seed)
        x = simulate_fgn(n, hurst, rng, sigma=sigma)
        truth = TruthSpec(
            process_family=self.family,
            generating_params=dict(params),
            target_estimand="hurst_scaling_proxy",
            target_value=hurst,
            notes=None,
        )
        prov = ProvenanceRecord(
            record_id=record_id,
            parent_id=None,
            manifest_id=manifest_id,
            created_at=datetime.now(UTC).isoformat(),
            source_version=self.version,
            software_version=None,
            git_commit=None,
            seed=seed,
        )
        ann: dict[str, Any] = {
            "process_family": self.family,
            "n": n,
            "H": hurst,
            "sigma": sigma,
        }
        return SeriesRecord(
            record_id=record_id,
            values=x,
            time_axis=None,
            sampling_rate=None,
            source_type=SourceType.SYNTHETIC,
            source_name="fGn",
            truth=truth,
            annotations=ann,
            provenance=prov,
        )
