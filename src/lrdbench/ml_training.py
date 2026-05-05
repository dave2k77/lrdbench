from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from lrdbench.estimators.data_driven import (
    DATA_DRIVEN_ESTIMATORS,
    train_sklearn_model,
    train_torch_model,
)
from lrdbench.registries import ContaminationRegistry, GeneratorRegistry
from lrdbench.schema import BenchmarkManifest, EstimatorSpec, SeriesRecord


def _stable_seed(global_seed: int, *parts: object) -> int:
    h = hashlib.sha256(repr(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % (2**31 - 1)


def _expand_generator_grid(source: Mapping[str, Any]) -> list[tuple[str, dict[str, Any], int]]:
    if source.get("type") != "generator_grid":
        raise ValueError("ml_training.source.type must be generator_grid")
    out: list[tuple[str, dict[str, Any], int]] = []
    for block in source["generators"]:
        family = str(block["family"])
        params = dict(block["params"])
        reps = int(block.get("replicates", 1))
        keys = list(params)
        val_lists: list[list[Any]] = []
        for key in keys:
            val = params[key]
            val_lists.append(val if isinstance(val, list) else [val])
        for combo in itertools.product(*val_lists):
            pdict = dict(zip(keys, combo, strict=True))
            for rep in range(reps):
                out.append((family, pdict, rep))
    return out


def _expand_contamination_grid(
    contamination: Mapping[str, Any] | None,
) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for block in dict(contamination or {}).get("operators", []):
        name = str(block["name"])
        params = dict(block.get("params") or {})
        if not params:
            out.append((name, {}))
            continue
        keys = list(params)
        val_lists: list[list[Any]] = []
        for key in keys:
            val = params[key]
            val_lists.append(val if isinstance(val, list) else [val])
        for combo in itertools.product(*val_lists):
            out.append((name, dict(zip(keys, combo, strict=True))))
    return out


def _record_id(manifest_id: str, family: str, params: Mapping[str, Any], rep: int) -> str:
    key = f"ml_train|{manifest_id}|{family}|{sorted(params.items())}|{rep}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]


def _contam_record_id(
    manifest_id: str, clean_id: str, op_name: str, op_params: Mapping[str, Any]
) -> str:
    key = f"ml_train|{manifest_id}|{clean_id}|{op_name}|{sorted(op_params.items())}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]


def requested_data_driven_estimators(estimator_specs: Sequence[EstimatorSpec]) -> tuple[str, ...]:
    names: list[str] = []
    for spec in estimator_specs:
        base = str(dict(spec.parameter_schema).get("_base_estimator_name", spec.name))
        base = base.split("::", 1)[0]
        if base in DATA_DRIVEN_ESTIMATORS and base not in names:
            names.append(base)
    return tuple(names)


def _spec_base_name(spec: EstimatorSpec) -> str:
    return str(dict(spec.parameter_schema).get("_base_estimator_name", spec.name)).split("::", 1)[0]


def _materialize_training_records(
    manifest: BenchmarkManifest,
    *,
    generators: GeneratorRegistry,
    contaminations: ContaminationRegistry,
    global_seed: int,
) -> list[SeriesRecord]:
    spec = dict(manifest.ml_training_spec)
    source = dict(spec["source"])
    contamination = dict(spec.get("contamination") or {})
    include_clean = bool(contamination.get("include_clean", True))
    scenarios = _expand_contamination_grid(contamination)
    records: list[SeriesRecord] = []
    for family, params, rep in _expand_generator_grid(source):
        gen = generators.get(family)
        rid = _record_id(manifest.manifest_id, family, params, rep)
        seed = _stable_seed(global_seed, manifest.manifest_id, "ml_train", family, params, rep)
        clean = gen.generate(
            record_id=rid,
            params=params,
            seed=seed,
            manifest_id=manifest.manifest_id,
        )
        if include_clean:
            records.append(
                replace(
                    clean,
                    annotations={
                        **dict(clean.annotations),
                        "ml_training_role": "clean",
                    },
                )
            )
        for op_name, op_params in scenarios:
            op = contaminations.get(op_name)
            nid = _contam_record_id(manifest.manifest_id, clean.record_id, op_name, op_params)
            cseed = _stable_seed(
                global_seed,
                manifest.manifest_id,
                "ml_train_contam",
                clean.record_id,
                op_name,
                tuple(sorted(op_params.items())),
            )
            rec = op.apply(
                clean,
                params=op_params,
                seed=cseed,
                manifest_id=manifest.manifest_id,
                new_record_id=nid,
            )
            records.append(
                replace(
                    rec,
                    annotations={
                        **dict(rec.annotations),
                        "ml_training_role": "contaminated",
                    },
                )
            )
    return records


def prepare_data_driven_estimators(
    manifest: BenchmarkManifest,
    *,
    generators: GeneratorRegistry,
    contaminations: ContaminationRegistry,
    run_id: str,
    artefact_root: Path,
    global_seed: int,
) -> BenchmarkManifest:
    requested = requested_data_driven_estimators(manifest.estimator_specs)
    if not requested:
        return manifest
    spec = dict(manifest.ml_training_spec)
    if not bool(spec.get("enabled", False)):
        return manifest
    records = _materialize_training_records(
        manifest,
        generators=generators,
        contaminations=contaminations,
        global_seed=global_seed,
    )
    model_dir = artefact_root / run_id / "ml_models"
    model_dir.mkdir(parents=True, exist_ok=True)

    summaries: dict[str, Mapping[str, Any]] = {}
    paths: dict[str, Path] = {}
    for estimator_name in requested:
        matching_specs = [e for e in manifest.estimator_specs if _spec_base_name(e) == estimator_name]
        params = dict(matching_specs[0].parameter_schema if matching_specs else {})
        params.setdefault("_validation_fraction", spec.get("validation_fraction", 0.0))
        if estimator_name in ("MLRandomForest", "MLSVR"):
            path = model_dir / f"{estimator_name}.pkl"
            summary = train_sklearn_model(estimator_name, records, params=params, artefact_path=path)
        else:
            path = model_dir / f"{estimator_name}.pt"
            summary = train_torch_model(estimator_name, records, params=params, artefact_path=path)
        paths[estimator_name] = path
        summaries[estimator_name] = summary

    manifest_summary = {
        "run_id": run_id,
        "manifest_id": manifest.manifest_id,
        "target_estimand": str(spec.get("target_estimand", "hurst_scaling_proxy")),
        "n_training_records": len(records),
        "models": {
            name: {"path": str(paths[name].as_posix()), "summary": dict(summaries[name])}
            for name in sorted(paths)
        },
    }
    (model_dir / "training_summary.json").write_text(
        json.dumps(manifest_summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    updated_specs: list[EstimatorSpec] = []
    for espec in manifest.estimator_specs:
        params = dict(espec.parameter_schema)
        base = _spec_base_name(espec)
        if base in paths:
            params["_trained_model_path"] = str(paths[base].resolve())
            params["_ml_training_summary_path"] = str((model_dir / "training_summary.json").resolve())
        updated_specs.append(replace(espec, parameter_schema=params))
    return replace(manifest, estimator_specs=tuple(updated_specs))
