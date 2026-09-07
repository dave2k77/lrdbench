"""Paired development comparison of interval constructions, never confirmation."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from lrdbench.bootstrap import circular_block_resample

try:
    from . import interval_candidates as candidates
    from . import run_calibration as shared
except ImportError:
    import interval_candidates as candidates
    import run_calibration as shared

DEFAULT_CONFIG = Path(__file__).with_name("interval-comparison.json")


def validate(config):
    expected = {
        "schema_version",
        "stage",
        "seed_namespace",
        "global_seed",
        "lengths",
        "processes",
        "repetitions",
        "bootstrap_draws",
        "nominal",
        "block_divisor",
        "methods",
        "fgn_model",
    }
    if set(config) != expected or config["schema_version"] != 1:
        raise ValueError("Unexpected interval comparison schema")
    if (
        config["stage"] != "development_interval_comparison"
        or config["fgn_model"] != "stationary_gaussian_fgn_known_zero_mean"
    ):
        raise ValueError(
            "Only the declared development stage and known-zero-mean fGn model are supported"
        )
    # Reuse the grid/seed/nominal validators without changing the archived runner.
    proxy = {k: v for k, v in config.items() if k not in {"block_divisor", "methods", "fgn_model"}}
    proxy.update(
        stage="development", block_divisors=[config["block_divisor"]], ci_methods={"GPH": {"m": 32}}
    )
    shared.validate_config(proxy)
    if (
        not config["methods"]
        or len(set(config["methods"])) != len(config["methods"])
        or set(config["methods"]) - set(candidates.METHODS)
    ):
        raise ValueError("Duplicate/unsupported method")
    if min(config["lengths"]) < 128:
        raise ValueError("The declared lag/frequency settings require n >= 128")


def workload(config):
    records = len(shared.cells(config)) * config["repetitions"]
    methods = len(config["methods"])
    return {
        "cells": len(shared.cells(config)),
        "independent_records": records,
        "model_fits": records,
        "point_statistics": records * methods,
        "physical_bootstrap_records": records * 2 * config["bootstrap_draws"],
        "bootstrap_statistic_attempts": records * 2 * config["bootstrap_draws"] * methods,
        "interval_rows": records * (4 * methods + int("GPH" in config["methods"])),
    }


def fit_record(x, metadata, cell, config):
    start = time.perf_counter()
    points, point_failures = {}, {}
    for method in config["methods"]:
        try:
            value = candidates.statistic(x, method)
            points[method] = value if value is not None and math.isfinite(value) else None
            if points[method] is None:
                point_failures[method] = "invalid_statistic"
        except Exception as exc:
            points[method] = None
            point_failures[method] = f"exception:{type(exc).__name__}:{exc}"
    point_seconds = time.perf_counter() - start
    model_start = time.perf_counter()
    try:
        model = candidates.fit_zero_mean_fgn(x)
        model_failure = None
    except Exception as exc:
        model = None
        model_failure = f"exception:{type(exc).__name__}:{exc}"
    model_seconds = time.perf_counter() - model_start
    pools, intervals = {}, []
    repetition = metadata["repetition"]
    for pool in ("cbc", "fgn"):
        pool_start = time.perf_counter()
        seed = shared.record_seed(config, cell, repetition, f"interval_{pool}")
        rng = np.random.default_rng(seed)
        failure = None
        try:
            if pool == "cbc":
                samples = np.array(
                    [
                        circular_block_resample(x, rng, len(x) // config["block_divisor"])
                        for _ in range(config["bootstrap_draws"])
                    ]
                )
            elif model is not None:
                samples = candidates.fitted_fgn_samples(
                    model, len(x), config["bootstrap_draws"], rng
                )
            else:
                samples = np.empty((0, len(x)))
                failure = model_failure
        except Exception as exc:
            samples = np.empty((0, len(x)))
            failure = f"exception:{type(exc).__name__}:{exc}"
        distributions, counts = {}, {}
        for method in config["methods"]:
            values, accounting = candidates.evaluate_draws(samples, method)
            distributions[method] = values.tolist()
            counts[method] = accounting
            center = points[method] if pool == "cbc" else model["H"] if model is not None else None
            for construction in ("percentile", "basic"):
                interval = (
                    None
                    if center is None
                    else candidates.bootstrap_interval(
                        points[method],
                        values,
                        center=center,
                        method=construction,
                        nominal=config["nominal"],
                    )
                )
                intervals.append(
                    {
                        "method": method,
                        "candidate": f"{pool}_{construction}",
                        "point": points[method],
                        "ci_low": interval[0] if interval else None,
                        "ci_high": interval[1] if interval else None,
                        "nominal": config["nominal"],
                        "draw_pool_id": f"{metadata['record_id']}:{pool}",
                        "unavailable_reason": (
                            failure or point_failures.get(method) or "insufficient_valid_draws"
                        )
                        if interval is None
                        else None,
                    }
                )
        pools[pool] = {
            "seed": seed,
            "requested_records": config["bootstrap_draws"],
            "generated_records": len(samples),
            "generation_failure": failure,
            "statistics": distributions,
            "accounting": counts,
            "elapsed_seconds": time.perf_counter() - pool_start,
        }
    if "GPH" in points:
        interval = candidates.gph_asymptotic_interval(
            points["GPH"], len(x), nominal=config["nominal"]
        )
        intervals.append(
            {
                "method": "GPH",
                "candidate": "gph_ols_normal",
                "point": points["GPH"],
                "ci_low": interval[0] if interval else None,
                "ci_high": interval[1] if interval else None,
                "nominal": config["nominal"],
                "draw_pool_id": None,
                "unavailable_reason": point_failures.get("GPH") if interval is None else None,
            }
        )
    target = (
        0.5
        if cell["family"] == "AR1"
        else cell["parameter"] + (0.5 if cell["family"] == "ARFIMA" else 0)
    )
    return shared.finite_json(
        {
            "record_id": metadata["record_id"],
            "input_sha256": metadata["sha256"],
            "repetition": repetition,
            "cell": shared.cell_id(cell),
            **cell,
            "H_target": target,
            "target_interpretation": "asymptotic_short_memory_control"
            if cell["family"] == "AR1"
            else "model_memory_parameter",
            "points": points,
            "point_failures": point_failures,
            "fitted_model": model,
            "model_failure": model_failure,
            "point_seconds": point_seconds,
            "model_seconds": model_seconds,
            "draw_pools": pools,
            "intervals": intervals,
            "elapsed_seconds": time.perf_counter() - start,
        }
    )


def interval_frame(records):
    rows = []
    for record in records:
        for interval in record["intervals"]:
            row = {
                k: record[k]
                for k in ("record_id", "repetition", "cell", "family", "parameter", "n", "H_target")
            }
            row.update(interval)
            finite_point = row["point"] is not None and math.isfinite(row["point"])
            row["available"] = bool(
                finite_point
                and row["ci_low"] is not None
                and row["ci_high"] is not None
                and math.isfinite(row["ci_low"])
                and math.isfinite(row["ci_high"])
                and row["ci_low"] <= row["ci_high"]
                and row["nominal"] == 0.95
            )
            row["covered"] = bool(
                row["available"] and row["ci_low"] <= row["H_target"] <= row["ci_high"]
            )
            rows.append(row)
    return pd.DataFrame(rows)


def summarize(frame):
    summaries = []
    for (cell, method, candidate), group in frame.groupby(["cell", "method", "candidate"]):
        valid = group.point.notna() & np.isfinite(pd.to_numeric(group.point, errors="coerce"))
        available = group[group.available]
        hits = int(available.covered.sum())
        low, high = shared.wilson(hits, len(available))
        target = group.H_target.iloc[0]
        summaries.append(
            {
                "cell": cell,
                "method": method,
                "candidate": candidate,
                "n": int(group.n.iloc[0]),
                "H_target": target,
                "nominal": 0.95,
                "n_attempted": len(group),
                "n_valid": int(valid.sum()),
                "n_available": len(available),
                "n_covered": hits,
                "availability": len(available) / len(group),
                "coverage": hits / len(available) if len(available) else None,
                "wilson_low": low,
                "wilson_high": high,
                "covered_per_attempt": hits / len(group),
                "mean_width": (available.ci_high - available.ci_low).mean(),
                "bias": (group.loc[valid, "point"] - target).mean(),
                "mae": (group.loc[valid, "point"] - target).abs().mean(),
            }
        )
    return pd.DataFrame(summaries)


def paired_comparisons(frame):
    rows = []
    for (cell, method), group in frame.groupby(["cell", "method"]):
        baseline = group[group.candidate == "cbc_percentile"].set_index("record_id")
        for candidate, compared in group.groupby("candidate"):
            if candidate == "cbc_percentile":
                continue
            compared = compared.set_index("record_id")
            paired = compared.join(baseline, lsuffix="_candidate", rsuffix="_baseline", how="outer")
            available = paired.available_candidate.fillna(False) & paired.available_baseline.fillna(
                False
            )
            pairs = paired[available]
            differences = pairs.covered_candidate.astype(float) - pairs.covered_baseline.astype(
                float
            )
            rows.append(
                {
                    "cell": cell,
                    "method": method,
                    "candidate": candidate,
                    "baseline": "cbc_percentile",
                    "n_attempted_pairs": len(paired),
                    "n_available_pairs": len(pairs),
                    "n_missing_pairs": int((~available).sum()),
                    "coverage_difference": differences.mean(),
                    "difference_mcse": differences.std(ddof=1) / np.sqrt(len(pairs))
                    if len(pairs) > 1
                    else None,
                    "width_difference": (
                        (pairs.ci_high_candidate - pairs.ci_low_candidate)
                        - (pairs.ci_high_baseline - pairs.ci_low_baseline)
                    ).mean(),
                }
            )
    return pd.DataFrame(rows)


def export(output, connection, config, index):
    records = []
    for payload, checksum in connection.execute(
        "SELECT payload, checksum FROM records ORDER BY record_id"
    ):
        record = json.loads(payload)
        if shared.digest(record) != checksum:
            raise ValueError("Checkpoint checksum mismatch")
        records.append(record)
    frame = interval_frame(records)
    if not frame.empty:
        frame.to_csv(output / "intervals.csv", index=False)
        summarize(frame).to_csv(output / "coverage_summary.csv", index=False)
        paired_comparisons(frame).to_csv(output / "paired_comparisons.csv", index=False)
    model_rows = [
        {
            "record_id": r["record_id"],
            "cell": r["cell"],
            "H_target": r["H_target"],
            "failure": r["model_failure"],
            **(r["fitted_model"] or {}),
        }
        for r in records
    ]
    pd.DataFrame(model_rows).to_csv(output / "fitted_models.csv", index=False)
    pd.DataFrame(index).to_csv(output / "input_index.csv", index=False)
    with (output / "records.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(shared.canonical(record) + "\n")
    accounting = []
    for record in records:
        for pool, details in record["draw_pools"].items():
            for method, counts in details["accounting"].items():
                accounting.append(
                    {"record_id": record["record_id"], "pool": pool, "method": method, **counts}
                )
    pd.DataFrame(accounting).to_csv(output / "draw_accounting.csv", index=False)
    expected = workload(config)
    shared.atomic_json(
        output / "progress.json",
        {
            "status": "development_only_not_confirmation",
            "completed_records": len(records),
            "complete": len(records) == expected["independent_records"],
            "expected": expected,
            "model_failures": sum(r["model_failure"] is not None for r in records),
            "model_boundary_hits": sum(
                bool(r["fitted_model"] and r["fitted_model"]["boundary_hit"]) for r in records
            ),
            "generated_bootstrap_records": sum(
                p["generated_records"] for r in records for p in r["draw_pools"].values()
            ),
            "elapsed_record_seconds": sum(r["elapsed_seconds"] for r in records),
            "artifact_sha256": {
                p.name: shared.file_hash(p)
                for p in output.iterdir()
                if p.suffix in {".csv", ".jsonl"}
            },
        },
    )


def run(config, output, *, max_new_records=None, experiment=None):
    """Checkpoint engine shared by explicitly versioned development experiments."""
    experiment = experiment or sys.modules[__name__]
    experiment.validate(config)
    if max_new_records is not None and max_new_records < 1:
        raise ValueError("max-new-records must be positive")
    output.mkdir(parents=True, exist_ok=True)
    identity = shared.run_identity(config, [], config["repetitions"], False)
    identity["status"] = config["stage"]
    for path in (Path(__file__), Path(candidates.__file__), Path(experiment.__file__)):
        identity["source_sha256"][str(path.relative_to(shared.ROOT))] = shared.file_hash(path)
    with shared.exclusive_run(output):
        shared.initialize(output, identity)
        with contextlib.closing(sqlite3.connect(output / "checkpoints.sqlite")) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS records (record_id TEXT PRIMARY KEY, payload TEXT NOT NULL, checksum TEXT NOT NULL)"
            )
            done = set()
            for record_id, payload, checksum in connection.execute(
                "SELECT record_id, payload, checksum FROM records"
            ):
                if shared.digest(json.loads(payload)) != checksum:
                    raise ValueError("Checkpoint checksum mismatch")
                done.add(record_id)
            expected_ids = {
                f"{shared.cell_id(cell)}_r{r}"
                for cell in shared.cells(config)
                for r in range(config["repetitions"])
            }
            if not done <= expected_ids:
                raise ValueError("Checkpoint contains records outside the declared grid")
            index, new = [], 0
            for cell in shared.cells(config):
                values, meta = shared.input_pool(output, config, cell, config["repetitions"])
                index.extend({"cell": shared.cell_id(cell), **m} for m in meta["records"])
                for x, metadata in zip(values, meta["records"], strict=True):
                    if metadata["record_id"] in done:
                        continue
                    if max_new_records is not None and new >= max_new_records:
                        experiment.export(output, connection, config, index)
                        return {"new_records": new, "completed_records": len(done) + new}
                    record = experiment.fit_record(x, metadata, cell, config)
                    with connection:
                        connection.execute(
                            "INSERT INTO records VALUES (?, ?, ?)",
                            (
                                metadata["record_id"],
                                shared.canonical(record),
                                shared.digest(record),
                            ),
                        )
                    new += 1
                    if (new + len(done)) % 16 == 0:
                        print(
                            f"Saved {len(done) + new}/{experiment.workload(config)['independent_records']} records",
                            flush=True,
                        )
            experiment.export(output, connection, config, index)
            return {"new_records": new, "completed_records": len(done) + new}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-new-records", type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate(config)
    if args.dry_run:
        print(json.dumps(workload(config), indent=2))
    elif args.output is None:
        parser.error("--output required")
    else:
        print(
            json.dumps(
                run(config, args.output.resolve(), max_new_records=args.max_new_records), indent=2
            )
        )


if __name__ == "__main__":
    main()
