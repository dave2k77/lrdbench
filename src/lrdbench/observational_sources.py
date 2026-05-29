from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lrdbench.enums import SourceType
from lrdbench.schema import BenchmarkManifest, ProvenanceRecord, SeriesRecord


def _stable_series_seed(global_seed: int, *parts: object) -> int:
    h = hashlib.sha256(repr(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % (2**31 - 1)


def _resolve_path(base_dir: Path, p: str) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _required_columns(block: Mapping[str, Any], value_column: str) -> list[str]:
    cols = [value_column]
    time_column = block.get("time_column")
    if time_column is not None:
        cols.append(str(time_column))
    return cols


def _read_required_csv_columns(path: Path, columns: list[str]) -> pd.DataFrame:
    try:
        return pd.read_csv(path, usecols=columns)
    except ValueError as exc:
        raise ValueError(
            f"missing required column in observational series file {path}: {columns}"
        ) from exc


def _finite_mask(values: np.ndarray, time_axis: np.ndarray | None) -> np.ndarray:
    mask = np.isfinite(values)
    if time_axis is not None:
        mask = mask & np.isfinite(time_axis)
    return mask


def _apply_missing_policy(
    *,
    rid: str,
    path: Path,
    values: np.ndarray,
    time_axis: np.ndarray | None,
    policy: str,
) -> tuple[np.ndarray, np.ndarray | None, int]:
    if policy not in {"drop", "error"}:
        raise ValueError(f"unknown missing_policy for observational series {rid!r}: {policy!r}")
    mask = _finite_mask(values, time_axis)
    missing_count = int(values.size - np.count_nonzero(mask))
    if policy == "error" and missing_count:
        raise ValueError(
            f"observational series {rid!r} from {path} has missing/non-finite values "
            "with missing_policy='error'"
        )
    values = values[mask]
    if time_axis is not None:
        time_axis = time_axis[mask]
    return values, time_axis, missing_count


def _observational_qc(
    *,
    raw_count: int,
    values: np.ndarray,
    time_axis: np.ndarray | None,
    missing_count: int,
) -> dict[str, float | int | None]:
    retained_count = int(values.size)
    qc: dict[str, float | int | None] = {
        "original_sample_count": int(raw_count),
        "retained_sample_count": retained_count,
        "missing_sample_count": int(missing_count),
        "missing_fraction": float(missing_count) / float(raw_count) if raw_count else None,
        "duration": None,
        "time_start": None,
        "time_end": None,
        "value_min": float(np.min(values)) if retained_count else None,
        "value_max": float(np.max(values)) if retained_count else None,
        "value_mean": float(np.mean(values)) if retained_count else None,
        "value_std": float(np.std(values)) if retained_count else None,
    }
    if time_axis is not None and time_axis.size:
        start = float(time_axis[0])
        end = float(time_axis[-1])
        qc["time_start"] = start
        qc["time_end"] = end
        qc["duration"] = end - start
    return qc


def load_observational_records(
    manifest: BenchmarkManifest, *, base_dir: Path, global_seed: int = 0
) -> list[SeriesRecord]:
    """Build observational SeriesRecords from manifest.source_spec (no truth)."""
    src = dict(manifest.source_spec)
    st = str(src.get("type", ""))
    if st == "inline_table":
        return _load_inline_table(manifest, src, global_seed=global_seed)
    if st == "csv_series_index":
        return _load_csv_series_index(manifest, src, base_dir, global_seed=global_seed)
    raise ValueError(f"unknown observational source.type: {st!r}")


def _load_inline_table(
    manifest: BenchmarkManifest, src: Mapping[str, Any], *, global_seed: int
) -> list[SeriesRecord]:
    records: list[SeriesRecord] = []
    for i, block in enumerate(src["series"]):
        rid = str(block.get("record_id") or f"{manifest.manifest_id}_inline_{i}")
        vals = np.asarray(block["values"], dtype=float).reshape(-1)
        if vals.size < 2:
            raise ValueError(f"inline series {rid!r} must have at least two samples")
        seed = _stable_series_seed(global_seed, manifest.manifest_id, "inline", rid, i)
        prov = ProvenanceRecord(
            record_id=rid,
            parent_id=None,
            manifest_id=manifest.manifest_id,
            created_at=datetime.now(UTC).isoformat(),
            source_version="inline_table",
            software_version=None,
            git_commit=None,
            seed=seed,
        )
        ann: dict[str, Any] = {
            "source_kind": "inline_table",
            "series_index": i,
        }
        records.append(
            SeriesRecord(
                record_id=rid,
                values=vals,
                time_axis=None,
                sampling_rate=None,
                source_type=SourceType.OBSERVATIONAL,
                source_name="inline_table",
                truth=None,
                annotations=ann,
                provenance=prov,
            )
        )
    return records


def _load_csv_series_index(
    manifest: BenchmarkManifest, src: Mapping[str, Any], base_dir: Path, *, global_seed: int
) -> list[SeriesRecord]:
    records: list[SeriesRecord] = []
    for i, block in enumerate(src["series"]):
        rel = str(block["path"])
        path = _resolve_path(base_dir, rel)
        rid = str(block.get("record_id") or path.stem)
        value_column = str(block.get("value_column", "value"))
        time_column = block.get("time_column")
        sampling_rate = (
            float(block["sampling_rate"]) if block.get("sampling_rate") is not None else None
        )
        missing_policy = str(block.get("missing_policy", "drop"))
        metadata = dict(block.get("metadata") or {})
        if not path.is_file():
            raise FileNotFoundError(f"observational series file not found: {path}")
        df = _read_required_csv_columns(path, _required_columns(block, value_column))
        raw_values = np.asarray(df[value_column].to_numpy(), dtype=float).reshape(-1)
        raw_time_axis = None
        if time_column is not None:
            raw_time_axis = np.asarray(df[str(time_column)].to_numpy(), dtype=float).reshape(-1)
        vals, time_axis, missing_count = _apply_missing_policy(
            rid=rid,
            path=path,
            values=raw_values,
            time_axis=raw_time_axis,
            policy=missing_policy,
        )
        if vals.size < 2:
            raise ValueError(f"series {rid!r} from {path} must have at least two finite samples")
        seed = _stable_series_seed(global_seed, manifest.manifest_id, "csv", str(path), rid, i)
        source_hash = _file_sha256(path)
        qc = _observational_qc(
            raw_count=int(raw_values.size),
            values=vals,
            time_axis=time_axis,
            missing_count=missing_count,
        )
        prov = ProvenanceRecord(
            record_id=rid,
            parent_id=None,
            manifest_id=manifest.manifest_id,
            created_at=datetime.now(UTC).isoformat(),
            source_version=str(path.as_posix()),
            software_version=None,
            git_commit=None,
            seed=seed,
        )
        ann: dict[str, Any] = {
            "source_kind": "csv_series_index",
            "source_path": str(path.as_posix()),
            "source_sha256": source_hash,
            "value_column": value_column,
            "series_index": i,
            "missing_policy": missing_policy,
            "original_row_count": int(raw_values.size),
            "retained_sample_count": int(vals.size),
            "missing_sample_count": missing_count,
            "qc": qc,
        }
        if time_column is not None:
            ann["time_column"] = str(time_column)
        if sampling_rate is not None:
            ann["sampling_rate"] = sampling_rate
        if metadata:
            ann["metadata"] = metadata
            for key, value in metadata.items():
                ann.setdefault(str(key), value)
        records.append(
            SeriesRecord(
                record_id=rid,
                values=vals,
                time_axis=time_axis,
                sampling_rate=sampling_rate,
                source_type=SourceType.OBSERVATIONAL,
                source_name=path.name,
                truth=None,
                annotations=ann,
                provenance=prov,
            )
        )
    return records
