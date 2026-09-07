"""Import existing clean parents and verify independently applied stress descendants.

Research artifact schema, separate from the public benchmark export contract.
No estimator roster or summary setting enters an input ID or contamination seed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace

import numpy as np

from lrdbench.defaults import build_default_contamination_registry
from lrdbench.enums import SourceType
from lrdbench.schema import ProvenanceRecord, SeriesRecord, TruthSpec

try:
    from . import run_calibration as shared
except ImportError:
    import run_calibration as shared


def validate_config(config):
    fields = {
        "schema_version",
        "stage",
        "clean_pool_identity_sha256",
        "seed_namespace",
        "global_seed",
        "lengths",
        "processes",
        "repetitions",
        "conditions",
        "summary",
    }
    if set(config) != fields or config["schema_version"] != 1:
        raise ValueError("Expected shared stress schema 1 fields.")
    if config["stage"] != "development_shared_parent_stress":
        raise ValueError("This runner is a development study, not a frozen confirmation.")
    if not config["seed_namespace"] or not isinstance(config["seed_namespace"], str):
        raise ValueError("A seed namespace is required.")
    for key, minimum in (("global_seed", 0), ("repetitions", 1)):
        if type(config[key]) is not int or config[key] < minimum:
            raise ValueError(f"Invalid {key}.")
    lengths = config["lengths"]
    if (
        not lengths
        or len(set(lengths)) != len(lengths)
        or any(type(n) is not int or n < 512 for n in lengths)
    ):
        raise ValueError("The complete 19-configuration roster requires n >= 512 here.")
    if not config["processes"] or set(config["processes"]) - {"AR1", "ARFIMA", "fGn"}:
        raise ValueError("Unsupported or empty process roster.")
    for family, values in config["processes"].items():
        low, high = {"fGn": (0, 1), "ARFIMA": (-0.5, 0.5), "AR1": (-1, 1)}[family]
        if not values or len(set(values)) != len(values) or any(not low < v < high for v in values):
            raise ValueError("Invalid or duplicate process parameters.")
    conditions = config["conditions"]
    ids = [c["id"] for c in conditions]
    if (
        not ids
        or len(set(ids)) != len(ids)
        or "clean" in ids
        or any(not isinstance(s, str) or not s for s in ids)
    ):
        raise ValueError("Conditions require unique nonempty names, excluding clean.")
    definitions = []
    for condition in conditions:
        if set(condition) != {"id", "operator", "params"}:
            raise ValueError("Unexpected condition fields.")
        op, p = condition["operator"], condition["params"]
        expected = {
            "constant_offset": {"shift"},
            "step_change": {"shift", "position"},
            "outliers": {"rate", "amplitude"},
            "polynomial_trend": {"order", "strength"},
            "heavy_tail_noise": {"df", "scale"},
        }
        if (
            op not in expected
            or set(p) != expected[op]
            or not all(np.isfinite(v) for v in p.values())
        ):
            raise ValueError("An explicit finite operator definition is required.")
        if op == "step_change" and not 0 < p["position"] < 1:
            raise ValueError("A step must leave two nonempty segments.")
        if op == "step_change" and any(not 1 <= int(p["position"] * n) < n for n in lengths):
            raise ValueError("A step must leave two nonempty segments at every length.")
        if op == "outliers" and not (0 <= p["rate"] <= 1 and p["amplitude"] >= 0):
            raise ValueError("Invalid outlier rate or amplitude.")
        if op == "polynomial_trend" and (
            type(p["order"]) is not int or p["order"] not in (1, 2) or p["strength"] < 0
        ):
            raise ValueError("This audit covers polynomial sums of order 1 or 2 only.")
        if op == "heavy_tail_noise" and not (p["df"] > 2 and p["scale"] >= 0):
            raise ValueError("This development grid uses df > 2 and nonnegative noise scale.")
        definitions.append(shared.canonical([op, p]))
    if len(set(definitions)) != len(definitions):
        raise ValueError("Duplicate operator definitions under different labels.")
    summary = config["summary"]
    if set(summary) != {"draws", "seed", "nominal", "denominator_floor"}:
        raise ValueError("Summary design must be explicit.")
    if (
        type(summary["draws"]) is not int
        or summary["draws"] < 5
        or type(summary["seed"]) is not int
        or summary["seed"] < 0
    ):
        raise ValueError("Invalid summary draws or seed.")
    if (
        summary["nominal"] != 0.95
        or not np.isfinite(summary["denominator_floor"])
        or summary["denominator_floor"] < 0
    ):
        raise ValueError("Invalid summary interval or denominator floor.")


def conditions(config):
    return sorted(config["conditions"], key=lambda c: c["id"])


def target(cell):
    return (
        0.5
        if cell["family"] == "AR1"
        else cell["parameter"] + (0.5 if cell["family"] == "ARFIMA" else 0)
    )


def parent_pool(source, config, cell):
    """Read and verify; never create or modify an upstream clean pool."""
    run = json.loads((source / "run.json").read_text(encoding="utf-8"))
    identity = run["identity"]
    if (
        run["identity_sha256"] != shared.digest(identity)
        or run["identity_sha256"] != config["clean_pool_identity_sha256"]
    ):
        raise ValueError("Clean source identity mismatch.")
    if (
        cell not in shared.cells(identity["config"])
        or config["repetitions"] > identity["actual_repetitions"]
    ):
        raise ValueError("Requested parents are absent from the pinned source design.")
    path = source / "inputs" / f"{shared.cell_id(cell)}.npz"
    with np.load(path, allow_pickle=False) as bundle:
        values, metadata = bundle["values"], json.loads(str(bundle["metadata"]))
    repetitions = identity["actual_repetitions"]
    if (
        metadata["cell"] != cell
        or values.shape != (repetitions, cell["n"])
        or len(metadata["records"]) != repetitions
        or not np.isfinite(values).all()
    ):
        raise ValueError("Invalid clean pool shape, metadata or values.")
    for r, (x, row) in enumerate(zip(values, metadata["records"], strict=True)):
        if (
            row["sha256"] != shared.array_hash(x)
            or row["record_id"] != f"{shared.cell_id(cell)}_r{r}"
            or row["repetition"] != r
            or row["input_seed"] != shared.record_seed(identity["config"], cell, r, "input")
            or row["resampling_seed"]
            != shared.record_seed(identity["config"], cell, r, "resampling")
        ):
            raise ValueError("Clean parent hash/seed/identity mismatch.")
    values.setflags(write=False)
    return (
        values[: config["repetitions"]],
        metadata["records"][: config["repetitions"]],
        shared.file_hash(path),
    )


def child_identity(config, parent, condition, version):
    definition = {
        "parent_id": parent["record_id"],
        "parent_sha256": parent["sha256"],
        "operator": condition["operator"],
        "parameters": condition["params"],
        "version": version,
        "seed_namespace": config["seed_namespace"],
        "global_seed": config["global_seed"],
    }
    sha = shared.digest(definition)
    seed = int.from_bytes(hashlib.sha256(("contamination:" + sha).encode()).digest()[:8], "little")
    return f"stress_{sha}", seed


def reference_values(x, condition, seed):
    """Equation replay independent of the production operator's apply method.

    RNG selection is part of the definition. Student-t uses NumPy's direct draw,
    independently of scipy.stats.t.rvs used by the public operator.
    """
    op, p, n = condition["operator"], condition["params"], len(x)
    sd = float(np.sqrt(np.mean((x - np.mean(x)) ** 2)))
    rng = np.random.default_rng(seed)
    delta = np.zeros(n)
    if op == "constant_offset":
        delta[:] = p["shift"] * (sd + 1e-12)
    elif op == "step_change":
        delta[int(np.floor(n * p["position"])) :] = p["shift"] * sd
    elif op == "outliers":
        count = max(1, round(p["rate"] * n)) if p["rate"] > 0 else 0
        indices = rng.choice(n, count, replace=False)
        signs = rng.choice([-1.0, 1.0], count)
        delta[indices] = signs * p["amplitude"] * (sd + 1e-12)
    elif op == "polynomial_trend":
        t = np.linspace(-1, 1, n)
        trend = t if p["order"] == 1 else t + t * t
        trend -= np.mean(trend)
        delta = p["strength"] * (sd + 1e-12) * (trend / (np.sqrt(np.mean(trend**2)) + 1e-12))
    elif op == "heavy_tail_noise":
        noise = rng.standard_t(p["df"], n)
        delta = p["scale"] * (sd + 1e-12) * (noise / (np.std(noise) + 1e-12))
    else:
        raise ValueError("Unaudited operator.")
    return x + delta


def build_parent(cell, values, metadata):
    return SeriesRecord(
        metadata["record_id"],
        values,
        None,
        None,
        SourceType.SYNTHETIC,
        cell["family"],
        truth=TruthSpec(
            cell["family"],
            {"parameter": cell["parameter"]},
            "latent_clean_H",
            target(cell),
            notes="Retained as the clean recovery target; no H truth is asserted for a descendant.",
        ),
        annotations={
            "pair_group_id": metadata["record_id"],
            "stress_role": "clean",
            "target_role": "latent_clean_recovery",
        },
        provenance=ProvenanceRecord(
            metadata["record_id"], None, "shared_stress", "", seed=metadata["input_seed"]
        ),
    )


def apply_child(config, parent, metadata, condition, registry):
    operator = registry.get(condition["operator"])
    child_id, seed = child_identity(config, metadata, condition, operator.version)
    before = shared.array_hash(parent.values)
    child = operator.apply(
        parent,
        params=condition["params"],
        seed=seed,
        manifest_id="shared_stress",
        new_record_id=child_id,
    )
    if child.provenance is None:
        raise ValueError("Missing contamination provenance.")
    # Deterministic scientific provenance; wall time belongs to execution logs.
    child = replace(child, provenance=replace(child.provenance, seed=seed, created_at=""))
    if before != shared.array_hash(parent.values) or before != metadata["sha256"]:
        raise ValueError("A contamination changed its clean parent.")
    if (
        child.truth != parent.truth
        or child.provenance.parent_id != parent.record_id
        or child.annotations["pair_group_id"] != parent.record_id
    ):
        raise ValueError("Contamination lost parent/latent-target provenance.")
    if (
        len(child.contamination_history) != 1
        or child.contamination_history[0].parent_id != parent.record_id
    ):
        raise ValueError("Descendants must each come directly from the clean parent.")
    child.values.setflags(write=False)
    return child


def materialize_cell(source, folder, config, cell):
    parents, parent_metadata, parent_file_hash = parent_pool(source, config, cell)
    registry = build_default_contamination_registry()
    ordered = conditions(config)
    path = folder / f"{shared.cell_id(cell)}.npz"
    expected = {
        "cell": cell,
        "source_pool_sha256": parent_file_hash,
        "source_identity_sha256": config["clean_pool_identity_sha256"],
        "conditions": ["clean", *[c["id"] for c in ordered]],
        "definitions": [{**c, "version": registry.get(c["operator"]).version} for c in ordered],
        "target_role": "latent_clean_recovery",
        "H_target": target(cell),
    }
    if path.exists():
        with np.load(path, allow_pickle=False) as bundle:
            values, metadata = bundle["values"], json.loads(str(bundle["metadata"]))
        if metadata["design"] != expected:
            raise ValueError("Stored contamination design mismatch.")
    else:
        blocks, rows = [], []
        for x, parent_meta in zip(parents, parent_metadata, strict=True):
            parent = build_parent(cell, x, parent_meta)
            block = [x]
            rows.append(
                {
                    **parent_meta,
                    "parent_id": parent.record_id,
                    "condition": "clean",
                    "parent_sha256": parent_meta["sha256"],
                    "contamination_seed": None,
                    "provenance": asdict(parent.provenance),
                    "transformation": None,
                }
            )
            for condition in ordered:
                child = apply_child(config, parent, parent_meta, condition, registry)
                block.append(child.values)
                rows.append(
                    {
                        **parent_meta,
                        "record_id": child.record_id,
                        "parent_id": parent.record_id,
                        "condition": condition["id"],
                        "parent_sha256": parent_meta["sha256"],
                        "sha256": shared.array_hash(child.values),
                        "contamination_seed": child.provenance.seed,
                        "provenance": asdict(child.provenance),
                        "transformation": asdict(child.contamination_history[0]),
                    }
                )
            blocks.append(block)
        values, metadata = np.asarray(blocks), {"design": expected, "records": rows}
        temporary = path.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            np.savez_compressed(handle, values=values, metadata=shared.canonical(metadata))
        temporary.replace(path)
    if (
        values.shape != (len(parents), len(ordered) + 1, cell["n"])
        or len(metadata["records"]) != len(parents) * (len(ordered) + 1)
        or not np.isfinite(values).all()
    ):
        raise ValueError("Stored contamination shape or values invalid.")
    for r, (x, parent_meta) in enumerate(zip(parents, parent_metadata, strict=True)):
        if not np.array_equal(values[r, 0], x):
            raise ValueError("Stored clean record differs from its imported parent.")
        for j, label in enumerate(expected["conditions"]):
            row = metadata["records"][r * (len(ordered) + 1) + j]
            record_id, seed = (
                (parent_meta["record_id"], None)
                if j == 0
                else child_identity(
                    config,
                    parent_meta,
                    ordered[j - 1],
                    registry.get(ordered[j - 1]["operator"]).version,
                )
            )
            if (
                row["record_id"] != record_id
                or row["parent_id"] != parent_meta["record_id"]
                or row["parent_sha256"] != parent_meta["sha256"]
                or row["condition"] != label
                or row["contamination_seed"] != seed
                or row["sha256"] != shared.array_hash(values[r, j])
                or any(
                    row[k] != parent_meta[k]
                    for k in ("input_seed", "resampling_seed", "repetition")
                )
            ):
                raise ValueError("Stored child/parent identity, hash or seed mismatch.")
            if j:
                reference = reference_values(x, ordered[j - 1], seed)
                if not np.allclose(values[r, j], reference, rtol=2e-14, atol=2e-14):
                    raise ValueError("Stored child fails independent operator equation replay.")
                provenance, trans = row["provenance"], row["transformation"]
                if (
                    provenance["seed"] != seed
                    or provenance["parent_id"] != parent_meta["record_id"]
                    or provenance["record_id"] != record_id
                    or trans["params"] != ordered[j - 1]["params"]
                    or trans["name"] != ordered[j - 1]["operator"]
                    or trans["version"] != registry.get(trans["name"]).version
                    or trans["parent_id"] != parent_meta["record_id"]
                ):
                    raise ValueError("Stored transformation provenance mismatch.")
    values.setflags(write=False)
    return values, metadata
