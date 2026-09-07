"""Cost and numerical-precision rehearsal on explicitly non-confirmatory parents."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from lrdbench.defaults import build_default_contamination_registry, build_default_estimator_registry

try:
    from . import compile_confirmation_protocol as design
except ImportError:
    import compile_confirmation_protocol as design

shared, intervals, stress_inputs, stress = (
    design.shared,
    design.intervals,
    design.stress_inputs,
    design.stress,
)

PROFILE = {
    "status": "rehearsal_never_confirmation",
    "parents_per_cell": 2,
    "interval_families": {"fGn": [0.25, 0.85], "AR1": [0.95]},
    "interval_lengths": [512, 1024],
    "streams": {
        "a": {"draws": 3999, "prefixes": [1999, 3999]},
        "b": {"draws": 1999, "prefixes": [1999]},
    },
    "endpoint_stability": {
        "refinement_90pct_absolute_change_limit": 0.01,
        "independent_repeat_90pct_absolute_change_limit": 0.02,
        "largest_absolute_change_limit": 0.05,
        "failure_action": "retain_counts_and_revisit_draw_budget_before_design_lock_no_method_selection",
    },
}


def profile_workload(protocol):
    n = PROFILE["parents_per_cell"]
    cells = design.cell_table(protocol)
    ci_parents = (
        len(PROFILE["interval_lengths"]) * sum(map(len, PROFILE["interval_families"].values())) * n
    )
    methods, conditions = (
        len(design.point_settings(512)),
        len(design.contamination_conditions(protocol)),
    )
    return {
        "clean_parents": len(cells) * n,
        "clean_point_fits": len(cells) * n * methods,
        "stress_descendants": int(cells.stress_parents.gt(0).sum()) * n * conditions,
        "stressed_point_fits": int(cells.stress_parents.gt(0).sum()) * n * conditions * methods,
        "interval_parents": ci_parents,
        "interval_model_fits": ci_parents * 2,
        "physical_bootstrap_records": ci_parents * 2 * (3999 + 1999),
        "bootstrap_statistic_attempts": ci_parents * 9 * (3999 + 1999),
        "confirmation_inputs": 0,
    }


def run(protocol, output):
    design.validate(protocol)
    source_config = design.data_config(
        protocol, rehearsal=True, repetitions=PROFILE["parents_per_cell"]
    )
    identity = shared.run_identity(
        source_config, stress.roster(), source_config["repetitions"], True
    )
    identity.update(status=PROFILE["status"], profile=PROFILE, planned_protocol=protocol)
    for path in (
        Path(__file__),
        Path(design.__file__),
        Path(intervals.__file__),
        Path(intervals.batch.__file__),
        Path(stress.__file__),
        Path(stress_inputs.__file__),
        Path(intervals.mean.__file__),
        Path(intervals.ci.__file__),
        Path(intervals.mean.engine.__file__),
        Path(__file__).with_name("estimator_eligibility.csv"),
    ):
        identity["source_sha256"][str(path.relative_to(shared.ROOT))] = shared.file_hash(path)
    output.mkdir(parents=True, exist_ok=True)
    with shared.exclusive_run(output):
        shared.initialize(output, identity)
        registry = build_default_estimator_registry()
        contamination_registry = build_default_contamination_registry()
        conditions = design.contamination_conditions(protocol)
        stress_cells = {shared.cell_id(c) for c in design.grid(protocol["stress"])}
        ci_cells = {
            shared.cell_id(c)
            for c in shared.cells(
                {"lengths": PROFILE["interval_lengths"], "processes": PROFILE["interval_families"]}
            )
        }
        records, costs, interval_rows, index = [], [], [], []
        checkpoint_folder = output / "records"
        checkpoint_folder.mkdir(exist_ok=True)
        for cell in design.grid(protocol["accuracy"]):
            generation_start = time.perf_counter()
            values, metadata = shared.input_pool(
                output, source_config, cell, source_config["repetitions"]
            )
            generation_seconds = metadata["generation_seconds"]
            load_seconds = time.perf_counter() - generation_start
            settings = design.point_settings(cell["n"])
            for x, meta in zip(values, metadata["records"], strict=True):
                index.append(
                    {
                        "cell": shared.cell_id(cell),
                        **meta,
                        "input_seed": str(meta["input_seed"]),
                        "resampling_seed": str(meta["resampling_seed"]),
                    }
                )
                path = checkpoint_folder / f"{meta['record_id']}.json"
                if path.exists():
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if (
                        payload["sha256"] != shared.digest(payload["record"])
                        or payload["record"]["input_sha256"] != meta["sha256"]
                    ):
                        raise ValueError("Rehearsal checkpoint identity mismatch.")
                    result = payload["record"]
                else:
                    row_meta = {**meta, "parent_id": meta["record_id"], "condition": "clean"}
                    start = time.perf_counter()
                    point_rows = [
                        stress.fit(registry, cell, x, row_meta, setting) for setting in settings
                    ]
                    clean_seconds = time.perf_counter() - start
                    stress_start, replayed = time.perf_counter(), 0
                    stress_rows = []
                    if shared.cell_id(cell) in stress_cells:
                        parent = stress_inputs.build_parent(cell, x, meta)
                        for condition in conditions:
                            child = stress_inputs.apply_child(
                                source_config, parent, meta, condition, contamination_registry
                            )
                            expected = stress_inputs.reference_values(
                                x, condition, child.provenance.seed
                            )
                            np.testing.assert_allclose(
                                child.values, expected, rtol=2e-14, atol=2e-14
                            )
                            replayed += 1
                            child_meta = {
                                **row_meta,
                                "record_id": child.record_id,
                                "condition": condition["id"],
                                "sha256": shared.array_hash(child.values),
                            }
                            stress_rows.extend(
                                stress.fit(registry, cell, child.values, child_meta, setting)
                                for setting in settings
                            )
                    stress_seconds = time.perf_counter() - stress_start
                    ci_records = {}
                    if shared.cell_id(cell) in ci_cells:
                        for stream, config in PROFILE["streams"].items():
                            seeds = {
                                pool: shared.record_seed(
                                    source_config,
                                    cell,
                                    meta["repetition"],
                                    f"rehearsal_{stream}_{pool}",
                                )
                                for pool in ("cbc", "fgn")
                            }
                            ci_records[stream] = intervals.fit_record(x, seeds=seeds, **config)
                    result = shared.finite_json(
                        {
                            "record_id": meta["record_id"],
                            "cell": shared.cell_id(cell),
                            "n": cell["n"],
                            "input_sha256": meta["sha256"],
                            "clean_seconds": clean_seconds,
                            "stress_seconds": stress_seconds,
                            "verified_descendants": replayed,
                            "clean_points": point_rows,
                            "stress_points": stress_rows,
                            "interval_records": ci_records,
                        }
                    )
                    shared.atomic_json(path, {"sha256": shared.digest(result), "record": result})
                records.append(result)
                costs.append(
                    {
                        "record_id": meta["record_id"],
                        "cell": shared.cell_id(cell),
                        "n": cell["n"],
                        "clean_seconds": result["clean_seconds"],
                        "stress_seconds": result["stress_seconds"],
                        "generation_seconds_per_cell": generation_seconds,
                        "this_load_seconds": load_seconds,
                    }
                )
                for stream, payload in result["interval_records"].items():
                    interval_rows.extend(
                        {
                            "record_id": meta["record_id"],
                            "cell": shared.cell_id(cell),
                            "n": cell["n"],
                            "stream": stream,
                            **row,
                        }
                        for row in payload["intervals"]
                    )
            print(f"Rehearsal complete: {shared.cell_id(cell)}", flush=True)
        pd.DataFrame(index).to_csv(output / "input_index.csv", index=False, lineterminator="\n")
        pd.DataFrame(costs).to_csv(output / "costs.csv", index=False, lineterminator="\n")
        pd.DataFrame(interval_rows).to_csv(
            output / "interval_endpoints.csv", index=False, lineterminator="\n"
        )
        summarize(protocol, output, records)


def summarize(protocol, output, records):
    endpoints = pd.read_csv(output / "interval_endpoints.csv", float_precision="round_trip")
    keys = ["record_id", "cell", "n", "method", "candidate"]
    bootstrap = endpoints[~endpoints.candidate.eq("gph_normal_raw")]
    baseline = bootstrap[bootstrap.stream.eq("a") & bootstrap.draws.eq(1999)].set_index(keys)
    comparisons = []
    for label, stream, count in (
        ("refinement_1999_to_3999", "a", 3999),
        ("independent_repeat_1999", "b", 1999),
    ):
        other = bootstrap[bootstrap.stream.eq(stream) & bootstrap.draws.eq(count)].set_index(keys)
        for endpoint in ("ci_low", "ci_high"):
            diff = (other[endpoint] - baseline[endpoint]).abs()
            comparisons.extend(
                {
                    **dict(zip(keys, key, strict=True)),
                    "comparison": label,
                    "endpoint": endpoint,
                    "absolute_change": value,
                }
                for key, value in diff.items()
            )
    changes = pd.DataFrame(comparisons)
    changes.to_csv(output / "endpoint_stability.csv", index=False, lineterminator="\n")
    q = changes.groupby("comparison").absolute_change.agg(["count", "median", "max"])
    q["p90"] = changes.groupby("comparison").absolute_change.quantile(0.9)
    q.to_csv(output / "endpoint_stability_summary.csv", lineterminator="\n")
    timing = []
    attempts, generated = 0, 0
    failures, boundary = 0, 0
    for record in records:
        for stream, payload in record["interval_records"].items():
            failures += int(payload["model_failure"] is not None)
            boundary += int(payload["model"] is not None and payload["model"]["boundary_hit"])
            row = {
                "record_id": record["record_id"],
                "n": record["n"],
                "stream": stream,
                "draws": PROFILE["streams"][stream]["draws"],
                "point_seconds": payload["point_seconds"],
                "model_seconds": payload["model_seconds"],
            }
            for pool, values in payload["pools"].items():
                row[pool + "_generation_seconds"] = values["generation_seconds"]
                row[pool + "_statistic_seconds"] = values["statistic_seconds"]
                generated += values["generated_records"]
                attempts += sum(c["attempted"] for c in values["accounting"].values())
            timing.append(row)
    times = pd.DataFrame(timing)
    time_columns = [c for c in times if c.endswith("_seconds")]
    times["total_seconds"] = times[time_columns].sum(axis=1)
    times.to_csv(output / "interval_costs.csv", index=False, lineterminator="\n")
    # Fixed per-length mean cost, no outcome-dependent cell weighting.
    table = design.cell_table(protocol)
    clean_seconds = sum(
        r["clean_seconds"] * protocol["accuracy"]["repetitions"] / PROFILE["parents_per_cell"]
        for r in records
    )
    stress_seconds = sum(
        r["stress_seconds"] * protocol["stress"]["repetitions"] / PROFILE["parents_per_cell"]
        for r in records
        if r["verified_descendants"]
    )
    ci_seconds = sum(
        int(group.interval_parents.sum())
        * times[
            (times.n == n) & (times.draws == protocol["intervals"]["bootstrap_draws"])
        ].total_seconds.mean()
        for n, group in table[table.interval_parents.gt(0)].groupby("n")
    )
    thresholds = PROFILE["endpoint_stability"]
    pass_tail = (
        q.loc["refinement_1999_to_3999", "p90"]
        <= thresholds["refinement_90pct_absolute_change_limit"]
        and q.loc["independent_repeat_1999", "p90"]
        <= thresholds["independent_repeat_90pct_absolute_change_limit"]
        and q["max"].max() <= thresholds["largest_absolute_change_limit"]
        and changes.absolute_change.notna().all()
    )
    summary = {
        "status": "rehearsal_not_confirmation",
        "workload": profile_workload(protocol),
        "valid_clean_points": sum(r["valid"] for record in records for r in record["clean_points"]),
        "valid_stressed_points": sum(
            r["valid"] for record in records for r in record["stress_points"]
        ),
        "verified_descendants": sum(r["verified_descendants"] for r in records),
        "generated_bootstrap_records": generated,
        "bootstrap_statistic_attempts": attempts,
        "interval_rows": len(endpoints),
        "available_interval_rows": int(endpoints.available.sum()),
        "model_failures": failures,
        "boundary_hits": boundary,
        "endpoint_stability_rule_passed": bool(pass_tail),
        "endpoint_stability_thresholds": thresholds,
        "projected_clean_fit_hours": clean_seconds / 3600,
        "projected_stress_fit_hours": stress_seconds / 3600,
        "projected_interval_fit_hours": ci_seconds / 3600,
        "projected_compute_hours": (clean_seconds + stress_seconds + ci_seconds) / 3600,
        "planning_hours_with_2x_allowance": (clean_seconds + stress_seconds + ci_seconds) / 1800,
        "timing_limit": "Small rehearsal; excludes full-scale output I/O, final summary analysis, verification and thermal/load changes. No completion-time guarantee.",
    }
    shared.atomic_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=design.DEFAULT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    protocol = design.load_protocol(args.protocol)
    design.validate(protocol)
    if args.dry_run:
        print(json.dumps(profile_workload(protocol), indent=2))
    elif args.output is None:
        parser.error("--output is required for rehearsal execution")
    else:
        run(protocol, args.output.resolve())
