from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lrdbench", description="lrdbench benchmark CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run a benchmark from a YAML manifest")
    run_p.add_argument("manifest", type=Path, help="Path to benchmark_manifest.yaml")

    args = parser.parse_args(argv)

    if args.command == "run":
        from lrdbench.runner import run_manifest_path

        out = run_manifest_path(args.manifest)
        print(f"run_id={out.run_id}")
        print(f"result_store={out.result_store_path}")
        if out.report_bundle and out.report_bundle.html_report_path:
            print(f"html_report={out.report_bundle.html_report_path}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
