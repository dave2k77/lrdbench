"""Independent release rehearsal audit; never generates confirmation parents."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import tracemalloc
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from scipy.stats import norm

from lrdbench.bootstrap import circular_block_resample

try:
    from . import run_confirmation as engine
    from . import summarize_confirmation as reporting
except ImportError:
    import run_confirmation as engine
    import summarize_confirmation as reporting

shared, store = engine.shared, engine.store


def snapshot(folder):
    return {
        p.relative_to(folder).as_posix(): {
            "sha256": shared.file_hash(p),
            "mtime_ns": p.stat().st_mtime_ns,
        }
        for p in folder.rglob("*")
        if p.is_file()
    }


def rehearse(output):
    """Exercise interruption on each side of the directory commit boundary."""
    output = Path(output).resolve()
    if output.exists() and (output / "run.json").exists():
        raise ValueError(
            "Recovery rehearsal requires a fresh output, preserving previous evidence."
        )
    checks = {}
    for boundary in ("before_commit", "after_commit"):

        def interrupt(stage, chunk_id, boundary=boundary):
            if stage == boundary:
                raise InterruptedError(f"deliberate_{boundary}")

        try:
            engine.run(output, rehearsal=True, max_new_chunks=1, fault=interrupt)
        except InterruptedError as exc:
            checks[boundary] = str(exc)
        else:
            raise AssertionError("Requested interruption did not execute.")
    before = snapshot(output / "chunks")
    partial = engine.run(output, rehearsal=True, max_new_chunks=0)
    assert not partial["complete"] and partial["completed_chunks"] == 1
    assert before == snapshot(output / "chunks")
    checks["partial_noop_preserved_committed_bytes_and_mtimes"] = True
    start = time.perf_counter()
    result = engine.run(output, rehearsal=True)
    checks["remaining_fit_seconds"] = time.perf_counter() - start
    assert result["complete"] and result["confirmation_parents"] == 0
    before = snapshot(output / "chunks")
    engine.run(output, rehearsal=True)
    assert before == snapshot(output / "chunks")
    checks["complete_noop_preserved_committed_bytes_and_mtimes"] = True
    assert len(list((output / "abandoned").iterdir())) == 1
    checks["abandoned_uncommitted_chunks_preserved"] = 1
    store.atomic_json(output / "recovery_checks.json", checks)
    start = time.perf_counter()
    reporting.summarize(output)
    checks["summary_seconds"] = time.perf_counter() - start
    before = snapshot(output / "summaries")
    reporting.summarize(output)
    assert before == snapshot(output / "summaries")
    checks["summary_noop_preserved_bytes_and_mtimes"] = True
    store.atomic_json(output / "recovery_checks.json", checks)
    return checks


def verify_intervals(entry, values, x, config, cell, *, rehearsal):
    result, draws = entry["result"], values.shape[-1]
    prefix = "executor_rehearsal" if rehearsal else "confirmation"
    scalar_compared, endpoints = 0, 0
    reconstructed = {}
    for pool in ("cbc", "fgn"):
        info = result["pools"][pool]
        assert info["seed"] == shared.record_seed(
            config, cell, entry["repetition"], f"{prefix}_{pool}"
        )
        assert info["requested_records"] == draws
        rng = np.random.default_rng(info["seed"])
        if pool == "cbc":
            generated = np.asarray(
                [circular_block_resample(x, rng, len(x) // 16) for _ in range(draws)]
            )
        elif result["model"]:
            generated = (
                engine.intervals.ci.fitted_fgn_samples(result["model"], len(x), draws, rng)
                + result["model"]["mean"]
            )
        else:
            generated = np.empty((0, len(x)))
        assert info["generated_records"] == len(generated)
        reconstructed[pool] = generated
    for j, (pool, key) in enumerate(engine.STREAMS):
        counts = result["pools"][pool]["accounting"][key]
        assert counts["attempted"] + counts["unattempted"] == draws
        assert counts["used"] + counts["invalid"] + counts["failed"] == counts["attempted"]
        assert int(np.isfinite(values[j]).sum()) == counts["used"]
        assert np.isnan(values[j, counts["attempted"] :]).all()
        treatment, method = key.split(":", 1)
        for k in sorted({0, draws // 2, draws - 1}):
            if k >= len(reconstructed[pool]):
                continue
            sample = reconstructed[pool][k]
            if treatment == "centered":
                sample = sample - np.mean(sample)
            reference = engine.intervals.statistic(sample, method)
            np.testing.assert_allclose(
                values[j, k],
                np.nan if reference is None else reference,
                rtol=2e-12,
                atol=2e-13,
                equal_nan=True,
            )
            scalar_compared += 1
    for ci in result["intervals"]:
        point = ci["point"]
        expected = None
        if ci["candidate"] == "gph_normal_raw":
            if point is not None and np.isfinite(point):
                regressor = np.log(4 * np.sin(np.pi * np.arange(1, 33) / len(x)) ** 2)
                radius = norm.ppf(0.975) * np.sqrt(
                    np.pi**2 / (6 * np.sum((regressor - regressor.mean()) ** 2))
                )
                expected = [point - radius, point + radius]
        else:
            key = (ci["pool"], ci["treatment"] + ":" + ci["method"])
            data = values[engine.STREAMS.index(key)]
            center = (
                point if ci["pool"] == "cbc" else result["model"]["H"] if result["model"] else None
            )
            if point is not None and center is not None and np.isfinite(data).all():
                lo, hi = np.quantile(data, [0.025, 0.975])
                expected = (
                    [point + center - hi, point + center - lo]
                    if ci["candidate"].endswith("basic")
                    else [lo, hi]
                )
        assert ci["available"] == (expected is not None)
        if expected is None:
            assert ci["ci_low"] is None and ci["ci_high"] is None
        else:
            np.testing.assert_allclose(
                [ci["ci_low"], ci["ci_high"]], expected, rtol=1e-13, atol=1e-14
            )
        endpoints += 2
    return scalar_compared, endpoints


def literal_indices(n, draws, seed, key):
    value = int.from_bytes(
        hashlib.sha256(f"lrdbench-confirmation-summary-v1:{seed}:{key}".encode()).digest()[:8],
        "little",
    )
    return np.random.default_rng(value).integers(0, n, (draws, n))


def audit_point_summaries(data, row, output, identity_sha, scope, config):
    count = row["accuracy_parents"] if scope == "accuracy" else row["stress_parents"]
    end = 1 if scope == "accuracy" else len(data["conditions"])
    x = data["points"][:count, :end]
    valid = np.isfinite(x)
    complete = valid.all(axis=(1, 2))
    # Release rehearsal has two parents, so literal parent gathers are small.
    assert len(x) == 2 and complete.all()
    key = f"{identity_sha}:{row['cell']}:{scope}"
    ix = literal_indices(len(x), config["bootstrap_draws"], config["seed"], key + ":common")
    full_ix = literal_indices(
        len(x), config["bootstrap_draws"], config["seed"], key + ":all_attempts"
    )
    error, sampled = x - row["H_target"], x[ix] - row["H_target"]
    drift, sampled_drift = x - x[:, :1], x[ix] - x[ix][:, :, :1]
    means = {
        "bias": error.mean(0),
        "mae": np.abs(error).mean(0),
        "mse": (error**2).mean(0),
        "rmse": np.sqrt((error**2).mean(0)),
        "absolute_estimate_drift": np.abs(drift).mean(0),
        "signed_estimate_drift": drift.mean(0),
    }
    distributions = {
        "bias": sampled.mean(1),
        "mae": np.abs(sampled).mean(1),
        "mse": (sampled**2).mean(1),
        "rmse": np.sqrt((sampled**2).mean(1)),
        "absolute_estimate_drift": np.abs(sampled_drift).mean(1),
        "signed_estimate_drift": sampled_drift.mean(1),
    }
    means["absolute_error_inflation"] = means["mae"] - means["mae"][:1]
    distributions["absolute_error_inflation"] = distributions["mae"] - distributions["mae"][:, :1]
    means["paired_mae_ratio"] = means["mae"] / means["mae"][:1]
    distributions["paired_mae_ratio"] = distributions["mae"] / distributions["mae"][:, :1]
    means["validity"] = valid.mean(0)
    distributions["validity"] = valid[full_ix].mean(1)
    means["validity_loss"] = means["validity"][:1] - means["validity"]
    distributions["validity_loss"] = distributions["validity"][:, :1] - distributions["validity"]
    for metric, values in (
        ("outside_0_1", (x < 0) | (x > 1)),
        ("H_ge_0p6_exceedance_diagnostic", x >= 0.6),
        ("mean_runtime_seconds", data["runtimes"][:count, :end]),
    ):
        means[metric], distributions[metric] = values.mean(0), values[full_ix].mean(1)
    result = reporting.read_group(output / "summaries" / f"{scope}__{row['cell']}")
    for summary, samples in zip(result.rows, result.draws, strict=True):
        j = data["conditions"].index(summary["condition"])
        k = data["methods"].index(summary["method"])
        metric = summary["metric"]
        if summary["contrast"]:
            kc = data["methods"].index(summary["method"] + "::centered")
            metric = {
                "mae_difference": "mae",
                "error_inflation_difference": "absolute_error_inflation",
                "absolute_drift_difference": "absolute_estimate_drift",
            }[metric]
            value = means[metric][j, kc] - means[metric][j, k]
            expected = distributions[metric][:, j, kc] - distributions[metric][:, j, k]
        else:
            value, expected = means[metric][j, k], distributions[metric][:, j, k]
        np.testing.assert_allclose(summary["value"], value, rtol=1e-12, atol=2e-13)
        np.testing.assert_allclose(samples, expected, rtol=2e-12, atol=2e-13)
    return len(result.rows), result.matrix().size


def audit_interval_summaries(data, row, output, identity_sha, config):
    covered = (
        data["available"] & (data["low"] <= row["H_target"]) & (row["H_target"] <= data["high"])
    )
    width = np.where(data["available"], data["high"] - data["low"], np.nan)
    n = len(width)
    assert n == 2 and data["available"].all()
    key = f"{identity_sha}:{row['cell']}:intervals:all_interval_attempts"
    ix = literal_indices(n, config["bootstrap_draws"], config["seed"], key)
    result = reporting.read_group(output / "summaries" / f"intervals__{row['cell']}")
    for summary, samples in zip(result.rows, result.draws, strict=True):
        metric, condition, method = summary["metric"], summary["condition"], summary["method"]
        if method == "unknown_mean_fGn_ML":
            raw = (
                data["model_boundary"]
                if metric == "model_boundary_rate_all_attempts"
                else data["model_available"]
            )
        elif summary["contrast"]:
            b, a = condition.split("_minus_")
            ai, bi = data["labels"].index((method, a)), data["labels"].index((method, b))
            raw = (
                covered[:, bi].astype(float) - covered[:, ai].astype(float)
                if metric == "coverage_difference"
                else width[:, bi] - width[:, ai]
            )
        else:
            j = data["labels"].index((method, condition))
            raw = (
                covered[:, j]
                if "coverage" in metric
                else data["available"][:, j]
                if metric == "availability"
                else width[:, j]
            )
        value = np.median(raw) if metric == "median_width" else raw.mean()
        np.testing.assert_allclose(summary["value"], value, rtol=1e-12, atol=1e-13)
        if metric == "median_width":
            assert np.isnan(samples).all()
        else:
            np.testing.assert_allclose(samples, raw[ix].mean(1), rtol=1e-12, atol=1e-13)
        if summary["interval_method"] == "Wilson_95":
            z = norm.ppf(0.975)
            denominator = summary["denominator"]
            p = summary["successes"] / denominator
            center = (p + z * z / (2 * denominator)) / (1 + z * z / denominator)
            half = (
                z
                / (1 + z * z / denominator)
                * np.sqrt(p * (1 - p) / denominator + z * z / (4 * denominator**2))
            )
            np.testing.assert_allclose(
                [summary["ci_low"], summary["ci_high"]], [center - half, center + half], atol=1e-14
            )
    return len(result.rows), result.matrix().size


def storage_and_summary_profile(output, frozen, receipts):
    """A full-shape synthetic estimator table tests resources, not performance."""
    protocol = frozen["design"]["protocol"]
    n = protocol["stress"]["repetitions"]
    methods = [s["method"] for s in engine.design.point_settings(512)]
    conditions = ["clean", *[c["id"] for c in frozen["design"]["conditions"]]]
    # Artificial estimator values, not simulated signal records or study data.
    values = np.random.default_rng(988031).normal(0.5, 0.2, (n, len(conditions), len(methods)))
    tracemalloc.start()
    started = time.perf_counter()
    result, _ = reporting.analysis.point_summaries(
        values,
        np.ones_like(values),
        target=0.5,
        methods=methods,
        conditions=conditions,
        draws=1999,
        seed=20260916,
        key="resource_shape_test_not_study_data",
    )
    matrix = result.matrix()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    profile = {
        "status": "resource_test_artificial_estimator_values_not_confirmation",
        "parents": n,
        "conditions": len(conditions),
        "methods": len(methods),
        "summary_rows": len(result.rows),
        "summary_draw_values": matrix.size,
        "seconds": elapsed,
        "peak_tracked_python_numpy_bytes": peak,
        "memory_limit": "Tracked allocations exclude some native library buffers and are not process RSS.",
    }
    del matrix, result, values
    workload = frozen["design"]["workload"]
    fits = sum(r["counts"]["point_fits"] for r in receipts.values())
    ci_parents = sum(r["counts"]["interval_parents"] for r in receipts.values())
    parents = sum(r["counts"]["parents"] for r in receipts.values())
    point_bytes = (
        sum(r["files"]["points.jsonl.gz"]["bytes"] for r in receipts.values())
        / fits
        * workload["total_point_fits"]
    )
    draw_bytes = (
        sum(r["files"]["draws.npz"]["bytes"] for r in receipts.values())
        / ci_parents
        * workload["interval_parent_subset"]
    )
    metadata_bytes = (
        sum(r["files"]["metadata.json.gz"]["bytes"] for r in receipts.values())
        / parents
        * workload["independent_clean_parents"]
    )
    summary_bytes = 0
    for path in (output / "summaries").glob("*/draws.npz"):
        with np.load(path, allow_pickle=False) as bundle:
            summary_bytes += bundle["values"].nbytes
    summary_bytes += sum(
        p.stat().st_size
        for p in (output / "summaries").rglob("*")
        if p.is_file() and p.suffix != ".npz"
    )
    primary_bytes = (
        point_bytes
        + draw_bytes
        + metadata_bytes
        + workload["raw_clean_signal_bytes"]
        + workload["raw_descendant_signal_bytes"]
    )
    planned = 2 * (primary_bytes + summary_bytes) + engine.EXECUTION["minimum_free_bytes"]
    capacity = engine.disk_check(output, initial=True)
    assert (
        capacity["free_bytes"] > planned
        and engine.EXECUTION["initial_required_free_bytes"] >= planned
    )
    return {
        "summary_resource_profile": profile,
        "projected_primary_bytes": primary_bytes,
        "conservative_uncompressed_summary_bytes": summary_bytes,
        "planning_bytes_2x_plus_10GiB_reserve": planned,
        "initial_required_free_bytes": engine.EXECUTION["initial_required_free_bytes"],
        "observed_free_bytes": capacity["free_bytes"],
        "within_planned_capacity": True,
        "limit": "A projection including summary arrays; actual free space is rechecked during execution. Abandoned chunks and other applications can consume capacity.",
    }


def verify(output, previous, archive):
    output, previous, archive = (
        Path(output).resolve(),
        Path(previous).resolve(),
        Path(archive).resolve(),
    )
    run, frozen, specs, receipts = reporting.read_run(output)
    assert run["identity"]["mode"] == "executor_rehearsal_never_confirmation"
    identity_sha, config = run["identity_sha256"], run["identity"]["config"]
    reporting.summarize(output)
    totals = {
        "parents_regenerated": 0,
        "descendants_equation_replayed": 0,
        "clean_points_matched_to_previous_rehearsal": 0,
        "aligned_statistics_checked": 0,
        "scalar_statistics_replayed": 0,
        "interval_endpoints_recomputed": 0,
        "point_summary_rows_independently_recomputed": 0,
        "point_summary_draws_independently_recomputed": 0,
        "interval_summary_rows_independently_recomputed": 0,
        "interval_summary_draws_independently_recomputed": 0,
    }
    conditions = {c["id"]: c for c in frozen["design"]["conditions"]}
    stress_config = {
        **config,
        "seed_namespace": frozen["design"]["protocol"]["randomness"]["stress_seed_namespace"]
        + ":executor_rehearsal",
    }
    for spec in specs:
        folder = output / "chunks" / spec["id"]
        metadata = store.read_json_gz(folder / "metadata.json.gz")
        cell = {k: spec["cell"][k] for k in ("family", "parameter", "n")}
        factor = shared.covariance_factor(cell)
        with np.load(folder / "signals.npz", allow_pickle=False) as bundle:
            signals = bundle["values"]
        assert len(signals) == len(metadata["signals"])
        parents = {}
        for values, meta in zip(signals, metadata["signals"], strict=True):
            assert shared.array_hash(values) == meta["sha256"]
            assert meta["input_seed"] == shared.record_seed(
                config, cell, meta["repetition"], "input"
            )
            assert meta["resampling_seed"] == shared.record_seed(
                config, cell, meta["repetition"], "resampling"
            )
            if meta["condition"] == "clean":
                regenerated = shared.generate_record(config, cell, meta["repetition"], factor)
                np.testing.assert_array_equal(values, regenerated)
                parents[meta["parent_id"]] = (values, meta)
                old = json.loads(
                    (previous / "records" / f"{meta['parent_id']}.json").read_text(encoding="utf-8")
                )
                assert old["sha256"] == shared.digest(old["record"])
                assert old["record"]["input_sha256"] == meta["sha256"]
                totals["parents_regenerated"] += 1
            else:
                parent_values, parent_meta = parents[meta["parent_id"]]
                condition = conditions[meta["condition"]]
                child_id, seed = engine.inputs.child_identity(
                    stress_config, parent_meta, condition, condition["version"]
                )
                assert (child_id, seed) == (meta["record_id"], meta["contamination_seed"])
                np.testing.assert_allclose(
                    values,
                    engine.inputs.reference_values(parent_values, condition, seed),
                    rtol=2e-14,
                    atol=2e-14,
                )
                assert meta["parent_sha256"] == parent_meta["sha256"]
                assert meta["transformation"]["parent_id"] == meta["parent_id"]
                assert meta["transformation"]["version"] == condition["version"]
                assert meta["transformation"]["params"] == condition["params"]
                totals["descendants_equation_replayed"] += 1
        old_records = {
            p: json.loads((previous / "records" / f"{p}.json").read_text(encoding="utf-8"))[
                "record"
            ]
            for p in parents
        }
        for fit in store.read_points(folder):
            if fit["condition"] == "clean":
                old = next(
                    p
                    for p in old_records[fit["parent_id"]]["clean_points"]
                    if p["method"] == fit["method"]
                )
                assert (
                    fit["valid"] == old["valid"]
                    and fit["analysed_sha256"] == old["analysed_sha256"]
                )
                np.testing.assert_allclose(fit["point"], old["point"], rtol=1e-13, atol=1e-14)
                totals["clean_points_matched_to_previous_rehearsal"] += 1
        with np.load(folder / "draws.npz", allow_pickle=False) as bundle:
            values = bundle["values"]
        assert values.shape == (len(metadata["interval_records"]), 9, 1999)
        for entry, draws in zip(metadata["interval_records"], values, strict=True):
            scalar, endpoints = verify_intervals(
                entry, draws, parents[entry["parent_id"]][0], config, cell, rehearsal=True
            )
            totals["aligned_statistics_checked"] += draws.size
            totals["scalar_statistics_replayed"] += scalar
            totals["interval_endpoints_recomputed"] += endpoints
        data = reporting.load_cell(output, spec["cell"], specs, identity_sha)
        for scope in ("accuracy", "stress"):
            if scope == "stress" and not spec["cell"]["stress_parents"]:
                continue
            rows, draws = audit_point_summaries(
                data,
                spec["cell"],
                output,
                identity_sha,
                scope,
                frozen["design"]["protocol"]["summaries"],
            )
            totals["point_summary_rows_independently_recomputed"] += rows
            totals["point_summary_draws_independently_recomputed"] += draws
        if spec["cell"]["interval_parents"]:
            rows, draws = audit_interval_summaries(
                data, spec["cell"], output, identity_sha, frozen["design"]["protocol"]["summaries"]
            )
            totals["interval_summary_rows_independently_recomputed"] += rows
            totals["interval_summary_draws_independently_recomputed"] += draws
        print(f"Audited {spec['id']}", flush=True)
    baseline = json.loads((engine.HERE / "baseline.json").read_text(encoding="utf-8"))
    assert all(
        shared.file_hash(shared.ROOT / p["path"]) == p["sha256"]
        for p in baseline["historical_files"]
    )
    tests = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for name in ("focused-tests.xml", "regression-tests.xml"):
        tree = ET.parse(output / name)
        for suite in tree.getroot().iter("testsuite"):
            for key in tests:
                tests[key] += int(suite.attrib.get(key, 0))
    assert tests["tests"] > 470 and tests["failures"] == tests["errors"] == 0
    recovery = json.loads((output / "recovery_checks.json").read_text(encoding="utf-8"))
    assert all(
        recovery[k]
        for k in (
            "partial_noop_preserved_committed_bytes_and_mtimes",
            "complete_noop_preserved_committed_bytes_and_mtimes",
            "summary_noop_preserved_bytes_and_mtimes",
        )
    )
    assert run["identity"]["runtime_sha256"] == shared.digest(engine.runtime_lock(frozen))
    resources = storage_and_summary_profile(output, frozen, receipts)
    verification = {
        "status": "execution_rehearsal_verified_not_confirmation",
        "runtime_sha256": run["identity"]["runtime_sha256"],
        "scientific_design_sha256": frozen["sha256"],
        "run_identity_sha256": identity_sha,
        "tests": tests,
        "confirmation_parents": 0,
        "historical_hashes_unchanged": len(baseline["historical_files"]),
        "checks": totals,
        "chunk_receipts_sha256": shared.digest(receipts),
        "raw_chunk_file_sha256": {
            p.relative_to(output).as_posix(): shared.file_hash(p)
            for p in (output / "chunks").rglob("*")
            if p.is_file()
        },
        "source_sha256": run["identity"]["source_sha256"],
        "source_archive_sha256": shared.file_hash(output / "executed_sources.zip"),
        "recovery": recovery,
    }
    archive.mkdir(parents=True, exist_ok=True)
    for name in (
        "executed_sources.zip",
        "run.json",
        "status.json",
        "recovery_checks.json",
        "focused-tests.xml",
        "regression-tests.xml",
    ):
        shutil.copyfile(output / name, archive / name)
    shutil.copyfile(output / "summaries/complete.json", archive / "summary_manifest.json")
    # Full per-cell summary/draw archives stay in the local evidence directory.
    store.atomic_json(archive / "verification.json", verification)
    store.atomic_json(archive / "resource_check.json", resources)
    release = {
        "status": "validated_for_fixed_confirmation",
        "runtime_sha256": run["identity"]["runtime_sha256"],
        "scientific_design_sha256": frozen["sha256"],
        "rehearsal_identity_sha256": identity_sha,
        "evidence_sha256": {
            p.name: shared.file_hash(p)
            for p in archive.iterdir()
            if p.is_file() and p.name != "release.json"
        },
    }
    store.atomic_json(archive / "release.json", release)
    print(
        json.dumps(
            {"verification": totals, "tests": tests, "runtime_sha256": release["runtime_sha256"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rehearse", action="store_true")
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--archive", type=Path, default=engine.HERE / "execution-v1")
    args = parser.parse_args()
    if args.rehearse:
        print(json.dumps(rehearse(args.output), indent=2))
    else:
        if args.previous is None:
            parser.error("--previous is required for the independent release audit")
        verify(args.output, args.previous, args.archive)
