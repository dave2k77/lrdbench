from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import numpy as np

from lrdbench.enums import SourceType
from lrdbench.schema import ProvenanceRecord, SeriesRecord, TransformationRecord


def contamination_severity_label(op_name: str, op_params: Mapping[str, Any]) -> str:
    """Stable severity tag for stratum labels and failure-map exports."""
    if op_params.get("severity") is not None:
        return str(op_params["severity"])
    if not op_params:
        return "default"
    parts = []
    for key, value in sorted(op_params.items(), key=lambda kv: kv[0]):
        parts.append(f"{key}={value}")
    return ";".join(parts)


def build_contaminated_series(
    record: SeriesRecord,
    *,
    new_record_id: str,
    values: np.ndarray,
    manifest_id: str | None,
    op_name: str,
    op_family: str,
    op_params: Mapping[str, Any],
    op_version: str,
) -> SeriesRecord:
    severity = contamination_severity_label(op_name, op_params)
    trans = TransformationRecord(
        name=op_name,
        family=op_family,
        params=dict(op_params),
        severity=severity,
        version=op_version,
        parent_id=record.record_id,
    )
    history = record.contamination_history + (trans,)
    clean_gid = str(record.annotations.get("pair_group_id", record.record_id))
    ann = {
        **dict(record.annotations),
        "stress_role": "contaminated",
        "pair_group_id": clean_gid,
        "clean_record_id": record.record_id,
        "contamination_operator": op_name,
        "contamination_family": op_family,
        "contamination_severity": severity,
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
        source_type=SourceType.CONTAMINATED,
        source_name=f"contaminated:{op_name}",
        contamination_history=history,
        annotations=ann,
        provenance=prov,
    )
