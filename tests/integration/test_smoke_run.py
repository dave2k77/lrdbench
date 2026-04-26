from __future__ import annotations

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
