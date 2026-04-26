from __future__ import annotations

import json
from pathlib import Path

from lrdbench.cli.main import main


def test_validate_manifest_command_accepts_smoke_manifest(capsys, repo_root: Path) -> None:
    manifest = repo_root / "configs" / "suites" / "smoke_ground_truth.yaml"

    code = main(["validate", str(manifest)])

    captured = capsys.readouterr()
    assert code == 0
    assert f"manifest_valid={manifest}" in captured.out
    assert "manifest_id=smoke_gt_v1" in captured.out
    assert "mode=ground_truth" in captured.out
    assert "estimators=1" in captured.out
    assert "metrics=8" in captured.out
    assert captured.err == ""


def test_validate_manifest_command_accepts_public_suite_name(capsys) -> None:
    code = main(["validate", "smoke_ground_truth"])

    captured = capsys.readouterr()
    assert code == 0
    assert "manifest_valid=" in captured.out
    assert "manifest_id=smoke_gt_v1" in captured.out
    assert captured.err == ""


def test_validate_manifest_command_rejects_invalid_manifest(tmp_path: Path, capsys) -> None:
    manifest = tmp_path / "invalid.yaml"
    manifest.write_text(
        "\n".join(
            [
                "manifest_id: bad",
                "name: bad",
                "mode: ground_truth",
                "source:",
                "  type: generator_grid",
                "estimators: []",
                "metrics: [mae]",
            ]
        ),
        encoding="utf-8",
    )

    code = main(["validate", str(manifest)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert f"manifest_invalid={manifest}" in captured.err
    assert "at least one estimator is required" in captured.err


def test_list_metrics_command_outputs_catalog(capsys) -> None:
    code = main(["list-metrics"])

    captured = capsys.readouterr()
    assert code == 0
    assert "mae\tMAE\ttruth\tground_truth,stress_test" in captured.out
    assert "runtime\tRT\ttruth_free\tground_truth,stress_test,observational" in captured.out
    assert captured.err == ""


def test_list_metrics_command_outputs_json(capsys) -> None:
    code = main(["list-metrics", "--format", "json"])

    captured = capsys.readouterr()
    assert code == 0
    rows = json.loads(captured.out)
    mae = next(row for row in rows if row["name"] == "mae")
    assert mae["requires_truth"] is True
    assert mae["optimisation_direction"] == "minimise"
    assert captured.err == ""


def test_list_estimators_command_outputs_registry_names(capsys) -> None:
    code = main(["list-estimators"])

    captured = capsys.readouterr()
    assert code == 0
    assert "DFA\n" in captured.out
    assert "RS\n" in captured.out
    assert "WaveletOLS\n" in captured.out
    assert captured.err == ""


def test_list_estimators_command_outputs_json(capsys) -> None:
    code = main(["list-estimators", "--format", "json"])

    captured = capsys.readouterr()
    assert code == 0
    names = {row["name"] for row in json.loads(captured.out)}
    assert {"RS", "GPH", "WaveletWhittle"}.issubset(names)
    assert captured.err == ""


def test_list_suites_command_outputs_public_suite_names(capsys) -> None:
    code = main(["list-suites"])

    captured = capsys.readouterr()
    assert code == 0
    assert "public_small_canonical_ground_truth\n" in captured.out
    assert "public_medium_stress_contamination\n" in captured.out
    assert captured.err == ""


def test_list_suites_command_outputs_json(capsys) -> None:
    code = main(["list-suites", "--format", "json"])

    captured = capsys.readouterr()
    assert code == 0
    names = {row["name"] for row in json.loads(captured.out)}
    assert "public_medium_canonical_ground_truth" in names
    assert "smoke_ground_truth" in names
    assert captured.err == ""


def test_validate_output_command_rejects_incomplete_run_directory(tmp_path: Path, capsys) -> None:
    code = main(["validate-output", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert f"output_invalid={tmp_path}" in captured.err
    assert "missing required file: tables/run_summary.csv" in captured.err
