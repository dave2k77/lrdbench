from __future__ import annotations

from pathlib import Path

import pytest

from lrdbench.manifest import manifest_from_mapping
from lrdbench.runner import run_manifest_mapping, run_manifest_path
from lrdbench.validation import ManifestValidationError


def test_observational_rejects_generator_grid_manifest() -> None:
    data = {
        "manifest_id": "o1",
        "name": "o",
        "mode": "observational",
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
                "params": {"n_bootstrap": 8},
            },
        ],
        "metrics": ["runtime"],
    }
    with pytest.raises(ManifestValidationError, match="generator_grid"):
        manifest_from_mapping(data)


def test_observational_rejects_unknown_source_type() -> None:
    data = {
        "manifest_id": "o2",
        "name": "o",
        "mode": "observational",
        "source": {"type": "unknown_source", "series": [{"record_id": "a", "path": "x.csv"}]},
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {},
            },
        ],
        "metrics": ["runtime"],
    }
    with pytest.raises(ManifestValidationError, match="source.type"):
        manifest_from_mapping(data)


def test_observational_rejects_contamination_block() -> None:
    data = {
        "manifest_id": "o3",
        "name": "o",
        "mode": "observational",
        "source": {
            "type": "inline_table",
            "series": [{"record_id": "s1", "values": [0.0, 1.0, 0.5, -0.2] * 20}],
        },
        "contamination": {"operators": [{"name": "level_shift", "params": {"shift": [0.1]}}]},
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {"n_bootstrap": 8},
            },
        ],
        "metrics": ["runtime"],
    }
    with pytest.raises(ManifestValidationError, match="contamination"):
        manifest_from_mapping(data)


@pytest.mark.integration
def test_observational_inline_table_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    data = {
        "manifest_id": "o_run",
        "name": "obs_inline",
        "mode": "observational",
        "source": {
            "type": "inline_table",
            "series": [
                {"record_id": "inline_a", "values": [float(i % 7 - 3) for i in range(128)]},
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "supports_ci": True,
                "params": {"n_bootstrap": 24, "bootstrap_block_len": 10, "ci_levels": [0.95]},
            },
        ],
        "metrics": [
            "validity_rate",
            "runtime",
            {"name": "ci_width", "levels": [0.95]},
            "instability",
            "preprocessing_sensitivity",
        ],
        "preprocessing": {"sensitivity_eps": 1.0e-4},
        "leaderboards": [
            {
                "name": "lb",
                "mode": "observational",
                "component_metrics": ["instability", "validity_rate", "runtime"],
                "weights": {"instability": 0.5, "validity_rate": 0.3, "runtime": 0.2},
                "ranking_rule": "weighted_rank",
                "tie_break_rule": "best_primary_metric",
            },
        ],
        "seeds": {"global_seed": 2},
    }
    out = run_manifest_mapping(data, base_dir=tmp_path)
    assert len(out.records) == 1
    assert out.records[0].truth is None
    inst = [m for m in out.metrics.per_series if m.metric_name == "instability"]
    assert inst and all(m.value is not None for m in inst)


@pytest.mark.integration
def test_smoke_observational_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo_root: Path
) -> None:
    manifest = repo_root / "configs" / "suites" / "smoke_observational.yaml"
    monkeypatch.chdir(tmp_path)
    out = run_manifest_path(manifest)
    assert out.run_id
    assert len(out.records) == 1
