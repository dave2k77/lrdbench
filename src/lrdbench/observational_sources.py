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
        if not path.is_file():
            raise FileNotFoundError(f"observational series file not found: {path}")
        df = pd.read_csv(path, usecols=[value_column])
        vals = np.asarray(df[value_column].dropna().to_numpy(), dtype=float).reshape(-1)
        if vals.size < 2:
            raise ValueError(f"series {rid!r} from {path} must have at least two finite samples")
        seed = _stable_series_seed(global_seed, manifest.manifest_id, "csv", str(path), rid, i)
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
            "value_column": value_column,
            "series_index": i,
        }
        records.append(
            SeriesRecord(
                record_id=rid,
                values=vals,
                time_axis=None,
                sampling_rate=None,
                source_type=SourceType.OBSERVATIONAL,
                source_name=path.name,
                truth=None,
                annotations=ann,
                provenance=prov,
            )
        )
    return records
