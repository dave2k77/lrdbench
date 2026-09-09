"""Development screen separating sample centering from unknown-mean model fitting.

Research exports only. No package estimator or default interval is changed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import cholesky, solve_triangular, toeplitz
from scipy.optimize import minimize_scalar

from lrdbench.bootstrap import circular_block_resample

try:
    from . import interval_candidates as ci
    from . import run_interval_comparison as engine
except ImportError:
    import interval_candidates as ci
    import run_interval_comparison as engine

shared = engine.shared
DEFAULT_CONFIG = Path(__file__).with_name("mean-comparison.json")


def centered(x):
    """Remove the arithmetic mean separately from each supplied record."""
    x = np.asarray(x, dtype=float)
    return x - x.mean(axis=-1, keepdims=True)


def profiled_unknown_mean_likelihood(x, h):
    """Gaussian ML: GLS mean, sigma²=Q/n, objective=n log(Q/n)+log|R|.

    This is ordinary profiled ML, not REML. The arithmetic mean used by the
    geometric statistic is a separate operation from the GLS model mean.
    """
    factor = cholesky(toeplitz(ci.fgn_covariance(len(x), h)), lower=True, check_finite=False)
    whitened = solve_triangular(
        factor, np.column_stack([x, np.ones(len(x))]), lower=True, check_finite=False
    )
    y, intercept = whitened.T
    mean = float(np.dot(intercept, y) / np.dot(intercept, intercept))
    residual = y - mean * intercept
    variance = float(np.dot(residual, residual) / len(x))
    if not math.isfinite(variance) or variance <= 0:
        raise ValueError("Nonpositive/nonfinite fitted variance")
    objective = len(x) * math.log(variance) + 2 * np.log(np.diag(factor)).sum()
    return float(objective), variance, mean


def fit_unknown_mean_fgn(x):
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or len(x) < 64 or not np.isfinite(x).all() or np.ptp(x) == 0:
        raise ValueError("fGn fitting requires a finite nonconstant vector of length >= 64")
    # Numerical translation/scale normalization; the GLS mean is still profiled
    # at every H, not fixed to this sample mean.
    location = float(x.mean())
    scale = float(np.max(np.abs(x - location)))
    normalized = (x - location) / scale
    grid = np.linspace(*ci.H_BOUNDS, 11)
    objectives = [profiled_unknown_mean_likelihood(normalized, h)[0] for h in grid]
    index = int(np.argmin(objectives))
    bracket = (grid[max(0, index - 1)], grid[min(len(grid) - 1, index + 1)])
    result = minimize_scalar(
        lambda h: profiled_unknown_mean_likelihood(normalized, h)[0],
        bounds=bracket,
        method="bounded",
        options={"xatol": 1e-5, "maxiter": 100},
    )
    if not result.success or not math.isfinite(result.fun):
        raise ValueError("fGn likelihood optimizer failed")
    h = float(result.x) if result.fun <= objectives[index] else float(grid[index])
    objective, variance, mean = profiled_unknown_mean_likelihood(normalized, h)
    return {
        "model": "stationary_gaussian_fgn_unknown_constant_mean_ml",
        "H": h,
        "sigma": math.sqrt(variance) * scale,
        "mean": location + mean * scale,
        "objective": objective + 2 * len(x) * math.log(scale),
        "bounds": ci.H_BOUNDS,
        "boundary_hit": min(h - ci.H_BOUNDS[0], ci.H_BOUNDS[1] - h) <= 1e-3,
        "optimizer_success": True,
        "covariance_diagonal_jitter": 0.0,
    }


def validate(config):
    if config.get("stage") != "development_mean_comparison" or config.get("schema_version") != 1:
        raise ValueError("Only the declared mean-comparison development schema is supported")
    if config.get("fgn_model") != "known_zero_and_unknown_constant_mean_ml":
        raise ValueError("Both declared fGn model fits are required")
    if config.get("offset_probe") != 1.0:
        raise ValueError("The paired constant-offset probe must be +1 in input units")
    proxy = {k: v for k, v in config.items() if k != "offset_probe"}
    proxy.update(
        stage="development_interval_comparison",
        fgn_model="stationary_gaussian_fgn_known_zero_mean",
    )
    engine.validate(proxy)


def workload(config):
    records = len(shared.cells(config)) * config["repetitions"]
    methods = len(config["methods"])
    return {
        "cells": len(shared.cells(config)),
        "independent_records": records,
        "model_fits": records * 2,
        "point_statistics": records * methods * 2,
        "offset_probe_statistics": records * methods * 2,
        "physical_bootstrap_records": records * 3 * config["bootstrap_draws"],
        "bootstrap_statistic_attempts": records * 5 * config["bootstrap_draws"] * methods,
        "interval_rows": records * (6 * methods + 2 * int("GPH" in config["methods"])),
    }


def fit_record(x, metadata, cell, config):
    start = time.perf_counter()
    points, point_failures, probes = {}, {}, []
    for treatment, values in (("raw", x), ("centered", centered(x))):
        for method in config["methods"]:
            key = f"{treatment}:{method}"
            try:
                value = ci.statistic(values, method)
                points[key] = value if value is not None and math.isfinite(value) else None
                if points[key] is None:
                    point_failures[key] = "invalid_statistic"
            except Exception as exc:
                points[key] = None
                point_failures[key] = f"exception:{type(exc).__name__}:{exc}"
            shifted = x + config["offset_probe"]
            shifted = centered(shifted) if treatment == "centered" else shifted
            try:
                shifted_point = ci.statistic(shifted, method)
                if shifted_point is None or not math.isfinite(shifted_point):
                    raise ValueError("invalid_statistic")
                probe_failure = None
            except Exception as exc:
                shifted_point = None
                probe_failure = f"exception:{type(exc).__name__}:{exc}"
            probes.append(
                {
                    "method": method,
                    "treatment": treatment,
                    "offset": config["offset_probe"],
                    "point": points[key],
                    "shifted_point": shifted_point,
                    "failure": probe_failure or point_failures.get(key),
                    "point_difference": shifted_point - points[key]
                    if shifted_point is not None and points[key] is not None
                    else None,
                }
            )
    point_seconds = time.perf_counter() - start
    model_start = time.perf_counter()
    models, model_failures = {}, {}
    for name, fit in (("zero", ci.fit_zero_mean_fgn), ("unknown", fit_unknown_mean_fgn)):
        try:
            models[name] = fit(x)
            model_failures[name] = None
        except Exception as exc:
            models[name] = None
            model_failures[name] = f"exception:{type(exc).__name__}:{exc}"
    model_seconds = time.perf_counter() - model_start
    pools, intervals = {}, []

    def add_interval(method, treatment, candidate, interval, pool, failure):
        key = f"{treatment}:{method}"
        intervals.append(
            {
                "method": method,
                "treatment": treatment,
                "candidate": candidate,
                "point": points[key],
                "ci_low": interval[0] if interval else None,
                "ci_high": interval[1] if interval else None,
                "nominal": config["nominal"],
                "draw_pool_id": f"{metadata['record_id']}:{pool}" if pool else None,
                "unavailable_reason": (
                    failure or point_failures.get(key) or "insufficient_valid_draws"
                )
                if interval is None
                else None,
            }
        )

    for pool in ("cbc", "zero", "unknown"):
        pool_start = time.perf_counter()
        # Common random numbers for the two Gaussian models; they remain two
        # distinct physical pools. Every method shares its pool's record draws.
        seed_label = "mean_cbc" if pool == "cbc" else "mean_fgn"
        seed = shared.record_seed(config, cell, metadata["repetition"], seed_label)
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
            elif models[pool] is not None:
                model = models[pool]
                samples = ci.fitted_fgn_samples(model, len(x), config["bootstrap_draws"], rng)
                samples += model["mean"]
            else:
                samples = np.empty((0, len(x)))
                failure = model_failures[pool]
        except Exception as exc:
            samples = np.empty((0, len(x)))
            failure = f"exception:{type(exc).__name__}:{exc}"
        distributions, counts = {}, {}
        treatments = ("centered",) if pool == "unknown" else ("raw", "centered")
        for treatment in treatments:
            # Re-estimate each bootstrap record's arithmetic mean before the
            # path transform; never subtract the original record's sample mean.
            values = centered(samples) if treatment == "centered" else samples
            for method in config["methods"]:
                key = f"{treatment}:{method}"
                draws, accounting = ci.evaluate_draws(values, method)
                distributions[key] = draws.tolist()
                counts[key] = accounting
                center = (
                    points[key]
                    if pool == "cbc"
                    else models[pool]["H"]
                    if models[pool] is not None
                    else None
                )
                constructions = (
                    ("percentile", "basic")
                    if pool == "cbc" and treatment == "centered"
                    else ("percentile",)
                    if pool == "cbc"
                    else ("basic",)
                )
                for construction in constructions:
                    interval = (
                        ci.bootstrap_interval(
                            points[key],
                            draws,
                            center=center,
                            method=construction,
                            nominal=config["nominal"],
                        )
                        if center is not None
                        else None
                    )
                    name = (
                        "cbc_percentile"
                        if pool == "cbc" and treatment == "raw"
                        else f"{pool}_{treatment}_{construction}"
                    )
                    add_interval(method, treatment, name, interval, pool, failure)
        pools[pool] = {
            "seed": seed,
            "requested_records": config["bootstrap_draws"],
            "generated_records": len(samples),
            "generation_failure": failure,
            "statistics": distributions,
            "accounting": counts,
            "elapsed_seconds": time.perf_counter() - pool_start,
        }
    if "GPH" in config["methods"]:
        for treatment in ("raw", "centered"):
            interval = ci.gph_asymptotic_interval(points[f"{treatment}:GPH"], len(x))
            add_interval("GPH", treatment, f"gph_{treatment}_normal", interval, None, None)
    target = (
        0.5
        if cell["family"] == "AR1"
        else cell["parameter"] + (0.5 if cell["family"] == "ARFIMA" else 0)
    )
    return shared.finite_json(
        {
            "record_id": metadata["record_id"],
            "input_sha256": metadata["sha256"],
            "repetition": metadata["repetition"],
            "cell": shared.cell_id(cell),
            **cell,
            "H_target": target,
            "target_interpretation": "asymptotic_short_memory_control"
            if cell["family"] == "AR1"
            else "model_memory_parameter",
            "points": points,
            "point_failures": point_failures,
            "offset_probes": probes,
            "fitted_models": models,
            "model_failures": model_failures,
            "point_seconds": point_seconds,
            "model_seconds": model_seconds,
            "draw_pools": pools,
            "intervals": intervals,
            "elapsed_seconds": time.perf_counter() - start,
        }
    )


def export(output, connection, config, index):
    records = []
    for payload, checksum in connection.execute(
        "SELECT payload, checksum FROM records ORDER BY record_id"
    ):
        record = json.loads(payload)
        if shared.digest(record) != checksum:
            raise ValueError("Checkpoint checksum mismatch")
        records.append(record)
    frame = engine.interval_frame(records)
    tables = {"input_index": pd.DataFrame(index)}
    if not frame.empty:
        tables.update(intervals=frame, coverage_summary=engine.summarize(frame))
        tables["paired_comparisons"] = engine.paired_comparisons(frame)
        # Also isolate the effect of the model mean after holding centering fixed.
        recoded = frame[
            frame.candidate.isin(["zero_centered_basic", "unknown_centered_basic"])
        ].copy()
        recoded.loc[recoded.candidate == "zero_centered_basic", "candidate"] = "cbc_percentile"
        isolated = engine.paired_comparisons(recoded)
        isolated["baseline"] = "zero_centered_basic"
        tables["mean_model_comparisons"] = isolated
    tables["fitted_models"] = pd.DataFrame(
        {
            "record_id": r["record_id"],
            "cell": r["cell"],
            "model_fit": name,
            "H_target": r["H_target"],
            "failure": r["model_failures"][name],
            **(model or {}),
        }
        for r in records
        for name, model in r["fitted_models"].items()
    )
    tables["offset_probes"] = pd.DataFrame(
        {"record_id": r["record_id"], "cell": r["cell"], **probe}
        for r in records
        for probe in r["offset_probes"]
    )
    tables["draw_accounting"] = pd.DataFrame(
        {"record_id": r["record_id"], "pool": pool, "statistic": key, **counts}
        for r in records
        for pool, details in r["draw_pools"].items()
        for key, counts in details["accounting"].items()
    )
    for name, table in tables.items():
        table.to_csv(output / f"{name}.csv", index=False, lineterminator="\n")
    with (output / "records.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(shared.canonical(record) + "\n")
    expected = workload(config)
    shared.atomic_json(
        output / "progress.json",
        {
            "status": "development_only_not_confirmation",
            "completed_records": len(records),
            "complete": len(records) == expected["independent_records"],
            "expected": expected,
            "model_failures": sum(
                f is not None for r in records for f in r["model_failures"].values()
            ),
            "model_boundary_hits": {
                name: sum(
                    bool(r["fitted_models"][name] and r["fitted_models"][name]["boundary_hit"])
                    for r in records
                )
                for name in ("zero", "unknown")
            },
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


def run(config, output, *, max_new_records=None):
    return engine.run(
        config, output, max_new_records=max_new_records, experiment=sys.modules[__name__]
    )


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
