from __future__ import annotations

import pytest

from lrdbench.enums import BenchmarkMode
from lrdbench.manifest import manifest_from_mapping
from lrdbench.metrics_catalog import METRIC_SPECS
from lrdbench.validation import ManifestValidationError, validate_metric_admissibility


def test_observational_rejects_truth_metrics() -> None:
    m = METRIC_SPECS["mae"]
    with pytest.raises(ManifestValidationError):
        validate_metric_admissibility(m, BenchmarkMode.OBSERVATIONAL)


def test_ground_truth_manifest_loads() -> None:
    data = {
        "manifest_id": "t1",
        "name": "t",
        "mode": "ground_truth",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [64]}, "replicates": 1},
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {},
            },
        ],
        "metrics": ["mae", "runtime"],
    }
    mf = manifest_from_mapping(data)
    assert mf.mode is BenchmarkMode.GROUND_TRUTH


def test_stress_requires_contamination() -> None:
    data = {
        "manifest_id": "t2",
        "name": "t",
        "mode": "stress_test",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [64]}, "replicates": 1},
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {},
            },
        ],
        "metrics": ["mae"],
    }
    with pytest.raises(ManifestValidationError):
        manifest_from_mapping(data)


def test_unknown_manifest_key_rejected() -> None:
    data = {
        "manifest_id": "t3",
        "name": "t",
        "mode": "ground_truth",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [64]}, "replicates": 1},
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {},
            },
        ],
        "metrics": ["mae"],
        "typo_field": 1,
    }
    with pytest.raises(ManifestValidationError):
        manifest_from_mapping(data)
