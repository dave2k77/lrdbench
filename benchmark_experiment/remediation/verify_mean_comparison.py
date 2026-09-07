"""Independently reconcile the mean-comparison bundle and archive compact evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from . import run_mean_comparison as runner
except ImportError:
    import run_mean_comparison as runner


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(output, archive):
    run = json.loads((output / "run.json").read_text())
    config = run["identity"]["config"]
    expected = runner.workload(config)
    # Completion resumption also checks source, environment, inputs and database.
    resumed = runner.run(config, output)
    assert resumed == {"new_records": 0, "completed_records": expected["independent_records"]}
    identity = run["identity"]
    assert all(file_hash(runner.shared.ROOT / p) == h for p, h in identity["source_sha256"].items())
    records = [json.loads(line) for line in (output / "records.jsonl").read_text().splitlines()]
    assert len(records) == len({r["record_id"] for r in records}) == expected["independent_records"]
    input_hashes, input_files = {}, {}
    for path in (output / "inputs").glob("*.npz"):
        input_files[path.name] = file_hash(path)
        with np.load(path, allow_pickle=False) as bundle:
            metadata = json.loads(str(bundle["metadata"]))
            for x, row in zip(bundle["values"], metadata["records"], strict=True):
                sha = hashlib.sha256(np.asarray(x, dtype="<f8").tobytes()).hexdigest()
                assert sha == row["sha256"]
                assert row["record_id"] not in input_hashes
                input_hashes[row["record_id"]] = sha
    assert len(input_hashes) == expected["independent_records"]
    assert all(input_hashes[r["record_id"]] == r["input_sha256"] for r in records)
    with sqlite3.connect(output / "checkpoints.sqlite") as connection:
        checksums = dict(connection.execute("SELECT record_id, checksum FROM records"))
    assert checksums == {r["record_id"]: runner.shared.digest(r) for r in records}
    first = json.loads((output / "first-four-checksums.json").read_text())
    assert len(first) == 4 and all(checksums[k] == h for k, h in first.items())

    reconstructed, draw_counts, physical = (
        [],
        dict.fromkeys(("attempted", "used", "invalid", "failed"), 0),
        0,
    )
    for record in records:
        for pool in record["draw_pools"].values():
            physical += pool["generated_records"]
            assert pool["requested_records"] == config["bootstrap_draws"]
            for key, counts in pool["accounting"].items():
                assert counts["attempted"] == counts["used"] + counts["invalid"] + counts["failed"]
                assert counts["attempted"] == pool["generated_records"]
                assert len(pool["statistics"][key]) == counts["used"]
                assert np.isfinite(pool["statistics"][key]).all()
                for name in draw_counts:
                    draw_counts[name] += counts[name]
        for interval in record["intervals"]:
            name, method, treatment = (
                interval["candidate"],
                interval["method"],
                interval["treatment"],
            )
            key = f"{treatment}:{method}"
            assert interval["point"] == record["points"][key]
            if interval["draw_pool_id"] is not None:
                pool_name = interval["draw_pool_id"].rsplit(":", 1)[1]
                draws = np.asarray(record["draw_pools"][pool_name]["statistics"][key])
                if len(draws) >= 5 and interval["point"] is not None:
                    endpoints = np.quantile(draws, [0.025, 0.975])
                    if name.endswith("basic"):
                        center = (
                            interval["point"]
                            if pool_name == "cbc"
                            else record["fitted_models"][pool_name]["H"]
                        )
                        endpoints = interval["point"] + center - endpoints[::-1]
                    np.testing.assert_allclose(
                        [interval["ci_low"], interval["ci_high"]], endpoints, atol=2e-14
                    )
            available = (
                interval["point"] is not None
                and interval["ci_low"] is not None
                and interval["ci_high"] is not None
            )
            if available:
                assert all(math.isfinite(interval[k]) for k in ("point", "ci_low", "ci_high"))
                assert interval["ci_low"] <= interval["ci_high"] and interval["nominal"] == 0.95
            reconstructed.append(
                {
                    "record_id": record["record_id"],
                    "cell": record["cell"],
                    "H_target": record["H_target"],
                    **interval,
                    "available": available,
                    "covered": bool(
                        available
                        and interval["ci_low"] <= record["H_target"] <= interval["ci_high"]
                    ),
                }
            )
    frame = pd.DataFrame(reconstructed)
    assert len(frame) == expected["interval_rows"]
    assert not frame.duplicated(["record_id", "method", "candidate"]).any()
    exported = pd.read_csv(output / "intervals.csv")
    for key in ("record_id", "method", "candidate", "available", "covered"):
        assert exported[key].tolist() == frame[key].tolist()
    summary = pd.read_csv(output / "coverage_summary.csv").set_index(
        ["cell", "method", "candidate"]
    )
    for key, group in frame.groupby(["cell", "method", "candidate"]):
        row = summary.loc[key]
        available = group[group.available]
        assert row.n_attempted == config["repetitions"] == len(group)
        assert row.n_available == len(available) and row.n_covered == available.covered.sum()
        if len(available):
            assert math.isclose(row.coverage, available.covered.mean(), abs_tol=1e-14)
            assert math.isclose(
                row.mean_width, (available.ci_high - available.ci_low).mean(), abs_tol=1e-14
            )
            # Independent Wilson formula, with a fixed 95% normal critical value.
            n, p, z = len(available), row.coverage, 1.959963984540054
            midpoint = (p + z * z / (2 * n)) / (1 + z * z / n)
            radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
            np.testing.assert_allclose(
                [row.wilson_low, row.wilson_high],
                [midpoint - radius, midpoint + radius],
                atol=1e-13,
            )
    for filename in ("paired_comparisons.csv", "mean_model_comparisons.csv"):
        for row in pd.read_csv(output / filename).itertuples():
            subset = frame[(frame.cell == row.cell) & (frame.method == row.method)]
            left = subset[subset.candidate == row.candidate].set_index("record_id")
            right = subset[subset.candidate == row.baseline].set_index("record_id")
            pairs = left.join(right, lsuffix="_left", rsuffix="_right", how="outer")
            valid = pairs.available_left.fillna(False) & pairs.available_right.fillna(False)
            assert row.n_attempted_pairs == len(pairs)
            assert row.n_available_pairs == valid.sum() and row.n_missing_pairs == (~valid).sum()
            differences = pairs.loc[valid, "covered_left"].astype(int) - pairs.loc[
                valid, "covered_right"
            ].astype(int)
            if len(differences) > 1:
                assert math.isclose(row.coverage_difference, differences.mean(), abs_tol=1e-14)
                assert math.isclose(
                    row.difference_mcse,
                    differences.std(ddof=1) / math.sqrt(len(differences)),
                    abs_tol=1e-14,
                )
    counts = pd.read_csv(output / "draw_accounting.csv")
    assert {k: int(counts[k].sum()) for k in draw_counts} == draw_counts
    assert draw_counts["attempted"] <= expected["bootstrap_statistic_attempts"]
    assert physical <= expected["physical_bootstrap_records"]
    historical = json.loads(
        (runner.shared.ROOT / "benchmark_experiment/remediation/baseline.json").read_text()
    )["historical_files"]
    assert all(file_hash(runner.shared.ROOT / f["path"]) == f["sha256"] for f in historical)
    probes = pd.read_csv(output / "offset_probes.csv")
    assert len(probes) == expected["offset_probe_statistics"]
    centered_probes = probes[probes.treatment == "centered"]
    maximum_shift = float(centered_probes.point_difference.abs().max())
    assert maximum_shift < 1e-10
    suites = [
        suite
        for name in ("tests.xml", "paired-tests.xml")
        for suite in ET.parse(output / name).getroot().iter("testsuite")
    ]
    test_counts = {
        key: sum(int(s.attrib.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    assert test_counts["failures"] == test_counts["errors"] == 0
    test_counts["passed"] = test_counts["tests"] - test_counts["skipped"]
    archive.mkdir(parents=True, exist_ok=True)
    names = [
        "run.json",
        "progress.json",
        "coverage_summary.csv",
        "paired_comparisons.csv",
        "mean_model_comparisons.csv",
        "fitted_models.csv",
        "input_index.csv",
        "offset_probes.csv",
        "first-four-checksums.json",
        "mean_comparison_higuchi.png",
        "mean_comparison_ghe.png",
        "mean_comparison_gph.png",
        "paired_offset_summary.csv",
        "paired_offset_parent_accounting.csv",
        "paired_offset_run.json",
    ]
    offset_identity = json.loads((output / "paired_offset_run.json").read_text())
    assert offset_identity["input_sha256"] == file_hash(output / "offset_probes.csv")
    assert all(file_hash(output / p) == h for p, h in offset_identity["artifact_sha256"].items())
    assert all(
        file_hash(runner.shared.ROOT / p) == h for p, h in offset_identity["source_sha256"].items()
    )
    offset_counts = pd.read_csv(output / "paired_offset_parent_accounting.csv")
    assert offset_counts.parents_attempted.eq(config["repetitions"]).all()
    assert offset_counts.pairs_missing.eq(0).all()
    assert offset_counts.parents_common_complete.eq(config["repetitions"]).all()
    offset_summary = pd.read_csv(output / "paired_offset_summary.csv")
    assert offset_summary.attempted_draws.eq(999).all()
    assert offset_summary.used_draws.eq(999).all()
    offset_centered = offset_summary[offset_summary.method.str.endswith("/centered")]
    assert (
        offset_centered[offset_centered.metric == "absolute_error_inflation"].value.abs().max()
        < 1e-10
    )
    assert (
        offset_centered[offset_centered.metric == "paired_mae_ratio"].value - 1
    ).abs().max() < 1e-10
    for name in names:
        shutil.copyfile(output / name, archive / name)
    # Preserve the exact executed bytes, including pre-existing Windows line
    # endings that Git's text normalization may change in a fresh checkout.
    snapshot_sources = identity["source_sha256"] | offset_identity["source_sha256"]
    with zipfile.ZipFile(archive / "executed_sources.zip", "w") as bundle:
        for name, checksum in sorted(snapshot_sources.items()):
            payload = (runner.shared.ROOT / name).read_bytes()
            assert hashlib.sha256(payload).hexdigest() == checksum
            entry = zipfile.ZipInfo(name.replace("\\", "/"), date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            bundle.writestr(entry, payload)
    pd.DataFrame(sorted(checksums.items()), columns=["record_id", "payload_sha256"]).to_csv(
        archive / "record_checksums.csv", index=False, lineterminator="\n"
    )
    verification = {
        "status": "development_only_intervals_not_accepted",
        "expected": expected,
        "independent_records": len(records),
        "interval_rows": len(frame),
        "physical_bootstrap_records": physical,
        "bootstrap_statistic_counts": draw_counts,
        "available_intervals": int(frame.available.sum()),
        "model_failures": sum(f is not None for r in records for f in r["model_failures"].values()),
        "offset_probe_failures": int(probes.failure.notna().sum()),
        "max_absolute_centered_offset_drift": maximum_shift,
        "first_four_checkpoints_unchanged_after_resume": True,
        "final_resume_new_records": resumed["new_records"],
        "all_input_hashes_verified": True,
        "input_bundle_sha256": input_files,
        "historical_baseline_hashes_unchanged": len(historical),
        "all_bootstrap_endpoints_recomputed": True,
        "coverage_width_wilson_and_paired_summaries_recomputed": True,
        "tests": test_counts,
        "paired_offset_summary_rows": len(offset_summary),
        "paired_offset_parent_support_complete": True,
        "source_sha256": identity["source_sha256"],
        "executed_source_snapshot_files": len(snapshot_sources),
        "source_snapshot_preserves_exact_working_file_bytes": True,
        "compact_artifact_sha256": {
            p.name: file_hash(p) for p in archive.iterdir() if p.name != "verification.json"
        },
    }
    (archive / "verification.json").write_text(
        json.dumps(verification, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                k: verification[k]
                for k in (
                    "independent_records",
                    "interval_rows",
                    "bootstrap_statistic_counts",
                    "available_intervals",
                    "model_failures",
                    "tests",
                )
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    verify(args.output.resolve(), args.archive.resolve())


if __name__ == "__main__":
    main()
