"""Checkpointed classical point-estimator stress development run. Dry-run first."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from lrdbench.defaults import build_default_estimator_registry
from lrdbench.enums import SourceType
from lrdbench.schema import EstimatorSpec

try:
    from . import materialize_shared_stress as inputs
    from . import paired_summary
    from . import run_calibration as shared
except ImportError:
    import materialize_shared_stress as inputs
    import paired_summary
    import run_calibration as shared

DEFAULT_CONFIG = Path(__file__).with_name("shared-stress.json")


def roster():
    configurations = shared.configurations(shared.ROOT)
    result = [
        {"method": name, "base": base, "params": params, "center": False}
        for name, base, params in configurations
    ]
    result += [
        {**row, "method": row["method"] + "::centered", "center": True}
        for row in result
        if row["base"] in {"Higuchi", "GHE"}
    ]
    return sorted(result, key=lambda row: row["method"])


def workload(config):
    parents = len(shared.cells(config)) * config["repetitions"]
    return {
        "cells": len(shared.cells(config)),
        "independent_parents": parents,
        "contamination_conditions": len(config["conditions"]),
        "descendants": parents * len(config["conditions"]),
        "methods": len(roster()),
        "point_fits": parents * (len(config["conditions"]) + 1) * len(roster()),
        "within_record_interval_fits": 0,
    }


def identity(config, source):
    pools = {}
    for cell in shared.cells(config):
        _, _, sha = inputs.parent_pool(source, config, cell)
        pools[shared.cell_id(cell)] = sha
    result = shared.run_identity(config, roster(), config["repetitions"], False)
    result["status"] = config["stage"]
    result["source_pool_sha256"] = pools
    for path in (
        Path(__file__),
        Path(inputs.__file__),
        Path(paired_summary.__file__),
        Path(__file__).with_name("estimator_eligibility.csv"),
    ):
        result["source_sha256"][str(path.relative_to(shared.ROOT))] = shared.file_hash(path)
    return result


def fit(registry, cell, values, metadata, setting):
    x = values.copy()
    if setting["center"]:
        x -= np.mean(x)
    x.setflags(write=False)
    parent_meta = {**metadata, "record_id": metadata["parent_id"]}
    record = inputs.build_parent(cell, x, parent_meta)
    record = replace(
        record,
        record_id=metadata["record_id"],
        truth=None,
        source_type=SourceType.SYNTHETIC
        if metadata["condition"] == "clean"
        else SourceType.CONTAMINATED,
        source_name=metadata["condition"],
        provenance=replace(
            record.provenance,
            record_id=metadata["record_id"],
            parent_id=None if metadata["condition"] == "clean" else metadata["parent_id"],
            seed=metadata["resampling_seed"],
        ),
    )
    spec = EstimatorSpec(
        setting["method"],
        "stress_development",
        "hurst_scaling_proxy",
        (),
        True,
        True,
        parameter_schema=setting["params"],
    )
    start = time.perf_counter()
    try:
        result = registry.get(setting["base"])(spec).fit(record)
        point = float(result.point) if result.point is not None else None
        valid = bool(result.valid and point is not None and np.isfinite(point))
        fields = {
            "point": point,
            "valid": valid,
            "failure_reason": result.failure_reason,
            "warnings": result.warnings,
            "diagnostics": dict(result.diagnostics),
            "estimator_version": result.estimator_version,
        }
        if not valid and not fields["failure_reason"]:
            fields["failure_reason"] = "invalid_or_nonfinite_point"
    except Exception as exc:
        fields = {
            "point": None,
            "valid": False,
            "failure_reason": f"exception:{type(exc).__name__}:{exc}",
            "warnings": [],
            "diagnostics": {},
            "estimator_version": None,
        }
    return shared.finite_json(
        {
            "cell": shared.cell_id(cell),
            **cell,
            "H_target": inputs.target(cell),
            "target_role": "latent_clean_recovery",
            "parent_id": metadata["parent_id"],
            "record_id": metadata["record_id"],
            "condition": metadata["condition"],
            "method": setting["method"],
            "base_method": setting["base"],
            "treatment": "sample_centered" if setting["center"] else "raw",
            "parameters": setting["params"],
            "input_sha256": metadata["sha256"],
            "analysed_sha256": shared.array_hash(x),
            "repetition": metadata["repetition"],
            "interval_status": "not_evaluated_point_stress_screen",
            **fields,
            "elapsed_seconds": time.perf_counter() - start,
        }
    )


def scientific_hash(rows):
    return shared.digest([{k: v for k, v in row.items() if k != "elapsed_seconds"} for row in rows])


def checkpoints(db):
    result = {}
    for parent, payload, sha in db.execute(
        "SELECT parent_id, payload, sha256 FROM completed ORDER BY parent_id"
    ):
        rows = json.loads(payload)
        if shared.digest(rows) != sha:
            raise ValueError("Checkpoint payload hash mismatch.")
        result[parent] = rows
    return result


def export(output, complete, index):
    rows = [row for parent in sorted(complete) for row in complete[parent]]
    frame = pd.DataFrame(rows)
    for column in ("parameters", "warnings", "diagnostics"):
        if column in frame:
            frame[column + "_json"] = frame.pop(column).map(shared.canonical)
    frame.to_csv(output / "point_estimates.csv", index=False, lineterminator="\n")
    # Nullable uint64-sized seeds otherwise coerce to float64 and lose digits.
    # Encode directly from Python integers before DataFrame type inference.
    exact_index = [
        {
            key: str(value) if key.endswith("_seed") and value is not None else value
            for key, value in row.items()
        }
        for row in index
    ]
    pd.DataFrame(exact_index).to_csv(output / "input_index.csv", index=False, lineterminator="\n")
    pd.DataFrame(
        [
            {"parent_id": parent, "fits": len(rows), "scientific_sha256": scientific_hash(rows)}
            for parent, rows in sorted(complete.items())
        ]
    ).to_csv(output / "record_checksums.csv", index=False, lineterminator="\n")
    return frame


def run(config, source, output, *, max_new_parents=None):
    inputs.validate_config(config)
    if max_new_parents is not None and (type(max_new_parents) is not int or max_new_parents < 0):
        raise ValueError("max_new_parents must be a nonnegative integer.")
    run_identity = identity(config, source)
    output.mkdir(parents=True, exist_ok=True)
    with shared.exclusive_run(output):
        shared.initialize(output, run_identity)
        folder = output / "inputs"
        folder.mkdir(exist_ok=True)
        registry, settings = build_default_estimator_registry(), roster()
        index, pools = [], []
        for cell in shared.cells(config):
            values, metadata = inputs.materialize_cell(source, folder, config, cell)
            pools.append((cell, values, metadata))
            for row in metadata["records"]:
                index.append(
                    {
                        "cell": shared.cell_id(cell),
                        **cell,
                        "H_target": inputs.target(cell),
                        **{
                            k: v
                            for k, v in row.items()
                            if k not in {"provenance", "transformation"}
                        },
                    }
                )
        db = sqlite3.connect(output / "checkpoint.sqlite")
        try:
            db.execute(
                "CREATE TABLE IF NOT EXISTS completed (parent_id TEXT PRIMARY KEY, payload TEXT NOT NULL, sha256 TEXT NOT NULL)"
            )
            complete, new = checkpoints(db), 0
            expected_parents = {row["parent_id"] for row in index}
            if set(complete) - expected_parents:
                raise ValueError("Checkpoint contains parents outside this design.")
            fits_per_parent = (len(config["conditions"]) + 1) * len(settings)
            for parent, rows in complete.items():
                if len(rows) != fits_per_parent or {r["parent_id"] for r in rows} != {parent}:
                    raise ValueError("Incomplete or mixed parent checkpoint.")
            for cell, values, metadata in pools:
                width = values.shape[1]
                for r, block in enumerate(values):
                    meta = metadata["records"][r * width : (r + 1) * width]
                    parent = meta[0]["parent_id"]
                    if parent in complete or (
                        max_new_parents is not None and new >= max_new_parents
                    ):
                        continue
                    rows = [
                        fit(registry, cell, x, row, setting)
                        for x, row in zip(block, meta, strict=True)
                        for setting in settings
                    ]
                    payload = shared.canonical(rows)
                    db.execute(
                        "INSERT INTO completed VALUES (?, ?, ?)",
                        (parent, payload, shared.digest(rows)),
                    )
                    db.commit()
                    complete[parent] = rows
                    new += 1
                    if new % 16 == 0 or new == 1:
                        print(
                            f"Checkpointed {len(complete)}/{len(expected_parents)} independent parents",
                            flush=True,
                        )
                    shared.atomic_json(
                        output / "progress.json",
                        {
                            "completed_parents": len(complete),
                            "expected_parents": len(expected_parents),
                            "complete": len(complete) == len(expected_parents),
                        },
                    )
            frame = export(output, complete, index)
            progress = {
                **workload(config),
                "completed_parents": len(complete),
                "new_parents": new,
                "completed_point_fits": len(frame),
                "valid_point_fits": int(frame.valid.sum()) if len(frame) else 0,
                "complete": len(complete) == len(expected_parents),
                "fit_seconds": float(frame.elapsed_seconds.sum()) if len(frame) else 0,
            }
            shared.atomic_json(output / "progress.json", progress)
        finally:
            db.close()
    return progress


def pair_frame(points):
    keys = ["cell", "parent_id", "method"]
    clean = points[points.condition == "clean"][keys + ["point", "valid", "H_target"]]
    clean = clean.rename(
        columns={"point": "clean_point", "valid": "clean_valid", "H_target": "clean_target"}
    )
    stressed = points[points.condition != "clean"].copy()
    pairs = stressed.merge(clean, on=keys, how="left", validate="many_to_one")
    if not pairs.H_target.eq(pairs.clean_target).all():
        raise ValueError("Stress and clean targets do not match.")
    pairs["clean_error"] = (
        (pairs.clean_point - pairs.H_target).abs().where(pairs.clean_valid.eq(True))
    )
    pairs["stressed_error"] = (pairs.point - pairs.H_target).abs().where(pairs.valid.eq(True))
    pairs["signed_estimate_drift"] = (pairs.point - pairs.clean_point).where(
        pairs.valid.eq(True) & pairs.clean_valid.eq(True)
    )
    pairs["absolute_estimate_drift"] = pairs.signed_estimate_drift.abs()
    return pairs.rename(columns={"cell": "stratum"})


def summarize(config, output):
    recorded = json.loads((output / "run.json").read_text(encoding="utf-8"))["identity"]
    if recorded["config"] != config or recorded["roster"] != roster():
        raise ValueError("Summary design differs from the recorded run.")
    progress = json.loads((output / "progress.json").read_text(encoding="utf-8"))
    if not progress["complete"]:
        raise ValueError("Summaries require the complete declared run.")
    points = pd.read_csv(output / "point_estimates.csv")
    pairs = pair_frame(points)
    tables, accounting, distributions, designs = [], [], [], {}
    for domain in sorted(config["processes"]):
        strata = [shared.cell_id(c) for c in shared.cells(config) if c["family"] == domain]
        design = {
            "methods": [r["method"] for r in roster()],
            "conditions": [c["id"] for c in inputs.conditions(config)],
            "parents_by_stratum": {
                s: [f"{s}_r{r}" for r in range(config["repetitions"])] for s in strata
            },
            "stratum_weights": {s: 1 / len(strata) for s in strata},
            **config["summary"],
        }
        designs[domain] = design
        result = paired_summary.summarize_paired_errors(pairs[pairs.stratum.isin(strata)], **design)
        for destination, table in zip((tables, accounting, distributions), result, strict=True):
            table.insert(0, "domain", domain)
            destination.append(table)
    for name, parts in (
        ("paired_summary", tables),
        ("parent_accounting", accounting),
        ("summary_draws", distributions),
    ):
        pd.concat(parts, ignore_index=True).to_csv(
            output / f"{name}.csv", index=False, lineterminator="\n"
        )
    # Per-cell accuracy and drift retain each method's available support; the
    # separate joint summaries above use explicitly reported common support.
    summaries = []
    for (cell, method, condition), group in points.groupby(["cell", "method", "condition"]):
        valid = group.valid & np.isfinite(group.point)
        errors = group.loc[valid, "point"] - group.loc[valid, "H_target"]
        summaries.append(
            {
                "cell": cell,
                "method": method,
                "condition": condition,
                "attempted": len(group),
                "valid": int(valid.sum()),
                "invalid": int((~valid).sum()),
                "bias": errors.mean(),
                "mae": errors.abs().mean(),
                "rmse": np.sqrt((errors**2).mean()),
                "bias_mcse": errors.std(ddof=1) / np.sqrt(len(errors))
                if len(errors) > 1
                else np.nan,
                "outside_0_1": int(
                    ((group.loc[valid, "point"] <= 0) | (group.loc[valid, "point"] >= 1)).sum()
                ),
            }
        )
    pd.DataFrame(summaries).to_csv(output / "cell_summary.csv", index=False, lineterminator="\n")
    drift = pairs.groupby(["stratum", "method", "condition"]).agg(
        attempted=("parent_id", "size"),
        available=("signed_estimate_drift", "count"),
        signed_drift=("signed_estimate_drift", "mean"),
        absolute_drift=("absolute_estimate_drift", "mean"),
    )
    drift.to_csv(output / "cell_drift.csv", lineterminator="\n")
    shared.atomic_json(
        output / "summary_design.json",
        {
            "status": "development_not_confirmation",
            "domains": designs,
            "point_input_sha256": shared.file_hash(output / "point_estimates.csv"),
            "source_sha256": {
                str(Path(p).relative_to(shared.ROOT)): shared.file_hash(Path(p))
                for p in (__file__, paired_summary.__file__)
            },
            "note": "Summary intervals concern performance across independent parents, not within-record H intervals. Drift is descriptive by cell; no pooled drift or coverage summary is implemented here.",
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-new-parents", type=int)
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    inputs.validate_config(config)
    if args.dry_run:
        run_identity = identity(config, args.source.resolve())
        print(
            json.dumps(
                {
                    **workload(config),
                    "source_pools_verified": len(run_identity["source_pool_sha256"]),
                },
                indent=2,
            )
        )
        return
    if args.output is None:
        parser.error("--output is required for execution.")
    output = args.output.resolve()
    progress = run(config, args.source.resolve(), output, max_new_parents=args.max_new_parents)
    print(json.dumps(progress, indent=2), flush=True)
    if args.summarize:
        summarize(config, output)


if __name__ == "__main__":
    main()
