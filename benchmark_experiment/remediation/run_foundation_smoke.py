"""Tiny reproducible software checks; not research validation or benchmark evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
from importlib.metadata import distributions
from pathlib import Path

import numpy as np
import yaml

from lrdbench.output_contract import validate_output_contract
from lrdbench.runner import run_manifest_mapping


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    summaries = []
    estimators = [
        {
            "name": name,
            "family": family,
            "target_estimand": "hurst_scaling_proxy",
            "supports_ci": True,
            "params": {"n_bootstrap": 8, "ci_levels": [0.8, 0.95]},
        }
        for name, family in (("RS", "temporal"), ("DFA", "temporal"), ("GPH", "spectral"))
    ]
    for mode, suite in (
        ("ground_truth", "smoke_ground_truth"),
        ("stress_test", "smoke_stress_test"),
        ("observational", "smoke_observational"),
    ):
        data = yaml.safe_load((root / "configs/suites" / f"{suite}.yaml").read_text())
        data.update(
            manifest_id=f"foundation_{mode}_v1",
            name=f"Foundation software check: {mode}",
            estimators=estimators,
        )
        data["description"] = (
            "Software smoke check; fixture/simulation data, not a publishable benchmark."
        )
        data["seeds"] = {"global_seed": 31415}
        data["metrics"].append({"name": "ci_availability", "levels": [0.8, 0.95]})
        data["report"] = {
            "formats": ["html", "csv"],
            "export_root": str(output / mode),
            "figure_set": ["degradation_curve", "benchmark_uncertainty_intervals"],
        }
        data["leaderboards"] = []
        if mode != "observational":
            data["source"]["generators"] = [
                {
                    "family": "fGn",
                    "params": {"H": [0.5, 0.7], "n": [256], "sigma": [1.0]},
                    "replicates": 2,
                }
            ]
            data["uncertainty"] = {
                "enabled": True,
                "n_bootstrap": 32,
                "ci_levels": [0.95],
                "metrics": ["mae", "coverage"],
            }
            data["leaderboards"] = [
                {
                    "name": "smoke_accuracy",
                    "mode": mode,
                    "component_metrics": ["mae", "validity_rate"],
                    "weights": {"mae": 0.75, "validity_rate": 0.25},
                    "tie_break_rule": "mae",
                }
            ]
        if mode == "stress_test":
            data["contamination"] = {
                "operators": [
                    {"name": "constant_offset", "params": {"shift": [0.5]}},
                    {
                        "name": "step_change",
                        "params": {"shift": [0.0, 0.5, 1.0], "position": [0.5]},
                    },
                ]
            }
        if mode == "observational":
            data["source"]["series"][0]["path"] = str(root / "configs/suites/data/smoke_series.csv")
        (output / f"{mode}.yaml").write_text(
            yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
        )
        first = run_manifest_mapping(data, discover_plugins=False)
        repeat_data = copy.deepcopy(data)
        repeat_data["report"]["export_root"] = str(output / "repeat" / mode)
        repeat_data["report"]["figure_set"] = []
        second = run_manifest_mapping(repeat_data, discover_plugins=False)
        for a, b in zip(first.records, second.records, strict=True):
            np.testing.assert_array_equal(a.values, b.values)
        for a, b in zip(first.estimates, second.estimates, strict=True):
            assert (a.point, a.bootstrap_cis, a.valid, a.diagnostics) == (
                b.point,
                b.bootstrap_cis,
                b.valid,
                b.diagnostics,
            )
        assert first.leaderboards == second.leaderboards
        for run in (first, second):
            assert run.result_store_path is not None
            assert validate_output_contract(run.result_store_path) == []
        if mode == "stress_test":
            indexed = {r.record_id: r for r in first.records}
            for record in first.records:
                if record.annotations.get("contamination_operator") != "step_change":
                    continue
                clean = indexed[record.annotations["clean_record_id"]]
                midpoint = len(clean.values) // 2
                shift = record.contamination_history[-1].params["shift"]
                np.testing.assert_array_equal(record.values[:midpoint], clean.values[:midpoint])
                np.testing.assert_allclose(
                    record.values[midpoint:] - clean.values[midpoint:],
                    shift * np.std(clean.values),
                    atol=1e-14,
                )
        summaries.append(
            {
                "mode": mode,
                "records": len(first.records),
                "fits": len(first.estimates),
                "valid_points": sum(e.valid for e in first.estimates),
                "bootstrap_attempts": sum(
                    e.diagnostics.get("bootstrap_replicates_attempted", 0) for e in first.estimates
                ),
                "result_store": first.result_store_path,
                "report": first.report_bundle.html_report_path,
                "figures": first.report_bundle.figure_paths,
                "reproducibility": "records, points, intervals, diagnostics, leaderboards identical",
                "output_contract": "passed",
            }
        )
    packages = {d.metadata["Name"]: d.version for d in distributions() if d.metadata["Name"]}
    hashes = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / "src/lrdbench").rglob("*.py"))
    }
    (output / "verification.json").write_text(
        json.dumps(
            {
                "purpose": "software checks only",
                "python": platform.python_version(),
                "packages": packages,
                "source_sha256": hashes,
                "runs": summaries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
