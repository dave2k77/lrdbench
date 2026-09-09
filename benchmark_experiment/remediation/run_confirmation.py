"""Execute the immutable scientific design in bounded, recoverable research chunks."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import time
import zipfile
from dataclasses import asdict
from pathlib import Path

import numpy as np

from lrdbench.defaults import build_default_contamination_registry, build_default_estimator_registry

try:
    from . import compile_confirmation_protocol as design
    from . import confirmation_store as store
except ImportError:
    import compile_confirmation_protocol as design
    import confirmation_store as store

shared, stress, inputs, intervals = (
    design.shared,
    design.stress,
    design.stress_inputs,
    design.intervals,
)
HERE = Path(__file__).resolve().parent
LOCK = HERE / "protocol-v1/scientific_design_lock.json"
RELEASE = HERE / "execution-v1/release.json"
EXECUTION = {
    "schema_version": 1,
    "chunk_parents": 32,
    "workers": 1,
    "rehearsal_parents_per_cell": 2,
    "minimum_free_bytes": 10 * 1024**3,
    "initial_required_free_bytes": 30 * 1024**3,
    "archive": "atomic_directory_signals_npz_draws_npz_metadata_json_gz_points_jsonl_gz_v1",
    "summary_resampling": "within_cell_joint_parent_multinomial_counts_v1",
    "partial_results": "no_scientific_summaries_until_all_declared_chunks_complete",
}
STREAMS = [
    (pool, f"{treatment}:{method}")
    for pool in ("cbc", "fgn")
    for treatment in (("raw", "centered") if pool == "cbc" else ("centered",))
    for method in intervals.METHODS
]


def load_lock(path=LOCK):
    envelope = json.loads(Path(path).read_text(encoding="utf-8"))
    frozen = envelope["design"]
    if envelope["sha256"] != shared.digest(frozen):
        raise ValueError("Scientific lock checksum mismatch.")
    protocol = frozen["protocol"]
    design.validate(protocol)
    if protocol != design.load_protocol():
        raise ValueError("Protocol differs from the versioned scientific lock.")
    settings = [row for n in protocol["accuracy"]["lengths"] for row in design.point_settings(n)]
    registry = build_default_contamination_registry()
    conditions = [
        {**c, "version": registry.get(c["operator"]).version}
        for c in design.contamination_conditions(protocol)
    ]
    if (
        frozen["settings"] != settings
        or frozen["conditions"] != conditions
        or frozen["workload"] != design.workload(protocol)
    ):
        raise ValueError("Executed methods, operators or workload differ from the scientific lock.")
    return envelope


def source_paths():
    return sorted(
        {
            *shared.ROOT.joinpath("src/lrdbench").rglob("*.py"),
            *HERE.glob("*.py"),
            *shared.ROOT.joinpath("tests/unit").glob("test_confirmation*.py"),
            HERE / "estimator_eligibility.csv",
            HERE / "confirmation-protocol-v1.json",
            HERE / "environment-py314-win64.lock",
            LOCK,
        }
    )


def runtime_lock(frozen):
    env = shared.environment()
    normalized = {re.sub(r"[-_.]+", "-", k).lower(): v for k, v in env["packages"].items()}
    pins = re.findall(
        r"^([A-Za-z0-9_.-]+)==([^\s\\]+)",
        (HERE / "environment-py314-win64.lock").read_text(encoding="utf-8"),
        re.M,
    )
    if env["python"] != "3.14.5" or env["machine"].lower() not in {"amd64", "x86_64"}:
        raise ValueError("Use the validated Python 3.14.5 64-bit execution environment.")
    mismatches = [
        name
        for name, version in pins
        if normalized.get(re.sub(r"[-_.]+", "-", name).lower()) != version
    ]
    if mismatches:
        raise ValueError(f"Installed environment differs from pinned versions: {mismatches}")
    return {
        "scientific_design_sha256": frozen["sha256"],
        "execution": EXECUTION,
        "environment": env,
        "source_sha256": {
            p.relative_to(shared.ROOT).as_posix(): shared.file_hash(p) for p in source_paths()
        },
    }


def run_identity(frozen, *, rehearsal):
    runtime = runtime_lock(frozen)
    return {
        **runtime,
        "runtime_sha256": shared.digest(runtime),
        "mode": "executor_rehearsal_never_confirmation" if rehearsal else "confirmation",
        "config": design.data_config(frozen["design"]["protocol"], rehearsal=rehearsal),
    }


def check_release(identity, path=RELEASE):
    release = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        release.get("status") != "validated_for_fixed_confirmation"
        or release.get("runtime_sha256") != identity["runtime_sha256"]
    ):
        raise ValueError(
            "Production requires a validated release matching these exact sources/environment."
        )
    for name, sha in release["evidence_sha256"].items():
        evidence = store.inside(Path(path).parent, Path(path).parent / name)
        if shared.file_hash(evidence) != sha:
            raise ValueError("Execution release evidence checksum mismatch.")
    return release


def cell_plan(frozen, rehearsal=False):
    rows = design.cell_table(frozen["design"]["protocol"]).to_dict("records")
    if rehearsal:
        for row in rows:
            for key in ("accuracy_parents", "stress_parents", "interval_parents"):
                row[key] = min(row[key], EXECUTION["rehearsal_parents_per_cell"])
    return rows


def chunk_plan(frozen, rehearsal=False):
    return [
        {
            "id": f"{row['cell']}__r{start:05d}_{min(start + EXECUTION['chunk_parents'], row['accuracy_parents']):05d}",
            "cell": row,
            "start": start,
            "stop": min(start + EXECUTION["chunk_parents"], row["accuracy_parents"]),
        }
        for row in cell_plan(frozen, rehearsal)
        for start in range(0, row["accuracy_parents"], EXECUTION["chunk_parents"])
    ]


def disk_check(output, *, initial=False):
    path = output.resolve()
    while not path.exists():
        path = path.parent
    free = shutil.disk_usage(path).free
    required = EXECUTION["initial_required_free_bytes" if initial else "minimum_free_bytes"]
    if free < required:
        raise ValueError(f"Disk capacity check failed: {free} bytes free, {required} required.")
    return {"free_bytes": free, "required_bytes": required}


def initialize(output, identity):
    shared.initialize(output, identity)
    archive = output / "executed_sources.zip"
    if not archive.exists():
        temporary = archive.with_suffix(".tmp")
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, sha in identity["source_sha256"].items():
                if shared.file_hash(shared.ROOT / name) != sha:
                    raise ValueError("Source changed during initialization.")
                bundle.write(shared.ROOT / name, name)
        temporary.replace(archive)
    with zipfile.ZipFile(archive) as bundle:
        import hashlib

        if set(bundle.namelist()) != set(identity["source_sha256"]):
            raise ValueError("Source snapshot file set mismatch.")
        if any(
            hashlib.sha256(bundle.read(n)).hexdigest() != sha
            for n, sha in identity["source_sha256"].items()
        ):
            raise ValueError("Source snapshot checksum mismatch.")


def produce_chunk(output, spec, frozen, identity, registries, factor, *, fault=None):
    folder = store.begin(output, spec["id"])
    identity_sha = shared.digest(identity)
    protocol, config = frozen["design"]["protocol"], identity["config"]
    row = spec["cell"]
    cell = {key: row[key] for key in ("family", "parameter", "n")}
    settings = [s for s in frozen["design"]["settings"] if s["n"] == cell["n"]]
    conditions = frozen["design"]["conditions"]
    stress_config = {**config, "seed_namespace": protocol["randomness"]["stress_seed_namespace"]}
    if identity["mode"] != "confirmation":
        stress_config["seed_namespace"] += ":executor_rehearsal"
    registry, contamination_registry = registries
    signals, signal_meta, point_rows, ci_records, draws = [], [], [], [], []
    started = time.perf_counter()
    for r in range(spec["start"], spec["stop"]):
        x = shared.generate_record(config, cell, r, factor)
        x.setflags(write=False)
        parent_id = f"{row['cell']}_r{r}"
        meta = {
            "record_id": parent_id,
            "parent_id": parent_id,
            "condition": "clean",
            "repetition": r,
            "sha256": shared.array_hash(x),
            "input_seed": shared.record_seed(config, cell, r, "input"),
            "resampling_seed": shared.record_seed(config, cell, r, "resampling"),
        }
        parent = inputs.build_parent(cell, x, meta)
        record_values = [
            (
                x,
                {
                    **meta,
                    "contamination_seed": None,
                    "parent_sha256": meta["sha256"],
                    "transformation": None,
                    "provenance": asdict(parent.provenance),
                },
            )
        ]
        if r < row["stress_parents"]:
            for condition in conditions:
                child = inputs.apply_child(
                    stress_config, parent, meta, condition, contamination_registry
                )
                np.testing.assert_allclose(
                    child.values,
                    inputs.reference_values(x, condition, child.provenance.seed),
                    rtol=2e-14,
                    atol=2e-14,
                )
                record_values.append(
                    (
                        child.values,
                        {
                            **meta,
                            "record_id": child.record_id,
                            "condition": condition["id"],
                            "sha256": shared.array_hash(child.values),
                            "parent_sha256": meta["sha256"],
                            "contamination_seed": child.provenance.seed,
                            "transformation": asdict(child.contamination_history[0]),
                            "provenance": asdict(child.provenance),
                        },
                    )
                )
        for values, metadata in record_values:
            signals.append(values)
            signal_meta.append(metadata)
            for setting in settings:
                fit = stress.fit(registry, cell, values, metadata, setting)
                fit.update(
                    run_identity_sha256=identity_sha,
                    interval_status="separate_clean_interval_study",
                )
                point_rows.append(fit)
        if r < row["interval_parents"]:
            prefix = "confirmation" if identity["mode"] == "confirmation" else "executor_rehearsal"
            seeds = {
                pool: shared.record_seed(config, cell, r, f"{prefix}_{pool}")
                for pool in ("cbc", "fgn")
            }
            result = intervals.fit_record(
                x, seeds=seeds, draws=protocol["intervals"]["bootstrap_draws"]
            )
            aligned = np.full((len(STREAMS), protocol["intervals"]["bootstrap_draws"]), np.nan)
            for j, (pool, key) in enumerate(STREAMS):
                values = np.asarray(result["pools"][pool]["statistics"].pop(key), dtype=float)
                aligned[j, : len(values)] = values
                result["pools"][pool]["accounting"][key]["unattempted"] = aligned.shape[1] - len(
                    values
                )
            draws.append(aligned)
            ci_records.append(
                {
                    "parent_id": parent_id,
                    "repetition": r,
                    "input_sha256": meta["sha256"],
                    "result": result,
                }
            )
    store.write_arrays(folder / "signals.npz", values=np.asarray(signals))
    store.write_arrays(
        folder / "draws.npz",
        values=np.asarray(draws).reshape(
            len(draws), len(STREAMS), protocol["intervals"]["bootstrap_draws"]
        ),
    )
    store.write_points(folder / "points.jsonl.gz", point_rows)
    counts = {
        "parents": spec["stop"] - spec["start"],
        "descendants": len(signals) - (spec["stop"] - spec["start"]),
        "point_fits": len(point_rows),
        "valid_point_fits": sum(p["valid"] for p in point_rows),
        "interval_parents": len(ci_records),
        "interval_rows": sum(len(c["result"]["intervals"]) for c in ci_records),
        "physical_bootstrap_records": sum(
            p["generated_records"] for c in ci_records for p in c["result"]["pools"].values()
        ),
        "statistic_attempts": sum(
            a["attempted"]
            for c in ci_records
            for p in c["result"]["pools"].values()
            for a in p["accounting"].values()
        ),
    }
    store.write_json_gz(
        folder / "metadata.json.gz",
        {
            "run_identity_sha256": identity_sha,
            "chunk": spec,
            "signals": signal_meta,
            "interval_records": ci_records,
            "draw_stream_order": STREAMS,
            "elapsed_seconds": time.perf_counter() - started,
        },
    )
    return store.seal(output, spec["id"], identity_sha=identity_sha, counts=counts, fault=fault)


def run(output, *, rehearsal=False, max_new_chunks=None, fault=None):
    if max_new_chunks is not None and (type(max_new_chunks) is not int or max_new_chunks < 0):
        raise ValueError("Chunk execution limit must be a nonnegative integer.")
    frozen = load_lock()
    identity = run_identity(frozen, rehearsal=rehearsal)
    if not rehearsal:
        check_release(identity)
    output = Path(output).resolve()
    disk_check(output, initial=not (output / "run.json").exists())
    output.mkdir(parents=True, exist_ok=True)
    with shared.exclusive_run(output):
        initialize(output, identity)
        specs = chunk_plan(frozen, rehearsal)
        if (output / "chunks").exists() and {p.name for p in (output / "chunks").iterdir()} - {
            s["id"] for s in specs
        }:
            raise ValueError("Unexpected committed chunks outside the fixed design.")
        registries = (build_default_estimator_registry(), build_default_contamination_registry())
        receipts, new, factor_cell, factor = [], 0, None, None
        for spec in specs:
            folder = output / "chunks" / spec["id"]
            if folder.exists():
                receipt = store.verify(folder, shared.digest(identity), spec["id"])
            else:
                if max_new_chunks is not None and new >= max_new_chunks:
                    continue
                disk_check(output)
                if factor_cell != spec["cell"]["cell"]:
                    factor_cell = spec["cell"]["cell"]
                    factor = shared.covariance_factor(spec["cell"])
                receipt = produce_chunk(
                    output, spec, frozen, identity, registries, factor, fault=fault
                )
                new += 1
                print(f"Committed {spec['id']} ({new} new chunks)", flush=True)
            receipts.append(receipt)
        status = {
            "mode": identity["mode"],
            "run_identity_sha256": shared.digest(identity),
            "complete": len(receipts) == len(specs),
            "planned_chunks": len(specs),
            "completed_chunks": len(receipts),
            "counts": {
                k: sum(r["counts"][k] for r in receipts)
                for k in (receipts[0]["counts"] if receipts else [])
            },
            "scientific_design_sha256": frozen["sha256"],
            "confirmation_parents": sum(r["counts"]["parents"] for r in receipts)
            if not rehearsal
            else 0,
        }
        store.atomic_json(output / "status.json", status)
        return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rehearsal", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-new-chunks", type=int)
    args = parser.parse_args()
    if args.dry_run:
        frozen = load_lock()
        result = {
            "scientific_design_sha256": frozen["sha256"],
            "workload": frozen["design"]["workload"],
            "execution": EXECUTION,
            "mode": "rehearsal" if args.rehearsal else "confirmation",
            "chunks": len(chunk_plan(frozen, args.rehearsal)),
            "disk": disk_check(args.output, initial=True),
            "generated_inputs": 0,
        }
    else:
        result = run(args.output, rehearsal=args.rehearsal, max_new_chunks=args.max_new_chunks)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
