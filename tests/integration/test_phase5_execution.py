from __future__ import annotations

from pathlib import Path

import pytest

from lrdbench.manifest import manifest_from_mapping
from lrdbench.runner import run_manifest_mapping
from lrdbench.validation import ManifestValidationError


def test_manifest_rejects_unknown_execution_key() -> None:
    data = {
        "manifest_id": "p5a",
        "name": "p5",
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
                "params": {"n_bootstrap": 8},
            },
        ],
        "metrics": ["mae", "runtime"],
        "execution": {"typo_parallel": 2},
    }
    with pytest.raises(ManifestValidationError, match="unknown execution"):
        manifest_from_mapping(data)


@pytest.mark.integration
def test_parallel_max_workers_matches_serial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = {
        "manifest_id": "p5_par",
        "name": "p5",
        "mode": "ground_truth",
        "source": {
            "type": "generator_grid",
            "generators": [
                {
                    "family": "fGn",
                    "params": {"H": [0.4, 0.6], "n": [96], "sigma": [1.0]},
                    "replicates": 1,
                },
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {"n_bootstrap": 16, "bootstrap_block_len": 8, "ci_levels": [0.95]},
            },
        ],
        "metrics": ["mae", "runtime"],
        "seeds": {"global_seed": 99},
    }
    serial = dict(base)
    serial["execution"] = {"max_workers": 1}
    parallel = dict(base)
    parallel["execution"] = {"max_workers": 4}
    out_s = run_manifest_mapping(serial, base_dir=tmp_path)
    out_p = run_manifest_mapping(parallel, base_dir=tmp_path)
    assert len(out_s.estimates) == len(out_p.estimates)
    for a, b in zip(out_s.estimates, out_p.estimates, strict=True):
        assert a.record_id == b.record_id
        assert a.estimator_name == b.estimator_name
        assert a.point == b.point or (a.point is None and b.point is None)


@pytest.mark.integration
def test_estimate_disk_cache_second_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / "est_cache"
    data = {
        "manifest_id": "p5_cache",
        "name": "p5",
        "mode": "ground_truth",
        "source": {
            "type": "generator_grid",
            "generators": [
                {"family": "fGn", "params": {"H": [0.5], "n": [80]}, "replicates": 1},
            ],
        },
        "estimators": [
            {
                "name": "RS",
                "family": "time_domain",
                "target_estimand": "hurst_scaling_proxy",
                "params": {"n_bootstrap": 12, "bootstrap_block_len": 8, "ci_levels": [0.95]},
            },
        ],
        "metrics": ["mae", "runtime"],
        "seeds": {"global_seed": 3},
        "execution": {
            "max_workers": 1,
            "estimate_cache_dir": str(cache_dir),
            "cache_read": True,
            "cache_write": True,
        },
    }
    run_manifest_mapping(data, base_dir=tmp_path)
    files_after_first = list(cache_dir.glob("*.pkl"))
    assert len(files_after_first) >= 1
    out2 = run_manifest_mapping(data, base_dir=tmp_path)
    assert out2.estimates[0].point is not None
