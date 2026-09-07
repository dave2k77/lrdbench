"""Bounded cellwise analysis and canonical exports for a complete fixed run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from . import confirmation_analysis as analysis
    from . import run_confirmation as engine
except ImportError:
    import confirmation_analysis as analysis
    import run_confirmation as engine

shared, store = engine.shared, engine.store


def read_run(output, *, require_complete=True):
    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    identity = run["identity"]
    if run["identity_sha256"] != shared.digest(identity):
        raise ValueError("Run identity checksum mismatch.")
    frozen = engine.load_lock()
    rehearsal = identity["mode"] == "executor_rehearsal_never_confirmation"
    if identity != engine.run_identity(frozen, rehearsal=rehearsal):
        raise ValueError("Analysis sources/environment do not match the execution snapshot.")
    specs = engine.chunk_plan(frozen, rehearsal)
    expected = {s["id"] for s in specs}
    actual = (
        {p.name for p in (output / "chunks").iterdir()} if (output / "chunks").exists() else set()
    )
    if actual - expected or (require_complete and actual != expected):
        raise ValueError("Scientific analysis requires every declared chunk, with no extras.")
    receipts = {
        s["id"]: store.verify(output / "chunks" / s["id"], run["identity_sha256"], s["id"])
        for s in specs
        if s["id"] in actual
    }
    return run, frozen, specs, receipts


def load_cell(output, row, specs, identity_sha):
    """One cell in memory; missing attempts/duplicate rows are archive errors.

    Failed/invalid attempts remain present and map to NaN in the point tensor.
    Interval endpoints remain aligned even when their availability flag is false.
    """
    frozen = engine.load_lock()
    settings = [s for s in frozen["design"]["settings"] if s["n"] == row["n"]]
    methods = [s["method"] for s in settings]
    conditions = (
        ["clean", *[c["id"] for c in frozen["design"]["conditions"]]]
        if row["stress_parents"]
        else ["clean"]
    )
    shape = (row["accuracy_parents"], len(conditions), len(methods))
    points, runtimes = np.full(shape, np.nan), np.full(shape, np.nan)
    seen = np.zeros(shape, bool)
    labels = [
        (method, candidate)
        for method in engine.intervals.METHODS
        for candidate in (
            *engine.intervals.CANDIDATES,
            *(("gph_normal_raw",) if method == "GPH::narrow_band" else ()),
        )
    ]
    ci_shape = (row["interval_parents"], len(labels))
    low, high, available, ci_seen = (
        np.full(ci_shape, np.nan),
        np.full(ci_shape, np.nan),
        np.zeros(ci_shape, bool),
        np.zeros(ci_shape, bool),
    )
    boundaries, model_available = (
        np.zeros(row["interval_parents"], bool),
        np.zeros(row["interval_parents"], bool),
    )
    parent_ids = [f"{row['cell']}_r{r}" for r in range(row["accuracy_parents"])]
    failures = []
    methods_index, conditions_index, label_index = (
        {v: i for i, v in enumerate(methods)},
        {v: i for i, v in enumerate(conditions)},
        {v: i for i, v in enumerate(labels)},
    )
    for spec in specs:
        if spec["cell"]["cell"] != row["cell"]:
            continue
        folder = output / "chunks" / spec["id"]
        store.verify(folder, identity_sha, spec["id"])
        metadata = store.read_json_gz(folder / "metadata.json.gz")
        if metadata["chunk"] != spec or metadata["run_identity_sha256"] != identity_sha:
            raise ValueError("Chunk metadata identity mismatch.")
        signal_meta = {s["record_id"]: s for s in metadata["signals"]}
        if len(signal_meta) != len(metadata["signals"]):
            raise ValueError("Duplicate signal identifiers.")
        for fit in store.read_points(folder):
            r = fit["repetition"]
            if (
                not spec["start"] <= r < spec["stop"]
                or fit["cell"] != row["cell"]
                or fit["parent_id"] != parent_ids[r]
                or fit["run_identity_sha256"] != identity_sha
            ):
                raise ValueError("Point fit does not belong to its run/parent/cell.")
            j, k = conditions_index[fit["condition"]], methods_index[fit["method"]]
            signal = signal_meta[fit["record_id"]]
            if (
                seen[r, j, k]
                or fit["input_sha256"] != signal["sha256"]
                or fit["parameters"] != settings[k]["params"]
                or fit["H_target"] != row["H_target"]
                or signal["parent_id"] != fit["parent_id"]
                or signal["condition"] != fit["condition"]
            ):
                raise ValueError("Duplicate fit or mismatched signal/settings/target.")
            seen[r, j, k] = True
            runtimes[r, j, k] = fit["elapsed_seconds"]
            if not np.isfinite(runtimes[r, j, k]) or runtimes[r, j, k] < 0:
                raise ValueError("Invalid runtime ledger.")
            if fit["valid"]:
                if fit["point"] is None or not np.isfinite(fit["point"]):
                    raise ValueError("Valid point flag contradicts its value.")
                points[r, j, k] = fit["point"]
            else:
                failures.append(
                    {
                        "parent_id": fit["parent_id"],
                        "record_id": fit["record_id"],
                        "method": fit["method"],
                        "condition": fit["condition"],
                        "reason": fit["failure_reason"],
                    }
                )
        for entry in metadata["interval_records"]:
            r, result = entry["repetition"], entry["result"]
            if (
                not spec["start"] <= r < min(spec["stop"], row["interval_parents"])
                or entry["parent_id"] != parent_ids[r]
                or entry["input_sha256"] != signal_meta[parent_ids[r]]["sha256"]
            ):
                raise ValueError("Interval fit does not belong to its selected clean parent.")
            model_available[r] = result["model"] is not None
            boundaries[r] = bool(result["model"] and result["model"]["boundary_hit"])
            for ci in result["intervals"]:
                j = label_index[ci["method"], ci["candidate"]]
                if (
                    ci_seen[r, j]
                    or ci["draws"] != frozen["design"]["protocol"]["intervals"]["bootstrap_draws"]
                    or ci["nominal"] != 0.95
                ):
                    raise ValueError("Duplicate interval or changed interval specification.")
                ci_seen[r, j] = True
                low[r, j], high[r, j], available[r, j] = (
                    ci["ci_low"],
                    ci["ci_high"],
                    ci["available"],
                )
    expected = np.zeros(shape, bool)
    expected[:, 0, :] = True
    expected[: row["stress_parents"], :, :] = True
    if not np.array_equal(seen, expected) or not ci_seen.all():
        raise ValueError("Saved attempt grid is incomplete or contains undeclared fits.")
    return {
        "points": points,
        "runtimes": runtimes,
        "methods": methods,
        "conditions": conditions,
        "low": low,
        "high": high,
        "available": available,
        "labels": labels,
        "model_boundary": boundaries,
        "model_available": model_available,
        "parent_ids": parent_ids,
        "failures": failures,
    }


def write_group(folder, result, accounting, context):
    folder.mkdir(parents=True, exist_ok=True)
    rows = [{**context, **r} for r in result.rows]
    frame = pd.DataFrame(shared.finite_json(rows))
    temporary = folder / "summary.csv.tmp"
    frame.to_csv(temporary, index=False, lineterminator="\n")
    temporary.replace(folder / "summary.csv")
    temporary = folder / "draws.npz.tmp"
    store.write_arrays(temporary, values=result.matrix())
    temporary.replace(folder / "draws.npz")
    store.write_json_gz(folder / "support.json.gz", accounting)
    files = {
        name: shared.file_hash(folder / name)
        for name in ("summary.csv", "draws.npz", "support.json.gz")
    }
    store.atomic_json(folder / "receipt.json", {"context": context, "sha256": files})


def read_group(folder):
    receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
    if any(shared.file_hash(folder / name) != sha for name, sha in receipt["sha256"].items()):
        raise ValueError("Summary archive checksum mismatch.")
    frame = pd.read_csv(folder / "summary.csv", float_precision="round_trip", keep_default_na=False)
    # Explicit conversions keep empty contrast identifiers intact and restore
    # unavailable numbers as NaN without guessing dtypes of any seed column.
    numeric = {
        "value",
        "ci_low",
        "ci_high",
        "mcse",
        "bootstrap_se",
        "parents_attempted",
        "parents_used",
        "parents_excluded",
        "successes",
        "denominator",
        "requested_draws",
        "used_draws",
        "invalid_draws",
    }
    for column in numeric & set(frame.columns):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    with np.load(folder / "draws.npz", allow_pickle=False) as arrays:
        values = arrays["values"]
    if values.shape[1] != len(frame):
        raise ValueError("Summary labels and draws are misaligned.")
    result = analysis.Summary(values.shape[0])
    result.rows = frame.to_dict("records")
    result.draws = [values[:, j] for j in range(values.shape[1])]
    return result


def summarize(output):
    output = Path(output).resolve()
    with shared.exclusive_run(output):
        run, frozen, specs, receipts = read_run(output)
        identity_sha = run["identity_sha256"]
        specification = {
            "run_identity_sha256": identity_sha,
            "receipts_sha256": shared.digest(receipts),
            "analysis_schema": 1,
        }
        folder = output / "summaries"
        marker = folder / "complete.json"
        if marker.exists():
            completed = json.loads(marker.read_text(encoding="utf-8"))
            if completed["specification"] != specification or any(
                shared.file_hash(folder / n) != h for n, h in completed["files"].items()
            ):
                raise ValueError("Completed summary identity or checksum mismatch.")
            return completed
        protocol = frozen["design"]["protocol"]
        config = {
            "draws": protocol["summaries"]["bootstrap_draws"],
            "seed": protocol["summaries"]["seed"],
        }
        rows = engine.cell_plan(frozen, run["identity"]["mode"] != "confirmation")
        domain_paths = {}
        group_paths = []
        for row in rows:
            engine.disk_check(output)
            data = load_cell(output, row, specs, identity_sha)
            for scope in ("accuracy", "stress", "intervals"):
                if (
                    scope == "stress"
                    and not row["stress_parents"]
                    or scope == "intervals"
                    and not row["interval_parents"]
                ):
                    continue
                key = f"{identity_sha}:{row['cell']}:{scope}"
                if scope == "intervals":
                    result, accounting = analysis.interval_summaries(
                        data["low"],
                        data["high"],
                        data["available"],
                        target=row["H_target"],
                        labels=data["labels"],
                        key=key,
                        model_boundary=data["model_boundary"],
                        model_available=data["model_available"],
                        **config,
                    )
                else:
                    count = (
                        row["accuracy_parents"] if scope == "accuracy" else row["stress_parents"]
                    )
                    end = 1 if scope == "accuracy" else len(data["conditions"])
                    result, accounting = analysis.point_summaries(
                        data["points"][:count, :end],
                        data["runtimes"][:count, :end],
                        target=row["H_target"],
                        methods=data["methods"],
                        conditions=data["conditions"][:end],
                        key=key,
                        floor=protocol["summaries"]["denominator_floor"],
                        **config,
                    )
                accounting.update(
                    parent_id_order=data["parent_ids"][
                        : row["interval_parents"] if scope == "intervals" else count
                    ],
                    run_identity_sha256=identity_sha,
                )
                if scope != "intervals":
                    accounting["failure_reasons"] = [
                        f
                        for f in data["failures"]
                        if f["parent_id"] in set(accounting["parent_id_order"])
                        and f["condition"] in data["conditions"][:end]
                    ]
                group = folder / f"{scope}__{row['cell']}"
                context = {
                    "run_identity_sha256": identity_sha,
                    "scope": scope,
                    "cell": row["cell"],
                    "domain": row["family"],
                    "parameter": row["parameter"],
                    "n": row["n"],
                    "H_target": row["H_target"],
                    "interval_role": row["interval_role"] if scope == "intervals" else "none",
                }
                write_group(group, result, accounting, context)
                group_paths.append(group)
                # Keep interval core and length sensitivity as separate designs.
                domain = (
                    scope,
                    row["family"],
                    row["interval_role"] if scope == "intervals" else "all_lengths",
                )
                domain_paths.setdefault(domain, []).append(group)
                del result
            print(f"Analyzed {row['cell']}", flush=True)
        for (scope, domain, role), paths in domain_paths.items():
            result = analysis.aggregate_groups(
                (read_group(p) for p in paths), floor=protocol["summaries"]["denominator_floor"]
            )
            group = folder / f"{scope}__domain_{domain}_{role}"
            write_group(
                group,
                result,
                {
                    "declared_cells": [p.name for p in paths],
                    "fixed_cell_weight": 1 / len(paths),
                    "no_renormalization_for_unavailable_cells": True,
                },
                {
                    "run_identity_sha256": identity_sha,
                    "scope": scope,
                    "cell": "domain_aggregate",
                    "domain": domain,
                    "interval_role": role,
                },
            )
            group_paths.append(group)
            del result
        frames = [
            pd.read_csv(p / "summary.csv", float_precision="round_trip", keep_default_na=False)
            for p in group_paths
        ]
        pd.concat(frames, ignore_index=True).to_csv(
            folder / "canonical_summary.csv", index=False, lineterminator="\n"
        )
        completed = {
            "specification": specification,
            "mode": run["identity"]["mode"],
            "groups": len(group_paths),
            "summary_rows": sum(len(f) for f in frames),
            "files": {
                p.relative_to(folder).as_posix(): shared.file_hash(p)
                for p in folder.rglob("*")
                if p.is_file() and p != marker
            },
            "confirmation_parents": 0
            if run["identity"]["mode"] != "confirmation"
            else sum(r["accuracy_parents"] for r in rows),
        }
        store.atomic_json(marker, completed)
        return completed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, indent=2))
