from __future__ import annotations

import numpy as np
import pytest

from lrdbench.enums import BenchmarkMode, SourceType
from lrdbench.evaluator import GroundTruthEvaluator
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


def _estimator(name: str, family: str) -> EstimatorSpec:
    return EstimatorSpec(
        name=name,
        family=family,
        target_estimand="hurst_scaling_proxy",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
    )


def test_estimator_disagreement_metrics_preserve_record_pairing_and_family_summaries() -> None:
    estimators = (
        _estimator("A", "time_domain"),
        _estimator("B", "time_domain"),
        _estimator("C", "spectral"),
    )
    metrics = metric_specs_from_manifest_entries(
        [
            "cross_estimator_dispersion",
            "pairwise_estimator_disagreement",
            "family_level_disagreement",
        ]
    )
    manifest = BenchmarkManifest(
        manifest_id="disagree",
        name="disagree",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "test"},
        estimator_specs=estimators,
        metric_specs=metrics,
    )
    records = (_record("r1"),)
    estimates = (
        EstimateResult(record_id="r1", estimator_name="A", point=0.5, valid=True),
        EstimateResult(record_id="r1", estimator_name="B", point=0.7, valid=True),
        EstimateResult(record_id="r1", estimator_name="C", point=1.1, valid=True),
    )

    bundle = GroundTruthEvaluator().evaluate(manifest, records, estimates)

    dispersion = [
        m for m in bundle.per_series if m.metric_name == "cross_estimator_dispersion"
    ]
    assert len(dispersion) == 1
    assert dispersion[0].record_id == "r1"
    assert dispersion[0].estimator_name == "__all_estimators__"
    assert dispersion[0].value == pytest.approx(0.2494438258)

    pairwise = {
        m.estimator_name: m.value
        for m in bundle.per_series
        if m.metric_name == "pairwise_estimator_disagreement"
    }
    assert pairwise["A__vs__B"] == pytest.approx(0.2)
    assert pairwise["A__vs__C"] == pytest.approx(0.6)
    assert pairwise["B__vs__C"] == pytest.approx(0.4)

    family = {
        m.estimator_name: m
        for m in bundle.per_series
        if m.metric_name == "family_level_disagreement"
    }
    assert family["family:time_domain"].value == pytest.approx(0.2)
    assert family["family:spectral__vs__time_domain"].value == pytest.approx(0.5)
    assert family["family:time_domain"].metadata["comparison_scope"] == "within_family"
    assert (
        family["family:spectral__vs__time_domain"].metadata["comparison_scope"]
        == "between_family"
    )

    global_dispersion = [
        m
        for m in bundle.aggregate
        if m.metric_name == "cross_estimator_dispersion"
        and m.stratum.get("level") == "balanced_global"
    ]
    assert len(global_dispersion) == 1
    assert global_dispersion[0].value == pytest.approx(dispersion[0].value)
