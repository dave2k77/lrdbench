from __future__ import annotations

from pathlib import Path

import pytest
from examples.custom_estimator_benchmark import run_custom_estimator_example

from lrdbench.output_contract import validate_output_contract


@pytest.mark.integration
def test_custom_estimator_programmatic_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    out = run_custom_estimator_example(export_root="reports/custom")

    assert out.report_bundle is not None
    assert out.leaderboards
    assert out.estimates
    assert all(est.estimator_name == "VarianceRatio" for est in out.estimates)
    assert validate_output_contract(out.result_store_path) == []
