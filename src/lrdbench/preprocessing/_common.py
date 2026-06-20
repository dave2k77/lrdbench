from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import numpy as np

from lrdbench.enums import SourceType
from lrdbench.schema import ProvenanceRecord, SeriesRecord, TransformationRecord


def preprocessing_severity_label(op_name: str, op_params: Mapping[str, Any]) -> str:
    if op_params.get("severity") is not None:
        return str(op_params["severity"])
    if not op_params:
        return "default"
    return ";".join(f"{key}={value}" for key, value in sorted(op_params.items()))


def standardize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    return (arr - float(np.mean(arr))) / (float(np.std(arr)) + eps)


def build_preprocessed_series(
    record: SeriesRecord,
    *,
    new_record_id: str,
    values: np.ndarray,
    manifest_id: str | None,
    op_name: str,
    op_family: str,
    op_kind: str,
    op_params: Mapping[str, Any],
    op_version: str,
    correction_target: str,
) -> SeriesRecord:
    severity = preprocessing_severity_label(op_name, op_params)
    trans = TransformationRecord(
        name=op_name,
        family=op_family,
        params=dict(op_params),
        severity=severity,
        version=op_version,
        parent_id=record.record_id,
    )
    history = record.preprocessing_history + (trans,)
    group_id = str(record.annotations.get("pair_group_id", record.record_id))
    ann = {
        **dict(record.annotations),
        "preprocessing_role": "corrected",
        "pair_group_id": group_id,
        "raw_record_id": record.record_id,
        "preprocessing_operator": op_name,
        "preprocessing_family": op_family,
        "preprocessing_kind": op_kind,
        "preprocessing_severity": severity,
        "correction_target": correction_target,
    }
    prov = ProvenanceRecord(
        record_id=new_record_id,
        parent_id=record.record_id,
        manifest_id=manifest_id,
        created_at=datetime.now(UTC).isoformat(),
        source_version=op_version,
        software_version=None,
        git_commit=None,
        seed=None,
    )
    return replace(
        record,
        record_id=new_record_id,
        values=np.asarray(values, dtype=float),
        source_type=SourceType.PREPROCESSED,
        source_name=f"preprocessed:{op_name}",
        preprocessing_history=history,
        annotations=ann,
        provenance=prov,
    )
