"""Independent, read-only verification of the complete confirmation archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

B = 1999
SELECTED = np.linspace(0, B - 1, 31, dtype=int)
RUN = "43d0a7f75c8afab6d32ab6fd1f2ff8db49cca59e36971e2b74404173f4cbfcf2"
DESIGN = "b5b9399d284e3fae8135050aeac5c8bc0a02ab36b4f0a6d15041f55a497681bb"
IMETHODS = ["GPH::narrow_band", "Higuchi", "GHE"]
CANDIDATES = [
    "cbc_raw_percentile",
    "cbc_raw_basic",
    "cbc_centered_percentile",
    "cbc_centered_basic",
    "unknown_fgn_centered_basic",
]
LABELS = [
    (m, c) for m in IMETHODS for c in CANDIDATES + (["gph_normal_raw"] if m == IMETHODS[0] else [])
]
STREAMS = [
    (p, t + ":" + m)
    for p in ["cbc", "fgn"]
    for t in (["raw", "centered"] if p == "cbc" else ["centered"])
    for m in IMETHODS
]
KEYS = ["method", "condition", "metric", "contrast"]
NUMERIC = [
    "value",
    "ci_low",
    "ci_high",
    "mcse",
    "bootstrap_se",
    "successes",
    "denominator",
    "parents_attempted",
    "parents_used",
    "parents_excluded",
    "requested_draws",
    "used_draws",
    "invalid_draws",
    "domain_cells",
    "cell_weight",
]


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def close(a, b, context="numeric mismatch"):
    if not np.allclose(a, b, rtol=2e-10, atol=2e-12, equal_nan=True):
        raise AssertionError(f"{context}: {np.asarray(a).shape} vs {np.asarray(b).shape}")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def array_hash(x):
    return hashlib.sha256(np.asarray(x, dtype="<f8").tobytes()).hexdigest()


def read_json(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def seed(cell, r, stream):
    data = ["lrdbench-classical-confirmation-v1", 20260915, cell, r, stream]
    return int.from_bytes(hashlib.sha256(canonical(data).encode()).digest()[:8], "little")


def grid(protocol):
    rows = []
    for family, parameters in protocol["accuracy"]["processes"].items():
        for parameter in parameters:
            for n in protocol["accuracy"]["lengths"]:
                cell = {"family": family, "parameter": float(parameter), "n": n}
                counts = {}
                role = "none"
                for name, design in [
                    ("stress", protocol["stress"]),
                    ("core", protocol["intervals"]["core"]),
                    ("length_sensitivity", protocol["intervals"]["length_sensitivity"]),
                ]:
                    present = n in design["lengths"] and parameter in design["processes"].get(
                        family, []
                    )
                    counts[name] = design["repetitions"] if present else 0
                    if present and name != "stress":
                        role = name
                rows.append(
                    {
                        **cell,
                        "cell": f"{family}_{parameter:g}_n{n}",
                        "H_target": 0.5
                        if family == "AR1"
                        else parameter + (0.5 if family == "ARFIMA" else 0),
                        "accuracy_parents": protocol["accuracy"]["repetitions"],
                        "stress_parents": counts["stress"],
                        "interval_parents": counts["core"] + counts["length_sensitivity"],
                        "interval_role": role,
                    }
                )
    return sorted(rows, key=lambda row: row["cell"])


def contaminated(x, definition, random_seed):
    """Direct equations, independent of public operators and producer helpers."""
    op, p = definition["operator"], definition["params"]
    rng, n, sd = np.random.default_rng(random_seed), len(x), np.std(x)
    delta = np.zeros(n)
    if op == "constant_offset":
        delta.fill(p["shift"] * (sd + 1e-12))
    elif op == "step_change":
        delta[int(n * p["position"]) :] = p["shift"] * sd
    elif op == "outliers":
        count = max(1, round(p["rate"] * n)) if p["rate"] else 0
        positions = rng.choice(n, count, replace=False)
        delta[positions] = rng.choice([-1.0, 1.0], count) * p["amplitude"] * (sd + 1e-12)
    elif op == "polynomial_trend":
        t = np.linspace(-1.0, 1.0, n)
        basis = sum(t**power for power in range(1, p["order"] + 1))
        basis -= basis.mean()
        delta = basis / (np.std(basis) + 1e-12) * p["strength"] * (sd + 1e-12)
    elif op == "heavy_tail_noise":
        noise = rng.standard_t(p["df"], n)
        delta = noise / (np.std(noise) + 1e-12) * p["scale"] * (sd + 1e-12)
    else:
        raise AssertionError(op)
    return x + delta


def endpoints(ci, result, distributions, n):
    point = ci["point"]
    if ci["candidate"] == "gph_normal_raw":
        if point is None or not np.isfinite(point):
            return None
        regressor = np.log(4 * np.sin(np.pi * np.arange(1, 33) / n) ** 2)
        half = (
            NormalDist().inv_cdf(0.975)
            * np.pi
            / np.sqrt(6 * np.sum((regressor - regressor.mean()) ** 2))
        )
        return np.array([point - half, point + half])
    values = distributions[STREAMS.index((ci["pool"], ci["treatment"] + ":" + ci["method"]))]
    center = result["model"]["H"] if ci["pool"] == "fgn" and result["model"] else point
    if (
        point is None
        or center is None
        or not np.isfinite(values).all()
        or not np.isfinite([point, center]).all()
    ):
        return None
    quantiles = np.quantile(values, [0.025, 0.975])
    return quantiles if ci["candidate"].endswith("percentile") else point + center - quantiles[::-1]


def load_raw(source, row, design, counters):
    n, rcount, s, icount = (
        row[k] for k in ["n", "accuracy_parents", "stress_parents", "interval_parents"]
    )
    settings = [v for v in design["settings"] if v["n"] == n]
    methods = [v["method"] for v in settings]
    definitions = {v["id"]: v for v in design["conditions"]}
    conditions = ["clean"] + (list(definitions) if s else [])
    mi, cj = {v: i for i, v in enumerate(methods)}, {v: i for i, v in enumerate(conditions)}
    shape = (rcount, len(conditions), len(methods))
    points, runtime, seen = np.full(shape, np.nan), np.full(shape, np.nan), np.zeros(shape, bool)
    low, high = np.full((icount, 16), np.nan), np.full((icount, 16), np.nan)
    available, ciseen = np.zeros((icount, 16), bool), np.zeros((icount, 16), bool)
    boundary, model = np.zeros(icount, bool), np.zeros(icount, bool)
    cell = {k: row[k] for k in ["family", "parameter", "n"]}
    for start in range(0, rcount, 32):
        stop = min(start + 32, rcount)
        chunkid = f"{row['cell']}__r{start:05}_{stop:05}"
        folder = source / "chunks" / chunkid
        receipt = read_json(folder / "receipt.json")
        require(digest(receipt["receipt"]) == receipt["sha256"], "receipt checksum")
        receipt = receipt["receipt"]
        require(
            receipt["run_identity_sha256"] == RUN and receipt["chunk_id"] == chunkid,
            "chunk identity",
        )
        require(
            set(receipt["files"])
            == {"signals.npz", "draws.npz", "metadata.json.gz", "points.jsonl.gz"},
            "chunk files",
        )
        for name, spec in receipt["files"].items():
            path = folder / name
            require(
                path.stat().st_size == spec["bytes"] and file_hash(path) == spec["sha256"],
                str(path),
            )
        meta = read_json(folder / "metadata.json.gz")
        require(meta["run_identity_sha256"] == RUN, "metadata run")
        require(
            meta["chunk"]["start"] == start
            and meta["chunk"]["stop"] == stop
            and meta["chunk"]["id"] == chunkid,
            "chunk range",
        )
        require(all(meta["chunk"]["cell"][k] == v for k, v in row.items()), "chunk cell")
        require(meta["draw_stream_order"] == [list(v) for v in STREAMS], "draw stream labels")
        with np.load(folder / "signals.npz", allow_pickle=False) as bundle:
            signals = bundle["values"]
        with np.load(folder / "draws.npz", allow_pickle=False) as bundle:
            draws = bundle["values"]
        require(
            signals.shape == (len(meta["signals"]), n) and np.isfinite(signals).all(),
            "signals shape/finite",
        )
        records, signalkeys, parents = {}, set(), {}
        local = Counter()
        for x, entry in zip(signals, meta["signals"], strict=True):
            r, condition = entry["repetition"], entry["condition"]
            pid = f"{row['cell']}_r{r}"
            require(start <= r < stop and entry["parent_id"] == pid, "signal parent")
            require(
                (r, condition) not in signalkeys and entry["record_id"] not in records,
                "duplicate signal",
            )
            signalkeys.add((r, condition))
            require(entry["sha256"] == array_hash(x), "signal checksum")
            require(
                entry["input_seed"] == seed(cell, r, "input")
                and entry["resampling_seed"] == seed(cell, r, "resampling"),
                "parent seed",
            )
            if condition == "clean":
                require(
                    entry["record_id"] == pid and entry["parent_sha256"] == entry["sha256"],
                    "clean identity",
                )
                require(
                    entry["contamination_seed"] is None and entry["transformation"] is None,
                    "clean transformation",
                )
                parents[r] = (x, entry)
                local["parents"] += 1
            else:
                parent, pm = parents[r]
                definition = definitions[condition]
                identity = {
                    "parent_id": pid,
                    "parent_sha256": pm["sha256"],
                    "operator": definition["operator"],
                    "parameters": definition["params"],
                    "version": definition["version"],
                    "global_seed": 20260915,
                    "seed_namespace": "lrdbench-classical-confirmation-contamination-v1",
                }
                sha = digest(identity)
                expected_seed = int.from_bytes(
                    hashlib.sha256(("contamination:" + sha).encode()).digest()[:8], "little"
                )
                require(
                    entry["record_id"] == "stress_" + sha
                    and entry["contamination_seed"] == expected_seed,
                    "child seed/identity",
                )
                require(entry["parent_sha256"] == pm["sha256"], "child parent hash")
                require(
                    entry["transformation"]["params"] == definition["params"]
                    and entry["transformation"]["name"] == definition["operator"],
                    "transformation",
                )
                require(
                    np.allclose(
                        x, contaminated(parent, definition, expected_seed), atol=2e-14, rtol=2e-14
                    ),
                    "contamination replay",
                )
                local["descendants"] += 1
            records[entry["record_id"]] = (entry, array_hash(x - x.mean()))
        expected_keys = {
            (r, c) for r in range(start, stop) for c in (conditions if r < s else ["clean"])
        }
        require(signalkeys == expected_keys, "signal grid")
        with gzip.open(folder / "points.jsonl.gz", "rt", encoding="utf-8") as handle:
            for line in handle:
                fit = json.loads(line)
                r, j, k = fit["repetition"], cj[fit["condition"]], mi[fit["method"]]
                entry, centered_hash = records[fit["record_id"]]
                require(
                    not seen[r, j, k] and (r, fit["condition"]) in signalkeys,
                    "point grid/duplicate",
                )
                require(
                    fit["run_identity_sha256"] == RUN
                    and fit["parent_id"] == entry["parent_id"]
                    and fit["repetition"] == entry["repetition"]
                    and fit["condition"] == entry["condition"],
                    "point alignment",
                )
                require(
                    all(
                        fit[key] == row[key]
                        for key in ["cell", "family", "parameter", "n", "H_target"]
                    ),
                    "point context",
                )
                require(
                    fit["parameters"] == settings[k]["params"]
                    and fit["base_method"] == settings[k]["base"],
                    "point settings",
                )
                require(
                    fit["treatment"] == ("sample_centered" if settings[k]["center"] else "raw"),
                    "point treatment",
                )
                require(
                    fit["input_sha256"] == entry["sha256"]
                    and fit["analysed_sha256"]
                    == (centered_hash if settings[k]["center"] else entry["sha256"]),
                    "analyzed input hash",
                )
                require(fit["target_role"] == "latent_clean_recovery", "point target role")
                require(
                    np.isfinite(fit["elapsed_seconds"]) and fit["elapsed_seconds"] >= 0,
                    "point runtime",
                )
                seen[r, j, k], runtime[r, j, k] = True, fit["elapsed_seconds"]
                if fit["valid"]:
                    require(
                        fit["point"] is not None and np.isfinite(fit["point"]), "point finite flag"
                    )
                    points[r, j, k] = fit["point"]
                    local["valid_point_fits"] += 1
                else:
                    require(bool(fit["failure_reason"]), "unexplained point failure")
                local["point_fits"] += 1
        expected_r = list(range(start, min(stop, icount)))
        require(
            [v["repetition"] for v in meta["interval_records"]] == expected_r,
            "interval parent selection",
        )
        require(draws.shape == (len(expected_r), 9, B), "draw shape")
        for index, entry in enumerate(meta["interval_records"]):
            r, result = entry["repetition"], entry["result"]
            require(
                entry["parent_id"] == parents[r][1]["record_id"]
                and entry["input_sha256"] == parents[r][1]["sha256"],
                "interval parent linkage",
            )
            local["interval_parents"] += 1
            model[r] = result["model"] is not None
            if model[r]:
                fitmodel = result["model"]
                require(
                    fitmodel["bounds"] == [0.01, 0.99]
                    and 0.01 <= fitmodel["H"] <= 0.99
                    and fitmodel["sigma"] > 0
                    and fitmodel["optimizer_success"],
                    "model parameters",
                )
                boundary[r] = fitmodel["boundary_hit"]
                require(
                    boundary[r] == (min(fitmodel["H"] - 0.01, 0.99 - fitmodel["H"]) <= 0.001),
                    "model boundary flag",
                )
            for pool, details in result["pools"].items():
                require(
                    details["seed"] == seed(cell, r, "confirmation_" + pool)
                    and details["requested_records"] == B,
                    "pool seed/budget",
                )
                local["physical_bootstrap_records"] += details["generated_records"]
                for statistic, accounting in details["accounting"].items():
                    values = draws[index, STREAMS.index((pool, statistic))]
                    require(
                        accounting["used"] == int(np.isfinite(values).sum()),
                        "finite draw accounting",
                    )
                    require(
                        accounting["attempted"]
                        == accounting["used"] + accounting["failed"] + accounting["invalid"],
                        "draw attempts",
                    )
                    require(accounting["attempted"] + accounting["unattempted"] == B, "draw budget")
                    local["statistic_attempts"] += accounting["attempted"]
                    for key in ["used", "failed", "invalid", "unattempted"]:
                        counters["statistic_" + key] += accounting[key]
            for ci in result["intervals"]:
                k = LABELS.index((ci["method"], ci["candidate"]))
                require(
                    not ciseen[r, k] and ci["draws"] == B and ci["nominal"] == 0.95,
                    "interval definition",
                )
                require(
                    ci["point"] == result["points"][ci["treatment"] + ":" + ci["method"]],
                    "interval point linkage",
                )
                expected = endpoints(ci, result, draws[index], n)
                point_method = ci["method"] + (
                    "::centered"
                    if ci["treatment"] == "centered" and ci["method"] in ("Higuchi", "GHE")
                    else ""
                )
                close(ci["point"], points[r, 0, mi[point_method]], "point/interval study agreement")
                require(ci["available"] == (expected is not None), "interval availability")
                if expected is not None:
                    close([ci["ci_low"], ci["ci_high"]], expected, "interval endpoints")
                    require(ci["unavailable_reason"] is None, "available interval reason")
                    counters["available_intervals"] += 1
                else:
                    require(
                        ci["ci_low"] is None and ci["ci_high"] is None and ci["unavailable_reason"],
                        "unavailable interval reason",
                    )
                low[r, k], high[r, k], available[r, k], ciseen[r, k] = (
                    ci["ci_low"],
                    ci["ci_high"],
                    ci["available"],
                    True,
                )
                local["interval_rows"] += 1
        require(
            all(local[k] == v for k, v in receipt["counts"].items()),
            f"receipt counts: {dict(local)} vs {receipt['counts']}",
        )
        counters.update(local)
        counters["chunks"] += 1
    expected = np.zeros(shape, bool)
    expected[:, 0] = True
    expected[:s] = True
    require(np.array_equal(expected, seen) and ciseen.all(), "full attempt grid")
    return {
        "points": points,
        "runtime": runtime,
        "methods": methods,
        "conditions": conditions,
        "low": low,
        "high": high,
        "available": available,
        "model": model,
        "boundary": boundary,
    }


def safe_ratio(a, b, floor=0):
    a, b = np.broadcast_arrays(np.asarray(a, float), np.asarray(b, float))
    return np.divide(a, b, out=np.full(a.shape, np.nan), where=b > floor)


def wilson(successes, n):
    if n == 0:
        return np.array([np.nan, np.nan])
    z = NormalDist().inv_cdf(0.975)
    p = successes / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return np.array([center - half, center + half])


def se(values):
    return (
        np.std(values, ddof=1, axis=0) / np.sqrt(len(values))
        if len(values) > 1
        else np.full(np.shape(values)[1:], np.nan)
    )


def sampled_means(values, key):
    """Literal parent gathering; never call the producer's count-matrix reducer."""
    n = len(values)
    if n < 2:
        return np.full((len(SELECTED), *values.shape[1:]), np.nan)
    payload = f"lrdbench-confirmation-summary-v1:20260916:{key}".encode()
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:8], "little"))
    indices = rng.integers(0, n, (B, n))[SELECTED]
    return np.asarray([np.mean(values[selection], axis=0) for selection in indices])


