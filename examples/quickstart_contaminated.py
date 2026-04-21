"""Run the tiny stress-test smoke suite."""

from __future__ import annotations

from pathlib import Path

from lrdbench.runner import run_manifest_path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = run_manifest_path(root / "configs" / "suites" / "smoke_stress_test.yaml")
    print("run_id", out.run_id)
    print("result_store", out.result_store_path)


if __name__ == "__main__":
    main()
