from __future__ import annotations

from pathlib import Path

from paper_support.run_paper_suites import DEFAULT_MANIFESTS, _resolve_manifest_paths

from lrdbench.manifest import load_manifest


def test_paper_manifests_validate(repo_root: Path) -> None:
    for rel_path in DEFAULT_MANIFESTS:
        manifest = load_manifest(repo_root / rel_path)
        assert manifest.manifest_id.startswith("paper_")
        assert manifest.report_spec is not None
        assert manifest.report_spec.export_root == "reports/paper"
        assert "latex" in manifest.report_spec.formats
        assert manifest.uncertainty_spec.get("enabled") is True


def test_default_manifest_resolution(repo_root: Path) -> None:
    paths = _resolve_manifest_paths(repo_root, [])
    assert paths == [repo_root / rel_path for rel_path in DEFAULT_MANIFESTS]
    assert all(path.is_file() for path in paths)