def point_expected(data, row, scope):
    count = row["accuracy_parents"] if scope == "accuracy" else row["stress_parents"]
    nc = 1 if scope == "accuracy" else len(data["conditions"])
    p, t = data["points"][:count, :nc], data["runtime"][:count, :nc]
    valid = np.isfinite(p)
    common = valid.all(axis=(1, 2))
    e = p[common] - row["H_target"]
    drift = p[common] - p[common, :1]
    primitive = np.stack([e, abs(e), e * e, drift, abs(drift)], axis=-1)
    full = np.stack(
        [valid, valid & ((p < 0) | (p > 1)), valid & (p >= 0.6), np.nan_to_num(t)], axis=-1
    )
    key = f"{RUN}:{row['cell']}:{scope}"
    avg, boot, errors = primitive.mean(0), sampled_means(primitive, key + ":common"), se(primitive)
    favg, fboot = full.mean(0), sampled_means(full, key + ":all_attempts")
    result = {}

    def add(
        method,
        condition,
        metric,
        value,
        samples,
        used,
        support,
        stderr=np.nan,
        contrast="",
        successes=None,
        denominator=None,
    ):
        result[method, condition, metric, contrast] = {
            "value": value,
            "samples": samples,
            "parents_attempted": count,
            "parents_used": used,
            "parents_excluded": count - used,
            "support": support,
            "mcse": stderr,
            "successes": successes,
            "denominator": denominator,
        }

    support = "common_complete_all_declared_methods_conditions"
    used = int(common.sum())
    for j, condition in enumerate(data["conditions"][:nc]):
        for k, method in enumerate(data["methods"]):
            for name, ix in [("bias", 0), ("mae", 1), ("mse", 2)]:
                add(
                    method,
                    condition,
                    name,
                    avg[j, k, ix],
                    boot[:, j, k, ix],
                    used,
                    support,
                    errors[j, k, ix],
                )
            rmse = np.sqrt(avg[j, k, 2])
            add(
                method,
                condition,
                "rmse",
                rmse,
                np.sqrt(boot[:, j, k, 2]),
                used,
                support,
                errors[j, k, 2] / (2 * rmse) if rmse else np.nan,
            )
            for name, ix in [
                ("validity", 0),
                ("outside_0_1", 1),
                ("H_ge_0p6_exceedance_diagnostic", 2),
            ]:
                denom = int(valid[:, j, k].sum()) if ix else count
                successes = int(full[:, j, k, ix].sum())
                samples = (
                    safe_ratio(fboot[:, j, k, ix], fboot[:, j, k, 0]) if ix else fboot[:, j, k, ix]
                )
                add(
                    method,
                    condition,
                    name,
                    successes / denom if denom else np.nan,
                    samples,
                    denom,
                    "method_valid_points" if ix else "all_attempts",
                    successes=successes,
                    denominator=denom,
                )
            add(
                method,
                condition,
                "mean_runtime_seconds",
                favg[j, k, 3],
                fboot[:, j, k, 3],
                count,
                "all_attempts",
                se(t[:, j, k]),
            )
            if j:
                for name, value, samples, individual in [
                    (
                        "absolute_error_inflation",
                        avg[j, k, 1] - avg[0, k, 1],
                        boot[:, j, k, 1] - boot[:, 0, k, 1],
                        primitive[:, j, k, 1] - primitive[:, 0, k, 1],
                    ),
                    (
                        "signed_estimate_drift",
                        avg[j, k, 3],
                        boot[:, j, k, 3],
                        primitive[:, j, k, 3],
                    ),
                    (
                        "absolute_estimate_drift",
                        avg[j, k, 4],
                        boot[:, j, k, 4],
                        primitive[:, j, k, 4],
                    ),
                ]:
                    add(method, condition, name, value, samples, used, support, se(individual))
                add(
                    method,
                    condition,
                    "paired_mae_ratio",
                    safe_ratio(avg[j, k, 1], avg[0, k, 1], 1e-12),
                    safe_ratio(boot[:, j, k, 1], boot[:, 0, k, 1], 1e-12),
                    used,
                    support,
                )
                add(
                    method,
                    condition,
                    "validity_loss",
                    favg[0, k, 0] - favg[j, k, 0],
                    fboot[:, 0, k, 0] - fboot[:, j, k, 0],
                    count,
                    "all_attempts",
                    se(full[:, 0, k, 0] - full[:, j, k, 0]),
                )
    for method in ["Higuchi", "GHE"]:
        a, b = data["methods"].index(method), data["methods"].index(method + "::centered")
        add(
            method,
            "clean",
            "mae_difference",
            avg[0, b, 1] - avg[0, a, 1],
            boot[:, 0, b, 1] - boot[:, 0, a, 1],
            used,
            support,
            se(primitive[:, 0, b, 1] - primitive[:, 0, a, 1]),
            "geometric_mean_removal_clean",
        )
        for j, condition in enumerate(data["conditions"][1:nc], 1):
            difference = (
                primitive[:, j, b, 1]
                - primitive[:, 0, b, 1]
                - primitive[:, j, a, 1]
                + primitive[:, 0, a, 1]
            )
            samples = boot[:, j, b, 1] - boot[:, 0, b, 1] - boot[:, j, a, 1] + boot[:, 0, a, 1]
            add(
                method,
                condition,
                "error_inflation_difference",
                difference.mean(),
                samples,
                used,
                support,
                se(difference),
                "geometric_mean_removal_stress",
            )
            add(
                method,
                condition,
                "absolute_drift_difference",
                avg[j, b, 4] - avg[j, a, 4],
                boot[:, j, b, 4] - boot[:, j, a, 4],
                used,
                support,
                se(primitive[:, j, b, 4] - primitive[:, j, a, 4]),
                "geometric_mean_removal_stress",
            )
    return result, common


