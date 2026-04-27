from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from lrdbench.output_contract import validate_output_contract

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_custom_estimator_programmatic_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(REPO_ROOT))

    module = import_module("examples.custom_estimator_benchmark")
    out = module.run_custom_estimator_example(export_root="reports/custom")

    assert out.report_bundle is not None
    assert out.leaderboards
    assert out.estimates
    assert all(est.estimator_name == "VarianceRatio" for est in out.estimates)
    assert validate_output_contract(out.result_store_path) == []
