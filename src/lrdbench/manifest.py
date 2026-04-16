from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from lrdbench.enums import BenchmarkMode
from lrdbench.metrics_catalog import metric_specs_from_manifest_entries
from lrdbench.schema import BenchmarkManifest
from lrdbench.validation import (
    ManifestValidationError,
    estimator_spec_from_mapping,
    leaderboard_spec_from_mapping,
    report_spec_from_mapping,
    validate_manifest,
)


def load_manifest_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ManifestValidationError("manifest root must be a mapping")
    return data


def manifest_from_mapping(data: Mapping[str, Any]) -> BenchmarkManifest:
    mode = BenchmarkMode(str(data["mode"]))
    estimators = tuple(estimator_spec_from_mapping(x) for x in data["estimators"])
    metrics_list: list[Any] = list(data["metrics"])
    try:
        metric_specs = metric_specs_from_manifest_entries(metrics_list)
    except (TypeError, ValueError) as exc:
        raise ManifestValidationError(str(exc)) from exc

    lbs_raw = data.get("leaderboards") or []
    leaderboard_specs = tuple(leaderboard_spec_from_mapping(x) for x in lbs_raw)

    report_spec = None
    if "report" in data and data["report"] is not None:
        report_spec = report_spec_from_mapping(data["report"])

    manifest = BenchmarkManifest(
        manifest_id=str(data["manifest_id"]),
        name=str(data["name"]),
        mode=mode,
        source_spec=dict(data["source"]),
        contamination_spec=dict(data.get("contamination") or {}),
        segmentation_spec=dict(data.get("segmentation") or {}),
        preprocessing_spec=dict(data.get("preprocessing") or {}),
        estimator_specs=estimators,
        metric_specs=metric_specs,
        leaderboard_specs=leaderboard_specs,
        report_spec=report_spec,
        execution_spec=dict(data.get("execution") or {}),
        seed_spec=dict(data.get("seeds") or {}),
        raw_yaml=dict(data),
    )
    strict = bool((data.get("validation") or {}).get("reject_unknown_keys", True))
    validate_manifest(manifest, strict_unknown_keys=strict)
    return manifest


def load_manifest(path: str | Path) -> BenchmarkManifest:
    return manifest_from_mapping(load_manifest_yaml(path))
