from __future__ import annotations

import csv
from pathlib import Path

import pytest

from lrdbench.output_contract import validate_output_contract
from lrdbench.runner import run_manifest_path


@pytest.mark.integration
def test_smoke_manifest_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo_root: Path
) -> None:
    manifest = repo_root / "configs" / "suites" / "smoke_ground_truth.yaml"
    monkeypatch.chdir(tmp_path)
    out = run_manifest_path(manifest)
    assert out.run_id
    assert out.result_store_path
    assert out.report_bundle is not None
    assert Path(out.report_bundle.html_report_path or "").is_file()
    assert (Path(out.result_store_path) / "raw" / "estimates.csv").is_file()
    assert validate_output_contract(out.result_store_path) == []


@pytest.mark.integration
def test_plugin_failures_are_recorded_in_result_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo_root: Path
) -> None:
    plugin = tmp_path / "bad_plugin.py"
    plugin.write_text('ENTRY_POINTS = "not a dict"\n', encoding="utf-8")
    monkeypatch.setenv("LRD_BENCH_ESTIMATOR_PLUGIN_PATH", str(plugin))
    monkeypatch.chdir(tmp_path)

    out = run_manifest_path(repo_root / "configs" / "suites" / "smoke_ground_truth.yaml")

    assert len(out.plugin_provenance) == 1
    assert out.plugin_provenance[0].status == "invalid_entry_points"
    provenance_path = Path(out.result_store_path or "") / "raw" / "plugin_provenance.csv"
    with provenance_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["status"] == "invalid_entry_points"
    assert "ENTRY_POINTS must be a dict" in rows[0]["failure_reason"]
