from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lrdbench.manifest import load_manifest_yaml
from lrdbench.runner import run_manifest_mapping


DEFAULT_MANIFESTS = (
    Path("configs/suites/paper/canonical_ground_truth.yaml"),
    Path("configs/suites/paper/stress_contamination.yaml"),
    Path("configs/suites/paper/null_false_positive.yaml"),
    Path("configs/suites/paper/sensitivity_disagreement.yaml"),
)


@dataclass(frozen=True)
class SuiteRunSummary:
    manifest_path: Path
    manifest_id: str
    run_id: str
    result_store_path: str | None
    html_report_path: str | None
    copied_artefacts: tuple[str, ...]


def _repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_manifest_paths(repo_root: Path, raw_paths: list[str]) -> list[Path]:
    selected = [Path(p) for p in raw_paths] if raw_paths else list(DEFAULT_MANIFESTS)
    resolved: list[Path] = []
    for path in selected:
        resolved.append(path if path.is_absolute() else repo_root / path)
    return resolved


def _copy_publication_artefacts(
    *,
    manifest_id: str,
    run_id: str,
    paths: tuple[str, ...],
    destination: Path,
) -> tuple[str, ...]:
    copied: list[str] = []
    destination.mkdir(parents=True, exist_ok=True)
    for raw in paths:
        src = Path(raw)
        if not src.is_file():
            continue
        target = destination / f"{manifest_id}__{run_id}__{src.name}"
        shutil.copy2(src, target)
        copied.append(str(target))
    return tuple(copied)


def _write_run_index(path: Path, rows: list[SuiteRunSummary]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=(
                "manifest_path",
                "manifest_id",
                "run_id",
                "result_store_path",
                "html_report_path",
                "copied_artefacts_json",
            ),
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "manifest_path": str(row.manifest_path),
                    "manifest_id": row.manifest_id,
                    "run_id": row.run_id,
                    "result_store_path": row.result_store_path or "",
                    "html_report_path": row.html_report_path or "",
                    "copied_artefacts_json": json.dumps(row.copied_artefacts),
                }
            )


def run_suites(
    *,
    repo_root: Path,
    manifest_paths: list[Path],
    export_root: Path,
    artefact_root: Path,
) -> list[SuiteRunSummary]:
    summaries: list[SuiteRunSummary] = []
    for manifest_path in manifest_paths:
        data = load_manifest_yaml(manifest_path)
        report = dict(data.get("report") or {})
        report["export_root"] = str(export_root)
        data["report"] = report

        output = run_manifest_mapping(data, base_dir=manifest_path.parent)
        bundle = output.report_bundle
        figure_paths = bundle.figure_paths if bundle is not None else ()
        latex_paths = bundle.latex_table_paths if bundle is not None else ()
        copied = _copy_publication_artefacts(
            manifest_id=str(data["manifest_id"]),
            run_id=output.run_id,
            paths=tuple(latex_paths) + tuple(figure_paths),
            destination=artefact_root,
        )
        summaries.append(
            SuiteRunSummary(
                manifest_path=manifest_path,
                manifest_id=str(data["manifest_id"]),
                run_id=output.run_id,
                result_store_path=output.result_store_path,
                html_report_path=bundle.html_report_path if bundle is not None else None,
                copied_artefacts=copied,
            )
        )
    return summaries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m paper_support.run_paper_suites",
        description="Run paper-oriented benchmark suites and collect publication artefacts.",
    )
    parser.add_argument(
        "manifests",
        nargs="*",
        help="Manifest paths. Defaults to all configs/suites/paper/*.yaml suites.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_repo_root_from_script(),
        help="Repository root used to resolve default and relative manifest paths.",
    )
    parser.add_argument(
        "--export-root",
        type=Path,
        default=Path("reports/paper"),
        help="Report export root injected into each manifest before running.",
    )
    parser.add_argument(
        "--artefact-root",
        type=Path,
        default=Path("paper_support/artefacts"),
        help="Directory where LaTeX tables and figures are copied for paper drafting.",
    )
    parser.add_argument(
        "--index-path",
        type=Path,
        default=Path("paper_support/artefacts/run_index.csv"),
        help="CSV index summarising run IDs, reports, and copied artefacts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    manifest_paths = _resolve_manifest_paths(repo_root, list(args.manifests))
    export_root = args.export_root
    artefact_root = args.artefact_root
    index_path = args.index_path
    if not export_root.is_absolute():
        export_root = repo_root / export_root
    if not artefact_root.is_absolute():
        artefact_root = repo_root / artefact_root
    if not index_path.is_absolute():
        index_path = repo_root / index_path

    summaries = run_suites(
        repo_root=repo_root,
        manifest_paths=manifest_paths,
        export_root=export_root,
        artefact_root=artefact_root,
    )
    _write_run_index(index_path, summaries)
    for row in summaries:
        print(
            f"{row.manifest_id}: run_id={row.run_id} "
            f"html_report={row.html_report_path or 'NA'} "
            f"copied_artefacts={len(row.copied_artefacts)}"
        )
    print(f"run_index={index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
