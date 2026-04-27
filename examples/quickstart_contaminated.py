"""Run the tiny stress-test smoke suite.

From the repository root:

    python examples/quickstart_contaminated.py
"""

from __future__ import annotations

from pathlib import Path

from lrdbench.runner import run_manifest_path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = run_manifest_path(root / "configs" / "suites" / "smoke_stress_test.yaml")
    print(f"run_id={out.run_id}")
    print(f"result_store={out.result_store_path}")
    if out.report_bundle and out.report_bundle.html_report_path:
        print(f"html_report={out.report_bundle.html_report_path}")
    if out.result_store_path:
        print(f"validate_output=lrdbench validate-output {out.result_store_path}")


if __name__ == "__main__":
    main()
