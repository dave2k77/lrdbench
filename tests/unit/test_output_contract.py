from __future__ import annotations

import json
from pathlib import Path

from lrdbench.output_contract import (
    PUBLIC_OUTPUT_CONTRACT,
    PUBLIC_OUTPUT_CONTRACT_VERSION,
    required_output_files,
    validate_output_contract,
)


def test_public_output_contract_declares_required_files_and_columns() -> None:
    assert PUBLIC_OUTPUT_CONTRACT["contract_version"] == PUBLIC_OUTPUT_CONTRACT_VERSION
    assert "tables/run_summary.csv" in PUBLIC_OUTPUT_CONTRACT["required_files"]["summary"]
    assert "raw/metrics.csv" in PUBLIC_OUTPUT_CONTRACT["required_files"]["raw_result_store"]
    assert PUBLIC_OUTPUT_CONTRACT["required_columns"]["tables/run_summary.csv"] == [
        "run_id",
        "manifest_id",
        "benchmark_name",
        "mode",
    ]
    assert "metadata_json" in PUBLIC_OUTPUT_CONTRACT["required_columns"]["raw/metrics.csv"]


def test_tracked_json_contract_matches_package_contract(repo_root: Path) -> None:
    path = repo_root / "configs" / "contracts" / "public_output_contract.json"
    tracked = json.loads(path.read_text(encoding="utf-8"))

    assert tracked == PUBLIC_OUTPUT_CONTRACT


def test_validate_output_contract_accepts_required_files_and_columns(tmp_path: Path) -> None:
    columns_by_path = PUBLIC_OUTPUT_CONTRACT["required_columns"]
    for rel in required_output_files():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        columns = columns_by_path.get(rel)
        if columns:
            path.write_text(",".join(columns) + "\n", encoding="utf-8")
        else:
            path.write_text("placeholder\n", encoding="utf-8")

    assert validate_output_contract(tmp_path) == []


def test_validate_output_contract_reports_missing_file_and_columns(tmp_path: Path) -> None:
    for rel in required_output_files():
        if rel == "tables/run_summary.csv":
            continue
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        columns = PUBLIC_OUTPUT_CONTRACT["required_columns"].get(rel, ["placeholder"])
        path.write_text(",".join(columns) + "\n", encoding="utf-8")
    bad_metrics = tmp_path / "raw" / "metrics.csv"
    bad_metrics.write_text("scope,record_id\n", encoding="utf-8")

    errors = validate_output_contract(tmp_path)

    assert "missing required file: tables/run_summary.csv" in errors
    assert any("raw/metrics.csv: missing required columns" in err for err in errors)
