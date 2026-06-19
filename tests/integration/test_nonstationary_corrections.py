from __future__ import annotations

from pathlib import Path

import pytest

from lrdbench.runner import run_manifest_mapping, run_manifest_path


@pytest.mark.integration
def test_nonstationary_preprocessing_pipeline_inline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    data = {
        "manifest_id": "nlrd_corrections_inline",
        "name": "nlrd_corrections_inline",
        "mode": "ground_truth",
        "source": {
            "type": "generator_grid",
            "generators": [
                {
                    "family": "NonstationaryLRD",
                    "params": {
                        "case": ["lrd_randomwalk_gain"],
                        "H": [0.7],
                        "n": [256],
                        "gain_amplitude": [0.8],
                    },
                    "replicates": 1,
                }
            ],
        },
        "preprocessing": {
            "include_raw": True,
            "operators": [
                {"name": "rolling_zscore", "params": {"window": [64]}},
                {"name": "oracle_gain", "params": {}},
            ],
        },
        "estimators": [
            {
                "name": "DFA",
                "family": "temporal",
                "target_estimand": "hurst_scaling_proxy",
                "supports_diagnostics": True,
                "params": {"min_scale": 8, "max_scale": 96, "detrend_order": 1},
            },
        ],
        "metrics": [
            "mae",
            "correction_drift",
            "correction_degradation_ratio",
            {
                "name": "oracle_gap",
                "label": "gain",
                "empirical_operator": "rolling_zscore",
                "oracle_operator": "oracle_gain",
            },
        ],
        "seeds": {"global_seed": 20260616},
        "execution": {"max_workers": 1, "cache_read": False, "cache_write": False},
    }

    out = run_manifest_mapping(data)

    assert len(out.records) == 3
    operators = {record.annotations["preprocessing_operator"] for record in out.records}
    assert operators == {"raw", "rolling_zscore", "oracle_gain"}
    correction_metrics = {
        metric.metric_name
        for metric in out.metrics.per_series
        if metric.record_id is not None
    }
    assert "correction_drift" in correction_metrics
    assert "correction_degradation_ratio" in correction_metrics
    assert "oracle_gap:gain" in correction_metrics
    correction_csv = Path(out.report_bundle.summary_table_path or "").parent / "correction_metrics.csv"
    assert correction_csv.is_file()


@pytest.mark.integration
def test_smoke_nonstationary_corrections_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo_root: Path
) -> None:
    manifest = repo_root / "configs" / "suites" / "smoke_nonstationary_lrd_corrections.yaml"
    monkeypatch.chdir(tmp_path)
    out = run_manifest_path(manifest)
    assert out.run_id
    assert any(
        record.annotations.get("preprocessing_operator") == "rolling_zscore"
        for record in out.records
    )
    assert any(
        metric.metric_name == "oracle_gap" and metric.value is not None
        for metric in out.metrics.per_series
    )
