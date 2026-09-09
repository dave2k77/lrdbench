"""Audit rehearsal equivalence, storage round trips, and the scientific design lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from . import profile_confirmation as profile
except ImportError:
    import profile_confirmation as profile

design, shared = profile.design, profile.shared


def records(folder):
    result = {}
    for path in sorted((folder / "records").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["sha256"] == shared.digest(payload["record"])
        record = payload["record"]
        assert record["record_id"] not in result
        result[record["record_id"]] = record
    return result


def compare(old, new):
    def strip(rows):
        return [{k: v for k, v in row.items() if k != "elapsed_seconds"} for row in rows]

    assert old.keys() == new.keys()
    maximum, endpoints, attempts, boundary_parents = 0.0, 0, 0, 0
    for name, record in new.items():
        reference = old[name]
        assert record["input_sha256"] == reference["input_sha256"]
        for field in ("clean_points", "stress_points"):
            assert strip(record[field]) == strip(reference[field])
        if any(
            r["model"] is not None and r["model"]["boundary_hit"]
            for r in record["interval_records"].values()
        ):
            boundary_parents += 1
        for stream, run in record["interval_records"].items():
            prior = reference["interval_records"][stream]
            assert run["points"] == prior["points"] and run["model"] == prior["model"]
            for pool, payload in run["pools"].items():
                original = prior["pools"][pool]
                assert payload["seed"] == original["seed"]
                assert payload["generated_records"] == original["generated_records"]
                assert payload["accounting"] == original["accounting"]
                for key, values in payload["statistics"].items():
                    a, b = (
                        np.asarray(values, dtype=float),
                        np.asarray(original["statistics"][key], dtype=float),
                    )
                    np.testing.assert_allclose(a, b, rtol=2e-12, atol=2e-13, equal_nan=True)
                    maximum = max(maximum, float(np.nanmax(np.abs(a - b))))
                    counts = payload["accounting"][key]
                    assert (
                        counts["attempted"] == counts["used"] + counts["invalid"] + counts["failed"]
                    )
                    attempts += counts["attempted"]
            for row, prior_row in zip(run["intervals"], prior["intervals"], strict=True):
                assert row["available"] == prior_row["available"]
                np.testing.assert_allclose(
                    [row["ci_low"], row["ci_high"]],
                    [prior_row["ci_low"], prior_row["ci_high"]],
                    rtol=2e-12,
                    atol=2e-13,
                )
                if row["pool"] is not None:
                    key = row["treatment"] + ":" + row["method"]
                    values = run["pools"][row["pool"]]["statistics"][key][: row["draws"]]
                    low, high = np.quantile(values, [0.025, 0.975])
                    if row["candidate"].endswith("basic"):
                        center = row["point"] if row["pool"] == "cbc" else run["model"]["H"]
                        low, high = row["point"] + center - high, row["point"] + center - low
                    np.testing.assert_allclose(
                        [row["ci_low"], row["ci_high"]], [low, high], atol=2e-13
                    )
                endpoints += 2
    return {
        "independent_rehearsal_parents": len(new),
        "compared_statistic_attempts": attempts,
        "max_absolute_scalar_batch_difference": maximum,
        "compared_interval_endpoints": endpoints,
        "distinct_rehearsal_parents_with_model_boundary_hits": boundary_parents,
    }


def storage_check(protocol, output, data):
    rows = []
    arrays = {}
    for record in data.values():
        for role, field in (("clean", "clean_points"), ("stressed", "stress_points")):
            for row in record[field]:
                flat = {"role": role, **row}
                for name in ("parameters", "warnings", "diagnostics"):
                    flat[name + "_json"] = shared.canonical(flat.pop(name))
                rows.append(flat)
        for stream, run in record["interval_records"].items():
            for pool, payload in run["pools"].items():
                for key, values in payload["statistics"].items():
                    name = shared.digest([record["record_id"], stream, pool, key])
                    arrays[name] = np.asarray(values, dtype="<f8")
    frame = pd.DataFrame(rows)
    path = output / "rehearsal_points.csv.gz"
    frame.to_csv(
        path,
        index=False,
        lineterminator="\n",
        compression={"method": "gzip", "compresslevel": 6, "mtime": 0},
    )
    loaded = pd.read_csv(path, float_precision="round_trip", keep_default_na=False)
    for column in frame:
        if pd.api.types.is_numeric_dtype(frame[column]):
            np.testing.assert_array_equal(frame[column].to_numpy(), loaded[column].to_numpy())
        else:
            assert (
                frame[column].fillna("").astype(str).tolist() == loaded[column].astype(str).tolist()
            )
    draw_path = output / "rehearsal_statistic_draws.npz"
    np.savez_compressed(draw_path, **arrays)
    with np.load(draw_path, allow_pickle=False) as bundle:
        for name, values in arrays.items():
            np.testing.assert_array_equal(bundle[name], values)
    w = design.workload(protocol)
    points_bytes = path.stat().st_size / len(frame) * w["total_point_fits"]
    draws_bytes = (
        draw_path.stat().st_size
        / sum(map(len, arrays.values()))
        * w["bootstrap_statistic_attempts"]
    )
    signal_bytes = w["raw_clean_signal_bytes"] + w["raw_descendant_signal_bytes"]
    estimated = points_bytes + draws_bytes + signal_bytes
    free = shutil.disk_usage(output).free
    result = {
        "lossless_gzip_csv_point_round_trip": True,
        "lossless_npz_draw_round_trip": True,
        "rehearsal_point_rows": len(frame),
        "rehearsal_csv_gzip_bytes": path.stat().st_size,
        "rehearsal_statistic_values": sum(map(len, arrays.values())),
        "rehearsal_npz_bytes": draw_path.stat().st_size,
        "projected_point_archive_bytes": points_bytes,
        "projected_draw_archive_bytes": draws_bytes,
        "raw_signal_bytes_conservative": signal_bytes,
        "projected_archive_bytes": estimated,
        "planning_bytes_with_2x_allowance_and_10GiB_free_reserve": 2 * estimated + 10 * 1024**3,
        "observed_free_bytes": free,
        "within_planning_disk_budget": free > 2 * estimated + 10 * 1024**3,
        "limit": "A sampled storage projection. Full-run summary exports and duplication must remain bounded; recheck immediately before execution. Raw bootstrap signals are reconstructed from seeds and are not all retained.",
    }
    shared.atomic_json(output / "storage_check.json", result)
    return result


def verify(scalar, output, archive):
    before = {p.name: shared.file_hash(p) for p in (output / "records").glob("*.json")}
    recorded = json.loads((output / "run.json").read_text(encoding="utf-8"))["identity"]
    protocol = design.load_protocol()
    assert protocol == recorded["planned_protocol"]
    assert all(
        shared.file_hash(shared.ROOT / path) == sha
        for path, sha in recorded["source_sha256"].items()
    )
    # Resume must reuse every completed rehearsal checkpoint without rewriting it.
    profile.run(protocol, output)
    assert before == {p.name: shared.file_hash(p) for p in (output / "records").glob("*.json")}
    old, new = records(scalar), records(output)
    comparison = compare(old, new)
    assert (
        comparison["compared_statistic_attempts"]
        == profile.profile_workload(protocol)["bootstrap_statistic_attempts"]
    )
    for folder in (scalar, output):
        identity = json.loads((folder / "run.json").read_text(encoding="utf-8"))["identity"]
        config = identity["config"]
        assert config["seed_namespace"] == protocol["randomness"]["rehearsal_namespace"]
        for cell in shared.cells(config):
            values, metadata = shared.input_pool(
                folder, config, cell, profile.PROFILE["parents_per_cell"]
            )
            for x, row in zip(values, metadata["records"], strict=True):
                assert shared.array_hash(x) == new[row["record_id"]]["input_sha256"]
    with zipfile.ZipFile(scalar / "executed_sources.zip") as bundle:
        scalar_identity = json.loads((scalar / "run.json").read_text(encoding="utf-8"))["identity"]
        assert all(
            hashlib.sha256(bundle.read(name.replace("\\", "/"))).hexdigest() == sha
            for name, sha in scalar_identity["source_sha256"].items()
        )
    storage = storage_check(protocol, output, new)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["endpoint_stability_rule_passed"]
    assert (
        summary["planning_hours_with_2x_allowance"]
        <= protocol["execution"]["provisional_budget_hours"]
    )
    assert storage["within_planning_disk_budget"]
    compiled = design.compile_protocol(protocol, archive)
    suites = [
        suite
        for name in ("focused-tests.xml", "regression-tests.xml")
        for suite in ET.parse(output / name).getroot().iter("testsuite")
    ]
    tests = {
        key: sum(int(s.attrib.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    assert tests["failures"] == tests["errors"] == 0
    tests["passed"] = tests["tests"] - tests["skipped"]
    baseline = json.loads(Path(__file__).with_name("baseline.json").read_text(encoding="utf-8"))
    assert all(
        shared.file_hash(shared.ROOT / row["path"]) == row["sha256"]
        for row in baseline["historical_files"]
    )
    names = [
        "run.json",
        "summary.json",
        "costs.csv",
        "interval_costs.csv",
        "input_index.csv",
        "interval_endpoints.csv",
        "endpoint_stability.csv",
        "endpoint_stability_summary.csv",
        "storage_check.json",
        "focused-tests.xml",
        "regression-tests.xml",
    ]
    for name in names:
        shutil.copyfile(output / name, archive / ("rehearsal_" + name))
    shutil.copyfile(scalar / "summary.json", archive / "scalar_rehearsal_summary.json")
    snapshot = dict(recorded["source_sha256"])
    for path in (Path(__file__), shared.ROOT / "tests/unit/test_confirmation_protocol.py"):
        snapshot[str(path.relative_to(shared.ROOT))] = shared.file_hash(path)
    with zipfile.ZipFile(archive / "executed_sources.zip", "w") as bundle:
        for name, sha in sorted(snapshot.items()):
            payload = (shared.ROOT / name).read_bytes()
            assert hashlib.sha256(payload).hexdigest() == sha
            entry = zipfile.ZipInfo(name.replace("\\", "/"), date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            bundle.writestr(entry, payload)
    verification = {
        "status": "scientific_design_locked_not_a_confirmation_run",
        "scientific_design_sha256": compiled["scientific_design_sha256"],
        **comparison,
        "rehearsal_resume_rewrote_checkpoints": False,
        "all_rehearsal_inputs_verified": True,
        "source_snapshot_files": len(snapshot),
        "snapshot_source_sha256": snapshot,
        "confirmation_inputs_generated": 0,
        "tests": tests,
        "historical_hashes_unchanged": len(baseline["historical_files"]),
        "storage_planning_check_passed": storage["within_planning_disk_budget"],
        "raw_rehearsal_record_sha256": before,
        "raw_rehearsal_csv_gzip_sha256": shared.file_hash(output / "rehearsal_points.csv.gz"),
        "raw_rehearsal_draw_npz_sha256": shared.file_hash(output / "rehearsal_statistic_draws.npz"),
        "compact_artifact_sha256": {
            p.name: shared.file_hash(p) for p in archive.iterdir() if p.name != "verification.json"
        },
    }
    (archive / "verification.json").write_text(
        json.dumps(verification, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "verification": comparison,
                "tests": tests,
                "scientific_design_sha256": compiled["scientific_design_sha256"],
                "projected_compute_hours": summary["projected_compute_hours"],
                "planning_hours": summary["planning_hours_with_2x_allowance"],
                "projected_storage_GiB": storage["projected_archive_bytes"] / 1024**3,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scalar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    verify(args.scalar.resolve(), args.output.resolve(), args.archive.resolve())