def interval_expected(data, row):
    a, lo, hi = data["available"], data["low"], data["high"]
    covered = a & (lo <= row["H_target"]) & (hi >= row["H_target"])
    widths = np.where(a, hi - lo, 0.0)
    n = len(a)
    key = f"{RUN}:{row['cell']}:intervals:all_interval_attempts"
    raw = np.stack([covered, a, widths], axis=-1)
    boot = sampled_means(raw, key)
    result = {}

    def add(
        method,
        candidate,
        metric,
        value,
        samples,
        used,
        support,
        stderr=np.nan,
        contrast="",
        successes=None,
        denominator=None,
    ):
        result[method, candidate, metric, contrast] = {
            "value": value,
            "samples": samples,
            "parents_attempted": n,
            "parents_used": used,
            "parents_excluded": n - used,
            "support": support,
            "mcse": stderr,
            "successes": successes,
            "denominator": denominator,
        }

    for j, (method, candidate) in enumerate(LABELS):
        success, avail = int(covered[:, j].sum()), int(a[:, j].sum())
        for metric, denom, samples in [
            ("unconditional_coverage", n, boot[:, j, 0]),
            ("availability", n, boot[:, j, 1]),
            ("conditional_coverage", avail, safe_ratio(boot[:, j, 0], boot[:, j, 1])),
        ]:
            numerator = avail if metric == "availability" else success
            add(
                method,
                candidate,
                metric,
                numerator / denom if denom else np.nan,
                samples,
                denom,
                "available_intervals"
                if metric == "conditional_coverage"
                else "all_attempts_unavailable_is_miss",
                successes=numerator,
                denominator=denom,
            )
        w = widths[a[:, j], j]
        add(
            method,
            candidate,
            "mean_width",
            w.mean() if avail else np.nan,
            safe_ratio(boot[:, j, 2], boot[:, j, 1]),
            avail,
            "available_intervals",
            se(w),
        )
        add(
            method,
            candidate,
            "median_width",
            np.median(w) if avail else np.nan,
            np.full(len(SELECTED), np.nan),
            avail,
            "available_intervals",
        )
    pairs = [
        ("interval_centering", "cbc_raw_" + v, "cbc_centered_" + v) for v in ["percentile", "basic"]
    ]
    pairs += [
        ("interval_construction", "cbc_" + v + "_percentile", "cbc_" + v + "_basic")
        for v in ["raw", "centered"]
    ]
    pairs += [("interval_model", "cbc_centered_basic", "unknown_fgn_centered_basic")]
    for method in IMETHODS:
        for contrast, left, right in pairs:
            j, k = LABELS.index((method, left)), LABELS.index((method, right))
            condition = right + "_minus_" + left
            difference = covered[:, k].astype(float) - covered[:, j]
            add(
                method,
                condition,
                "coverage_difference",
                difference.mean(),
                boot[:, k, 0] - boot[:, j, 0],
                n,
                "all_attempts_unavailable_is_miss",
                se(difference),
                contrast,
            )
            common = a[:, j] & a[:, k]
            d = widths[:, k] - widths[:, j]
            wb = sampled_means(np.column_stack([common, np.where(common, d, 0)]), key)
            add(
                method,
                condition,
                "mean_width_difference",
                d[common].mean() if common.any() else np.nan,
                safe_ratio(wb[:, 1], wb[:, 0]),
                int(common.sum()),
                "pair_common_available_intervals_resample_all_attempts_then_condition",
                se(d[common]),
                contrast,
            )
    for name, flags in [
        ("model_boundary_rate_all_attempts", data["boundary"]),
        ("model_fit_availability", data["model"]),
    ]:
        add(
            "unknown_mean_fGn_ML",
            "clean",
            name,
            flags.mean(),
            sampled_means(flags.astype(float), key),
            n,
            "all_model_attempts",
            successes=int(flags.sum()),
            denominator=n,
        )
    return result


