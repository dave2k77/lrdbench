from __future__ import annotations

from pathlib import Path

import pytest

from lrdbench.manifest import load_manifest, manifest_from_mapping
from lrdbench.runner import run_manifest_mapping, run_manifest_path
from lrdbench.validation import ManifestValidationError


def _observational_manifest(source: dict[str, object]) -> dict[str, object]:
    return {
        "manifest_id": "obs_validation",
        "name": "observational validation",
        "mode": "observational",
        "source": source,
        "estimators": [
            {
                "name": "RS",
                "family": "temporal",
                "target_estimand": "hurst_scaling_proxy",
                "params": {"n_bootstrap": 8},
            },
        ],
        "metrics": ["runtime"],
    }


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
                "family": "temporal",
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
                "family": "temporal",
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
                "family": "temporal",
                "target_estimand": "hurst_scaling_proxy",
                "params": {"n_bootstrap": 8},
            },
        ],
        "metrics": ["runtime"],
    }
    with pytest.raises(ManifestValidationError, match="contamination"):
        manifest_from_mapping(data)


def test_observational_rejects_non_mapping_series_entries() -> None:
    data = _observational_manifest(
        {"type": "csv_series_index", "series": ["data/series.csv"]}
    )

    with pytest.raises(ManifestValidationError, match=r"series\[0\] must be a mapping"):
        manifest_from_mapping(data)


def test_observational_rejects_duplicate_record_ids() -> None:
    data = _observational_manifest(
        {
            "type": "csv_series_index",
            "series": [
                {"record_id": "duplicate", "path": "a.csv"},
                {"record_id": "duplicate", "path": "b.csv"},
            ],
        }
    )

    with pytest.raises(ManifestValidationError, match="duplicate record_id 'duplicate'"):
        manifest_from_mapping(data)


def test_observational_rejects_blank_record_id() -> None:
    data = _observational_manifest(
        {"type": "inline_table", "series": [{"record_id": "  ", "values": [1.0, 2.0]}]}
    )

    with pytest.raises(ManifestValidationError, match="record_id must be a non-empty string"):
        manifest_from_mapping(data)


def test_observational_rejects_csv_series_without_path() -> None:
    data = _observational_manifest(
        {"type": "csv_series_index", "series": [{"record_id": "s1"}]}
    )

    with pytest.raises(ManifestValidationError, match="path must be a non-empty string"):
        manifest_from_mapping(data)


def test_observational_rejects_blank_value_column() -> None:
    data = _observational_manifest(
        {
            "type": "csv_series_index",
            "series": [{"record_id": "s1", "path": "s1.csv", "value_column": ""}],
        }
    )

    with pytest.raises(ManifestValidationError, match="value_column must be a non-empty string"):
        manifest_from_mapping(data)


def test_observational_rejects_invalid_sampling_rate() -> None:
    data = _observational_manifest(
        {
            "type": "csv_series_index",
            "series": [{"record_id": "s1", "path": "s1.csv", "sampling_rate": 0}],
        }
    )

    with pytest.raises(ManifestValidationError, match="sampling_rate must be positive"):
        manifest_from_mapping(data)


def test_observational_rejects_non_mapping_metadata() -> None:
    data = _observational_manifest(
        {
            "type": "csv_series_index",
            "series": [{"record_id": "s1", "path": "s1.csv", "metadata": ["bad"]}],
        }
    )

    with pytest.raises(ManifestValidationError, match="metadata must be a mapping"):
        manifest_from_mapping(data)


def test_observational_rejects_unknown_missing_policy() -> None:
    data = _observational_manifest(
        {
            "type": "csv_series_index",
            "series": [
                {"record_id": "s1", "path": "s1.csv", "missing_policy": "ignore"}
            ],
        }
    )

    with pytest.raises(ManifestValidationError, match="missing_policy must be one of"):
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
                "family": "temporal",
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


@pytest.mark.integration
def test_openneuro_ds002691_pilot_manifest(repo_root: Path) -> None:
    manifest_path = repo_root / "configs" / "suites" / "openneuro_ds002691_pilot.yaml"
    manifest = load_manifest(manifest_path)

    assert manifest.mode.value == "observational"
    assert manifest.manifest_id == "openneuro_ds002691_pilot_v1"
    assert len(manifest.source_spec["series"]) == 16
    assert all(not spec.requires_truth for spec in manifest.metric_specs)
    assert {
        block["metadata"]["dataset"] for block in manifest.source_spec["series"]
    } == {"openneuro_ds002691"}
    assert {
        block["metadata"]["subject"] for block in manifest.source_spec["series"]
    } == {"sub-001", "sub-002", "sub-003", "sub-004"}
    assert {
        block["metadata"]["channel"] for block in manifest.source_spec["series"]
    } == {"E1", "E8", "E16", "E24"}
    assert all(
        (manifest_path.parent / block["path"]).is_file()
        for block in manifest.source_spec["series"]
    )


@pytest.mark.integration
def test_neural_observational_fixture_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo_root: Path
) -> None:
    manifest_path = repo_root / "configs" / "suites" / "neural_observational_fixture.yaml"
    manifest = load_manifest(manifest_path)

    assert manifest.mode.value == "observational"
    assert all(not spec.requires_truth for spec in manifest.metric_specs)
    assert {spec.name for spec in manifest.metric_specs} >= {
        "validity_rate",
        "runtime",
        "ci_width",
        "instability",
        "preprocessing_sensitivity",
        "cross_estimator_dispersion",
        "pairwise_estimator_disagreement",
        "family_level_disagreement",
        "parameter_variant_sensitivity",
        "max_variant_drift",
    }

    monkeypatch.chdir(tmp_path)
    out = run_manifest_path(manifest_path, discover_plugins=False)

    assert out.run_id
    assert len(out.records) >= 4
    assert {record.truth for record in out.records} == {None}
    assert {record.annotations["subject"] for record in out.records} >= {"sub-01", "sub-02"}
    assert {record.annotations["condition"] for record in out.records} >= {"rest", "task"}
    assert all("source_sha256" in record.annotations for record in out.records)
    assert all("qc" in record.annotations for record in out.records)
    assert any(
        metric.metric_name == "pairwise_estimator_disagreement"
        for metric in out.metrics.aggregate
    )
