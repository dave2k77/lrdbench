from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lrdbench.validation import ManifestValidationError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lrdbench", description="lrdbench benchmark CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run a benchmark from a YAML manifest")
    run_p.add_argument("manifest", type=Path, help="Path to benchmark_manifest.yaml")

    validate_p = sub.add_parser("validate", help="Validate a YAML benchmark manifest")
    validate_p.add_argument("manifest", type=Path, help="Path to benchmark_manifest.yaml")

    metrics_p = sub.add_parser("list-metrics", help="List built-in metric catalog entries")
    metrics_p.add_argument("--format", choices=("text", "json"), default="text")

    estimators_p = sub.add_parser("list-estimators", help="List built-in estimator registry entries")
    estimators_p.add_argument("--format", choices=("text", "json"), default="text")

    suites_p = sub.add_parser("list-suites", help="List packaged public suite manifests")
    suites_p.add_argument("--format", choices=("text", "json"), default="text")

    output_p = sub.add_parser("validate-output", help="Validate a generated run output directory")
    output_p.add_argument("run_root", type=Path, help="Path to <report.export_root>/<run_id>")

    args = parser.parse_args(argv)

    if args.command == "run":
        from lrdbench.public_assets import resolve_manifest_argument
        from lrdbench.runner import run_manifest_path

        with resolve_manifest_argument(args.manifest) as manifest_path:
            out = run_manifest_path(manifest_path)
        print(f"run_id={out.run_id}")
        print(f"result_store={out.result_store_path}")
        if out.report_bundle and out.report_bundle.html_report_path:
            print(f"html_report={out.report_bundle.html_report_path}")
        return 0

    if args.command == "validate":
        from lrdbench.manifest import load_manifest
        from lrdbench.public_assets import resolve_manifest_argument

        try:
            with resolve_manifest_argument(args.manifest) as manifest_path:
                manifest = load_manifest(manifest_path)
        except (FileNotFoundError, ManifestValidationError, KeyError, TypeError, ValueError) as exc:
            print(f"manifest_invalid={args.manifest}", file=sys.stderr)
            print(f"error={exc}", file=sys.stderr)
            return 2

        print(f"manifest_valid={args.manifest}")
        print(f"manifest_id={manifest.manifest_id}")
        print(f"mode={manifest.mode.value}")
        print(f"estimators={len(manifest.estimator_specs)}")
        print(f"metrics={len(manifest.metric_specs)}")
        return 0

    if args.command == "list-metrics":
        from lrdbench.metrics_catalog import METRIC_SPECS

        rows = [
            {
                "name": spec.name,
                "symbol": spec.symbol,
                "requires_truth": spec.requires_truth,
                "admissible_modes": [mode.value for mode in spec.admissible_modes],
                "aggregation_rule": spec.aggregation_rule,
                "optimisation_direction": spec.optimisation_direction.value,
                "unit": spec.unit,
                "null_policy": spec.null_policy,
            }
            for spec in sorted(METRIC_SPECS.values(), key=lambda item: item.name)
        ]
        if args.format == "json":
            print(json.dumps(rows, indent=2, sort_keys=True))
        else:
            for row in rows:
                modes = ",".join(row["admissible_modes"])
                truth = "truth" if row["requires_truth"] else "truth_free"
                print(
                    f"{row['name']}\t{row['symbol']}\t{truth}\t{modes}\t"
                    f"{row['aggregation_rule']}\t{row['optimisation_direction']}"
                )
        return 0

    if args.command == "list-estimators":
        from lrdbench.defaults import build_default_estimator_registry

        rows = [{"name": name} for name in build_default_estimator_registry().list()]
        if args.format == "json":
            print(json.dumps(rows, indent=2, sort_keys=True))
        else:
            for row in rows:
                print(row["name"])
        return 0

    if args.command == "list-suites":
        from lrdbench.public_assets import list_public_suites

        rows = [{"name": name} for name in list_public_suites()]
        if args.format == "json":
            print(json.dumps(rows, indent=2, sort_keys=True))
        else:
            for row in rows:
                print(row["name"])
        return 0

    if args.command == "validate-output":
        from lrdbench.output_contract import (
            PUBLIC_OUTPUT_CONTRACT_VERSION,
            validate_output_contract,
        )

        errors = validate_output_contract(args.run_root)
        if errors:
            print(f"output_invalid={args.run_root}", file=sys.stderr)
            print(f"contract_version={PUBLIC_OUTPUT_CONTRACT_VERSION}", file=sys.stderr)
            for err in errors:
                print(f"error={err}", file=sys.stderr)
            return 2
        print(f"output_valid={args.run_root}")
        print(f"contract_version={PUBLIC_OUTPUT_CONTRACT_VERSION}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
