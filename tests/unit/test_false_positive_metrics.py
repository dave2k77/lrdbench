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
from lrdbench.validation import ManifestValidationError


def _record(record_id: str, target_value: float) -> SeriesRecord:
    return SeriesRecord(
        record_id=record_id,
        values=np.asarray([0.0, 1.0, -1.0, 0.5], dtype=float),
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="synthetic_null",
        truth=TruthSpec(
            process_family="fGn",
            generating_params={"H": target_value},
            target_estimand="hurst_scaling_proxy",
            target_value=target_value,
        ),
        annotations={"process_family": "fGn", "H": target_value, "n": 4},
    )


def test_false_positive_metric_manifest_parameters_are_preserved() -> None:
    specs = metric_specs_from_manifest_entries(
        [{"name": "false_positive_lrd_rate", "threshold": 0.62, "null_max": 0.51}]
    )

    assert specs[0].name == "false_positive_lrd_rate"
    assert specs[0].parameters == {"threshold": 0.62, "null_max": 0.51}


def test_false_positive_metric_counts_only_null_truth_records() -> None:
    espec = EstimatorSpec(
        name="Toy",
        family="test",
        target_estimand="hurst_scaling_proxy",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
    )
    metric = metric_specs_from_manifest_entries(
        [{"name": "false_positive_lrd_rate", "threshold": 0.6, "null_max": 0.5}]
    )[0]
    manifest = BenchmarkManifest(
        manifest_id="fp",
        name="fp",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "test"},
        estimator_specs=(espec,),
        metric_specs=(metric,),
    )
    records = (_record("null_high", 0.5), _record("null_low", 0.5), _record("non_null", 0.8))
    estimates = (
        EstimateResult(record_id="null_high", estimator_name="Toy", point=0.7, valid=True),
        EstimateResult(record_id="null_low", estimator_name="Toy", point=0.55, valid=True),
        EstimateResult(record_id="non_null", estimator_name="Toy", point=0.9, valid=True),
    )

    bundle = GroundTruthEvaluator().evaluate(manifest, records, estimates)

    per_series = [m for m in bundle.per_series if m.metric_name == "false_positive_lrd_rate"]
    assert [(m.record_id, m.value) for m in per_series] == [
        ("null_high", 1.0),
        ("null_low", 0.0),
    ]
    global_rows = [
        m
        for m in bundle.aggregate
        if m.metric_name == "false_positive_lrd_rate"
        and m.stratum.get("level") == "balanced_global"
    ]
    assert len(global_rows) == 1
    assert global_rows[0].value == 0.5


def test_false_positive_metric_rejected_in_observational_mode() -> None:
    data = {
        "manifest_id": "fp_obs",
        "name": "fp_obs",
        "mode": "observational",
        "source": {
            "type": "inline_table",
            "series": [{"record_id": "s1", "values": [0.0, 1.0, 0.0, -1.0] * 20}],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {"n_bootstrap": 8},
            },
        ],
        "metrics": [{"name": "false_positive_lrd_rate", "threshold": 0.6}],
    }

    with pytest.raises(ManifestValidationError, match="not admissible"):
        manifest_from_mapping(data)
