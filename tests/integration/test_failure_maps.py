from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from lrdbench.runner import run_manifest_mapping


@pytest.mark.integration
def test_stress_failure_map_includes_contamination_severity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    data = {
        "manifest_id": "failure_map_stress",
        "name": "failure_map_stress",
        "mode": "stress_test",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [128]}, "replicates": 1},
            ],
        },
        "contamination": {
            "operators": [
                {"name": "outliers", "params": {"rate": [0.02], "amplitude": [5.0]}},
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "supports_ci": True,
                "params": {"n_bootstrap": 8, "bootstrap_block_len": 8},
            },
        ],
        "metrics": ["mae", "validity_rate", "runtime", "estimate_drift"],
        "report": {"formats": ["html", "csv"], "export_root": "reports"},
        "seeds": {"global_seed": 13},
    }

    out = run_manifest_mapping(data, base_dir=tmp_path)
    tables = Path(out.report_bundle.summary_table_path or "").parent

    stress_rows = pd.read_csv(tables / "stress_metrics.csv")
    stress_strata = [json.loads(raw) for raw in stress_rows["stratum_json"]]
    assert any(s.get("contamination_severity") == "amplitude=5.0;rate=0.02" for s in stress_strata)

    failure_map = pd.read_csv(tables / "failure_map.csv")
    assert "stratum__contamination_severity" in failure_map.columns
    assert "metric__estimate_drift" in failure_map.columns
    assert "amplitude=5.0;rate=0.02" in set(failure_map["stratum__contamination_severity"])
