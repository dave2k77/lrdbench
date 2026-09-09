"""Rebuild stress summaries independently and archive a compact verified bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from . import run_shared_stress as runner
except ImportError:
    import run_shared_stress as runner

shared = runner.shared


def close(actual, expected):
    np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=2e-13, equal_nan=True)


def independent_summaries(points, output, config):
    """Direct index-vector replay; does not call the paired-summary helper."""
    summary = pd.read_csv(output / "paired_summary.csv", float_precision="round_trip")
    accounting = pd.read_csv(output / "parent_accounting.csv")
    draws = pd.read_csv(output / "summary_draws.csv", float_precision="round_trip")
    saved_draws = {
        key: group.sort_values("draw")
        for key, group in draws.groupby(["domain", "method", "condition", "metric"])
    }
    indexed = points.set_index(["cell", "parent_id", "method", "condition"])
    methods = sorted(row["method"] for row in runner.roster())
    conditions = sorted(c["id"] for c in config["conditions"])
    count, m, c = config["summary"]["draws"], len(methods), len(conditions)
    common_counts = {}
    for domain in sorted(config["processes"]):
        cells = [cell for cell in shared.cells(config) if cell["family"] == domain]
        clean_total, stress_total = np.zeros((2, m, c))
        clean_draws, stress_draws = np.zeros((2, count, m, c))
        for cell in cells:
            stratum = shared.cell_id(cell)
            target = runner.inputs.target(cell)
            parents = sorted(f"{stratum}_r{r}" for r in range(config["repetitions"]))
            clean, stressed = np.full((2, len(parents), m, c), np.nan)
            for i, parent in enumerate(parents):
                for j, method in enumerate(methods):
                    baseline = indexed.loc[stratum, parent, method, "clean"]
                    for k, condition in enumerate(conditions):
                        child = indexed.loc[stratum, parent, method, condition]
                        if baseline.valid and np.isfinite(baseline.point):
                            clean[i, j, k] = abs(baseline.point - target)
                        if child.valid and np.isfinite(child.point):
                            stressed[i, j, k] = abs(child.point - target)
            available = np.isfinite(clean) & np.isfinite(stressed)
            common = available.all(axis=(1, 2))
            common_counts[stratum] = int(common.sum())
            for j, method in enumerate(methods):
                for k, condition in enumerate(conditions):
                    row = accounting[
                        (accounting.stratum == stratum)
                        & (accounting.method == method)
                        & (accounting.condition == condition)
                    ].iloc[0]
                    assert row.parents_attempted == len(parents)
                    assert row.pairs_available == available[:, j, k].sum()
                    assert row.pairs_missing == len(parents) - available[:, j, k].sum()
                    assert row.parents_common_complete == common.sum()
            # This completed screen has usable common support in every cell.
            assert common.sum() >= 2
            a, b = clean[common], stressed[common]
            clean_total += a.mean(axis=0) / len(cells)
            stress_total += b.mean(axis=0) / len(cells)
            seed = int.from_bytes(
                hashlib.sha256(
                    f"lrdbench-paired-summary-v1:{config['summary']['seed']}:{stratum}".encode()
                ).digest()[:8],
                "little",
            )
            indices = np.random.default_rng(seed).integers(0, len(a), size=(count, len(a)))
            # Different batching from the production helper, same full draw indices.
            for start in range(0, count, 17):
                selected = indices[start : start + 17]
                clean_draws[start : start + 17] += a[selected].mean(axis=1) / len(cells)
                stress_draws[start : start + 17] += b[selected].mean(axis=1) / len(cells)
        floor = config["summary"]["denominator_floor"]
        for j, method in enumerate(methods):
            for k, condition in enumerate(conditions):
                a, b = clean_total[j, k], stress_total[j, k]
                ad, bd = clean_draws[:, j, k], stress_draws[:, j, k]
                for metric, value, distribution in (
                    ("absolute_error_inflation", b - a, bd - ad),
                    (
                        "paired_mae_ratio",
                        b / a if a > floor else np.nan,
                        np.divide(bd, ad, out=np.full_like(ad, np.nan), where=ad > floor),
                    ),
                ):
                    row = summary[
                        (summary.domain == domain)
                        & (summary.method == method)
                        & (summary.condition == condition)
                        & (summary.metric == metric)
                    ].iloc[0]
                    actual_draws = saved_draws[domain, method, condition, metric]
                    assert np.array_equal(actual_draws.draw, np.arange(count))
                    close(actual_draws.value, distribution)
                    close(actual_draws.clean_mae, ad)
                    close(actual_draws.stressed_mae, bd)
                    close([row.value, row.clean_mae, row.stressed_mae], [value, a, b])
                    finite = distribution[np.isfinite(distribution)]
                    assert row.attempted_draws == count and row.used_draws == len(finite)
                    assert row.invalid_draws == count - len(finite)
                    close([row.ci_low, row.ci_high], np.quantile(finite, [0.025, 0.975]))
                    close(row.bootstrap_se, np.std(finite, ddof=1))
    assert len(summary) == len(config["processes"]) * m * c * 2
    assert len(draws) == len(summary) * count
    assert len(accounting) == len(shared.cells(config)) * m * c
    # Independently check cell accuracy and paired drift, including denominators.
    cell_summary = pd.read_csv(output / "cell_summary.csv", float_precision="round_trip").set_index(
        ["cell", "method", "condition"]
    )
    drift = pd.read_csv(output / "cell_drift.csv", float_precision="round_trip").set_index(
        ["stratum", "method", "condition"]
    )
    for keys, group in points.groupby(["cell", "method", "condition"]):
        cell, method, condition = keys
        valid = group.valid & np.isfinite(group.point)
        errors = group.loc[valid, "point"] - group.loc[valid, "H_target"]
        row = cell_summary.loc[keys]
        assert row.attempted == len(group) and row.valid == valid.sum()
        close(
            [row.bias, row.mae, row.rmse, row.bias_mcse],
            [
                errors.mean(),
                errors.abs().mean(),
                np.sqrt(np.mean(errors**2)),
                errors.std(ddof=1) / np.sqrt(len(errors)),
            ],
        )
        if condition != "clean":
            baseline = points[
                (points.cell == cell) & (points.method == method) & (points.condition == "clean")
            ].set_index("parent_id")
            delta = group.set_index("parent_id").point - baseline.point
            usable = group.set_index("parent_id").valid & baseline.valid & np.isfinite(delta)
            row = drift.loc[keys]
            assert row.attempted == len(group) and row.available == usable.sum()
            close(
                [row.signed_drift, row.absolute_drift],
                [delta[usable].mean(), delta[usable].abs().mean()],
            )
    return len(summary), len(draws), common_counts


def verify(source, output, archive):
    run = json.loads((output / "run.json").read_text(encoding="utf-8"))
    identity = run["identity"]
    config = identity["config"]
    assert run["identity_sha256"] == shared.digest(identity)
    assert all(
        shared.file_hash(shared.ROOT / path) == sha
        for path, sha in identity["source_sha256"].items()
    )
    files_before = {p.name: shared.file_hash(p) for p in (output / "inputs").glob("*.npz")}
    # Resume exercises guards and re-verifies all inputs; it must perform no fits.
    progress = runner.run(config, source, output, max_new_parents=0)
    assert progress["complete"] and progress["new_parents"] == 0
    assert files_before == {p.name: shared.file_hash(p) for p in (output / "inputs").glob("*.npz")}
    point_hash = shared.file_hash(output / "point_estimates.csv")
    runner.summarize(config, output)
    with (output / "input_index.csv").open(encoding="utf-8", newline="") as handle:
        csv_index = {row["record_id"]: row for row in csv.DictReader(handle)}
    intended = {}
    for cell in shared.cells(config):
        values, metadata = runner.inputs.materialize_cell(source, output / "inputs", config, cell)
        assert (
            metadata["design"]["source_pool_sha256"]
            == identity["source_pool_sha256"][shared.cell_id(cell)]
        )
        for r, block in enumerate(values):
            for j, x in enumerate(block):
                row = metadata["records"][r * len(block) + j]
                intended[row["record_id"]] = (cell, row)
                actual = csv_index[row["record_id"]]
                assert actual["sha256"] == shared.array_hash(x)
                assert actual["parent_id"] == row["parent_id"]
                for name in ("input_seed", "resampling_seed", "contamination_seed"):
                    assert actual[name] == ("" if row[name] is None else str(row[name]))
    expected = runner.workload(config)
    assert (
        len(intended) == len(csv_index) == expected["independent_parents"] + expected["descendants"]
    )
    points = pd.read_csv(output / "point_estimates.csv", float_precision="round_trip")
    assert len(points) == expected["point_fits"]
    assert not points.duplicated(["record_id", "method"]).any()
    assert set(points.record_id) == set(intended)
    assert points.interval_status.eq("not_evaluated_point_stress_screen").all()
    assert points.target_role.eq("latent_clean_recovery").all()
    assert points.groupby("record_id").size().eq(expected["methods"]).all()
    for row in points.itertuples():
        cell, metadata = intended[row.record_id]
        assert row.parent_id == metadata["parent_id"] and row.input_sha256 == metadata["sha256"]
        assert row.H_target == runner.inputs.target(cell)
        assert json.loads(row.parameters_json)["n_bootstrap"] == 0
    with sqlite3.connect(output / "checkpoint.sqlite") as db:
        completed = runner.checkpoints(db)
    checksums = pd.read_csv(output / "record_checksums.csv").set_index("parent_id")
    for parent, rows in completed.items():
        assert checksums.loc[parent, "scientific_sha256"] == runner.scientific_hash(rows)
    first = pd.read_csv(output / "first-two-checksums.csv").set_index("parent_id")
    assert len(first) == 2
    pd.testing.assert_frame_equal(first, checksums.loc[first.index])
    summary_count, draw_count, common_counts = independent_summaries(points, output, config)
    baseline = json.loads(
        (shared.ROOT / "benchmark_experiment/remediation/baseline.json").read_text(encoding="utf-8")
    )
    assert all(
        shared.file_hash(shared.ROOT / row["path"]) == row["sha256"]
        for row in baseline["historical_files"]
    )
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
    snapshot = dict(identity["source_sha256"])
    for path in (
        Path(__file__),
        Path(__file__).with_name("plot_shared_stress.py"),
        shared.ROOT / "tests/unit/test_shared_stress_research.py",
    ):
        snapshot[str(path.relative_to(shared.ROOT))] = shared.file_hash(path)
    archive.mkdir(parents=True, exist_ok=True)
    compact = [
        "run.json",
        "progress.json",
        "input_index.csv",
        "record_checksums.csv",
        "first-two-checksums.csv",
        "cell_summary.csv",
        "cell_drift.csv",
        "paired_summary.csv",
        "parent_accounting.csv",
        "summary_design.json",
        "focused-tests.xml",
        "regression-tests.xml",
        "stress_fGn.png",
        "stress_AR1.png",
        "stress_ARFIMA.png",
    ]
    for name in compact:
        shutil.copyfile(output / name, archive / name)
    with zipfile.ZipFile(archive / "executed_sources.zip", "w") as bundle:
        for name, sha in sorted(snapshot.items()):
            payload = (shared.ROOT / name).read_bytes()
            assert hashlib.sha256(payload).hexdigest() == sha
            entry = zipfile.ZipInfo(name.replace("\\", "/"), date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            bundle.writestr(entry, payload)
    verification = {
        "status": "development_shared_parent_stress_not_confirmation",
        "expected": expected,
        "completed_point_fits": len(points),
        "valid_point_fits": int(points.valid.sum()),
        "independent_parent_counts": common_counts,
        "all_children_equation_verified": True,
        "all_parent_signal_and_source_hashes_verified": True,
        "csv_seeds_exact_integer_round_trip": True,
        "input_bundle_sha256": files_before,
        "raw_point_csv_sha256": point_hash,
        "checkpoint_database_sha256": shared.file_hash(output / "checkpoint.sqlite"),
        "first_two_checkpoints_unchanged": True,
        "final_resume_new_parents": progress["new_parents"],
        "paired_summary_rows": summary_count,
        "joint_summary_draw_rows": draw_count,
        "joint_summary_draws_sha256": shared.file_hash(output / "summary_draws.csv"),
        "all_summary_draws_quantiles_and_standard_errors_independently_recomputed": True,
        "cell_accuracy_and_drift_recomputed": True,
        "tests": tests,
        "historical_hashes_unchanged": len(baseline["historical_files"]),
        "source_snapshot_files": len(snapshot),
        "snapshot_source_sha256": snapshot,
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
                k: verification[k]
                for k in (
                    "completed_point_fits",
                    "valid_point_fits",
                    "paired_summary_rows",
                    "joint_summary_draw_rows",
                    "tests",
                    "historical_hashes_unchanged",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    verify(args.source.resolve(), args.output.resolve(), args.archive.resolve())
