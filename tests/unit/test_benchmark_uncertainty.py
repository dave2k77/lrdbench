from __future__ import annotations

import numpy as np
import pytest

from lrdbench.enums import BenchmarkMode, SourceType
from lrdbench.evaluator import GroundTruthEvaluator
from lrdbench.manifest import manifest_from_mapping
from lrdbench.schema import (
    BenchmarkManifest,
    EstimateResult,
    EstimatorSpec,
    SeriesRecord,
    TruthSpec,
)
from lrdbench.validation import ManifestValidationError


def _record(record_id: str, h: float) -> SeriesRecord:
    return SeriesRecord(
        record_id=record_id,
        values=np.asarray([0.0, 1.0, -1.0, 0.5], dtype=float),
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="synthetic",
        truth=TruthSpec(
            process_family="fGn",
            generating_params={"H": h},
            target_estimand="hurst_scaling_proxy",
            target_value=h,
        ),
        annotations={"process_family": "fGn", "H": h, "n": 4},
    )


def _estimator(name: str) -> EstimatorSpec:
    return EstimatorSpec(
        name=name,
        family="test",
        target_estimand="hurst_scaling_proxy",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
    )


def test_benchmark_uncertainty_adds_aggregate_and_paired_bootstrap_rows() -> None:
    manifest = BenchmarkManifest(
        manifest_id="uq",
        name="uq",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "test"},
        estimator_specs=(_estimator("A"), _estimator("B")),
        metric_specs=manifest_from_mapping(
            {
                "manifest_id": "inner",
                "name": "inner",
                "mode": "ground_truth",
                "source": {"type": "generator_grid", "generators": []},
                "estimators": [
                    {
                        "name": "A",
                        "family": "test",
                        "target_estimand": "hurst_scaling_proxy",
                    }
                ],
                "metrics": ["mae"],
            }
        ).metric_specs,
        uncertainty_spec={
            "enabled": True,
            "n_bootstrap": 32,
            "ci_levels": [0.95],
            "metrics": ["mae"],
            "paired": True,
            "paired_metrics": ["mae"],
            "seed": 123,
        },
    )
    records = (_record("r1", 0.5), _record("r2", 0.5))
    estimates = (
        EstimateResult(record_id="r1", estimator_name="A", point=0.6, valid=True),
        EstimateResult(record_id="r2", estimator_name="A", point=0.7, valid=True),
        EstimateResult(record_id="r1", estimator_name="B", point=0.8, valid=True),
        EstimateResult(record_id="r2", estimator_name="B", point=0.9, valid=True),
    )

    bundle = GroundTruthEvaluator().evaluate(manifest, records, estimates)

    aggregate_rows = [
        m
        for m in bundle.uncertainty
        if m.metadata.get("uncertainty_type") == "aggregate_bootstrap"
        and m.estimator_name == "A"
        and m.metric_name == "mae"
    ]
    assert {m.metadata["aggregation"] for m in aggregate_rows} == {
        "bootstrap_within_stratum",
        "bootstrap_over_strata",
    }
    assert all(m.metadata["ci_low"] <= m.value <= m.metadata["ci_high"] for m in aggregate_rows)

    paired = [
        m
        for m in bundle.uncertainty
        if m.metadata.get("uncertainty_type") == "paired_bootstrap_difference"
    ]
    assert len(paired) == 1
    assert paired[0].estimator_name == "A__minus__B"
    assert paired[0].value == pytest.approx(-0.2)
    assert paired[0].metadata["ci_low"] == pytest.approx(-0.2)
    assert paired[0].metadata["ci_high"] == pytest.approx(-0.2)


def test_uncertainty_block_validation_rejects_invalid_levels() -> None:
    data = {
        "manifest_id": "bad_uq",
        "name": "bad uq",
        "mode": "ground_truth",
        "source": {"type": "generator_grid", "generators": []},
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
            }
        ],
        "metrics": ["mae"],
        "uncertainty": {"enabled": True, "ci_levels": [1.5]},
    }

    with pytest.raises(ManifestValidationError, match="uncertainty.ci_levels"):
        manifest_from_mapping(data)
