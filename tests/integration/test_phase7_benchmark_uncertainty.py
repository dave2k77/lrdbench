from __future__ import annotations

from pathlib import Path

import pandas as pd

from lrdbench.runner import run_manifest_mapping


def test_benchmark_uncertainty_pipeline_exports_raw_and_report_tables(tmp_path: Path) -> None:
    out = run_manifest_mapping(
        {
            "manifest_id": "uq_run",
            "name": "uq run",
            "mode": "ground_truth",
            "source": {
                "type": "generator_grid",
                "generators": [
                    {"family": "fGn", "params": {"H": [0.5], "n": [96]}, "replicates": 2},
                ],
            },
            "estimators": [
                {
                    "name": "RS",
                    "family": "time_domain",
                    "target_estimand": "hurst_scaling_proxy",
                    "params": {"n_bootstrap": 0},
                },
                {
                    "name": "DFA",
                    "family": "time_domain",
                    "target_estimand": "hurst_scaling_proxy",
                    "params": {"n_bootstrap": 0, "min_scale": 8, "max_scale": 32},
                },
            ],
            "metrics": ["mae"],
            "uncertainty": {
                "enabled": True,
                "n_bootstrap": 24,
                "ci_levels": [0.95],
                "metrics": ["mae"],
                "paired": True,
                "paired_metrics": ["mae"],
                "seed": 7,
            },
            "report": {"formats": ["csv"], "export_root": str(tmp_path / "reports")},
            "seeds": {"global_seed": 11},
        },
        base_dir=tmp_path,
    )

    assert out.metrics.uncertainty
    raw_metrics = pd.read_csv(Path(out.result_store_path or "") / "raw" / "metrics.csv")
    assert "uncertainty" in set(raw_metrics["scope"])
    raw_artefacts = pd.read_csv(Path(out.result_store_path or "") / "raw" / "artefacts.csv")
    assert "artefact_index" in set(raw_artefacts["artefact_type"])
    assert out.report_bundle is not None
    paths = {a.path for a in out.report_bundle.artefacts}
    assert any(path.endswith("benchmark_uncertainty.csv") for path in paths)
    assert any(path.endswith("failures.csv") for path in paths)
    assert any(path.endswith("artefact_index.csv") for path in paths)
