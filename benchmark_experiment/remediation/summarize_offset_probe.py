"""Descriptive paired-error summaries for the mean screen's fixed +1 offset.

Separate fGn, ARFIMA and AR(1) domains; equal fixed cell weights within each.
This secondary diagnostic does not select an interval or test a new hypothesis.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

try:
    from . import paired_summary
    from . import run_mean_comparison as mean
except ImportError:
    import paired_summary
    import run_mean_comparison as mean


def run(output):
    config = json.loads((output / "run.json").read_text())["identity"]["config"]
    probes = pd.read_csv(output / "offset_probes.csv")
    probes["method"] = probes.method + "/" + probes.treatment
    cells = mean.shared.cells(config)
    targets = {
        mean.shared.cell_id(c): 0.5
        if c["family"] == "AR1"
        else c["parameter"] + (0.5 if c["family"] == "ARFIMA" else 0)
        for c in cells
    }
    probes["H_target"] = probes.cell.map(targets)
    pairs = probes.rename(columns={"cell": "stratum", "record_id": "parent_id"})
    pairs["condition"] = "constant_offset_1"
    pairs["clean_error"] = (pairs.point - pairs.H_target).abs()
    pairs["stressed_error"] = (pairs.shifted_point - pairs.H_target).abs()
    outputs = [[], [], []]
    designs = {}
    for family in sorted(config["processes"]):
        strata = sorted(mean.shared.cell_id(c) for c in cells if c["family"] == family)
        subset = pairs[pairs.stratum.isin(strata)]
        design = {
            "methods": sorted(probes.method.unique()),
            "conditions": ["constant_offset_1"],
            "parents_by_stratum": {
                s: [f"{s}_r{r}" for r in range(config["repetitions"])] for s in strata
            },
            "stratum_weights": {s: 1 / len(strata) for s in strata},
            "draws": 999,
            "seed": 20260912,
            "nominal": 0.95,
            "denominator_floor": 1e-12,
        }
        designs[family] = design
        tables = paired_summary.summarize_paired_errors(subset, **design)
        for result, table in zip(outputs, tables, strict=True):
            table.insert(0, "domain", family)
            result.append(table)
    files = []
    for suffix, tables in zip(
        ("summary", "parent_accounting", "bootstrap_draws"), outputs, strict=True
    ):
        path = output / f"paired_offset_{suffix}.csv"
        pd.concat(tables, ignore_index=True).to_csv(path, index=False, lineterminator="\n")
        files.append(path)
    identity = {
        "status": "descriptive_secondary_constant_offset_diagnostic",
        "config": designs,
        "source_sha256": {
            str(Path(p).relative_to(mean.shared.ROOT)): mean.shared.file_hash(Path(p))
            for p in (__file__, paired_summary.__file__)
        },
        "input_sha256": mean.shared.file_hash(output / "offset_probes.csv"),
        "artifact_sha256": {p.name: mean.shared.file_hash(p) for p in files},
        "independent_parents": config["repetitions"] * len(cells),
        "resampling_unit": "complete_parent_vector_within_fixed_cell",
        "not_independent": ["methods", "transformations", "offset_descendants", "bootstrap_draws"],
    }
    mean.shared.atomic_json(output / "paired_offset_run.json", identity)
    print(
        json.dumps(
            {
                "independent_parents": identity["independent_parents"],
                "summary_rows": sum(len(t) for t in outputs[0]),
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())


if __name__ == "__main__":
    main()
