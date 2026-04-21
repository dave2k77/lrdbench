from __future__ import annotations

from pathlib import Path

import pytest

from lrdbench.manifest import manifest_from_mapping
from lrdbench.runner import run_manifest_mapping
from lrdbench.validation import ManifestValidationError


def test_coverage_error_requires_coverage_metric() -> None:
    data = {
        "manifest_id": "p2",
        "name": "p2",
        "mode": "ground_truth",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [128]}, "replicates": 1},
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {"n_bootstrap": 20},
            },
        ],
        "metrics": [
            "mae",
            {"name": "coverage_error", "levels": [0.95]},
        ],
    }
    with pytest.raises(ManifestValidationError, match="coverage_error requires"):
        manifest_from_mapping(data)


def test_nominal_level_must_be_in_unit_interval() -> None:
    data = {
        "manifest_id": "p2b",
        "name": "p2b",
        "mode": "ground_truth",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [128]}, "replicates": 1},
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {"n_bootstrap": 20},
            },
        ],
        "metrics": [
            {"name": "coverage", "levels": [1.5]},
        ],
    }
    with pytest.raises(ManifestValidationError, match="nominal level"):
        manifest_from_mapping(data)


@pytest.mark.integration
def test_phase2_bootstrap_coverage_in_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    data = {
        "manifest_id": "p2_run",
        "name": "phase2_mini",
        "mode": "ground_truth",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [256]}, "replicates": 1},
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {"n_bootstrap": 60, "bootstrap_block_len": 16, "ci_levels": [0.95]},
            },
        ],
        "metrics": [
            "mae",
            {"name": "coverage", "levels": [0.95]},
            {"name": "ci_width", "levels": [0.95]},
            {"name": "coverage_error", "levels": [0.95]},
        ],
        "leaderboards": [],
        "report": {"formats": ["html", "csv", "latex"], "export_root": "reports"},
        "seeds": {"global_seed": 7},
    }
    out = run_manifest_mapping(data)
    assert out.metrics.aggregate
    assert any(m.metric_name == "coverage" for m in out.metrics.aggregate)
    est_path = Path(out.result_store_path or "") / "raw" / "estimates.csv"
    assert est_path.is_file()
    text = est_path.read_text(encoding="utf-8")
    assert "ci_low" in text and "bootstrap_cis_json" in text
    if out.report_bundle and out.report_bundle.latex_table_paths:
        assert Path(out.report_bundle.latex_table_paths[0]).is_file()
