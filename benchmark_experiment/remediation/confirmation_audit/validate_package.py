"""Verify derived table round trips and preservation of source/history artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from audit import compare_exports, file_hash, read_json, require


def main(source, runtime, output):
    repository = Path(__file__).resolve().parents[3]
    evidence = read_json(output / "audit_evidence.json")
    require(
        file_hash(Path(__file__).with_name("audit.py")) == evidence["audit_source_sha256"],
        "audited source changed",
    )
    require(
        file_hash(Path(__file__).with_name("README.md")) == evidence["audit_specification_sha256"],
        "audit specification changed",
    )
    manifest = read_json(output / "export_provenance.json")
    require(
        file_hash(source / "summaries/canonical_summary.csv")
        == manifest["canonical_summary_sha256"],
        "canonical source changed",
    )
    canonical = pd.read_csv(
        source / "summaries/canonical_summary.csv",
        keep_default_na=False,
        float_precision="round_trip",
        low_memory=False,
    )
    checked_rows = 0
    for name, count in manifest["table_rows"].items():
        saved = pd.read_csv(
            output / name, keep_default_na=False, float_precision="round_trip", low_memory=False
        )
        require(len(saved) == count, name + " row count")
        if name == "planned_contrasts.csv.gz":
            mask = canonical.contrast.ne("")
        elif name == "accuracy_mae.csv":
            mask = canonical.scope.eq("accuracy") & canonical.metric.eq("mae")
        elif name == "interval_coverage.csv":
            mask = canonical.scope.eq("intervals") & canonical.metric.eq("unconditional_coverage")
        elif name == "stress_effects_domains.csv":
            mask = (
                canonical.scope.eq("stress")
                & canonical.cell.eq("domain_aggregate")
                & canonical.metric.isin(["absolute_error_inflation", "absolute_estimate_drift"])
            )
        else:
            scope, level = name.removesuffix(".csv.gz").split("_")
            mask = canonical.scope.eq(scope) & (
                canonical.cell.eq("domain_aggregate") == (level == "domains")
            )
        compare_exports(saved, canonical.loc[mask, saved.columns])
        checked_rows += len(saved)
    for name, sha in manifest["files"].items():
        require(file_hash(output / name) == sha, "export checksum: " + name)
    narrative = pd.read_csv(
        output / "narrative_evidence.csv",
        keep_default_na=False,
        float_precision="round_trip",
        low_memory=False,
    )
    keys = ["scope", "cell", "domain", "interval_role", "method", "condition", "metric", "contrast"]
    joined = canonical.merge(narrative[keys], on=keys, how="inner")
    compare_exports(narrative, joined[narrative.columns])
    baseline = read_json(repository / "benchmark_experiment/remediation/baseline.json")
    for entry in baseline["historical_files"]:
        require(
            file_hash(repository / entry["path"]) == entry["sha256"], "historical artifact changed"
        )
    restoration = read_json(runtime / "runtime-restoration.json")
    for name, sha in restoration["source_sha256"].items():
        require(file_hash(runtime / name) == sha, "frozen runtime source changed")
    record = {
        "status": "passed",
        "derived_rows_reconciled": checked_rows,
        "narrative_rows_reconciled": len(narrative),
        "historical_files_unchanged": len(baseline["historical_files"]),
        "frozen_runtime_sources_unchanged": len(restoration["source_sha256"]),
        "audit_source_hash_matches_executed_version": True,
        "artifact_files_verified": len(manifest["files"]),
        "figures": ["clean_accuracy.png/svg", "interval_coverage.png/svg"],
    }
    (output / "package_validation.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.source, args.runtime, args.output)
