from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import numpy as np

from lrdbench.enums import SourceType
from lrdbench.generators._signal import simulate_multitimescale
from lrdbench.interfaces import BaseGenerator
from lrdbench.schema import ProvenanceRecord, SeriesRecord, TruthSpec


class MultiTimescaleGenerator(BaseGenerator):
    """Short-memory superposition of AR(1) timescales (apparent-LRD null).

    A finite sum of exponentially-decaying components is genuinely short-memory
    (summable autocovariance, bounded spectral density at zero) so its declared
    Hurst truth is 0.5 -- there is *no* long-range dependence. The spread of
    timescales nonetheless mimics power-law scaling over finite samples, which is
    exactly the confound used to probe whether estimators discriminate true from
    apparent LRD. The severity of the illusion is set primarily by ``tau_max``
    relative to the series length (larger ``tau_max`` -> stronger apparent Hurst),
    not by ``beta_target``; both are recorded in annotations.
    """

    @property
    def family(self) -> str:
        return "multi_timescale"

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
        n_components = int(params.get("n_components", 8))
        tau_min = float(params.get("tau_min", 1.5))
        tau_max = float(params.get("tau_max", 16.0))
        beta_target = float(params.get("beta_target", 1.0))
        sigma = float(params.get("sigma", 1.0))
        burnin = int(params["burnin"]) if params.get("burnin") is not None else None
        rng = np.random.default_rng(seed)
        x = simulate_multitimescale(
            n,
            rng,
            n_components=n_components,
            tau_min=tau_min,
            tau_max=tau_max,
            beta_target=beta_target,
            sigma=sigma,
            burnin=burnin,
        )
        truth = TruthSpec(
            process_family=self.family,
            generating_params=dict(params),
            target_estimand="hurst_scaling_proxy",
            target_value=0.5,
            validity_domain={
                "n_components": n_components,
                "tau_min": tau_min,
                "tau_max": tau_max,
                "beta_target": beta_target,
            },
            notes=(
                "Apparent LRD only: a finite sum of AR(1) timescales is short-memory "
                "(summable ACF, H = 0.5). Non-0.5 estimates are false positives."
            ),
        )
        # No single characteristic timescale: the construction is multi-timescale
        # by design, so tau is undefined.
        additional_truths = (
            TruthSpec(
                process_family=self.family,
                generating_params=dict(params),
                target_estimand="timescale_tau",
                target_value=None,
                notes="no single timescale (superposition of tau_min..tau_max)",
            ),
            TruthSpec(
                process_family=self.family,
                generating_params=dict(params),
                target_estimand="lrd_class",
                target_value=0.0,
                notes="short-memory null: not LRD (apparent LRD only)",
            ),
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
            "n_components": n_components,
            "tau_min": tau_min,
            "tau_max": tau_max,
            "beta_target": beta_target,
            "sigma": sigma,
        }
        if burnin is not None:
            ann["burnin"] = burnin
        return SeriesRecord(
            record_id=record_id,
            values=x,
            time_axis=None,
            sampling_rate=None,
            source_type=SourceType.SYNTHETIC,
            source_name="multi_timescale",
            truth=truth,
            additional_truths=additional_truths,
            annotations=ann,
            provenance=prov,
        )
