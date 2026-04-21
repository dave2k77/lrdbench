"""Run the tiny ground-truth smoke suite (from repo root: python examples/quickstart_pure.py)."""

from __future__ import annotations

from pathlib import Path

from lrdbench.runner import run_manifest_path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = run_manifest_path(root / "configs" / "suites" / "smoke_ground_truth.yaml")
    print("run_id", out.run_id)
    print("result_store", out.result_store_path)


if __name__ == "__main__":
    main()
