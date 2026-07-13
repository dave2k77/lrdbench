"""Phase 3a: per-series LRD model selection (lrd_class estimand + classification metrics)."""

from __future__ import annotations

import numpy as np

from lrdbench.enums import BenchmarkMode, SourceType
from lrdbench.evaluator import (
    _classification_metric_rows,
    _metric_applies_per_series,
    _roc_auc,
    estimand_kind,
)
from lrdbench.generators.fgn import FGNGenerator
from lrdbench.generators.multitimescale import MultiTimescaleGenerator
from lrdbench.metrics_catalog import METRIC_SPECS, metric_specs_from_manifest_entries
from lrdbench.schema import (
    BenchmarkManifest,
    EstimateResult,
    EstimatorSpec,
    SeriesRecord,
    TruthSpec,
)
from lrdbench.validation import truth_for


def test_roc_auc_rank_based() -> None:
    assert _roc_auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0
    assert _roc_auc([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1]) == 0.0
    # ties across the class boundary -> 0.5
    assert _roc_auc([0.5, 0.5, 0.5, 0.5], [0, 0, 1, 1]) == 0.5
    assert _roc_auc([0.3, 0.7], [1, 1]) is None  # single class


def test_metric_routing_by_estimand_kind() -> None:
    assert estimand_kind("lrd_class") == "classification"
    assert estimand_kind("hurst_scaling_proxy") == "regression"
    # regression truth-metric does not apply to a decision estimand
    assert not _metric_applies_per_series(METRIC_SPECS["bias"], "lrd_class")
    assert _metric_applies_per_series(METRIC_SPECS["bias"], "hurst_scaling_proxy")
    # classification metrics are aggregate-only (never per-series)
    assert not _metric_applies_per_series(METRIC_SPECS["roc_auc"], "lrd_class")
    # neutral metrics apply to anything
    assert _metric_applies_per_series(METRIC_SPECS["validity_rate"], "lrd_class")
    assert _metric_applies_per_series(METRIC_SPECS["runtime"], "hurst_scaling_proxy")


def test_generators_label_lrd_class() -> None:
    lrd = FGNGenerator().generate(
        record_id="a", params={"H": 0.8, "n": 64, "sigma": 1.0}, seed=1, manifest_id="m"
    )
    null = FGNGenerator().generate(
        record_id="b", params={"H": 0.5, "n": 64, "sigma": 1.0}, seed=1, manifest_id="m"
    )
    mt = MultiTimescaleGenerator().generate(
        record_id="c", params={"n": 64, "tau_max": 8.0}, seed=1, manifest_id="m"
    )
    assert truth_for(lrd, "lrd_class").target_value == 1.0
    assert truth_for(null, "lrd_class").target_value == 0.0
    assert truth_for(mt, "lrd_class").target_value == 0.0


def _labelled_record(rid: str, label: float) -> SeriesRecord:
    return SeriesRecord(
        record_id=rid,
        values=np.zeros(8, dtype=float),
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="t",
        truth=TruthSpec("t", {}, "hurst_scaling_proxy", 0.5),
        additional_truths=(TruthSpec("t", {}, "lrd_class", label),),
    )


def test_classification_metric_rows_compute_auc_and_confusion() -> None:
    disc = EstimatorSpec(
        name="Disc",
        family="discrimination",
        target_estimand="lrd_class",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
    )
    metrics = metric_specs_from_manifest_entries(
        ["roc_auc", "balanced_accuracy", "true_positive_rate", "false_positive_rate"]
    )
    manifest = BenchmarkManifest(
        manifest_id="ms",
        name="ms",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "test"},
        estimator_specs=(disc,),
        metric_specs=tuple(metrics),
    )
    records = [
        _labelled_record("p1", 1.0),
        _labelled_record("p2", 1.0),
        _labelled_record("n1", 0.0),
        _labelled_record("n2", 0.0),
    ]
    # perfectly separating scores
    idx = {
        ("p1", "Disc"): EstimateResult(record_id="p1", estimator_name="Disc", point=0.9, valid=True),
        ("p2", "Disc"): EstimateResult(record_id="p2", estimator_name="Disc", point=0.8, valid=True),
        ("n1", "Disc"): EstimateResult(record_id="n1", estimator_name="Disc", point=0.2, valid=True),
        ("n2", "Disc"): EstimateResult(record_id="n2", estimator_name="Disc", point=0.1, valid=True),
    }
    rows = _classification_metric_rows("ms", records, idx, manifest)
    vals = {r.metric_name: r.value for r in rows}

    assert vals["roc_auc"] == 1.0
    assert vals["balanced_accuracy"] == 1.0
    assert vals["true_positive_rate"] == 1.0
    assert vals["false_positive_rate"] == 0.0
    assert all(r.stratum.get("level") == "balanced_global" for r in rows)