def read_group(folder):
    frame = pd.read_csv(folder / "summary.csv", keep_default_na=False, float_precision="round_trip")
    for key in set(NUMERIC) & set(frame.columns):
        frame[key] = pd.to_numeric(frame[key], errors="coerce")
    with np.load(folder / "draws.npz", allow_pickle=False) as bundle:
        draws = bundle["values"]
    require(draws.shape == (B, len(frame)), "summary draw shape")
    require(not frame.duplicated(KEYS).any(), "duplicate summary key")
    return frame, draws


def check_summary(folder, expected, counters):
    frame, draws = read_group(folder)
    keys = list(frame[KEYS].itertuples(index=False, name=None))
    require(set(keys) == set(expected), f"summary roster {folder.name}")
    close(frame.value.to_numpy(), [expected[k]["value"] for k in keys], folder.name + " values")
    close(
        draws[SELECTED],
        np.column_stack([expected[k]["samples"] for k in keys]),
        folder.name + " sampled draws",
    )
    for i, saved in enumerate(frame.to_dict("records")):
        truth = expected[keys[i]]
        for key in ["parents_attempted", "parents_used", "parents_excluded", "support"]:
            require(saved[key] == truth[key], f"{folder.name}: {key}")
        distribution = draws[:, i]
        finite = np.isfinite(distribution)
        require(
            saved["requested_draws"] == B
            and saved["used_draws"] == int(finite.sum())
            and saved["invalid_draws"] == int((~finite).sum()),
            "summary draw accounting",
        )
        complete = finite.all() and np.isfinite(truth["value"])
        bounds = np.quantile(distribution, [0.025, 0.975]) if complete else [np.nan, np.nan]
        stderr = truth["mcse"]
        if truth["successes"] is not None:
            success, denom = truth["successes"], truth["denominator"]
            require(
                saved["successes"] == success
                and saved["denominator"] == denom
                and saved["interval_method"] == "Wilson_95",
                "binomial accounting",
            )
            bounds = wilson(success, denom)
            stderr = (
                np.sqrt((success / denom) * (1 - success / denom) / denom)
                if 0 < success < denom
                else np.nan
            )
        else:
            require(
                np.isnan(saved["successes"])
                and np.isnan(saved["denominator"])
                and saved["interval_method"] == "joint_parent_percentile",
                "continuous accounting",
            )
        close([saved["ci_low"], saved["ci_high"]], bounds, "summary interval")
        close(saved["mcse"], stderr, "MCSE")
        close(
            saved["bootstrap_se"], distribution.std(ddof=1) if complete else np.nan, "bootstrap SE"
        )
    counters["cell_summary_rows"] += len(frame)
    counters["cell_summary_draw_positions_inspected"] += draws.size
    counters["cell_summary_draws_reconstructed"] += len(frame) * len(SELECTED)
    return frame


