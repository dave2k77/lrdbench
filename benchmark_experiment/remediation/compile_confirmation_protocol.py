"""Expand and lock a scientific protocol without generating confirmation data."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pywt
from scipy.stats import norm

from lrdbench.defaults import build_default_contamination_registry

try:
    from . import confirmation_intervals as intervals
    from . import materialize_shared_stress as stress_inputs
    from . import run_shared_stress as stress
except ImportError:
    import confirmation_intervals as intervals
    import materialize_shared_stress as stress_inputs
    import run_shared_stress as stress

shared = stress.shared
DEFAULT = Path(__file__).with_name("confirmation-protocol-v1.json")


def load_protocol(path=DEFAULT):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def grid(block):
    return shared.cells(block)


def point_settings(n):
    rows = copy.deepcopy(stress.roster())
    for row in rows:
        p, base = row["params"], row["base"]
        p.pop("bootstrap_block_len", None)
        p.pop("ci_levels", None)
        if base == "RS":
            p.update(
                min_scale=8, max_scale=n // 2, scale_ratio=1.5, use_anis_lloyd_correction=False
            )
        if base in {"AbsoluteMoment", "Variance", "VarianceResidual"}:
            p.setdefault("scale_ratio", 1.5)
        if base == "GHE":
            p.update(n_scales=18, h_min=1, h_max=(n + 1) // 8, q=1.0)
        row["n"] = n
        row["target_estimand"] = "hurst_scaling_proxy"
        if base == "WaveletOLS":
            maximum = pywt.dwt_max_level(n, pywt.Wavelet(p["wavelet"]).dec_len)
            row["retained_wavelet_levels"] = list(
                range(p["j_drop_high"] + 1, maximum - p["j_drop_low"] + 1)
            )
            if len(row["retained_wavelet_levels"]) < 3:
                raise ValueError("Frozen wavelet band has fewer than three levels.")
        if base in {"GPH", "ModifiedLocalWhittle", "WhittleMLE"}:
            row["lowest_frequency_cycles_per_sample"] = 1 / n
            row["highest_frequency_cycles_per_sample"] = p["m"] / n
    return rows


def contamination_conditions(protocol):
    s, rows = protocol["stress"], []

    def add(op, params):
        label = op + "__" + "__".join(f"{k}_{v:g}" for k, v in sorted(params.items()))
        rows.append({"id": label, "operator": op, "params": params})

    for shift in s["offset_shifts"]:
        add("constant_offset", {"shift": shift})
    for shift in s["step_shifts"]:
        for position in s["step_positions"]:
            add("step_change", {"shift": shift, "position": position})
    for rate in s["outlier_rates"]:
        for amplitude in s["outlier_amplitudes"]:
            add("outliers", {"rate": rate, "amplitude": amplitude})
    for order in s["polynomial_orders"]:
        for strength in s["polynomial_strengths"]:
            add("polynomial_trend", {"order": order, "strength": strength})
    for df in s["student_t_df"]:
        for scale in s["student_t_scales"]:
            add("heavy_tail_noise", {"df": df, "scale": scale})
    return sorted(rows, key=lambda row: row["id"])


def data_config(protocol, *, rehearsal=False, repetitions=None):
    return {
        "seed_namespace": protocol["randomness"][
            "rehearsal_namespace" if rehearsal else "confirmation_namespace"
        ],
        "global_seed": protocol["randomness"]["global_seed"],
        "lengths": protocol["accuracy"]["lengths"],
        "processes": protocol["accuracy"]["processes"],
        "repetitions": protocol["accuracy"]["repetitions"] if repetitions is None else repetitions,
    }


def validate(protocol):
    expected = {
        "schema_version",
        "protocol_id",
        "phase",
        "signal",
        "target",
        "randomness",
        "accuracy",
        "stress",
        "intervals",
        "summaries",
        "planned_contrasts",
        "claim_exclusions",
        "execution",
    }
    if (
        set(protocol) != expected
        or protocol["schema_version"] != 1
        or protocol["phase"] != "scientific_design_before_confirmation"
    ):
        raise ValueError("Unexpected scientific protocol schema or phase.")
    if protocol["execution"]["status"] != "design_only_no_confirmation_inputs_generated":
        raise ValueError("Compilation does not authorize an unvalidated execution release.")
    fixed = {
        "signal": "stationary_scalar_increments_no_physical_sampling_rate",
        "target": "fGn_H__ARFIMA_d_plus_half__AR1_asymptotic_half",
    }
    if any(protocol[k] != value for k, value in fixed.items()):
        raise ValueError("Signal/target differs from the implemented study.")
    if (
        protocol["accuracy"]["roster"] != "audited_19_plus_centered_geometric_v1"
        or protocol["accuracy"]["generator"]
        != "exact_covariance_cholesky_no_jitter_or_stationary_AR1_recursion"
    ):
        raise ValueError("Unsupported point roster or generator definition.")
    random = protocol["randomness"]
    namespaces = [
        random[k]
        for k in ("confirmation_namespace", "rehearsal_namespace", "stress_seed_namespace")
    ]
    if any(not isinstance(n, str) or not n for n in namespaces) or len(set(namespaces)) != 3:
        raise ValueError("Confirmation, rehearsal and contamination namespaces must differ.")
    if type(random["global_seed"]) is not int or random["global_seed"] < 0:
        raise ValueError("Invalid global seed.")
    for name in (
        "mean-comparison.json",
        "interval-comparison.json",
        "calibration-screen.json",
        "shared-stress.json",
    ):
        old = json.loads(DEFAULT.with_name(name).read_text(encoding="utf-8"))
        if old.get("seed_namespace") in namespaces:
            raise ValueError("A confirmation namespace reuses a development namespace.")
    blocks = [
        protocol["accuracy"],
        protocol["stress"],
        protocol["intervals"]["core"],
        protocol["intervals"]["length_sensitivity"],
    ]
    for block in blocks:
        if type(block["repetitions"]) is not int or block["repetitions"] < 2:
            raise ValueError("Every fixed cell needs at least two independent parents.")
        if (
            not block["lengths"]
            or len(set(block["lengths"])) != len(block["lengths"])
            or any(type(n) is not int or n < 512 for n in block["lengths"])
        ):
            raise ValueError("Invalid or ineligible record lengths.")
        if not block["processes"] or set(block["processes"]) - {"fGn", "ARFIMA", "AR1"}:
            raise ValueError("Unsupported process family.")
        for family, values in block["processes"].items():
            low, high = {"fGn": (0, 1), "ARFIMA": (-0.5, 0.5), "AR1": (-1, 1)}[family]
            if (
                not values
                or len(set(values)) != len(values)
                or any(not low < value < high for value in values)
            ):
                raise ValueError("Invalid process parameter.")
    parents = {shared.cell_id(c) for c in grid(blocks[0])}
    for block in blocks[1:]:
        if {shared.cell_id(c) for c in grid(block)} - parents or block["repetitions"] > blocks[0][
            "repetitions"
        ]:
            raise ValueError("Substudy must select existing main-study parents.")
    if {shared.cell_id(c) for c in grid(blocks[2])} & {shared.cell_id(c) for c in grid(blocks[3])}:
        raise ValueError("Core and sensitivity interval cells overlap.")
    p = protocol["intervals"]
    if (
        p["input_conditions"] != ["clean"]
        or p["nominal"] != 0.95
        or p["methods"] != list(intervals.METHODS)
    ):
        raise ValueError(
            "This compiled interval implementation is restricted to clean, central 95% comparisons."
        )
    if p["candidates"] != [*intervals.CANDIDATES, "gph_normal_raw"] or p[
        "normal_candidate_methods"
    ] != ["GPH::narrow_band"]:
        raise ValueError("Unsupported interval candidate roster.")
    if (
        p["block_rule"] != "floor_n_divided_by_16"
        or p["availability"] != "finite_original_point_and_every_requested_statistic_draw"
    ):
        raise ValueError("Interval rules differ from the implemented kernel.")
    if (
        p["model"] != "stationary_gaussian_fgn_unknown_constant_mean_profile_ML"
        or p["mean_rule"] != "sample_center_each_record_and_each_bootstrap_record_separately"
    ):
        raise ValueError("Model or mean treatment differs from the implemented kernel.")
    if type(p["bootstrap_draws"]) is not int or p["bootstrap_draws"] < 1999:
        raise ValueError("Confirmation requires at least 1,999 within-record draws.")
    summary = protocol["summaries"]
    if (
        summary["nominal"] != 0.95
        or type(summary["bootstrap_draws"]) is not int
        or summary["bootstrap_draws"] < 1999
    ):
        raise ValueError("Invalid parent-summary precision settings.")
    for block, label in ((blocks[2], "core"), (blocks[3], "secondary")):
        if (
            np.sqrt(0.95 * 0.05 / block["repetitions"])
            > summary["precision"][f"{label}_coverage_mcse_at_0p95_max"]
        ):
            raise ValueError("Requested repetitions do not meet declared coverage MCSE.")
    # Apply the operator validator to the fully expanded grid, not just examples.
    proxy = {
        "schema_version": 1,
        "stage": "development_shared_parent_stress",
        "clean_pool_identity_sha256": "compiler_no_parent_generation",
        "seed_namespace": random["stress_seed_namespace"],
        "global_seed": random["global_seed"],
        "lengths": blocks[1]["lengths"],
        "processes": blocks[1]["processes"],
        "repetitions": blocks[1]["repetitions"],
        "conditions": contamination_conditions(protocol),
        "summary": {
            "draws": summary["bootstrap_draws"],
            "seed": summary["seed"],
            "nominal": summary["nominal"],
            "denominator_floor": summary["denominator_floor"],
        },
    }
    stress_inputs.validate_config(proxy)
    for n in blocks[0]["lengths"]:
        point_settings(n)


def cell_table(protocol):
    stress_counts = {
        shared.cell_id(c): protocol["stress"]["repetitions"] for c in grid(protocol["stress"])
    }
    interval_counts = {
        shared.cell_id(c): (block["repetitions"], label)
        for label in ("core", "length_sensitivity")
        for block in [protocol["intervals"][label]]
        for c in grid(block)
    }
    rows = []
    for cell in grid(protocol["accuracy"]):
        label = shared.cell_id(cell)
        ci_count, role = interval_counts.get(label, (0, "none"))
        rows.append(
            {
                "cell": label,
                **cell,
                "H_target": stress_inputs.target(cell),
                "accuracy_parents": protocol["accuracy"]["repetitions"],
                "stress_parents": stress_counts.get(label, 0),
                "interval_parents": ci_count,
                "interval_role": role,
                "input_generator": "stationary_AR1_recursion"
                if cell["family"] == "AR1"
                else "covariance_Cholesky_no_jitter",
                "scale": "innovation_sd_1" if cell["family"] == "ARFIMA" else "marginal_sd_1",
            }
        )
    return pd.DataFrame(rows)


def workload(protocol):
    cells = cell_table(protocol)
    methods = len(point_settings(min(protocol["accuracy"]["lengths"])))
    parents, stress_parents, ci_parents = (
        int(cells[k].sum()) for k in ("accuracy_parents", "stress_parents", "interval_parents")
    )
    conditions = len(contamination_conditions(protocol))
    b = protocol["intervals"]["bootstrap_draws"]
    return {
        "accuracy_cells": len(cells),
        "independent_clean_parents": parents,
        "point_pipelines": methods,
        "clean_point_fits": parents * methods,
        "stress_cells": int(cells.stress_parents.gt(0).sum()),
        "stress_parent_subset": stress_parents,
        "contamination_conditions": conditions,
        "descendants": stress_parents * conditions,
        "stressed_point_fits": stress_parents * conditions * methods,
        "total_point_fits": (parents + stress_parents * conditions) * methods,
        "interval_cells": int(cells.interval_parents.gt(0).sum()),
        "interval_parent_subset": ci_parents,
        "interval_model_fits": ci_parents,
        "interval_point_statistics": ci_parents * 6,
        "interval_rows": ci_parents * 16,
        "within_record_draws_per_pool": b,
        "physical_bootstrap_records": ci_parents * 2 * b,
        "bootstrap_statistic_attempts": ci_parents * 9 * b,
        "summary_draws_per_domain": protocol["summaries"]["bootstrap_draws"],
        "descendants_and_interval_subsets_add_independent_parents": False,
        "raw_clean_signal_bytes": int(
            sum(row.accuracy_parents * row.n * 8 for row in cells.itertuples())
        ),
        "raw_descendant_signal_bytes": int(
            sum(row.stress_parents * conditions * row.n * 8 for row in cells.itertuples())
        ),
    }


def precision_table(protocol):
    rows = []
    for role, repetitions in (
        ("accuracy", protocol["accuracy"]["repetitions"]),
        ("stress", protocol["stress"]["repetitions"]),
        ("interval_core", protocol["intervals"]["core"]["repetitions"]),
        ("interval_length_sensitivity", protocol["intervals"]["length_sensitivity"]["repetitions"]),
    ):
        for proportion in (0.95, 0.5):
            se = np.sqrt(proportion * (1 - proportion) / repetitions)
            rows.append(
                {
                    "role": role,
                    "independent_parents_per_cell": repetitions,
                    "assumed_event_probability": proportion,
                    "mcse": se,
                    "normal_95_halfwidth_planning_only": norm.ppf(0.975) * se,
                }
            )
    return pd.DataFrame(rows)


def seed_reservation(protocol):
    primary = data_config(protocol)
    rehearsal = data_config(protocol, rehearsal=True)
    confirmation_seeds, rehearsal_seeds, stream_seeds = set(), set(), set()
    hasher = hashlib.sha256()
    for cell in grid(protocol["accuracy"]):
        for r in range(protocol["accuracy"]["repetitions"]):
            seed = shared.record_seed(primary, cell, r, "input")
            if seed in confirmation_seeds:
                raise ValueError("Duplicate clean-data seed in the frozen grid.")
            confirmation_seeds.add(seed)
            rehearsal_seeds.add(shared.record_seed(rehearsal, cell, r, "input"))
            for stream in ("confirmation_cbc", "confirmation_fgn"):
                pool_seed = shared.record_seed(primary, cell, r, stream)
                if pool_seed in stream_seeds:
                    raise ValueError("Duplicate interval stream seed.")
                stream_seeds.add(pool_seed)
            hasher.update(shared.canonical([cell, r, str(seed)]).encode() + b"\n")
    if (
        confirmation_seeds & rehearsal_seeds
        or confirmation_seeds & stream_seeds
        or rehearsal_seeds & stream_seeds
    ):
        raise ValueError("Data/rehearsal/interval random streams overlap.")
    return {
        "clean_seed_count": len(confirmation_seeds),
        "reserved_interval_stream_seed_count": len(stream_seeds),
        "ordered_clean_seed_ledger_sha256": hasher.hexdigest(),
        "no_rehearsal_or_interval_seed_collisions": True,
        "confirmation_signals_generated": 0,
        "note": "Seed reservation is deterministic bookkeeping; distinct pseudorandom streams are not a mathematical independence proof.",
    }


def compile_protocol(protocol, output):
    validate(protocol)
    settings = [row for n in protocol["accuracy"]["lengths"] for row in point_settings(n)]
    registry = build_default_contamination_registry()
    conditions = [
        {**c, "version": registry.get(c["operator"]).version}
        for c in contamination_conditions(protocol)
    ]
    lock = {
        "protocol": protocol,
        "settings": settings,
        "conditions": conditions,
        "workload": workload(protocol),
        "seed_reservation": seed_reservation(protocol),
        "status": "scientific_design_locked_execution_release_still_required",
    }
    sha = shared.digest(lock)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "scientific_design_lock.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous["sha256"] != shared.digest(previous["design"]) or previous["sha256"] != sha:
            raise ValueError(
                "Refusing to overwrite a different or corrupted frozen scientific design; use a new version."
            )
    serial = json.dumps({"sha256": sha, "design": lock}, indent=2) + "\n"
    path.write_text(serial, encoding="utf-8", newline="\n")
    cell_table(protocol).to_csv(output / "cells.csv", index=False, lineterminator="\n")
    precision_table(protocol).to_csv(output / "precision.csv", index=False, lineterminator="\n")
    pd.DataFrame([{**row, "params": shared.canonical(row["params"])} for row in settings]).to_csv(
        output / "method_settings.csv", index=False, lineterminator="\n"
    )
    pd.DataFrame([{**row, "params": shared.canonical(row["params"])} for row in conditions]).to_csv(
        output / "conditions.csv", index=False, lineterminator="\n"
    )
    return {"scientific_design_sha256": sha, **lock["workload"], "confirmation_inputs_generated": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    protocol = load_protocol(args.protocol)
    validate(protocol)
    print(
        json.dumps(
            compile_protocol(protocol, args.output.resolve())
            if args.output
            else workload(protocol),
            indent=2,
        )
    )
