from __future__ import annotations

from pathlib import Path

import pytest

from lrdbench.manifest import manifest_from_mapping
from lrdbench.runner import _expand_contamination_grid, run_manifest_mapping, run_manifest_path
from lrdbench.validation import ManifestValidationError


def test_expand_contamination_grid_cartesian() -> None:
    spec = {
        "operators": [
            {
                "name": "level_shift",
                "params": {"shift": [0.1, 0.2]},
            },
        ],
    }
    out = _expand_contamination_grid(spec)
    assert out == [("level_shift", {"shift": 0.1}), ("level_shift", {"shift": 0.2})]


def test_stress_manifest_rejects_empty_operators() -> None:
    data = {
        "manifest_id": "p3v",
        "name": "p3",
        "mode": "stress_test",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [64]}, "replicates": 1},
            ],
        },
        "contamination": {"operators": []},
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
    with pytest.raises(ManifestValidationError, match="operators"):
        manifest_from_mapping(data)


def test_relative_degradation_requires_mae() -> None:
    data = {
        "manifest_id": "p3r",
        "name": "p3",
        "mode": "stress_test",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [64]}, "replicates": 1},
            ],
        },
        "contamination": {
            "operators": [{"name": "level_shift", "params": {"shift": [0.1]}}],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {},
            },
        ],
        "metrics": ["relative_degradation_ratio"],
    }
    with pytest.raises(ManifestValidationError, match="relative_degradation_ratio requires"):
        manifest_from_mapping(data)


@pytest.mark.integration
def test_stress_pipeline_inline_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    data = {
        "manifest_id": "p3_run",
        "name": "phase3_mini",
        "mode": "stress_test",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [128]}, "replicates": 1},
            ],
        },
        "contamination": {
            "operators": [{"name": "level_shift", "params": {"shift": [0.1]}}],
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
            "mae",
            "estimate_drift",
            "relative_degradation_ratio",
            "validity_rate",
            "runtime",
            {"name": "coverage", "levels": [0.95]},
            {"name": "ci_width", "levels": [0.95]},
            {"name": "coverage_error", "levels": [0.95]},
            {"name": "coverage_collapse", "levels": [0.95]},
        ],
        "leaderboards": [
            {
                "name": "lb",
                "mode": "stress_test",
                "component_metrics": ["mae", "estimate_drift", "validity_rate", "runtime"],
                "weights": {"mae": 0.35, "estimate_drift": 0.35, "validity_rate": 0.2, "runtime": 0.1},
                "ranking_rule": "weighted_rank",
                "tie_break_rule": "best_primary_metric",
            },
        ],
        "seeds": {"global_seed": 3},
    }
    out = run_manifest_mapping(data)
    assert len(out.records) == 2
    roles = {r.annotations.get("stress_role") for r in out.records}
    assert roles == {"clean", "contaminated"}
    drift = [m for m in out.metrics.per_series if m.metric_name == "estimate_drift"]
    assert drift
    assert all(m.value is not None for m in drift if m.metric_name == "estimate_drift")


@pytest.mark.integration
def test_smoke_stress_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo_root: Path
) -> None:
    manifest = repo_root / "configs" / "suites" / "smoke_stress_test.yaml"
    monkeypatch.chdir(tmp_path)
    out = run_manifest_path(manifest)
    assert out.run_id
    stress_csv = Path(out.report_bundle.summary_table_path or "").parent / "stress_metrics.csv"
    assert stress_csv.is_file()
