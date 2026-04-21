from __future__ import annotations

import numpy as np
import pytest

from lrdbench.enums import BenchmarkMode, SourceType
from lrdbench.evaluator import GroundTruthEvaluator
from lrdbench.manifest import manifest_from_mapping
from lrdbench.metrics_catalog import metric_specs_from_manifest_entries
from lrdbench.schema import (
    BenchmarkManifest,
    EstimateResult,
    EstimatorSpec,
    SeriesRecord,
    TruthSpec,
)


def _record(record_id: str) -> SeriesRecord:
    return SeriesRecord(
        record_id=record_id,
        values=np.asarray([0.0, 1.0, -1.0, 0.5], dtype=float),
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="synthetic",
        truth=TruthSpec(
            process_family="fGn",
            generating_params={"H": 0.5},
            target_estimand="hurst_scaling_proxy",
            target_value=0.5,
        ),
        annotations={"process_family": "fGn", "H": 0.5, "n": 4},
    )


def _variant(name: str, variant_name: str) -> EstimatorSpec:
    return EstimatorSpec(
        name=f"{name}::{variant_name}",
        family="time_domain",
        target_estimand="hurst_scaling_proxy",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
        parameter_schema={
            "_base_estimator_name": name,
            "_variant_name": variant_name,
            "min_scale": 8,
        },
    )


def test_manifest_expands_estimator_variants_with_base_registry_metadata() -> None:
    manifest = manifest_from_mapping(
        {
            "manifest_id": "variant_manifest",
            "name": "variant manifest",
            "mode": "ground_truth",
            "source": {"type": "generator_grid", "generators": []},
            "estimators": [
                {
                    "name": "DFA",
                    "family": "time_domain",
                    "target_estimand": "hurst_scaling_proxy",
                    "params": {"n_bootstrap": 0},
                    "variants": [
                        {"name": "short", "params": {"min_scale": 8, "max_scale": 32}},
                        {"name": "long", "params": {"min_scale": 16, "max_scale": 64}},
                    ],
                }
            ],
            "metrics": ["parameter_variant_sensitivity"],
        }
    )

    assert [e.name for e in manifest.estimator_specs] == ["DFA::short", "DFA::long"]
    assert manifest.estimator_specs[0].parameter_schema["_base_estimator_name"] == "DFA"
    assert manifest.estimator_specs[0].parameter_schema["_variant_name"] == "short"
    assert manifest.estimator_specs[0].parameter_schema["n_bootstrap"] == 0
    assert manifest.estimator_specs[0].parameter_schema["max_scale"] == 32


def test_scale_window_sensitivity_metrics_preserve_base_estimator_pairing() -> None:
    estimators = (
        _variant("DFA", "short"),
        _variant("DFA", "long"),
        _variant("DMA", "short"),
        _variant("DMA", "long"),
    )
    metrics = metric_specs_from_manifest_entries(
        ["parameter_variant_sensitivity", "max_variant_drift"]
    )
    manifest = BenchmarkManifest(
        manifest_id="sensitivity",
        name="sensitivity",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "test"},
        estimator_specs=estimators,
        metric_specs=metrics,
    )
    estimates = (
        EstimateResult(record_id="r1", estimator_name="DFA::short", point=0.5, valid=True),
        EstimateResult(record_id="r1", estimator_name="DFA::long", point=0.9, valid=True),
        EstimateResult(record_id="r1", estimator_name="DMA::short", point=0.4, valid=True),
        EstimateResult(record_id="r1", estimator_name="DMA::long", point=0.7, valid=True),
    )

    bundle = GroundTruthEvaluator().evaluate(manifest, (_record("r1"),), estimates)

    rows = {(m.estimator_name, m.metric_name): m.value for m in bundle.per_series}
    assert rows[("DFA", "parameter_variant_sensitivity")] == pytest.approx(0.2)
    assert rows[("DFA", "max_variant_drift")] == pytest.approx(0.4)
    assert rows[("DMA", "parameter_variant_sensitivity")] == pytest.approx(0.15)
    assert rows[("DMA", "max_variant_drift")] == pytest.approx(0.3)

    global_rows = [
        m
        for m in bundle.aggregate
        if m.metric_name == "parameter_variant_sensitivity"
        and m.stratum.get("level") == "balanced_global"
    ]
    assert {m.estimator_name for m in global_rows} == {"DFA", "DMA"}