def aggregate_expected(frames, matrices):
    """Equal-cell summaries; nonlinear estimands calculated after averaging."""
    keys = list(frames[0][KEYS].itertuples(index=False, name=None))
    require(
        all(list(f[KEYS].itertuples(index=False, name=None)) == keys for f in frames),
        "domain roster",
    )
    values = np.mean([f.value.to_numpy() for f in frames], axis=0)
    draws = sum(matrices) / len(matrices)
    lookup = {key: i for i, key in enumerate(keys)}
    for i, (method, condition, metric, contrast) in enumerate(keys):
        if metric == "rmse":
            j = lookup[method, condition, "mse", contrast]
            values[i], draws[:, i] = np.sqrt(values[j]), np.sqrt(draws[:, j])
        elif metric == "paired_mae_ratio":
            j, k = (
                lookup[method, condition, "mae", contrast],
                lookup[method, "clean", "mae", contrast],
            )
            values[i], draws[:, i] = (
                safe_ratio(values[j], values[k], 1e-12),
                safe_ratio(draws[:, j], draws[:, k], 1e-12),
            )
    keep = [i for i, k in enumerate(keys) if k[2] != "median_width"]
    return [keys[i] for i in keep], values[keep], draws[:, keep]


def main(source, lockpath, output):
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=True)
    run, lock = read_json(source / "run.json"), read_json(lockpath)
    require(run["identity_sha256"] == digest(run["identity"]) == RUN, "run identity")
    require(digest(lock["design"]) == DESIGN, "design identity")
    design = lock["design"]
    rows = grid(design["protocol"])
    expected_chunks = {
        f"{row['cell']}__r{i:05}_{min(i + 32, row['accuracy_parents']):05}"
        for row in rows
        for i in range(0, row["accuracy_parents"], 32)
    }
    require({p.name for p in (source / "chunks").iterdir()} == expected_chunks, "chunk roster")
    manifest = read_json(source / "summaries/complete.json")
    require(
        manifest["specification"]["run_identity_sha256"] == RUN
        and manifest["mode"] == "confirmation",
        "summary run",
    )
    for name, sha in manifest["files"].items():
        require(file_hash(source / "summaries" / name) == sha, "summary checksum: " + name)
    counters, domains, cell_reports, export_frames = Counter(), {}, [], []
    for row in rows:
        data = load_raw(source, row, design, counters)
        for scope in ["accuracy", "stress", "intervals"]:
            if (
                scope == "stress"
                and not row["stress_parents"]
                or scope == "intervals"
                and not row["interval_parents"]
            ):
                continue
            folder = source / "summaries" / f"{scope}__{row['cell']}"
            support = read_json(folder / "support.json.gz")
            expected = (
                interval_expected(data, row)
                if scope == "intervals"
                else point_expected(data, row, scope)[0]
            )
            frame = check_summary(folder, expected, counters)
            count = (
                row["interval_parents"]
                if scope == "intervals"
                else row["accuracy_parents"]
                if scope == "accuracy"
                else row["stress_parents"]
            )
            require(
                support["parent_id_order"] == [f"{row['cell']}_r{r}" for r in range(count)]
                and support["run_identity_sha256"] == RUN,
                "support parent order",
            )
            require(
                frame.run_identity_sha256.eq(RUN).all()
                and frame.cell.eq(row["cell"]).all()
                and frame.domain.eq(row["family"]).all(),
                "summary context",
            )
            if scope != "intervals":
                nc = 1 if scope == "accuracy" else len(data["conditions"])
                valid = np.isfinite(data["points"][:count, :nc])
                common = valid.all(axis=(1, 2))
                require(
                    support["complete_parent_indices"] == np.flatnonzero(common).tolist()
                    and support["excluded_parent_indices"] == np.flatnonzero(~common).tolist(),
                    "common support",
                )
            else:
                require(
                    support["model_failures"] == np.flatnonzero(~data["model"]).tolist()
                    and support["model_boundary_hits"] == np.flatnonzero(data["boundary"]).tolist(),
                    "model support",
                )
            role = row["interval_role"] if scope == "intervals" else "all_lengths"
            domains.setdefault((scope, row["family"], role), []).append(folder)
            export_frames.append(
                pd.read_csv(
                    folder / "summary.csv", keep_default_na=False, float_precision="round_trip"
                )
            )
        cell_reports.append(
            {
                **row,
                "available_intervals": int(data["available"].sum()),
                "model_failures": int((~data["model"]).sum()),
                "model_boundary_hits": int(data["boundary"].sum()),
            }
        )
        print(f"Verified {row['cell']} ({len(cell_reports)}/{len(rows)})", flush=True)
    for (scope, domain, role), paths in domains.items():
        parts = [read_group(p) for p in paths]
        frames, matrices = zip(*parts, strict=True)
        keys, values, draws = aggregate_expected(frames, matrices)
        folder = source / "summaries" / f"{scope}__domain_{domain}_{role}"
        frame, saved = read_group(folder)
        require(list(frame[KEYS].itertuples(index=False, name=None)) == keys, "domain keys")
        close(frame.value.to_numpy(), values, "domain values")
        close(saved, draws, "all domain draws")
        keep = frames[0].metric.ne("median_width").to_numpy()
        for key in ["parents_attempted", "parents_used", "parents_excluded"]:
            require(
                np.array_equal(frame[key].to_numpy(), sum(f[key].to_numpy() for f in frames)[keep]),
                "domain support counts",
            )
        require(
            frame.domain_cells.eq(len(paths)).all() and frame.cell_weight.eq(1 / len(paths)).all(),
            "domain weights",
        )
        for i, savedrow in enumerate(frame.to_dict("records")):
            distribution = draws[:, i]
            finite = np.isfinite(distribution)
            complete = finite.all() and np.isfinite(values[i])
            close(
                [savedrow["ci_low"], savedrow["ci_high"]],
                np.quantile(distribution, [0.025, 0.975]) if complete else [np.nan, np.nan],
                "domain interval",
            )
            close(
                savedrow["bootstrap_se"],
                distribution.std(ddof=1) if complete else np.nan,
                "domain bootstrap SE",
            )
            require(
                savedrow["used_draws"] == finite.sum()
                and savedrow["invalid_draws"] == (~finite).sum(),
                "domain draw accounting",
            )
            require(
                np.isnan(savedrow["mcse"])
                and np.isnan(savedrow["successes"])
                and np.isnan(savedrow["denominator"]),
                "domain uncertainty type",
            )
        counters["domain_summary_rows"] += len(frame)
        counters["domain_summary_draws_reconstructed"] += draws.size
        export_frames.append(
            pd.read_csv(folder / "summary.csv", keep_default_na=False, float_precision="round_trip")
        )
        print(f"Verified domain {scope}/{domain}/{role}", flush=True)
        del parts, matrices, saved, draws
    canonical_frame = pd.read_csv(
        source / "summaries/canonical_summary.csv",
        keep_default_na=False,
        float_precision="round_trip",
    )
    recombined = pd.concat(export_frames, ignore_index=True).fillna("")
    compare_exports(canonical_frame, recombined)
    require(
        len(canonical_frame) == manifest["summary_rows"] == 118917
        and len(export_frames) == manifest["groups"] == 68,
        "canonical totals",
    )
    pd.DataFrame(cell_reports).to_csv(output / "cell_accounting.csv", index=False)
    evidence = {
        "status": "passed",
        "audited_utc": datetime.now(UTC).isoformat(),
        "run_identity_sha256": RUN,
        "scientific_design_sha256": DESIGN,
        "source": str(source.resolve()),
        "summary_manifest_sha256": file_hash(source / "summaries/complete.json"),
        "audit_source_sha256": file_hash(Path(__file__)),
        "audit_specification_sha256": file_hash(Path(__file__).with_name("README.md")),
        "selected_summary_draw_indices": SELECTED.tolist(),
        "counts": dict(counters),
        "elapsed_seconds": time.monotonic() - started,
        "limits": [
            "No full estimator refit or clean-parent simulation rerun in this package.",
            "31 of 1999 cell summary draws reconstructed from raw parents; all saved draw positions inspected for interval/SE reconstruction.",
            "All domain draw positions reconstructed from verified cell outputs.",
        ],
    }
    (output / "audit_evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2), flush=True)


def compare_exports(canonical_frame, recombined):
    """Parse declared numeric columns explicitly; never infer across CSV chunks.

    Empty domain fields and median intervals cause pandas' mixed-type inference.
    Python's float parser preserves the exact serialized binary64 values.
    """
    left, right = canonical_frame.copy(), recombined.copy()
    for column in NUMERIC + ["parameter", "n", "H_target", "nominal"]:
        if column in left:
            for table in [left, right]:
                table[column] = table[column].map(lambda v: np.nan if v == "" else float(v))
    sorting = ["scope", "cell", "domain", "interval_role", *KEYS]
    pd.testing.assert_frame_equal(
        left.sort_values(sorting).reset_index(drop=True),
        right.sort_values(sorting).reset_index(drop=True),
        check_dtype=False,
        check_exact=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.source, args.lock, args.output)
