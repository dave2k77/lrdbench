from __future__ import annotations

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
