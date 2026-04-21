from __future__ import annotations

from pathlib import Path

import pytest

from lrdbench.runner import run_manifest_mapping


@pytest.mark.integration
def test_mrw_and_fou_manifest_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    data = {
        "manifest_id": "p4_generators",
        "name": "phase4_generators",
        "mode": "ground_truth",
        "source": {
            "type": "generator_grid",
            "generators": [
                {
                    "family": "MRW",
                    "params": {
                        "H": [0.6],
                        "n": [96],
                        "sigma": [1.0],
                        "lambda2": [0.02],
                        "integral_scale": [24],
                    },
                    "replicates": 1,
                },
                {
                    "family": "fOU",
                    "params": {
                        "H": [0.6],
                        "n": [96],
                        "theta": [0.2],
                        "sigma": [1.0],
                        "dt": [1.0],
                        "burnin": [32],
                    },
                    "replicates": 1,
                },
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "supports_ci": True,
                "params": {"n_bootstrap": 8, "bootstrap_block_len": 8, "ci_levels": [0.95]},
            },
        ],
        "metrics": ["validity_rate", "runtime"],
        "seeds": {"global_seed": 11},
    }

    out = run_manifest_mapping(data, base_dir=tmp_path)

    assert len(out.records) == 2
    assert {r.source_name for r in out.records} == {"MRW", "fOU"}
    assert all(r.truth is not None for r in out.records)
    assert len(out.estimates) == 2
    assert out.metrics.aggregate
