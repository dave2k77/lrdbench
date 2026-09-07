"""Resumable development calibration; research exports, not the public run contract.

Dry-run first. --profile-repetitions reduces independent records, retaining the
full process/length/settings grid and bootstrap draws for cost measurement.
Results are checkpointed after each fit. One writer owns an output directory.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import os
import platform
import sqlite3
import subprocess
import time
from importlib.metadata import distributions
from itertools import groupby
from pathlib import Path

import numpy as np
import pandas as pd

from lrdbench.defaults import build_default_estimator_registry
from lrdbench.enums import SourceType
from lrdbench.generators._signal import arfima_autocovariance
from lrdbench.schema import EstimatorSpec, ProvenanceRecord, SeriesRecord

try:
    from .run_remaining_audit import configurations, wilson
except ImportError:  # Direct script execution.
    from run_remaining_audit import configurations, wilson

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).with_name("calibration-screen.json")
COUNTERS = (
    "bootstrap_replicates_attempted",
    "bootstrap_replicates_used",
    "bootstrap_replicates_invalid",
    "bootstrap_replicates_failed",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_hash(values):
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes()).hexdigest()


def finite_json(value):
    """Keep strict JSON; nonfinite diagnostic scalars become explicit nulls."""
    if isinstance(value, dict):
        return {str(k): finite_json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, np.ndarray)):
        return [finite_json(v) for v in value]
    if isinstance(value, np.generic):
        return finite_json(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(finite_json(value), indent=2, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(path)


@contextlib.contextmanager
def exclusive_run(output):
    """OS lock releases on process death; the harmless lock file stays on disk."""
    with (output / "run.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("Another calibration process owns this output directory.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def validate_config(config):
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
        "block_divisors",
        "ci_methods",
    }
    if set(config) != expected:
        raise ValueError(f"Configuration fields differ: {set(config) ^ expected}")
    if config["schema_version"] != 1 or config["stage"] != "development":
        raise ValueError("Only development schema 1 is implemented; confirmation is not frozen.")
    if not isinstance(config["seed_namespace"], str) or not config["seed_namespace"]:
        raise ValueError("A nonempty seed namespace is required.")
    for key, minimum in (("global_seed", 0), ("repetitions", 1), ("bootstrap_draws", 5)):
        if type(config[key]) is not int or config[key] < minimum:
            raise ValueError(f"{key} must be an integer >= {minimum}.")
    if config["nominal"] != 0.95:
        raise ValueError("This candidate screen currently evaluates central 95% intervals.")
    for key, minimum in (("lengths", 32), ("block_divisors", 2)):
        values = config[key]
        if (
            not values
            or len(values) != len(set(values))
            or any(type(v) is not int or v < minimum for v in values)
        ):
            raise ValueError(f"Invalid or duplicate {key}.")
    for n in config["lengths"]:
        blocks = [n // d for d in config["block_divisors"]]
        if min(blocks) < 2 or len(blocks) != len(set(blocks)):
            raise ValueError("Block rules must produce distinct lengths >= 2 in every cell.")
    if not config["processes"] or set(config["processes"]) - {"fGn", "ARFIMA", "AR1"}:
        raise ValueError("Supported processes are fGn, ARFIMA and AR1.")
    for family, values in config["processes"].items():
        low, high = {"fGn": (0, 1), "ARFIMA": (-0.5, 0.5), "AR1": (-1, 1)}[family]
        if (
            not values
            or len(values) != len(set(values))
            or any(not low < float(v) < high for v in values)
        ):
            raise ValueError(f"Invalid or duplicate {family} parameters.")
    if not config["ci_methods"] or set(config["ci_methods"]) - {"GPH", "Higuchi", "GHE"}:
        raise ValueError("This screen implements the audited GPH, Higuchi and GHE candidates.")
    for name, params in config["ci_methods"].items():
        if set(params) & {"n_bootstrap", "bootstrap_block_len", "ci_levels"}:
            raise ValueError("Resampling settings must be declared at the screen level.")
        if name in {"Higuchi", "GHE"} and params.get("input_representation") != "increments":
            raise ValueError("Geometric candidates must explicitly accept increments.")


def cells(config):
    return [
        {"family": family, "parameter": float(value), "n": n}
        for family, values in sorted(config["processes"].items())
        for value in sorted(values)
        for n in sorted(config["lengths"])
    ]


def cell_id(cell):
    return f"{cell['family']}_{cell['parameter']:g}_n{cell['n']}"


def record_seed(config, cell, repetition, stream):
    payload = [config["seed_namespace"], config["global_seed"], cell, repetition, stream]
    return int.from_bytes(hashlib.sha256(canonical(payload).encode()).digest()[:8], "little")


def covariance_factor(cell):
    n, p, family = cell["n"], cell["parameter"], cell["family"]
    if family == "AR1":
        return None
    if family == "ARFIMA":
        covariance = arfima_autocovariance(p, n)
    else:
        k = np.arange(n, dtype=float)
        covariance = (np.abs(k - 1) ** (2 * p) - 2 * k ** (2 * p) + (k + 1) ** (2 * p)) / 2
    lag = np.abs(np.arange(n)[:, None] - np.arange(n)[None, :])
    return np.linalg.cholesky(covariance[lag])


def generate_record(config, cell, repetition, factor):
    z = np.random.default_rng(record_seed(config, cell, repetition, "input")).normal(size=cell["n"])
    if cell["family"] == "AR1":
        # Exact stationary initialization with marginal variance 1, no burn-in.
        x = z.copy()
        phi = cell["parameter"]
        for t in range(1, len(x)):
            x[t] = phi * x[t - 1] + np.sqrt(1 - phi**2) * z[t]
        return x
    # One matvec per record makes the computation independent of batch size.
    return factor @ z


def input_pool(output, config, cell, repetitions):
    folder = output / "inputs"
    folder.mkdir(exist_ok=True)
    path = folder / f"{cell_id(cell)}.npz"
    if path.exists():
        with np.load(path, allow_pickle=False) as bundle:
            values = bundle["values"]
            metadata = json.loads(str(bundle["metadata"]))
    else:
        start = time.perf_counter()
        factor = covariance_factor(cell)
        values = np.array([generate_record(config, cell, r, factor) for r in range(repetitions)])
        metadata = {
            "cell": cell,
            "algorithm": "stationary_recursion"
            if cell["family"] == "AR1"
            else "covariance_cholesky",
            "covariance_diagonal_jitter": 0.0,
            "scale": "innovation_sd_1" if cell["family"] == "ARFIMA" else "marginal_sd_1",
            "generation_seconds": time.perf_counter() - start,
            "records": [
                {
                    "record_id": f"{cell_id(cell)}_r{r}",
                    "repetition": r,
                    "input_seed": record_seed(config, cell, r, "input"),
                    "resampling_seed": record_seed(config, cell, r, "resampling"),
                    "sha256": array_hash(x),
                }
                for r, x in enumerate(values)
            ],
        }
        temporary = path.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            np.savez_compressed(handle, values=values, metadata=canonical(metadata))
        temporary.replace(path)
    if metadata["cell"] != cell or values.shape != (repetitions, cell["n"]):
        raise ValueError(f"Input pool identity/shape mismatch: {path}")
    if len(metadata["records"]) != repetitions or not np.isfinite(values).all():
        raise ValueError(f"Invalid input pool: {path}")
    for r, (x, record) in enumerate(zip(values, metadata["records"], strict=True)):
        if (
            record["sha256"] != array_hash(x)
            or record["repetition"] != r
            or record["input_seed"] != record_seed(config, cell, r, "input")
            or record["resampling_seed"] != record_seed(config, cell, r, "resampling")
            or record["record_id"] != f"{cell_id(cell)}_r{r}"
        ):
            raise ValueError(f"Input pool hash/seed mismatch: {path}, repetition {r}")
    values.setflags(write=False)
    return values, metadata


def fit_settings(config, roster, n):
    for name, base, params in roster:
        yield "point", name, base, dict(params), None
    for base, params in sorted(config["ci_methods"].items()):
        for divisor in config["block_divisors"]:
            yield (
                "ci",
                base,
                base,
                {
                    **params,
                    "n_bootstrap": config["bootstrap_draws"],
                    "bootstrap_block_len": n // divisor,
                    "ci_levels": [config["nominal"]],
                },
                divisor,
            )


def workload(config, roster, repetitions):
    count = len(cells(config))
    ci_count = len(config["ci_methods"]) * len(config["block_divisors"])
    return {
        "cells": count,
        "independent_inputs": count * repetitions,
        "point_fits": count * repetitions * len(roster),
        "ci_fits": count * repetitions * ci_count,
        "bootstrap_draws": count * repetitions * ci_count * config["bootstrap_draws"],
    }


def environment():
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        np.show_config()
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy_build": buffer.getvalue(),
        "packages": {d.metadata["Name"]: d.version for d in distributions() if d.metadata["Name"]},
        "thread_environment": {
            k: os.environ.get(k)
            for k in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
            )
        },
    }


def run_identity(config, roster, repetitions, profile):
    source_paths = [
        *sorted((ROOT / "src/lrdbench").rglob("*.py")),
        Path(__file__),
        Path(__file__).with_name("run_remaining_audit.py"),
    ]
    return {
        "schema_version": 1,
        "research_exports_only": True,
        "status": "cost_profile_not_coverage_evidence"
        if profile
        else "development_not_confirmation",
        "config": config,
        "roster": roster,
        "actual_repetitions": repetitions,
        "environment": environment(),
        "source_sha256": {str(p.relative_to(ROOT)): file_hash(p) for p in source_paths},
    }


def initialize(output, identity):
    path = output / "run.json"
    identity = json.loads(canonical(identity))
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8"))["identity"] != identity:
            raise ValueError(
                "Resume refused: configuration, sources or environment changed. Use a new output."
            )
    else:
        if any(output.iterdir()):
            leftovers = [p.name for p in output.iterdir() if p.name != "run.lock"]
            if leftovers:
                raise ValueError("New runs require an empty output directory.")
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        atomic_json(
            path,
            {
                "identity": identity,
                "identity_sha256": digest(identity),
                "base_revision": revision.stdout.strip() if revision.returncode == 0 else None,
            },
        )
        packages = identity["environment"]["packages"]
        (output / "environment-pins.txt").write_text(
            "# Observed environment, not a wheel-hash lock; install this checkout separately.\n"
            + "\n".join(
                f"{name}=={version}"
                for name, version in sorted(packages.items())
                if name.lower() != "lrdbench"
            )
            + "\n",
            encoding="utf-8",
        )


def fit_one(registry, cell, values, record_meta, setting):
    phase, name, base, params, divisor = setting
    # Protect the shared parent even if a future estimator writes to its argument.
    x = values.copy()
    x.setflags(write=False)
    record = SeriesRecord(
        record_meta["record_id"],
        x,
        None,
        None,
        SourceType.SYNTHETIC,
        cell["family"],
        provenance=ProvenanceRecord(
            record_meta["record_id"], None, "calibration", "", seed=record_meta["resampling_seed"]
        ),
    )
    spec = EstimatorSpec(
        name, "calibration", "hurst_scaling_proxy", (), True, True, parameter_schema=params
    )
    start = time.perf_counter()
    try:
        estimate = registry.get(base)(spec).fit(record)
        result = {
            "point": estimate.point,
            "valid": estimate.valid,
            "ci_low": estimate.ci_low,
            "ci_high": estimate.ci_high,
            "bootstrap_cis": estimate.bootstrap_cis,
            "failure_reason": estimate.failure_reason,
            "warnings": estimate.warnings,
            "estimator_version": estimate.estimator_version,
            "diagnostics": dict(estimate.diagnostics),
        }
    except Exception as exc:  # Preserve every failed job; do not abort an experiment.
        result = {
            "point": None,
            "valid": False,
            "ci_low": None,
            "ci_high": None,
            "bootstrap_cis": [],
            "failure_reason": f"exception:{type(exc).__name__}:{exc}",
            "warnings": [],
            "estimator_version": None,
            "diagnostics": {},
        }
    return finite_json(
        {
            "record_id": record.record_id,
            "input_sha256": record_meta["sha256"],
            "cell": cell_id(cell),
            **cell,
            "repetition": record_meta["repetition"],
            "H_target": 0.5
            if cell["family"] == "AR1"
            else cell["parameter"] + (0.5 if cell["family"] == "ARFIMA" else 0),
            "target_interpretation": "asymptotic_short_memory_control"
            if cell["family"] == "AR1"
            else "model_memory_parameter",
            "phase": phase,
            "method": name,
            "base_method": base,
            "block_divisor": divisor,
            "parameters": params,
            "elapsed_seconds": time.perf_counter() - start,
            **result,
        }
    )


def summarize(rows, config):
    frame = pd.DataFrame(rows)
    summaries = []
    for keys, group in frame.groupby(["cell", "phase", "method", "block_divisor"], dropna=False):
        cell, phase, method, divisor = keys
        target = float(group.H_target.iloc[0])
        points = pd.to_numeric(group.point, errors="coerce")
        valid = group.valid & np.isfinite(points)
        lo = pd.to_numeric(group.ci_low, errors="coerce")
        hi = pd.to_numeric(group.ci_high, errors="coerce")
        # Endpoints alone do not prove the interval has the requested nominal level.
        labelled = group.bootstrap_cis.map(
            lambda intervals: any(
                len(ci) == 3
                and ci[0] is not None
                and abs(ci[0] - config["nominal"]) < 1e-9
                and ci[1] is not None
                and ci[2] is not None
                for ci in intervals
            )
        )
        available = valid & labelled & np.isfinite(lo) & np.isfinite(hi) & (lo <= hi)
        hits = int((available & (lo <= target) & (hi >= target)).sum())
        total, count = len(group), int(available.sum())
        lower, upper = wilson(hits, count)
        errors = points[valid] - target
        summary = {
            "cell": cell,
            "family": group.family.iloc[0],
            "parameter": group.parameter.iloc[0],
            "n": int(group.n.iloc[0]),
            "H_target": target,
            "phase": phase,
            "method": method,
            "block_divisor": None if pd.isna(divisor) else int(divisor),
            "block_length": group.parameters.iloc[0].get("bootstrap_block_len")
            if phase == "ci"
            else None,
            "n_attempted": total,
            "n_valid": int(valid.sum()),
            "n_invalid": int((~valid).sum()),
            "mean_H": points[valid].mean(),
            "bias": errors.mean(),
            "mae": errors.abs().mean(),
            "rmse": np.sqrt((errors**2).mean()),
            "mean_mcse": points[valid].std(ddof=1) / np.sqrt(valid.sum())
            if valid.sum() > 1
            else None,
            "outside_nominal_range": int((valid & ((points <= 0) | (points >= 1))).sum()),
            "point_exceeds_06": int((valid & (points >= 0.6)).sum()),
            "n_available": count if phase == "ci" else None,
            "ci_availability": count / total if phase == "ci" else None,
            "n_covered": hits if phase == "ci" else None,
            "conditional_coverage": hits / count if count else None,
            "coverage_wilson_low": lower,
            "coverage_wilson_high": upper,
            "covered_per_attempt": hits / total if phase == "ci" else None,
            "mean_width": (hi[available] - lo[available]).mean() if count else None,
            "nominal": config["nominal"] if phase == "ci" else None,
            "seconds_per_fit": group.elapsed_seconds.mean(),
            "bootstrap_accounting_missing_fits": sum(
                not all(k in d for k in COUNTERS) for d in group.diagnostics
            )
            if phase == "ci"
            else 0,
        }
        for counter in COUNTERS:
            summary[counter] = sum(d.get(counter, 0) for d in group.diagnostics)
        summaries.append(finite_json(summary))
    return pd.DataFrame(summaries)


def export_results(output, connection, config, expected, full_expected, pool_index, complete):
    summaries, total, fit_seconds = [], 0, 0.0
    with (output / "estimates.jsonl.tmp").open("w", encoding="utf-8") as handle:
        cursor = connection.execute(
            "SELECT cell, payload, checksum FROM fits ORDER BY cell, job_id"
        )
        for _, cell_rows in groupby(cursor, key=lambda entry: entry[0]):
            rows = []
            for _, payload, checksum in cell_rows:
                row = json.loads(payload)
                if digest(row) != checksum:
                    raise ValueError(
                        "Checkpoint checksum mismatch; scientific results were altered."
                    )
                rows.append(row)
                total += 1
                fit_seconds += row["elapsed_seconds"]
                handle.write(payload + "\n")
            summaries.append(summarize(rows, config))
    (output / "estimates.jsonl.tmp").replace(output / "estimates.jsonl")
    summary = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    summary.to_csv(output / "summary.csv", index=False)
    pd.DataFrame(pool_index).to_csv(output / "input_index.csv", index=False)
    if not summary.empty:
        timing = summary[
            ["cell", "phase", "method", "block_divisor", "n_attempted", "seconds_per_fit"]
        ].copy()
        timing["projected_full_cell_seconds"] = timing.seconds_per_fit * config["repetitions"]
        timing.to_csv(output / "timing.csv", index=False)
    atomic_json(
        output / "progress.json",
        {
            "complete": complete,
            "completed_fits": total,
            "actual_workload": expected,
            "full_development_workload": full_expected,
            "observed_fit_seconds": fit_seconds,
            "projected_full_fit_hours": float(
                summary.seconds_per_fit.sum() * config["repetitions"] / 3600
            )
            if complete
            else None,
            "timing_limit": "Single-process measured fit time; excludes generation, disk/export overhead and contention. A small cost sample is not coverage evidence.",
            "artifact_sha256": {
                p.name: file_hash(p) for p in output.iterdir() if p.suffix in {".csv", ".jsonl"}
            },
        },
    )


def run(config, output, *, profile_repetitions=None, max_new_fits=None, roster=None):
    validate_config(config)
    roster = configurations(ROOT) if roster is None else roster
    repetitions = config["repetitions"] if profile_repetitions is None else profile_repetitions
    if not 1 <= repetitions <= config["repetitions"]:
        raise ValueError("Profile repetitions must be between 1 and the planned repetitions.")
    if max_new_fits is not None and max_new_fits < 1:
        raise ValueError("max-new-fits must be positive.")
    output.mkdir(parents=True, exist_ok=True)
    expected = workload(config, roster, repetitions)
    full_expected = workload(config, roster, config["repetitions"])
    with exclusive_run(output):
        initialize(
            output, run_identity(config, roster, repetitions, profile_repetitions is not None)
        )
        with contextlib.closing(sqlite3.connect(output / "checkpoints.sqlite")) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS fits (job_id TEXT PRIMARY KEY, cell TEXT NOT NULL, payload TEXT NOT NULL, checksum TEXT NOT NULL)"
            )
            registry = build_default_estimator_registry()
            done = set()
            for job_id, payload, checksum in connection.execute(
                "SELECT job_id, payload, checksum FROM fits"
            ):
                if digest(json.loads(payload)) != checksum:
                    raise ValueError(
                        "Checkpoint checksum mismatch; scientific results were altered."
                    )
                done.add(job_id)
            pool_index, new_fits, expected_ids = [], 0, set()
            stopped = False
            for cell in cells(config):
                # Even finished cells are verified on resume.
                values, metadata = input_pool(output, config, cell, repetitions)
                for record_meta in metadata["records"]:
                    pool_index.append({"cell": cell_id(cell), **cell, **record_meta})
                for r, x in enumerate(values):
                    for setting in fit_settings(config, roster, cell["n"]):
                        job_id = digest([metadata["records"][r]["record_id"], setting])
                        expected_ids.add(job_id)
                        if job_id in done:
                            continue
                        if max_new_fits is not None and new_fits >= max_new_fits:
                            stopped = True
                            break
                        row = fit_one(registry, cell, x, metadata["records"][r], setting)
                        with connection:
                            connection.execute(
                                "INSERT INTO fits VALUES (?, ?, ?, ?)",
                                (job_id, cell_id(cell), canonical(row), digest(row)),
                            )
                        new_fits += 1
                    if stopped:
                        break
                print(f"{cell_id(cell)}: {len(done) + new_fits} saved fits", flush=True)
                if stopped:
                    break
            total_expected = expected["point_fits"] + expected["ci_fits"]
            complete = not stopped and len(done) + new_fits == total_expected
            if not stopped and not done <= expected_ids:
                raise ValueError("Checkpoint contains jobs outside the declared design.")
            export_results(
                output, connection, config, expected, full_expected, pool_index, complete
            )
            return {"complete": complete, "new_fits": new_fits, "total_fits": len(done) + new_fits}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--profile-repetitions", type=int)
    parser.add_argument(
        "--max-new-fits", type=int, help="Stop cleanly after this many additional fits."
    )
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_config(config)
    roster = configurations(ROOT)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "full": workload(config, roster, config["repetitions"]),
                    "requested": workload(
                        config, roster, args.profile_repetitions or config["repetitions"]
                    ),
                    "status": "development_only; interval eligibility remains unvalidated",
                },
                indent=2,
            )
        )
    elif args.output is None:
        parser.error("--output is required unless --dry-run is used")
    else:
        print(
            json.dumps(
                run(
                    config,
                    args.output.resolve(),
                    profile_repetitions=args.profile_repetitions,
                    max_new_fits=args.max_new_fits,
                    roster=roster,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
