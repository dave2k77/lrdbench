from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lrdbench.schema import SeriesRecord


def stratum_from_record(record: SeriesRecord) -> Mapping[str, Any]:
    keys = (
        "process_family",
        "n",
        "H",
        "d",
        "sigma",
        "stress_role",
        "contamination_operator",
        "source_kind",
        "source_path",
        "series_index",
    )
    out: dict[str, Any] = {}
    for k in keys:
        if k in record.annotations:
            out[k] = record.annotations[k]
    if record.truth is not None:
        out["target_estimand"] = record.truth.target_estimand
        out["target_value"] = record.truth.target_value
    return out


def stratum_key(record: SeriesRecord) -> tuple[tuple[str, Any], ...]:
    d = stratum_from_record(record)
    return tuple(sorted(d.items(), key=lambda kv: kv[0]))
